"""Validazione del motore contro tre fonti indipendenti (fase 6): SMAP, NDVI MODIS, rese ISTAT.

Tutto offline (solo cache). Scelte di metodo fissate prima di guardare i risultati
(vedi ``reports/validation.md``):

* A. SMAP SPL3SMP_E (0-5 cm, cella 9 km) contro ``theta_e`` del motore (strato evaporante,
  Ze = 10 cm, a fine giorno). Solo giorni SMAP di qualita' raccomandata e gli stessi giorni del
  modello; medie mensili con almeno 5 giorni; anomalie = media mensile - climatologia di quel
  mese sullo stesso periodo. Periodo principale 2015-04 -> 2022-12; secondario fino alla fine
  della serie simulabile (pioggia POWER non affidabile dopo il 2022, D1).
* B. NDVI MODIS MOD13Q1, media della finestra 9x9 (pixel buoni o marginali), luglio-agosto
  (media) e giugno-agosto (picco), contro il fattore d'acqua ``f_acqua`` del mais continuo.
* C. Rese ISTAT provinciali 2006-2022 (detrendizzate con una retta; anche differenze prime)
  contro la resa relativa simulata della stessa coltura e anno: monosuccessione e media delle
  rotazioni di tre colture (tutte le 216, con e senza cover) che la contengono in quell'anno.
* D. Robustezza del punto C per il mais: Kc singolo e pioggia IMERG.
* E. ECOSTRESS ET giornaliera (ECO_L3T_JET.002, 70 m, 2018-2022) contro ``eta`` del motore nei
  giorni di passaggio: verifica dell'evapotraspirazione simulata, NON un input del modello.
  Medie mensili tra i punti (mesi con almeno 5 passaggi), bootstrap a blocchi come per SMAP;
  scarto medio, correlazione sui valori grezzi e sulle anomalie rispetto al mese di calendario.
  La coltura simulata di ogni punto-anno e' un argomento esplicito (``colture``): la regola che
  la sceglie non e' in questo modulo (vedi ``validate_ecostress``).

Intervalli di confidenza al 95%: serie mensili (A) con bootstrap a blocchi mobili di 6 mesi
(le anomalie di umidita' persistono per mesi: Fisher con n mesi sarebbe troppo stretto);
serie annuali (B, C, D) con la trasformata di Fisher (Pearson) e la varianza di Bonett-Wright
(Spearman), dato che gli scarti interannuali sono quasi indipendenti (autocorrelazione a un
passo riportata come controllo).

Le simulazioni usano la pioggia ``rain_source="power"`` (stessi valori del default fino al
2022, verificato in ``run_all``) solo perche' il ciclo valutato di un anno termina in aprile
dell'anno dopo: altrimenti la coltura 2022 non sarebbe simulabile. Nessun valore della coltura
<= 2022 dipende dalla pioggia dopo la raccolta.

CLI: ``python -m fieldwise.validation [--lat 45.2 --lon 10.0]``.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as _st

from . import config as _config
from . import rotation as R
from . import weather as _weather
from .data import cache as _cache
from .data import ecostress as _ecostress
from .data import modis as _modis
from .data import smap as _smap

ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = ROOT / "reports" / "figure"
SCENARI = R.SCENARI
SCENARIO_RAPPRESENTATIVO = "tetto_irriguo"   # scelto a priori, vedi reports/validation.md
MAIN_PERIOD = ("2015-04-01", "2022-12-31")
ISTAT_YEARS = (2006, 2022)
NDVI_YEARS = (2001, 2022)          # il mais 2000 non ha un anno di avviamento
CASE_YEARS = (2003, 2012, 2022)
BLOCK_MONTHS = 6
N_BOOT = 5000
SEED = 20261113
MIN_DAYS_MONTH = 5
ECOSTRESS_YEARS = (2018, 2022)     # fino al 2022: pioggia POWER non affidabile dopo (D1)
ECOSTRESS_MIN_PASSAGGI = 5         # passaggi per mese (come MIN_DAYS_MONTH per SMAP)
ECOSTRESS_COLTURE = ("mais", "soia", "frumento")
ECOSTRESS_COLTURE_FILE = "ecostress_colture.csv"   # data/processed/cremona/, con il suo .meta.json
ECOSTRESS_PESO_STAGIONE = 0.5      # regola 'mix_istat': in stagione se il peso delle colture in stagione e' >= 0,5
WM2_TO_MM = 86400 / 2.45e6         # lettura alternativa dell'unita': W m-2 medi -> mm/giorno

MAIS = R.Rotation(("mais",), (False,))
MSF = R.Rotation(("mais", "soia", "frumento"), (False, False, False))


# =============================================================================
# Statistiche
# =============================================================================
def _lag1(x) -> float:
    x = np.asarray(x, float)
    return float(np.corrcoef(x[:-1], x[1:])[0, 1]) if len(x) > 3 else math.nan


def _fisher_ci(r: float, n: int, se: float) -> list:
    if n < 4 or not np.isfinite(r):
        return [math.nan, math.nan]
    z = np.arctanh(np.clip(r, -0.999999, 0.999999))
    return [float(np.tanh(z - 1.959964 * se)), float(np.tanh(z + 1.959964 * se))]


def _block_boot(x, y, block: int, n_boot: int, seed: int):
    rng = np.random.default_rng(seed)
    n = len(x)
    nb = int(math.ceil(n / block))
    starts = rng.integers(0, n - block + 1, size=(n_boot, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(n_boot, -1)[:, :n]
    rp, rs = np.empty(n_boot), np.empty(n_boot)
    for b in range(n_boot):
        xi, yi = x[idx[b]], y[idx[b]]
        rp[b] = np.corrcoef(xi, yi)[0, 1]
        rs[b] = _st.spearmanr(xi, yi)[0]
    q = lambda a: [float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5))]  # noqa: E731
    return q(rp), q(rs)


def corr_stats(x, y, ci: str = "fisher", block: int = BLOCK_MONTHS, n_boot: int = N_BOOT,
               seed: int = SEED) -> dict:
    """Pearson e Spearman con IC 95%. ``ci``: 'fisher' (Pearson: se = 1/sqrt(n-3); Spearman:
    se di Bonett-Wright sqrt((1 + rho^2/2)/(n-3))) oppure 'block' (bootstrap a blocchi mobili
    di ``block`` elementi consecutivi, percentili 2,5-97,5)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = int(len(x))
    out = {"n": n, "metodo_ic": ci}
    if n < 4 or np.std(x) == 0 or np.std(y) == 0:
        out.update(pearson=math.nan, pearson_ic95=[math.nan] * 2, pearson_p=math.nan,
                   spearman=math.nan, spearman_ic95=[math.nan] * 2, spearman_p=math.nan)
        return out
    rp, pp = _st.pearsonr(x, y)
    rs, ps = _st.spearmanr(x, y)
    rp, rs = float(rp), float(rs)
    if ci == "block":
        if n < block:      # meno elementi di un blocco: il bootstrap non e' definito, IC non stimato
            cip = cis = [math.nan, math.nan]
        else:
            cip, cis = _block_boot(x, y, block, n_boot, seed)
        out["blocco"] = block
    else:
        cip = _fisher_ci(rp, n, 1.0 / math.sqrt(n - 3))
        cis = _fisher_ci(rs, n, math.sqrt((1 + rs * rs / 2) / (n - 3)))
    out.update(pearson=rp, pearson_ic95=cip, pearson_p=float(pp), spearman=rs,
               spearman_ic95=cis, spearman_p=float(ps), autocorr_lag1_x=_lag1(x),
               autocorr_lag1_y=_lag1(y))
    return out


# =============================================================================
# Contesti
# =============================================================================
def contexts(lat: float, lon: float) -> dict:
    """Contesti del motore: 'power' (pioggia POWER su tutta la serie, per poter valutare la
    coltura 2022), 'default' (per il controllo di uguaglianza), 'imerg' (se disponibile)."""
    out = {"default": R.build_context(lat=lat, lon=lon),
           "power": R.build_context(forcing=_weather.load_forcing(lat, lon, rain_source="power"))}
    try:
        out["imerg"] = R.build_context(forcing=_weather.load_forcing(lat, lon, rain_source="imerg"))
    except Exception as e:   # noqa: BLE001 - la robustezza IMERG e' facoltativa
        out["imerg_errore"] = repr(e)
    return out


# =============================================================================
# A. SMAP
# =============================================================================
def model_theta_daily(ctx, rotation: R.Rotation, anno: int, scenario: str,
                      metodo_et: str = "doppio") -> pd.Series:
    """``theta_e`` giornaliero di un'unica simulazione continua (nessun riavvio): avviamenti
    ripetuti dal 1 gennaio di ``anno`` fino all'ultimo ciclo che termina entro il meteo."""
    best = None
    for n_avv in range(1, 40):
        if not R.build_calendar(ctx, rotation, anno, n_avv).ok:
            break
        best = n_avv
    if best is None:
        raise ValueError(f"{rotation.label} non simulabile dal {anno}")
    o = R.simulate(ctx, rotation, anno, scenario, n_avviamento=best, dettaglio=True,
                   metodo_et=metodo_et)
    i0 = o["segmenti"][0].start
    th = np.asarray(o["acqua"].theta_e, float)
    return pd.Series(th, index=pd.DatetimeIndex(ctx.dates[i0:i0 + len(th)]), name="theta_e")


def monthly_anomalies(obs: pd.Series, mod: pd.Series, start: str, end: str,
                      min_days: int = MIN_DAYS_MONTH) -> pd.DataFrame:
    """Medie mensili sugli stessi giorni (osservazione valida e modello disponibile), mesi con
    almeno ``min_days`` giorni, anomalie rispetto alla climatologia del mese sul periodo."""
    d = pd.DataFrame({"obs": obs, "mod": mod}).loc[start:end].dropna()
    g = d.groupby(d.index.to_period("M"))
    m = g.mean()
    m["n_giorni"] = g.size()
    m = m[m["n_giorni"] >= min_days].copy()
    mon = m.index.month
    for c in ("obs", "mod"):
        m[f"{c}_anom"] = m[c] - m.groupby(mon)[c].transform("mean")
    m.index = m.index.to_timestamp()
    return m


def validate_smap(ctxs: dict, lat: float, lon: float) -> tuple[dict, pd.DataFrame]:
    sm = _smap.load(lat, lon).set_index("date")["sm_good_mean"]
    ctx = ctxs["power"]
    configs = [("mais continuo", MAIS, 2013), ("mais > soia > frumento", MSF, 2012)]
    res, tabs = {"periodo_principale": list(MAIN_PERIOD), "giorni_smap_validi": int(sm.notna().sum()),
                 "confronti": []}, []
    for lab, rot, a0 in configs:
        for sc in SCENARI:
            th = model_theta_daily(ctx, rot, a0, sc)
            for per, (s, e) in (("principale", MAIN_PERIOD),
                                ("secondario", (MAIN_PERIOD[0], str(th.index[-1].date())))):
                m = monthly_anomalies(sm, th, s, e)
                st_a = corr_stats(m["obs_anom"], m["mod_anom"], ci="block")
                st_r = corr_stats(m["obs"], m["mod"], ci="block")
                res["confronti"].append({
                    "configurazione": lab, "scenario": sc, "periodo": per, "inizio": s, "fine": e,
                    "mesi": int(len(m)), "anomalie": st_a, "grezzi": st_r,
                    "media_smap": float(m["obs"].mean()), "media_modello": float(m["mod"].mean()),
                    "sd_anom_smap": float(m["obs_anom"].std()),
                    "sd_anom_modello": float(m["mod_anom"].std())})
                t = m.reset_index().rename(columns={"index": "mese"})
                t.insert(0, "periodo", per)
                t.insert(0, "scenario", sc)
                t.insert(0, "configurazione", lab)
                tabs.append(t)
    return res, pd.concat(tabs, ignore_index=True)


# =============================================================================
# Simulazione delle colture per anno di raccolta
# =============================================================================
def crop_years(ctx, rotation: R.Rotation, scenario: str, metodo_et: str = "doppio") -> pd.DataFrame:
    """Colture del ciclo valutato per ogni anno di partenza simulabile (un avviamento)."""
    rows = []
    for a in R.start_years(ctx, rotation):
        o = R.simulate(ctx, rotation, a, scenario, metodo_et=metodo_et)
        if o["esito"] != R.ESITO_OK:
            continue
        for c in o["colture"]:
            rows.append({"rotazione": rotation.label, "anno_partenza": a, "scenario": scenario,
                         "coltura": c["coltura"], "anno": int(c["raccolta"][:4]),
                         "resa_relativa": c["resa_relativa"], "f_acqua": c["f_acqua"],
                         "f_caldo": c["f_caldo"], "irrigazione": c["irrigazione"]})
    return pd.DataFrame(rows)


def mono_series(ctx, crop: str, scenario: str, metodo_et: str = "doppio") -> pd.DataFrame:
    d = crop_years(ctx, R.Rotation((crop,), (False,)), scenario, metodo_et)
    return d.groupby("anno")[["resa_relativa", "f_acqua", "f_caldo", "irrigazione"]].mean()


def rotation_mean_series(ctx, scenario: str) -> pd.DataFrame:
    """Per coltura e anno di raccolta: media su tutte le rotazioni di tre colture (216, con e
    senza cover) e tutti gli anni di partenza il cui ciclo valutato contiene quella coltura."""
    d = pd.concat([crop_years(ctx, e["rotation"], scenario)
                   for e in R.enumerate_rotations(ctx.p)], ignore_index=True)
    g = d.groupby(["coltura", "anno"])
    out = g[["resa_relativa", "f_acqua"]].mean()
    out["n_simulazioni"] = g.size()
    return out


# =============================================================================
# B. NDVI
# =============================================================================
def ndvi_annual(lat: float, lon: float) -> pd.DataFrame:
    m = _modis.load(lat, lon)
    m = m.dropna(subset=["ndvi_window_mean_good"])
    m["anno"], m["mese"] = m["date"].dt.year, m["date"].dt.month
    ja = m[m["mese"].isin([7, 8])].groupby("anno")["ndvi_window_mean_good"].agg(["mean", "size"])
    pk = m[m["mese"].isin([6, 7, 8])].groupby("anno")["ndvi_window_mean_good"].max()
    return pd.DataFrame({"ndvi_lug_ago": ja["mean"], "n_compositi_lug_ago": ja["size"],
                         "ndvi_picco_giu_ago": pk})


def ndvi_heterogeneity(lat: float, lon: float, years=NDVI_YEARS) -> dict:
    """Quanto la finestra mescola situazioni diverse: dispersione tra pixel dell'NDVI di
    luglio-agosto, quota di pixel bassi (stoppie, suolo nudo), anomalie dei pixel nel 2022."""
    px = _modis.load_pixels(lat, lon)
    px = px[px["reliability"].isin([0, 1])].copy()
    px["anno"], px["mese"] = px["date"].dt.year, px["date"].dt.month
    ja = px[px["mese"].isin([7, 8]) & px["anno"].between(*years)]
    pp = ja.groupby(["anno", "pixel"])["ndvi"].mean().unstack()
    sd_between = pp.std(axis=1)
    frac_low = (pp < 0.5).sum(axis=1) / pp.notna().sum(axis=1)
    ref = pp.drop(index=[2022], errors="ignore").median()
    out = {"sd_tra_pixel_media": float(sd_between.mean()),
           "sd_interannuale_media_finestra": float(pp.mean(axis=1).std()),
           "quota_pixel_ndvi_sotto_0_5_media": float(frac_low.mean()),
           "n_pixel_medio": float(pp.notna().sum(axis=1).mean())}
    if 2022 in pp.index:
        an = pp.loc[2022] - ref
        an = an.dropna()
        out.update(anomalia_2022_pixel_mediana=float(an.median()),
                   quota_pixel_2022_sotto_meno_0_05=float((an < -0.05).mean()),
                   quota_pixel_2022_sopra_0=float((an > 0).mean()))
    return out


def validate_ndvi(ctxs: dict, lat: float, lon: float) -> tuple[dict, pd.DataFrame]:
    nd = ndvi_annual(lat, lon).loc[NDVI_YEARS[0]:NDVI_YEARS[1]]
    ctx = ctxs["power"]
    t = nd.copy()
    for sc in ("solo_pioggia", "tetto_irriguo"):
        ms = mono_series(ctx, "mais", sc)
        t[f"f_acqua_{sc}"] = ms["f_acqua"].reindex(t.index)
    res = {"anni": [int(t.index.min()), int(t.index.max())], "confronti": []}
    for ind in ("ndvi_lug_ago", "ndvi_picco_giu_ago"):
        for sc in ("solo_pioggia", "tetto_irriguo"):
            res["confronti"].append({"indicatore": ind, "scenario": sc,
                                     **corr_stats(t[ind], t[f"f_acqua_{sc}"])})
    res["eterogeneita_finestra"] = ndvi_heterogeneity(lat, lon)
    rk = t.rank()
    res["casi"] = {int(y): {"ndvi_lug_ago": float(t.loc[y, "ndvi_lug_ago"]),
                            "rango_ndvi_lug_ago": int(rk.loc[y, "ndvi_lug_ago"]),
                            "ndvi_picco_giu_ago": float(t.loc[y, "ndvi_picco_giu_ago"]),
                            "f_acqua_solo_pioggia": float(t.loc[y, "f_acqua_solo_pioggia"]),
                            "rango_f_acqua_solo_pioggia": int(rk.loc[y, "f_acqua_solo_pioggia"]),
                            "f_acqua_tetto_irriguo": float(t.loc[y, "f_acqua_tetto_irriguo"]),
                            "rango_f_acqua_tetto_irriguo": int(rk.loc[y, "f_acqua_tetto_irriguo"])}
                   for y in CASE_YEARS if y in t.index}
    res["n_anni"] = int(len(t))
    return res, t


# =============================================================================
# C. ISTAT
# =============================================================================
def istat_table(lat: float | None = None, lon: float | None = None) -> pd.DataFrame:
    p = _config.PROCESSED_DIR / "cremona" / "istat_yields.csv"
    if not p.exists():
        from .data import istat as _istat
        return _istat.load()
    return pd.read_csv(p)


def detrend(years, y) -> np.ndarray:
    years, y = np.asarray(years, float), np.asarray(y, float)
    b = np.polyfit(years, y, 1)
    return y - np.polyval(b, years)


def _istat_compare(obs: pd.Series, sim: pd.Series) -> dict:
    d = pd.DataFrame({"obs": obs, "sim": sim}).dropna().sort_index()
    out = {"anni": [int(d.index.min()), int(d.index.max())] if len(d) else []}
    if len(d) < 5:
        return out
    res = detrend(d.index, d["obs"])
    out["detrend"] = corr_stats(res, d["sim"])
    full = d.reindex(range(int(d.index.min()), int(d.index.max()) + 1))
    dd = full.diff().dropna()
    out["differenze_prime"] = corr_stats(dd["obs"], dd["sim"])
    return out


def validate_istat(ctxs: dict) -> tuple[dict, pd.DataFrame]:
    ist = istat_table()
    ist = ist[ist["year"].between(*ISTAT_YEARS)]
    ctx = ctxs["power"]
    rows, res = [], {"anni": list(ISTAT_YEARS), "scenario_rappresentativo": SCENARIO_RAPPRESENTATIVO,
                     "confronti": []}
    rot_mean = {sc: rotation_mean_series(ctx, sc) for sc in SCENARI}
    for crop in ("mais", "soia", "frumento"):
        obs = ist[ist["crop"] == crop].set_index("year")["yield_t_ha"].astype(float)
        scen = SCENARI if crop != "frumento" else ("solo_pioggia",)
        resid = pd.Series(detrend(obs.index, obs.values), index=obs.index)
        for sc in scen:
            mono = mono_series(ctx, crop, sc)["resa_relativa"]
            rm = rot_mean[sc].xs(crop, level="coltura")["resa_relativa"]
            for kind, sim in (("monosuccessione", mono), ("media_rotazioni", rm)):
                res["confronti"].append({"coltura": crop, "scenario": sc, "simulazione": kind,
                                         **_istat_compare(obs, sim)})
                for y in obs.index:
                    rows.append({"coltura": crop, "scenario": sc, "simulazione": kind, "anno": int(y),
                                 "resa_istat_t_ha": float(obs[y]), "residuo_trend_t_ha": float(resid[y]),
                                 "resa_relativa_sim": float(sim.get(y, np.nan))})
    return res, pd.DataFrame(rows)


def validate_robustness(ctxs: dict) -> dict:
    """Punto C per il mais (monosuccessione, residui dal trend) con Kc singolo e con IMERG."""
    ist = istat_table()
    obs = ist[(ist["crop"] == "mais") & ist["year"].between(*ISTAT_YEARS)].set_index("year")["yield_t_ha"]
    out = {"confronti": []}
    variants = [("doppio_power", ctxs["power"], "doppio"), ("singolo_power", ctxs["power"], "singolo")]
    if "imerg" in ctxs:
        variants.append(("doppio_imerg", ctxs["imerg"], "doppio"))
    else:
        out["imerg"] = f"non disponibile: {ctxs.get('imerg_errore')}"
    for name, ctx, met in variants:
        for sc in SCENARI:
            sim = mono_series(ctx, "mais", sc, met)["resa_relativa"]
            c = _istat_compare(obs, sim)
            out["confronti"].append({"variante": name, "scenario": sc, **c})
    return out


# =============================================================================
# E. ECOSTRESS: evapotraspirazione giornaliera osservata contro simulata
# =============================================================================
def mono_daily(ctx, crop: str, scenario: str, anno: int = 2000) -> pd.DataFrame:
    """``ks``, ``eta``, ``etc`` giornalieri di un'unica simulazione continua della monosuccessione
    di ``crop`` (come ``model_theta_daily``: avviamenti ripetuti fino all'ultimo ciclo che termina
    entro il meteo) e indicatore ``in_stagione`` (giorni dal segmento 'coltura', cioe' tra semina e
    raccolta simulate). Indice: data del giorno simulato."""
    best = None
    for n_avv in range(1, 40):
        if not R.build_calendar(ctx, R.Rotation((crop,), (False,)), anno, n_avv).ok:
            break
        best = n_avv
    if best is None:
        raise ValueError(f"{crop} non simulabile dal {anno}")
    o = R.simulate(ctx, R.Rotation((crop,), (False,)), anno, scenario, n_avviamento=best, dettaglio=True)
    segs = o["segmenti"]
    i0 = segs[0].start
    w = o["acqua"]
    n = len(w.ks)
    stag = np.zeros(n, bool)
    for sg in segs:
        if sg.kind == "coltura":
            stag[sg.start - i0: sg.end - i0 + 1] = True
    return pd.DataFrame({"ks": np.asarray(w.ks, float), "eta": np.asarray(w.eta, float),
                         "etc": np.asarray(w.etc, float), "in_stagione": stag},
                        index=pd.DatetimeIndex(ctx.dates[i0:i0 + n]))


def ecostress_monthly(d: pd.DataFrame, min_passaggi: int = ECOSTRESS_MIN_PASSAGGI) -> pd.DataFrame:
    """Medie mensili di ``et_obs`` e ``eta_sim`` sui passaggi (tutti i punti insieme), solo mesi con
    almeno ``min_passaggi`` passaggi. Indice: mese (Period)."""
    g = d.groupby(d["data"].dt.to_period("M"))
    m = g[["et_obs", "eta_sim"]].mean()
    m["n_passaggi"] = g.size()
    m.index.name = "mese"
    return m[m["n_passaggi"] >= min_passaggi]


def calendar_anomalies(m: pd.DataFrame) -> pd.DataFrame:
    """Anomalie rispetto al mese di calendario: a ogni mese si toglie la media dello stesso mese
    (gennaio, febbraio, ...) sugli anni disponibili, per osservato e simulato. I mesi presenti in
    un solo anno non hanno anomalia (sarebbe zero) e sono esclusi. Con 5 anni al massimo la media
    del mese e' una stima rozza."""
    m = m.sort_index()
    mon = m.index.month
    cnt = m.groupby(mon)["et_obs"].transform("size")
    h = m[cnt >= 2].copy()
    for c in ("et_obs", "eta_sim"):
        h[f"{c}_anom"] = h[c] - h.groupby(h.index.month)[c].transform("mean")
    return h


def _passaggi_stat(q: pd.DataFrame) -> dict:
    if len(q) < 4:
        return {"n_passaggi": int(len(q))}
    x, y = q["et_obs"].to_numpy(float), q["eta_sim"].to_numpy(float)
    return {"n_passaggi": int(len(q)), "n_punti": int(q["punto"].nunique()),
            "media_obs": float(x.mean()), "media_sim": float(y.mean()),
            "scarto_sim_meno_obs": float((y - x).mean()),
            "rmse": float(np.sqrt(((y - x) ** 2).mean())),
            "r_passaggi": float(np.corrcoef(x, y)[0, 1]),
            "scarto_lettura_wm2": float((y - x * WM2_TO_MM).mean())}


def _ecostress_subset(q: pd.DataFrame, anomalie: bool) -> tuple[dict, pd.DataFrame]:
    r = _passaggi_stat(q)
    if len(q):
        m = ecostress_monthly(q)
    else:
        m = pd.DataFrame({"et_obs": [], "eta_sim": [], "n_passaggi": []},
                         index=pd.PeriodIndex([], freq="M", name="mese"))
    r["mensile"] = corr_stats(m["et_obs"], m["eta_sim"], ci="block")
    r["mensile"]["n_mesi"] = int(len(m))
    t = m.reset_index()
    t["mese"] = t["mese"].astype(str)
    if anomalie:
        h = calendar_anomalies(m)
        r["anomalie"] = corr_stats(h["et_obs_anom"], h["eta_sim_anom"], ci="block")
        r["anomalie"]["n_mesi"] = int(len(h))
        ha = h[["et_obs_anom", "eta_sim_anom"]].reset_index()
        ha["mese"] = ha["mese"].astype(str)
        t = t.merge(ha, on="mese", how="left")
    return r, t


def validate_ecostress(ctxs: dict, passaggi: pd.DataFrame, colture: pd.DataFrame,
                       scenari=SCENARI) -> tuple[dict, pd.DataFrame]:
    """Verifica dell'ET simulata contro ECOSTRESS ETdaily nei giorni di passaggio (non e' un input).

    ``passaggi``: ``fieldwise.data.ecostress.load()``; si usano solo i passaggi validi fino al
    ``ECOSTRESS_YEARS[1]``. ``colture``: tabella ``punto, anno, coltura`` (coltura in mais, soia,
    frumento) che dice QUALE coltura simulare per ogni punto-anno: entrano solo i passaggi dei
    punto-anno presenti. Il modulo non ha una regola per sceglierla (le colture dei punti non sono
    note: sono pixel di seminativo a caso); la scelta cambia i numeri in modo sostanziale (vedi
    ``reports/validation.md``). Le simulazioni usano la pioggia POWER e il meteo del punto pilota
    per tutti i punti (cella POWER da circa 50 km).

    Per ogni scenario d'acqua e sottoinsieme (tutti, stagione = tra semina e raccolta simulate,
    fuori stagione, e per coltura in stagione) riporta: passaggi, punti, ET media osservata e
    simulata, scarto medio (simulata - osservata, mm/giorno), RMSE e correlazione sui passaggi, e sulle
    medie mensili: correlazione sui valori grezzi (ciclo stagionale compreso) e, per i tre
    sottoinsiemi principali, sulle anomalie rispetto al mese di calendario (interannuale), con IC
    95% da bootstrap a blocchi di 6 mesi. ``scarto_lettura_wm2``: lo scarto se ETdaily fosse in
    W m-2 (tab. 10 della guida utente) invece che in mm/giorno (testo, par. 5.4).
    """
    ctx = ctxs["power"]
    e = _ecostress.valid_passages(passaggi, ECOSTRESS_YEARS[1]).rename(columns={"et_mm_giorno": "et_obs"})
    e = e[e["data"].dt.year >= ECOSTRESS_YEARS[0]].copy()
    e["anno"] = e["data"].dt.year
    n_valid = int(len(e))
    col = colture[["punto", "anno", "coltura"]].drop_duplicates(["punto", "anno"])
    e = e.merge(col, on=["punto", "anno"], how="inner")
    res = {"anni": list(ECOSTRESS_YEARS), "scenario_rappresentativo": SCENARIO_RAPPRESENTATIVO,
           "unita": "mm/giorno (guida utente ECOSTRESS Collection 2 v2, par. 5.4, p. 16; la tab. 10 e "
                    "il catalogo .002 dicono W m-2)",
           "passaggi_validi_2018_2022": n_valid, "passaggi_usati": int(len(e)),
           "punti_usati": int(e["punto"].nunique()),
           "coltura_dei_passaggi": e["coltura"].value_counts().to_dict(),
           "min_passaggi_per_mese": ECOSTRESS_MIN_PASSAGGI, "scenari": {}}
    tabs = []
    for sc in scenari:
        parts = []
        for crop in ECOSTRESS_COLTURE:
            u = e[e["coltura"] == crop].copy()
            if u.empty:
                continue
            day = mono_daily(ctx, crop, sc)
            u["eta_sim"] = day["eta"].reindex(u["data"]).to_numpy()
            u["in_stagione"] = day["in_stagione"].reindex(u["data"]).to_numpy()
            parts.append(u)
        p = pd.concat(parts, ignore_index=True).dropna(subset=["eta_sim"])
        p["in_stagione"] = p["in_stagione"].astype(bool)
        out = {}
        subsets = [("tutti", p, True), ("stagione", p[p["in_stagione"]], True),
                   ("fuori_stagione", p[~p["in_stagione"]], True)]
        subsets += [(f"stagione_{c}", p[p["in_stagione"] & (p["coltura"] == c)], False)
                    for c in ECOSTRESS_COLTURE]
        for nome, q, anom in subsets:
            r, t = _ecostress_subset(q, anom)
            out[nome] = r
            t.insert(0, "sottoinsieme", nome)
            t.insert(0, "scenario", sc)
            tabs.append(t)
        res["scenari"][sc] = out
    return res, pd.concat(tabs, ignore_index=True)


def ecostress_colture_table() -> pd.DataFrame | None:
    """Tabella ``punto, anno, coltura`` salvata come dato del prodotto (``ecostress_colture.csv``,
    con i metadati di origine accanto), oppure None se non c'e'."""
    p = _cache.processed_dir(key="cremona", create=False) / ECOSTRESS_COLTURE_FILE
    return pd.read_csv(p) if p.exists() else None


def _pesi_istat(ist: pd.DataFrame) -> dict[int, dict[str, float]]:
    """Per anno, il peso di mais, soia e frumento: superficie ISTAT della coltura / somma delle tre."""
    a = ist[ist["crop"].isin(ECOSTRESS_COLTURE)].pivot_table(index="year", columns="crop",
                                                              values="area_ha", aggfunc="sum")
    a = a.reindex(columns=list(ECOSTRESS_COLTURE)).dropna()
    a = a.div(a.sum(axis=1), axis=0)
    return {int(y): {c: float(a.loc[y, c]) for c in ECOSTRESS_COLTURE} for y in a.index}


def validate_ecostress_controlli(ctxs: dict, passaggi: pd.DataFrame, ist: pd.DataFrame,
                                 scenari=SCENARI) -> tuple[dict, pd.DataFrame]:
    """Regole di controllo senza riconoscimento della coltura, su TUTTI i passaggi validi 2018-2022.

    Servono a dire quanto i risultati di ``validate_ecostress`` dipendono dalla scelta della coltura;
    non la sostituiscono. Regole: ``tutti_mais``, ``tutti_soia``, ``tutti_frumento`` (ogni passaggio
    simulato con quella coltura) e ``mix_istat`` (media delle tre colture pesata con le superfici
    ISTAT dell'anno; un passaggio e' 'in stagione' se il peso delle colture che quel giorno sono in
    stagione e' almeno ``ECOSTRESS_PESO_STAGIONE``). Stesse statistiche di ``validate_ecostress``
    (tutti, stagione, fuori stagione; senza i sottoinsiemi per coltura). Tabella mensile con la colonna
    ``regola``.
    """
    ctx = ctxs["power"]
    e = _ecostress.valid_passages(passaggi, ECOSTRESS_YEARS[1]).rename(columns={"et_mm_giorno": "et_obs"})
    e = e[e["data"].dt.year >= ECOSTRESS_YEARS[0]].copy()
    pesi = {y: w for y, w in _pesi_istat(ist).items() if ECOSTRESS_YEARS[0] <= y <= ECOSTRESS_YEARS[1]}
    e = e[e["data"].dt.year.isin(pesi)].reset_index(drop=True)
    w_mix = pd.DataFrame([pesi[y] for y in e["data"].dt.year], index=e.index)
    regole = {f"tutti_{c}": pd.DataFrame({k: float(k == c) for k in ECOSTRESS_COLTURE}, index=e.index)
              for c in ECOSTRESS_COLTURE}
    regole["mix_istat"] = w_mix
    res = {"anni": list(ECOSTRESS_YEARS), "passaggi_validi": int(len(e)), "punti": int(e["punto"].nunique()),
           "regole": {"tutti_mais": "ogni passaggio simulato come mais (monosuccessione)",
                      "tutti_soia": "ogni passaggio simulato come soia",
                      "tutti_frumento": "ogni passaggio simulato come frumento",
                      "mix_istat": "media di mais, soia e frumento pesata con le superfici ISTAT dell'anno "
                                   f"(in stagione se il peso delle colture in stagione e' >= {ECOSTRESS_PESO_STAGIONE})"},
           "pesi_istat": {str(y): v for y, v in pesi.items()}, "scenari": {}}
    tabs = []
    for sc in scenari:
        giorni = {c: mono_daily(ctx, c, sc) for c in ECOSTRESS_COLTURE}
        eta = pd.DataFrame({c: giorni[c]["eta"].reindex(e["data"]).to_numpy() for c in ECOSTRESS_COLTURE})
        stag = pd.DataFrame({c: giorni[c]["in_stagione"].reindex(e["data"]).to_numpy(dtype=float)
                             for c in ECOSTRESS_COLTURE})
        out = {}
        for nome, w in regole.items():
            attivi = w.to_numpy() > 0
            ok = ~(eta.isna().to_numpy() & attivi).any(axis=1)
            p = e[ok].copy()
            p["eta_sim"] = (eta.fillna(0.0).to_numpy() * w.to_numpy()).sum(axis=1)[ok]
            p["in_stagione"] = ((stag.fillna(0.0).to_numpy() * w.to_numpy()).sum(axis=1)[ok]
                                >= ECOSTRESS_PESO_STAGIONE)
            sub = {}
            for nm, q in (("tutti", p), ("stagione", p[p["in_stagione"]]), ("fuori_stagione", p[~p["in_stagione"]])):
                r, t = _ecostress_subset(q, True)
                sub[nm] = r
                t.insert(0, "sottoinsieme", nm)
                t.insert(0, "regola", nome)
                t.insert(0, "scenario", sc)
                tabs.append(t)
            out[nome] = sub
        res["scenari"][sc] = out
    return res, pd.concat(tabs, ignore_index=True)


# =============================================================================
# Figure
# =============================================================================
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def fig_smap(tab: pd.DataFrame, path: Path):
    plt = _plt()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    t = tab[tab["periodo"] == "principale"]
    base = t[(t["configurazione"] == "mais continuo") & (t["scenario"] == "solo_pioggia")]
    ax.plot(base["mese"], base["obs_anom"], "k-o", ms=3, lw=1.6, label="SMAP (0-5 cm, cella 9 km)")
    sty = {("mais continuo", "solo_pioggia"): ("tab:red", "-"),
           ("mais continuo", "tetto_irriguo"): ("tab:blue", "-"),
           ("mais > soia > frumento", "tetto_irriguo"): ("tab:green", "--")}
    for (cf, sc), (col, ls) in sty.items():
        s = t[(t["configurazione"] == cf) & (t["scenario"] == sc)]
        ax.plot(s["mese"], s["mod_anom"], color=col, ls=ls, lw=1.1,
                label=f"modello, {cf}, {sc.replace('_', ' ')} (strato 0-10 cm)")
    ax.axhline(0, color="0.6", lw=0.8)
    ax.set_xlabel("mese")
    ax.set_ylabel("anomalia mensile dell'umidità [m³/m³]")
    ax.set_title("Umidità superficiale: anomalie mensili SMAP e modello, 2015-2022 (stessi giorni)")
    ax.legend(fontsize=8, ncol=2, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fig_ndvi(t: pd.DataFrame, path: Path):
    plt = _plt()
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6), sharey=True)
    for ax, sc in zip(axs, ("solo_pioggia", "tetto_irriguo")):
        x, y = t[f"f_acqua_{sc}"], t["ndvi_lug_ago"]
        ax.scatter(x, y, c=["tab:red" if a in CASE_YEARS else "tab:blue" for a in t.index], s=28)
        for a in t.index:
            ax.annotate(str(a), (x[a], y[a]), fontsize=7, xytext=(3, 2), textcoords="offset points")
        ax.set_xlabel(f"fattore d'acqua simulato del mais [-], {sc.replace('_', ' ')}")
        ax.set_title(f"mais continuo, {sc.replace('_', ' ')}")
    axs[0].set_ylabel("NDVI medio luglio-agosto, finestra 2 km [-]")
    fig.suptitle("NDVI MODIS contro stress idrico simulato del mais, 2001-2022")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fig_istat(tab: pd.DataFrame, path: Path):
    plt = _plt()
    fig, axs = plt.subplots(1, 3, figsize=(13, 4.4))
    for ax, crop in zip(axs, ("mais", "soia", "frumento")):
        sc = SCENARIO_RAPPRESENTATIVO if crop != "frumento" else "solo_pioggia"
        for kind, mk, col in (("monosuccessione", "o", "tab:blue"), ("media_rotazioni", "^", "tab:orange")):
            s = tab[(tab["coltura"] == crop) & (tab["scenario"] == sc) & (tab["simulazione"] == kind)]
            ax.scatter(s["resa_relativa_sim"], s["residuo_trend_t_ha"], marker=mk, color=col, s=26,
                       label=kind.replace("_", " "))
            if kind == "monosuccessione":
                for _, r in s.iterrows():
                    ax.annotate(str(r["anno"])[2:], (r["resa_relativa_sim"], r["residuo_trend_t_ha"]),
                                fontsize=7, xytext=(3, 2), textcoords="offset points")
        ax.axhline(0, color="0.6", lw=0.8)
        ax.set_xlabel("resa relativa simulata [-]")
        ax.set_title(f"{crop}, {sc.replace('_', ' ')}")
        ax.legend(fontsize=7)
    axs[0].set_ylabel("resa ISTAT, scarto dal trend lineare [t/ha]")
    fig.suptitle("Rese provinciali ISTAT (Cremona) contro resa relativa simulata, 2006-2022")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def fig_case(ctx, lat: float, lon: float, path: Path):
    plt = _plt()
    m = _modis.load(lat, lon).dropna(subset=["ndvi_window_mean_good"])
    m = m[m["date"].dt.year.between(*NDVI_YEARS)]
    m["anno"], m["doy"] = m["date"].dt.year, m["date"].dt.day_of_year
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.6))
    ref = m[~m["anno"].isin(CASE_YEARS)].groupby("doy")["ndvi_window_mean_good"]
    q = ref.quantile([0.1, 0.5, 0.9]).unstack()
    axs[0].fill_between(q.index, q[0.1], q[0.9], color="0.85", label="altri anni, 10°-90° percentile")
    axs[0].plot(q.index, q[0.5], color="0.4", label="altri anni, mediana")
    cols = {2003: "tab:orange", 2012: "tab:green", 2022: "tab:red"}
    for y, c in cols.items():
        s = m[m["anno"] == y]
        axs[0].plot(s["doy"], s["ndvi_window_mean_good"], "-o", ms=3, color=c, label=str(y))
    axs[0].set_xlabel("giorno dell'anno (inizio del composito di 16 giorni)")
    axs[0].set_ylabel("NDVI finestra 2 km [-]")
    axs[0].set_title("NDVI MODIS")
    axs[0].legend(fontsize=7)
    for y, c in cols.items():
        for sc, ls in (("solo_pioggia", "-"), ("tetto_irriguo", "--")):
            o = R.simulate(ctx, MAIS, y - 1, sc, dettaglio=True)
            if o["esito"] != R.ESITO_OK:
                continue
            seg = [s for s in o["segmenti"] if s.kind == "coltura" and s.cycle == o["n_avviamento"]][0]
            i0 = o["segmenti"][0].start
            ks = np.asarray(o["acqua"].ks)[seg.start - i0:seg.end - i0 + 1]
            d = pd.DatetimeIndex(ctx.dates[seg.start:seg.end + 1]).day_of_year
            axs[1].plot(d, ks, ls=ls, color=c, lw=1.2, label=f"{y}, {sc.replace('_', ' ')}")
    axs[1].set_xlabel("giorno dell'anno")
    axs[1].set_ylabel("coefficiente di stress idrico Ks [-]")
    axs[1].set_title("Mais continuo simulato")
    axs[1].legend(fontsize=7, ncol=2)
    fig.suptitle("Casi di studio 2003, 2012, 2022: NDVI osservato e stress idrico simulato")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# =============================================================================
# Esecuzione
# =============================================================================
def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def run_all(lat: float = _config.PILOT_LAT, lon: float = _config.PILOT_LON,
            figures: bool = True, ecostress_colture: pd.DataFrame | None = None) -> dict:
    """Rigenera tabelle (CSV), ``validation_summary.json`` e figure. Solo cache.

    ``ecostress_colture``: tabella ``punto, anno, coltura`` per la verifica dell'ET con ECOSTRESS
    (vedi ``validate_ecostress``). Se non e' data si usa quella salvata in
    ``data/processed/cremona/ecostress_colture.csv`` (``ecostress_colture_table``); se non c'e'
    nemmeno quella, la sezione ``ecostress`` non viene calcolata e non compare nel riepilogo (nessuna
    regola predefinita: la scelta della coltura e' una decisione di metodo, non un default). Con la
    tabella si calcolano anche le regole di controllo (``validate_ecostress_controlli``)."""
    ctxs = contexts(lat, lon)
    # controllo: pioggia 'power' e default coincidono fino al 2022
    d0, dp = ctxs["default"], ctxs["power"]
    k = d0.last_idx + 1
    same = bool(np.allclose(d0.rain[:k], dp.rain[:k]) and np.allclose(d0.et0[:k], dp.et0[:k]))
    out_dir = _cache.processed_dir(lat, lon)
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    a, a_tab = validate_smap(ctxs, lat, lon)
    b, b_tab = validate_ndvi(ctxs, lat, lon)
    c, c_tab = validate_istat(ctxs)
    d = validate_robustness(ctxs)
    e_res = e_tab = None
    if ecostress_colture is None:
        ecostress_colture = ecostress_colture_table()
    if ecostress_colture is not None:
        passaggi = _ecostress.load()
        e_res, e_tab = validate_ecostress(ctxs, passaggi, ecostress_colture)
        k_res, k_tab = validate_ecostress_controlli(ctxs, passaggi, istat_table())
        e_res["controlli"] = k_res
        e_tab.insert(1, "regola", "principale")
        e_tab = pd.concat([e_tab, k_tab], ignore_index=True)
    a_tab.to_csv(out_dir / "validation_smap_mensile.csv", index=False)
    b_tab.to_csv(out_dir / "validation_ndvi_annuale.csv", index_label="anno")
    c_tab.to_csv(out_dir / "validation_istat.csv", index=False)
    if e_tab is not None:
        e_tab.to_csv(out_dir / "validation_ecostress_mensile.csv", index=False)
    figs = {"smap": "validazione_smap_anomalie.png", "ndvi": "validazione_ndvi_stress.png",
            "istat": "validazione_istat_rese.png", "caso_2022": "validazione_caso_2022.png"}
    if figures:
        fig_smap(a_tab, FIG_DIR / figs["smap"])
        fig_ndvi(b_tab, FIG_DIR / figs["ndvi"])
        fig_istat(c_tab, FIG_DIR / figs["istat"])
        fig_case(dp, lat, lon, FIG_DIR / figs["caso_2022"])
    summary = {"punto": {"lat": lat, "lon": lon},
               "metodo": {"ic_mensile": f"bootstrap a blocchi mobili di {BLOCK_MONTHS} mesi, {N_BOOT} repliche",
                          "ic_annuale": "Fisher (Pearson), Bonett-Wright (Spearman)",
                          "pioggia_simulazioni": "power (uguale al default fino al 2022)",
                          "pioggia_power_uguale_default_fino_2022": same,
                          "scenario_rappresentativo": SCENARIO_RAPPRESENTATIVO},
               "smap": a, "ndvi": b, "istat": c, "robustezza_mais": d,
               "figure": {k2: f"reports/figure/{v}" for k2, v in figs.items()},
               "tabelle": ["validation_smap_mensile.csv", "validation_ndvi_annuale.csv",
                           "validation_istat.csv"]
               + (["validation_ecostress_mensile.csv"] if e_tab is not None else []),
               **({"ecostress": e_res} if e_res is not None else {}),
               "non_validato": ["azoto (concime, assorbimento, mineralizzazione)", "humus",
                                "lisciviazione dei nitrati", "percolazione e ruscellamento"]}
    summary = _clean(summary)
    (out_dir / "validation_summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False),
                                                     encoding="utf-8")
    return summary


def _fmt(s: dict, key: str) -> str:
    r, ci = s.get(key), s.get(f"{key}_ic95")
    if r is None or ci is None or ci[0] is None:
        return "n/d"
    return f"{r:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]"


def _print(summary: dict):
    print("A. SMAP (anomalie mensili)")
    for c in summary["smap"]["confronti"]:
        print(f"  {c['configurazione']:24s} {c['scenario']:18s} {c['periodo']:10s} mesi {c['mesi']:3d} "
              f"r {_fmt(c['anomalie'], 'pearson')} rho {_fmt(c['anomalie'], 'spearman')} "
              f"| grezzi r {_fmt(c['grezzi'], 'pearson')}")
    print("B. NDVI")
    for c in summary["ndvi"]["confronti"]:
        print(f"  {c['indicatore']:20s} {c['scenario']:14s} n {c['n']} r {_fmt(c, 'pearson')} "
              f"rho {_fmt(c, 'spearman')}")
    print("C. ISTAT")
    for c in summary["istat"]["confronti"]:
        if "detrend" in c:
            print(f"  {c['coltura']:9s} {c['scenario']:18s} {c['simulazione']:16s} n {c['detrend']['n']} "
                  f"det r {_fmt(c['detrend'], 'pearson')} rho {_fmt(c['detrend'], 'spearman')} "
                  f"| diff r {_fmt(c['differenze_prime'], 'pearson')}")
    if "ecostress" in summary:
        print("E. ECOSTRESS (ET, medie mensili)")
        for sc, sub in summary["ecostress"]["scenari"].items():
            for nome in ("tutti", "stagione", "fuori_stagione"):
                r = sub[nome]
                print(f"  {sc:18s} {nome:15s} passaggi {r.get('n_passaggi', 0):5d} "
                      f"scarto {r.get('scarto_sim_meno_obs', float('nan')):+.2f} mm/g "
                      f"grezza r {_fmt(r['mensile'], 'pearson')} ({r['mensile']['n_mesi']} mesi) "
                      f"anomalie r {_fmt(r['anomalie'], 'pearson')} ({r['anomalie']['n_mesi']} mesi)")
            for regola, cs in summary["ecostress"].get("controlli", {}).get("scenari", {}).get(sc, {}).items():
                r = cs["stagione"]
                print(f"  {sc:18s} controllo {regola:15s} passaggi {r.get('n_passaggi', 0):5d} "
                      f"scarto {r.get('scarto_sim_meno_obs', float('nan')):+.2f} mm/g "
                      f"grezza r {_fmt(r['mensile'], 'pearson')} anomalie r {_fmt(r['anomalie'], 'pearson')} (stagione)")
    print("D. Robustezza mais")
    for c in summary["robustezza_mais"]["confronti"]:
        if "detrend" in c:
            print(f"  {c['variante']:14s} {c['scenario']:18s} det r {_fmt(c['detrend'], 'pearson')} "
                  f"rho {_fmt(c['detrend'], 'spearman')} | diff r {_fmt(c['differenze_prime'], 'pearson')}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validazione FIELDWISE (SMAP, NDVI, ISTAT, ECOSTRESS), offline")
    ap.add_argument("--lat", type=float, default=_config.PILOT_LAT)
    ap.add_argument("--lon", type=float, default=_config.PILOT_LON)
    ap.add_argument("--no-figure", action="store_true")
    a = ap.parse_args(argv)
    _print(run_all(a.lat, a.lon, figures=not a.no_figure))


if __name__ == "__main__":
    main()
