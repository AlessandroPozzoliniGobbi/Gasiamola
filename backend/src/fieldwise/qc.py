"""Controllo qualita' dei dati in cache (fase 1 del piano).

Uso::

    python -m fieldwise.qc [--lat 45.2 --lon 10.0]

Legge i dati gia' in cache (mai la rete) con le funzioni ``load`` dei client in
``fieldwise.data`` e, dove non esiste un ``load``, dai CSV elaborati. Per ogni controllo
produce: dataset, nome, esito (OK / ATTENZIONE / ERRORE / NON DISPONIBILE) e un dettaglio
numerico in una riga. Un dataset assente non e' mai un errore del programma: dichiara
NON DISPONIBILE col motivo e i controlli che ne dipendono vengono saltati dichiarandolo.

Uscite
- ``data/CHECKS.md``: la parte generata sta tra ``<!-- qc:auto:start -->`` e
  ``<!-- qc:auto:end -->``; la sezione ``## Decisioni`` e' scritta a mano, viene creata
  (con il segnaposto "Da compilare") solo se manca e non viene mai toccata.
- ``data/processed/<punto>/qc_summary.json`` e ``qc_rain_annual.csv``.
- codice di uscita 1 se almeno un controllo e' ERRORE.

Le soglie sono quelle decise nel brief della fase 1 (vedi le costanti qui sotto); dove la
regola non fissa un criterio ("utilizzabile in estate", "mese con lo scarto maggiore") la
scelta e' dichiarata nel docstring della funzione.
"""
from __future__ import annotations

import argparse
import calendar
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable

import numpy as np
import pandas as pd

from . import config, et0
from .data import arpa, cache, imerg, modis, power, smap

# --- esiti ---------------------------------------------------------------------------
OK = "OK"
WARN = "ATTENZIONE"
ERR = "ERRORE"
NA = "NON DISPONIBILE"

MARK_START = "<!-- qc:auto:start -->"
MARK_END = "<!-- qc:auto:end -->"
DECISIONI_HEADING = "## Decisioni"
DECISIONI_PLACEHOLDER = "Da compilare"

# --- soglie (brief fase 1) ---------------------------------------------------------------
SENTINEL_MAX = -900.0
POWER_VARS = ["tmax", "tmin", "tmean", "rain", "srad", "rh", "wind"]
RANGES = {  # variabile: (minimo, massimo, unita')
    "tmax": (-30.0, 50.0, "degC"),
    "tmin": (-40.0, 40.0, "degC"),
    "rain": (0.0, 300.0, "mm/g"),
    "srad": (0.0, 35.0, "MJ/m2/g"),
    "rh": (0.0, 100.0, "%"),
    "wind": (0.0, 20.0, "m/s"),
}
RAIN_WARN_MM = 150.0
CLEAR_SKY_MAX_RATIO = 1.1
TEMP_COHERENCE_TOL = 0.05
RAIN_REL_TOL = 0.25            # scarto relativo annuo POWER vs riferimento
MIN_COMPLETE_PCT = 80.0        # % di giorni completi per entrare nel confronto
WET_DAY_MM = 1.0
REGIME_EARLY_END = 2022        # 2000-2022 contro 2023-2025
ET0_RATIO_RANGE = (0.85, 1.30)
TEMP_SUMMER_DIFF_MAX = 1.0     # degC, |media (POWER - ARPA) di tmax in giugno-agosto|
HOT_DAY_C = 35.0
ARPA_COMPLETE_MIN_PCT = 90.0
MODIS_EXPECTED = 23
MODIS_EXPECTED_FIRST_YEAR = 20
MODIS_MIN_DATES = 20
MODIS_MIN_USABLE_SUMMER_PCT = 60.0
MODIS_NDVI_RANGE = (-0.2, 1.0)
MODIS_WINDOW_GOOD_FRACTION = 0.5
SUMMER_MONTHS = (6, 7, 8)
SOIL_SUM_TOL = 2.0
SOIL_BDOD_RANGE = (1.0, 1.8)
SOIL_OM_WARN = 3.0
ISTAT_RANGES = {"mais": (5.0, 16.0), "soia": (1.5, 6.0), "frumento": (3.0, 9.0)}
ISTAT_JUMP = 0.30
IMERG_RANGE = (0.0, 400.0)
SMAP_RANGE = (0.02, 0.60)

MONTHS_IT = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
             "agosto", "settembre", "ottobre", "novembre", "dicembre"]

# nomi dei controlli (servono anche per dichiarare i controlli saltati)
D_POWER, D_ARPA, D_ARPA_T = "POWER", "ARPA pioggia", "ARPA temperature"
D_CMP_ARPA, D_CMP_IMERG = "POWER vs ARPA pioggia", "POWER vs IMERG"
D_ET0, D_CMP_T = "POWER ET0", "POWER vs ARPA temperature"
D_MODIS, D_SOIL, D_ISTAT, D_IMERG, D_SMAP = "MODIS NDVI", "SoilGrids", "ISTAT", "IMERG", "SMAP"

N_POWER = ["Completezza giornaliera", "Valori mancanti", "Sentinelle", "Intervallo tmax",
           "Intervallo tmin", "Intervallo pioggia", "Intervallo radiazione",
           "Radiazione / cielo sereno", "Intervallo umidita'", "Intervallo vento",
           "Coerenza tmin <= tmean <= tmax"]
N_RAIN_CMP = ["Pioggia annua", "Correlazione dei totali mensili", "Giorni piovosi (>= 1 mm)",
              "Rapporto annuo nel tempo"]
N_ET0 = ["Penman-Monteith vs Hargreaves"]
N_TEMP_CMP = ["Differenza tmax/tmin", "Giorni con tmax > 35 degC"]
N_ARPA = ["Completezza per anno"]
N_MODIS = ["Date per anno", "Intervallo NDVI", "Pixel centrale buono/marginale",
           "Finestra con almeno meta' pixel buoni", "Date utilizzabili in estate",
           "NDVI medio luglio-agosto"]
N_SOIL = ["Sabbia + argilla + limo", "Densita' apparente", "Sostanza organica 0-30 cm"]
N_ISTAT = ["Anni presenti per coltura", "Rese in intervalli plausibili",
           "Anni successivi all'ultimo anno di meteo", "Salti annui > 30%"]
N_IMERG = ["Completezza giornaliera", "Intervallo valori", "Ultimo giorno disponibile"]
N_SMAP = ["Giorni con passaggio di qualita' raccomandata", "Intervallo valori"]


@dataclass
class Check:
    dataset: str
    name: str
    status: str
    detail: str


def _skip(dataset: str, names: list[str], reason: str) -> list[Check]:
    return [Check(dataset, n, NA, f"saltato: {reason}") for n in names]


def _unavailable(dataset: str, names: list[str], reason: str) -> list[Check]:
    """Dataset assente: una riga di disponibilita' col motivo + i controlli saltati."""
    return [Check(dataset, "Disponibilita'", NA, reason)] + _skip(dataset, names, reason)


# --- caricamento tollerante -----------------------------------------------------------------
def _load(what: str, fn: Callable[[], Any]) -> tuple[Any, str | None]:
    """(oggetto, None) oppure (None, motivo). Mai eccezioni: l'assenza e' un esito."""
    try:
        return fn(), None
    except FileNotFoundError:  # include cache.CacheMiss
        return None, f"{what} assente (non in cache)"
    except Exception as exc:  # file corrotto, colonne strane, ecc.
        return None, f"{what} illeggibile ({type(exc).__name__})"


def _read_csv(path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def _missing_cols(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c not in df.columns]


def _fmt_dates(idx, limit: int = 6) -> str:
    items = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in list(idx)[:limit]]
    more = len(idx) - limit
    return ", ".join(items) + (f" (+{more})" if more > 0 else "")


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for v in mask:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def _clean_power(df: pd.DataFrame) -> pd.DataFrame:
    """Ordina, toglie i giorni duplicati e trasforma le sentinelle in NaN (per i confronti)."""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out = out.sort_values("date").drop_duplicates("date", keep="first").reset_index(drop=True)
    for c in POWER_VARS:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").mask(lambda s: s <= SENTINEL_MAX)
    return out


# ======================================================================================
# 1-4. POWER
# ======================================================================================
def check_power(df: pd.DataFrame, lat: float, elev_m: float | None,
                start: str, end: str) -> list[Check]:
    """Regole 1-4: completezza, sentinelle, intervalli fisici, coerenza delle temperature."""
    miss = _missing_cols(df, ["date", *POWER_VARS])
    if miss:
        return _skip(D_POWER, N_POWER, f"colonne mancanti nel file POWER: {', '.join(miss)}")
    out: list[Check] = []
    dates = pd.DatetimeIndex(pd.to_datetime(df["date"]).dt.normalize())

    # 1. completezza
    expected = pd.date_range(start, end, freq="D")
    missing = expected.difference(dates)
    extra = dates.difference(expected)
    dup = int(dates.duplicated().sum())
    gap = _longest_run(np.isin(expected, dates, invert=True))
    gap_txt = ""
    if len(missing):
        runs = (pd.Series(missing).diff() != pd.Timedelta(days=1)).cumsum()
        longest = pd.Series(missing).groupby(runs.to_numpy()).agg(["first", "count"]).sort_values(
            "count", ascending=False).iloc[0]
        gap_txt = f" (da {pd.Timestamp(longest['first']).date()})"
    bad = len(missing) > 0 or dup > 0
    out.append(Check(D_POWER, N_POWER[0], ERR if bad else OK,
                     f"{len(df)} righe su {len(expected)} attese ({start}..{end}); giorni mancanti "
                     f"{len(missing)}; duplicati {dup}; fuori periodo {len(extra)}; "
                     f"buco piu' lungo {gap} giorni{gap_txt}"))
    nan_parts = []
    for c in POWER_VARS:
        s = pd.to_numeric(df[c], errors="coerce")
        n = int(s.isna().sum())
        if n:
            nan_parts.append(f"{c} {n} (serie piu' lunga {_longest_run(s.isna().to_numpy())} gg)")
    out.append(Check(D_POWER, N_POWER[1], WARN if nan_parts else OK,
                     "; ".join(nan_parts) if nan_parts else "nessun NaN in nessuna variabile"))

    # 2. sentinelle
    num = df[POWER_VARS].apply(pd.to_numeric, errors="coerce")
    sent = (num <= SENTINEL_MAX).sum()
    n_sent = int(sent.sum())
    out.append(Check(D_POWER, N_POWER[2], ERR if n_sent else OK,
                     (f"{n_sent} valori <= {SENTINEL_MAX:.0f} (" +
                      ", ".join(f"{k} {int(v)}" for k, v in sent.items() if v) + ")")
                     if n_sent else f"nessun valore <= {SENTINEL_MAX:.0f} su {num.size} letture"))

    # 3. intervalli fisici
    clean = _clean_power(df)
    for var, name in (("tmax", N_POWER[3]), ("tmin", N_POWER[4]), ("rain", N_POWER[5]),
                      ("srad", N_POWER[6])):
        out.append(_range_check(D_POWER, name, clean, var))
        if var == "srad":
            out.append(_clear_sky_check(clean, lat, elev_m))
    out.append(_range_check(D_POWER, N_POWER[8], clean, "rh"))
    out.append(_range_check(D_POWER, N_POWER[9], clean, "wind"))

    # 4. coerenza
    lo = clean["tmin"] - clean["tmean"] > TEMP_COHERENCE_TOL
    hi = clean["tmean"] - clean["tmax"] > TEMP_COHERENCE_TOL
    both = clean["tmin"] - clean["tmax"] > TEMP_COHERENCE_TOL
    nb = int((lo | hi | both).sum())
    out.append(Check(D_POWER, N_POWER[10], ERR if nb else OK,
                     f"{nb} giorni incoerenti (tolleranza {TEMP_COHERENCE_TOL} degC): "
                     f"tmin > tmean {int(lo.sum())}, tmean > tmax {int(hi.sum())}, "
                     f"tmin > tmax {int(both.sum())}"))
    return out


def _range_check(dataset: str, name: str, df: pd.DataFrame, var: str) -> Check:
    lo, hi, unit = RANGES[var]
    s = df[var].dropna()
    if s.empty:
        return Check(dataset, name, NA, f"{var}: nessun valore valido")
    n_out = int(((s < lo) | (s > hi)).sum())
    detail = f"{var}: min {s.min():.2f}, max {s.max():.2f} {unit}; attesi [{lo:g}, {hi:g}]; fuori: {n_out}"
    status = ERR if n_out else OK
    if var == "rain" and not n_out and s.max() > RAIN_WARN_MM:
        status = WARN
    if var == "rain" and (status != OK):
        top = df.loc[s.nlargest(5).index, ["date", "rain"]]
        detail += "; 5 giorni piu' piovosi: " + ", ".join(
            f"{d:%Y-%m-%d} {v:.1f}" for d, v in zip(top["date"], top["rain"]))
        if status == WARN:
            detail += f" (ATTENZIONE oltre {RAIN_WARN_MM:g} mm)"
    return Check(dataset, name, status, detail)


def _clear_sky_check(df: pd.DataFrame, lat: float, elev_m: float | None) -> Check:
    name = N_POWER[7]
    if elev_m is None:
        return Check(D_POWER, name, NA, "quota della cella POWER non disponibile (power_site.json)")
    doy = df["date"].dt.day_of_year.to_numpy()
    rso = np.asarray(et0.clear_sky_radiation(et0.extraterrestrial_radiation(doy, lat), elev_m))
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = pd.Series(df["srad"].to_numpy() / rso, index=df["date"]).dropna()
    if ratio.empty:
        return Check(D_POWER, name, NA, "nessun valore di radiazione valido")
    n_bad = int((ratio > CLEAR_SKY_MAX_RATIO).sum())
    return Check(D_POWER, name, ERR if n_bad else OK,
                 f"Rs/Rso: max {ratio.max():.3f} il {ratio.idxmax():%Y-%m-%d}, mediana "
                 f"{ratio.median():.3f}; oltre {CLEAR_SKY_MAX_RATIO:g}: {n_bad} giorni "
                 f"(Rso a quota {elev_m:g} m, FAO-56 eq. 37)")


# ======================================================================================
# 5. Pioggia annua POWER contro un riferimento (ARPA o IMERG)
# ======================================================================================
RAIN_COLS = ["reference", "year", "power_total_mm", "ref_total_mm", "ref_complete_pct",
             "power_common_mm", "ref_common_mm", "n_common_days", "rel_diff", "ratio",
             "wet_freq_power_pct", "wet_freq_ref_pct", "esito"]


def _ref_frame(df: pd.DataFrame, valid: pd.Series) -> pd.DataFrame:
    r = pd.DataFrame({"date": pd.to_datetime(df["date"]).dt.normalize(),
                      "rain_mm": pd.to_numeric(df["rain_mm"], errors="coerce"),
                      "valid": valid.to_numpy(bool)})
    r["valid"] &= r["rain_mm"].notna()
    return r.sort_values("date").drop_duplicates("date", keep="first").reset_index(drop=True)


def rain_annual_table(power_df: pd.DataFrame, ref: pd.DataFrame, ref_name: str) -> tuple[
        pd.DataFrame, dict[str, Any]]:
    """Tabella annua POWER contro riferimento + statistiche di sintesi.

    ``ref``: colonne ``date, rain_mm, valid`` (valid = giorno ARPA ``complete`` con valore;
    per IMERG = giorno con valore). Totali ricalcolati SOLO sui giorni validi del riferimento
    (e con POWER presente); scarto relativo (POWER - rif)/rif su quei giorni. L'anno e'
    confrontabile solo con almeno ``MIN_COMPLETE_PCT`` % di giorni validi nell'anno
    solare; ATTENZIONE se il valore assoluto dello scarto supera ``RAIN_REL_TOL``.
    """
    p = power_df.set_index("date")["rain"]
    m = ref.merge(p.rename("power").reset_index(), on="date", how="left")
    m["year"] = m["date"].dt.year
    m["both"] = m["valid"] & m["power"].notna()
    years = sorted(set(m["year"]) & set(p.index.year))
    rows = []
    for y in years:
        g = m[m["year"] == y]
        ndays = 366 if calendar.isleap(y) else 365
        pct = 100.0 * g["valid"].sum() / ndays
        c = g[g["both"]]
        pc, rc = c["power"].sum(), c["rain_mm"].sum()
        comparable = pct >= MIN_COMPLETE_PCT and len(c) > 0 and rc > 0
        rel = (pc - rc) / rc if rc > 0 else np.nan
        if not comparable:
            esito = "non confrontabile"
        else:
            esito = WARN if abs(rel) > RAIN_REL_TOL else OK
        rows.append({
            "reference": ref_name, "year": y,
            "power_total_mm": float(p[p.index.year == y].sum()),
            "ref_total_mm": float(g["rain_mm"].sum()),
            "ref_complete_pct": pct, "power_common_mm": float(pc), "ref_common_mm": float(rc),
            "n_common_days": int(len(c)), "rel_diff": rel,
            "ratio": pc / rc if rc > 0 else np.nan,
            "wet_freq_power_pct": 100.0 * float((c["power"] >= WET_DAY_MM).mean()) if len(c) else np.nan,
            "wet_freq_ref_pct": 100.0 * float((c["rain_mm"] >= WET_DAY_MM).mean()) if len(c) else np.nan,
            "esito": esito})
    table = pd.DataFrame(rows, columns=RAIN_COLS)
    comp_years = set(table.loc[table["esito"].isin([OK, WARN]), "year"])

    # correlazione dei totali mensili (anni confrontabili, mesi con >= 80% di giorni validi)
    mc = m[m["year"].isin(comp_years)].copy()
    mc["month"] = mc["date"].dt.month
    mc["p"] = mc["power"].where(mc["both"], 0.0)
    mc["r"] = mc["rain_mm"].where(mc["both"], 0.0)
    agg = mc.groupby(["year", "month"]).agg(n_valid=("valid", "sum"), p=("p", "sum"), r=("r", "sum")).reset_index()
    agg["valid_pct"] = [100.0 * n / calendar.monthrange(int(y), int(mo))[1]
                        for n, y, mo in zip(agg["n_valid"], agg["year"], agg["month"])]
    corr, n_months = np.nan, 0
    if len(agg):
        agg = agg[agg["valid_pct"] >= MIN_COMPLETE_PCT]
        n_months = len(agg)
        if n_months >= 3 and agg["p"].std() > 0 and agg["r"].std() > 0:
            corr = float(np.corrcoef(agg["p"], agg["r"])[0, 1])
    # regime: media del rapporto annuo (anni confrontabili)
    cmp_tab = table[table["year"].isin(comp_years)]
    early = cmp_tab.loc[cmp_tab["year"] <= REGIME_EARLY_END, "ratio"]
    late = cmp_tab.loc[cmp_tab["year"] > REGIME_EARLY_END, "ratio"]
    stats = {"corr_monthly": corr, "n_months": n_months, "comparable": sorted(comp_years),
             "ratio_early": float(early.mean()) if len(early) else np.nan,
             "ratio_late": float(late.mean()) if len(late) else np.nan,
             "n_early": int(len(early)), "n_late": int(len(late))}
    return table, stats


def check_rain_compare(dataset: str, ref_name: str, table: pd.DataFrame,
                       stats: dict[str, Any]) -> list[Check]:
    out: list[Check] = []
    comp = table[table["esito"].isin([OK, WARN])]
    notcomp = table[table["esito"] == "non confrontabile"]
    if comp.empty:
        why = f"nessun anno con almeno {MIN_COMPLETE_PCT:g}% di giorni completi di {ref_name}"
        return _skip(dataset, N_RAIN_CMP, why)
    flagged = comp[comp["esito"] == WARN]
    detail = (f"{len(comp)} anni confrontabili (>= {MIN_COMPLETE_PCT:g}% giorni completi), "
              f"{len(notcomp)} non confrontabili; scarto relativo (POWER-{ref_name})/{ref_name} "
              f"sui giorni comuni: mediano {comp['rel_diff'].median():+.1%}, "
              f"min {comp['rel_diff'].min():+.1%}, max {comp['rel_diff'].max():+.1%}; ")
    if len(flagged):
        detail += f"anni oltre +-{RAIN_REL_TOL:.0%}: " + ", ".join(
            f"{int(r.year)} {r.rel_diff:+.0%}" for r in flagged.itertuples())
    else:
        detail += f"nessun anno oltre +-{RAIN_REL_TOL:.0%}"
    if len(notcomp):
        detail += "; non confrontabili: " + ", ".join(
            f"{int(r.year)} ({r.ref_complete_pct:.1f}%)" for r in notcomp.itertuples())
    out.append(Check(dataset, N_RAIN_CMP[0], WARN if len(flagged) else OK, detail))

    c = stats["corr_monthly"]
    out.append(Check(dataset, N_RAIN_CMP[1], OK if np.isfinite(c) else NA,
                     (f"r di Pearson tra totali mensili POWER e {ref_name} = {c:.3f} su "
                      f"{stats['n_months']} mesi (anni confrontabili, mesi con >= "
                      f"{MIN_COMPLETE_PCT:g}% di giorni completi); informativo, nessuna soglia")
                     if np.isfinite(c) else "mesi insufficienti per la correlazione"))
    out.append(Check(dataset, N_RAIN_CMP[2], OK,
                     f"frequenza media POWER {comp['wet_freq_power_pct'].mean():.1f}% contro "
                     f"{ref_name} {comp['wet_freq_ref_pct'].mean():.1f}% dei giorni comuni "
                     f"(differenza {comp['wet_freq_power_pct'].mean() - comp['wet_freq_ref_pct'].mean():+.1f} "
                     f"punti); per anno nella tabella; informativo"))
    e, l = stats["ratio_early"], stats["ratio_late"]
    if not (np.isfinite(e) and np.isfinite(l)):
        out.append(Check(dataset, N_RAIN_CMP[3], NA,
                         f"servono anni confrontabili sia nel periodo <= {REGIME_EARLY_END} "
                         f"(trovati {stats['n_early']}) sia dopo (trovati {stats['n_late']})"))
    else:
        jump = l / e - 1.0
        out.append(Check(dataset, N_RAIN_CMP[3], WARN if abs(jump) > RAIN_REL_TOL else OK,
                         f"rapporto POWER/{ref_name} medio: fino al {REGIME_EARLY_END} {e:.2f} "
                         f"({stats['n_early']} anni), dopo {l:.2f} ({stats['n_late']} anni); "
                         f"variazione {jump:+.0%} (ATTENZIONE oltre +-{RAIN_REL_TOL:.0%})"))
    return out


# ======================================================================================
# 6. ET0
# ======================================================================================
def et0_tables(power_df: pd.DataFrame, lat: float, elev_m: float) -> tuple[
        pd.DataFrame, pd.DataFrame, dict[str, float]]:
    """(tabella annua, tabella mensile climatologica, sintesi) PM contro Hargreaves.

    Solo giorni con entrambi i metodi calcolabili. Mese con lo scarto maggiore = il mese
    del calendario in cui il totale medio mensile di Hargreaves si discosta di piu', in
    valore relativo, da quello di Penman-Monteith.
    """
    clean = _clean_power(power_df)
    res = et0.et0_from_power(clean, lat, elev_m)
    res["date"] = pd.to_datetime(res["date"])
    pair = res.dropna(subset=["et0_pm", "et0_hargreaves"]).copy()
    pair["year"], pair["month"] = pair["date"].dt.year, pair["date"].dt.month
    ann = pair.groupby("year").agg(n_days=("et0_pm", "size"), et0_pm=("et0_pm", "sum"),
                                   et0_hargreaves=("et0_hargreaves", "sum")).reset_index()
    ann["ratio"] = ann["et0_hargreaves"] / ann["et0_pm"]
    mon = pair.groupby("month").agg(et0_pm=("et0_pm", "sum"), et0_hargreaves=("et0_hargreaves", "sum"),
                                    n_years=("year", "nunique")).reset_index()
    mon["et0_pm"] /= mon["n_years"]
    mon["et0_hargreaves"] /= mon["n_years"]
    mon["diff_mm"] = mon["et0_hargreaves"] - mon["et0_pm"]
    mon["rel_diff"] = mon["diff_mm"] / mon["et0_pm"]
    mon.insert(1, "mese", [MONTHS_IT[m - 1] for m in mon["month"]])
    full = ann[ann["n_days"] >= 0.95 * 365]
    corr = float(pair["et0_pm"].corr(pair["et0_hargreaves"])) if len(pair) > 2 else np.nan
    worst = mon.loc[mon["rel_diff"].abs().idxmax()] if len(mon) else None
    summary = {"pm_mean": float(full["et0_pm"].mean()) if len(full) else np.nan,
               "hg_mean": float(full["et0_hargreaves"].mean()) if len(full) else np.nan,
               "ratio_mean": float(full["ratio"].mean()) if len(full) else np.nan,
               "corr": corr, "n_years": int(len(full)),
               "worst_month": str(worst["mese"]) if worst is not None else "",
               "worst_rel": float(worst["rel_diff"]) if worst is not None else np.nan,
               "worst_mm": float(worst["diff_mm"]) if worst is not None else np.nan}
    return ann, mon, summary


def check_et0(ann: pd.DataFrame, summary: dict[str, float]) -> list[Check]:
    full = ann[ann["n_days"] >= 0.95 * 365]
    if full.empty:
        return _skip(D_ET0, N_ET0, "nessun anno con dati sufficienti per calcolare ET0")
    lo, hi = ET0_RATIO_RANGE
    outside = full[(full["ratio"] < lo) | (full["ratio"] > hi)]
    detail = (f"totali annui medi su {summary['n_years']} anni: Penman-Monteith {summary['pm_mean']:.0f} mm, "
              f"Hargreaves {summary['hg_mean']:.0f} mm; rapporto medio HG/PM {summary['ratio_mean']:.3f} "
              f"(annuo min {full['ratio'].min():.3f}, max {full['ratio'].max():.3f}); correlazione "
              f"giornaliera {summary['corr']:.3f}; mese con lo scarto maggiore: {summary['worst_month']} "
              f"({summary['worst_rel']:+.0%}, {summary['worst_mm']:+.1f} mm); ")
    detail += ("anni con rapporto fuori [%.2f, %.2f]: " % (lo, hi) +
               ", ".join(f"{int(r.year)} {r.ratio:.2f}" for r in outside.itertuples())
               if len(outside) else f"nessun anno con rapporto fuori [{lo:.2f}, {hi:.2f}]")
    return [Check(D_ET0, N_ET0[0], WARN if len(outside) else OK, detail)]


# ======================================================================================
# 7. Temperature POWER contro ARPA
# ======================================================================================
TEMP_COLS = ["year", "n_days", "d_tmax", "d_tmin", "d_tmax_jja", "d_tmin_jja", "n_jja",
             "hot_days_power", "hot_days_arpa"]


def temp_tables(power_df: pd.DataFrame, arpa_t: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, float]]:
    """Differenze POWER - ARPA di tmax/tmin sui soli giorni ARPA completi."""
    a = arpa_t.copy()
    a["date"] = pd.to_datetime(a["date"]).dt.normalize()
    a["complete"] = a["complete"].fillna(False).astype(bool)
    a = a[a["complete"]].sort_values("date").drop_duplicates("date")
    m = a[["date", "tmax", "tmin"]].merge(power_df[["date", "tmax", "tmin"]], on="date",
                                          suffixes=("_arpa", "_power")).dropna()
    m["year"] = m["date"].dt.year
    m["jja"] = m["date"].dt.month.isin(SUMMER_MONTHS)
    m["dx"] = m["tmax_power"] - m["tmax_arpa"]
    m["dn"] = m["tmin_power"] - m["tmin_arpa"]
    rows = []
    for y, g in m.groupby("year"):
        s = g[g["jja"]]
        rows.append({"year": int(y), "n_days": len(g), "d_tmax": g["dx"].mean(), "d_tmin": g["dn"].mean(),
                     "d_tmax_jja": s["dx"].mean() if len(s) else np.nan,
                     "d_tmin_jja": s["dn"].mean() if len(s) else np.nan, "n_jja": len(s),
                     "hot_days_power": int((g["tmax_power"] > HOT_DAY_C).sum()),
                     "hot_days_arpa": int((g["tmax_arpa"] > HOT_DAY_C).sum())})
    table = pd.DataFrame(rows, columns=TEMP_COLS)
    s = m[m["jja"]]
    summary = {"n": len(m), "d_tmax": m["dx"].mean(), "d_tmin": m["dn"].mean(),
               "d_tmax_jja": s["dx"].mean() if len(s) else np.nan,
               "d_tmin_jja": s["dn"].mean() if len(s) else np.nan, "n_jja": len(s),
               "hot_power": int((m["tmax_power"] > HOT_DAY_C).sum()),
               "hot_arpa": int((m["tmax_arpa"] > HOT_DAY_C).sum())}
    return table, summary


def check_temp(table: pd.DataFrame, s: dict[str, float]) -> list[Check]:
    if not s["n"]:
        return _skip(D_CMP_T, N_TEMP_CMP, "nessun giorno ARPA completo in comune con POWER")
    jja = s["d_tmax_jja"]
    flag = np.isfinite(jja) and abs(jja) > TEMP_SUMMER_DIFF_MAX
    return [
        Check(D_CMP_T, N_TEMP_CMP[0], WARN if flag else OK,
              f"POWER - ARPA su {s['n']} giorni completi: tmax {s['d_tmax']:+.2f} degC, tmin "
              f"{s['d_tmin']:+.2f} degC (anno); giugno-agosto ({s['n_jja']} giorni): tmax "
              f"{s['d_tmax_jja']:+.2f}, tmin {s['d_tmin_jja']:+.2f} degC "
              f"(ATTENZIONE se |tmax estiva| > {TEMP_SUMMER_DIFF_MAX:g})"),
        Check(D_CMP_T, N_TEMP_CMP[1], OK,
              f"giorni con tmax > {HOT_DAY_C:g} degC nei giorni comuni: POWER {s['hot_power']}, "
              f"ARPA {s['hot_arpa']}; per anno nella tabella; informativo")]


# ======================================================================================
# 8. ARPA completezza
# ======================================================================================
def check_arpa_completeness(dataset: str, df: pd.DataFrame) -> list[Check]:
    miss = _missing_cols(df, ["date", "complete"])
    if miss:
        return _skip(dataset, N_ARPA, f"colonne mancanti: {', '.join(miss)}")
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["complete"] = d["complete"].fillna(False).astype(bool)
    d = d.drop_duplicates("date")
    per = d.groupby(d["date"].dt.year)["complete"].sum()
    pct = pd.Series({y: 100.0 * n / (366 if calendar.isleap(int(y)) else 365) for y, n in per.items()})
    low = pct[pct < ARPA_COMPLETE_MIN_PCT]
    detail = (f"giorni completi per anno: min {pct.min():.0f}% ({int(pct.idxmin())}), media "
              f"{pct.mean():.0f}%, {len(d)} giorni, {int(d['complete'].sum())} completi; ")
    detail += (f"anni sotto {ARPA_COMPLETE_MIN_PCT:g}%: " + ", ".join(f"{int(y)} {v:.0f}%" for y, v in low.items())
               if len(low) else f"nessun anno sotto {ARPA_COMPLETE_MIN_PCT:g}%")
    return [Check(dataset, N_ARPA[0], WARN if len(low) else OK, detail)]


# ======================================================================================
# 9. MODIS
# ======================================================================================
MODIS_COLS = ["year", "n_dates", "expected", "ndvi_min", "ndvi_max", "center_ok_pct",
              "window_ok_pct", "ndvi_julaug_mean", "summer_usable_pct", "esito"]


def modis_table(df: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Per anno: date, NDVI min/max, % date con pixel centrale buono/marginale (affidabilita'
    0 o 1 con NDVI valido), % date con almeno meta' pixel della finestra buoni, NDVI medio
    di luglio-agosto (``ndvi_window_mean_good``) e % di date utilizzabili in estate
    (giugno-agosto; utilizzabile = pixel centrale buono/marginale)."""
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d["year"] = d["date"].dt.year
    d["center_ok"] = d["reliability_center"].isin(modis.GOOD_RELIABILITY) & d["ndvi_center"].notna()
    with np.errstate(invalid="ignore", divide="ignore"):
        d["window_ok"] = (d["n_good"] / d["n_pixels"]) >= MODIS_WINDOW_GOOD_FRACTION
    rows = []
    for y in range(start_year, end_year + 1):
        g = d[d["year"] == y]
        exp = MODIS_EXPECTED_FIRST_YEAR if y == start_year else MODIS_EXPECTED
        if g.empty:
            rows.append({"year": y, "n_dates": 0, "expected": exp, "esito": WARN})
            continue
        s = g[g["date"].dt.month.isin(SUMMER_MONTHS)]
        ja = g[g["date"].dt.month.isin((7, 8))]
        usable = 100.0 * s["center_ok"].mean() if len(s) else 0.0
        bad = len(g) < MODIS_MIN_DATES or usable < MODIS_MIN_USABLE_SUMMER_PCT
        rows.append({"year": y, "n_dates": len(g), "expected": exp,
                     "ndvi_min": g["ndvi_center"].min(), "ndvi_max": g["ndvi_center"].max(),
                     "center_ok_pct": 100.0 * g["center_ok"].mean(),
                     "window_ok_pct": 100.0 * g["window_ok"].mean(),
                     "ndvi_julaug_mean": ja["ndvi_window_mean_good"].mean() if len(ja) else np.nan,
                     "summer_usable_pct": usable, "esito": WARN if bad else OK})
    return pd.DataFrame(rows, columns=MODIS_COLS)


def check_modis(df: pd.DataFrame, start_year: int, end_year: int) -> tuple[list[Check], pd.DataFrame | None]:
    need = ["date", "ndvi_center", "reliability_center", "ndvi_window_mean_good", "n_good", "n_pixels"]
    miss = _missing_cols(df, need)
    if miss:
        return _skip(D_MODIS, N_MODIS, f"colonne mancanti: {', '.join(miss)}"), None
    t = modis_table(df, start_year, end_year)
    out: list[Check] = []
    # date per anno
    few = t[t["n_dates"] < MODIS_MIN_DATES]
    off = t[(t["n_dates"] != t["expected"]) & (t["n_dates"] >= MODIS_MIN_DATES)]
    detail = (f"{len(t) - len(few) - len(off)} anni su {len(t)} con le date attese "
              f"({MODIS_EXPECTED}; {MODIS_EXPECTED_FIRST_YEAR} nel {start_year}); ")
    if len(off):
        detail += "diversi dall'atteso ma >= %d: " % MODIS_MIN_DATES + ", ".join(
            f"{int(r.year)} {int(r.n_dates)}" for r in off.itertuples()) + "; "
    detail += (f"anni con meno di {MODIS_MIN_DATES} date: " + ", ".join(
        f"{int(r.year)} ({int(r.n_dates)})" for r in few.itertuples()) if len(few)
        else f"nessun anno con meno di {MODIS_MIN_DATES} date")
    out.append(Check(D_MODIS, N_MODIS[0], WARN if len(few) else OK, detail))
    # intervallo
    lo, hi = MODIS_NDVI_RANGE
    vals = pd.concat([pd.to_numeric(df[c], errors="coerce") for c in
                      ("ndvi_center", "ndvi_window_mean_good", "ndvi_window_median_good")
                      if c in df.columns]).dropna()
    nout = int(((vals < lo) | (vals > hi)).sum())
    out.append(Check(D_MODIS, N_MODIS[1], ERR if nout else OK,
                     f"{len(vals)} valori NDVI (centro e finestra): min {vals.min():.3f}, max "
                     f"{vals.max():.3f}; attesi [{lo:g}, {hi:g}]; fuori: {nout}" if len(vals)
                     else "nessun valore NDVI valido"))
    d = df.copy()
    ok_c = d["reliability_center"].isin(modis.GOOD_RELIABILITY) & d["ndvi_center"].notna()
    out.append(Check(D_MODIS, N_MODIS[2], OK,
                     f"{100 * ok_c.mean():.1f}% delle {len(d)} date ha il pixel centrale buono o "
                     f"marginale (affidabilita' 0/1); informativo"))
    with np.errstate(invalid="ignore", divide="ignore"):
        ok_w = ((d["n_good"] / d["n_pixels"]) >= MODIS_WINDOW_GOOD_FRACTION)
    out.append(Check(D_MODIS, N_MODIS[3], OK,
                     f"{100 * ok_w.mean():.1f}% delle date ha almeno il {MODIS_WINDOW_GOOD_FRACTION:.0%} "
                     f"dei pixel della finestra buoni; informativo"))
    # utilizzabili in estate
    have = t[t["n_dates"] > 0]
    low = have[have["summer_usable_pct"] < MODIS_MIN_USABLE_SUMMER_PCT]
    if have.empty:
        out.append(Check(D_MODIS, N_MODIS[4], NA, "nessun anno con date"))
    else:
        tail = (f"anni sotto {MODIS_MIN_USABLE_SUMMER_PCT:g}%: " + ", ".join(
            f"{int(r.year)} {r.summer_usable_pct:.0f}%" for r in low.itertuples())
            if len(low) else f"nessun anno sotto {MODIS_MIN_USABLE_SUMMER_PCT:g}%")
        out.append(Check(D_MODIS, N_MODIS[4], WARN if len(low) else OK,
                         f"date estive (giugno-agosto) con pixel centrale utilizzabile: min "
                         f"{have['summer_usable_pct'].min():.0f}%, media {have['summer_usable_pct'].mean():.0f}% "
                         f"su {len(have)} anni; {tail}"))
    ja = have.dropna(subset=["ndvi_julaug_mean"])
    out.append(Check(D_MODIS, N_MODIS[5], OK if len(ja) else NA,
                     (f"media di luglio-agosto (finestra) su {len(ja)} anni: min "
                      f"{ja['ndvi_julaug_mean'].min():.3f} ({int(ja.loc[ja['ndvi_julaug_mean'].idxmin(), 'year'])}), "
                      f"max {ja['ndvi_julaug_mean'].max():.3f} ({int(ja.loc[ja['ndvi_julaug_mean'].idxmax(), 'year'])}); "
                      f"per anno nella tabella") if len(ja) else "nessuna data di luglio-agosto"))
    return out, t


# ======================================================================================
# 10. SoilGrids
# ======================================================================================
def check_soil(agg: pd.DataFrame) -> list[Check]:
    miss = _missing_cols(agg, ["property", "layer", "mean", "q05", "q95"])
    if miss:
        return _skip(D_SOIL, N_SOIL, f"colonne mancanti: {', '.join(miss)}")
    piv = agg.pivot_table(index="layer", columns="property", values="mean", sort=False)
    out: list[Check] = []
    if {"sand", "clay", "silt"} <= set(piv.columns):
        tot = piv["sand"] + piv["clay"] + piv["silt"]
        bad = tot[(tot - 100).abs() > SOIL_SUM_TOL]
        out.append(Check(D_SOIL, N_SOIL[0], ERR if len(bad) else OK,
                         "somma per strato: " + ", ".join(f"{k} {v:.2f}%" for k, v in tot.items()) +
                         f"; attesa 100 +-{SOIL_SUM_TOL:g}; fuori: {len(bad)}"))
    else:
        out += _skip(D_SOIL, N_SOIL[:1], "sabbia, argilla o limo assenti")
    if "bdod" in piv.columns:
        lo, hi = SOIL_BDOD_RANGE
        b = piv["bdod"]
        nb = int(((b < lo) | (b > hi)).sum())
        out.append(Check(D_SOIL, N_SOIL[1], ERR if nb else OK,
                         "media per strato: " + ", ".join(f"{k} {v:.2f}" for k, v in b.items()) +
                         f" g/cm3; attesa [{lo:g}, {hi:g}]; fuori: {nb}"))
    else:
        out += _skip(D_SOIL, N_SOIL[1:2], "densita' apparente assente")
    om = agg[(agg["property"] == "om") & (agg["layer"].astype(str).str.startswith("0-30"))]
    if om.empty:
        out += _skip(D_SOIL, N_SOIL[2:], "riga della sostanza organica 0-30 cm assente")
    else:
        r = om.iloc[0]
        out.append(Check(D_SOIL, N_SOIL[2], WARN if r["mean"] > SOIL_OM_WARN else OK,
                         f"media {r['mean']:.2f}%, intervallo q05-q95 {r['q05']:.2f}-{r['q95']:.2f}%; "
                         f"ATTENZIONE oltre {SOIL_OM_WARN:g}% (valore alto per un seminativo di pianura)"))
    return out


# ======================================================================================
# 11. ISTAT
# ======================================================================================
def istat_tables(df: pd.DataFrame) -> pd.DataFrame:
    """Tabella per coltura: anni, intervallo, rese min/max."""
    rows = []
    for crop, g in df.groupby("crop"):
        rows.append({"crop": crop, "n_years": g["year"].nunique(), "first": int(g["year"].min()),
                     "last": int(g["year"].max()), "yield_min": g["yield_t_ha"].min(),
                     "yield_max": g["yield_t_ha"].max(), "yield_mean": g["yield_t_ha"].mean()})
    return pd.DataFrame(rows)


def istat_detail(df: pd.DataFrame, last_weather_year: int) -> pd.DataFrame:
    """Una riga per anno e coltura con la resa, la variazione annua e le segnalazioni."""
    d = df.sort_values(["crop", "year"]).copy()
    d["prev_year"] = d.groupby("crop")["year"].shift()
    d["prev_yield"] = d.groupby("crop")["yield_t_ha"].shift()
    consecutive = d["year"] - d["prev_year"] == 1
    d["change"] = np.where(consecutive, d["yield_t_ha"] / d["prev_yield"] - 1.0, np.nan)
    d["out_of_range"] = [not (ISTAT_RANGES[c][0] <= y <= ISTAT_RANGES[c][1]) if c in ISTAT_RANGES else False
                         for c, y in zip(d["crop"], d["yield_t_ha"])]
    d["provisional"] = d["year"] > last_weather_year
    d["jump"] = d["change"].abs() > ISTAT_JUMP
    return d


def check_istat(df: pd.DataFrame, last_weather_year: int) -> list[Check]:
    miss = _missing_cols(df, ["year", "crop", "yield_t_ha"])
    if miss:
        return _skip(D_ISTAT, N_ISTAT, f"colonne mancanti: {', '.join(miss)}")
    out: list[Check] = []
    d = istat_detail(df.dropna(subset=["yield_t_ha"]), last_weather_year)
    present = {c: g for c, g in d.groupby("crop")}
    absent = [c for c in ISTAT_RANGES if c not in present]
    parts = []
    for c in ISTAT_RANGES:
        if c in present:
            g = present[c]
            parts.append(f"{c} {g['year'].min()}-{g['year'].max()} ({g['year'].nunique()} anni)")
    out.append(Check(D_ISTAT, N_ISTAT[0], WARN if absent else OK,
                     "; ".join(parts) + (f"; colture assenti: {', '.join(absent)}" if absent else "")))
    bad = d[d["out_of_range"]]
    rng = "; ".join(f"{c} {lo:g}-{hi:g}" for c, (lo, hi) in ISTAT_RANGES.items())
    out.append(Check(D_ISTAT, N_ISTAT[1], ERR if len(bad) else OK,
                     (f"{len(bad)} rese fuori intervallo: " + ", ".join(
                         f"{r.crop} {int(r.year)} {r.yield_t_ha:.1f}" for r in bad.itertuples())
                      if len(bad) else f"tutte le rese in intervallo (t/ha: {rng})")))
    prov = d[d["provisional"]]
    out.append(Check(D_ISTAT, N_ISTAT[2], WARN if len(prov) else OK,
                     (f"anni oltre l'ultimo anno di meteo ({last_weather_year}) da escludere dalla "
                      f"validazione (stime provvisorie): " + ", ".join(
                          sorted({f"{c} {', '.join(str(int(y)) for y in g['year'])}"
                                  for c, g in prov.groupby('crop')})))
                     if len(prov) else f"nessun anno oltre {last_weather_year}"))
    jumps = d[d["jump"]]
    out.append(Check(D_ISTAT, N_ISTAT[3], WARN if len(jumps) else OK,
                     (f"{len(jumps)} variazioni oltre +-{ISTAT_JUMP:.0%} rispetto all'anno precedente: " +
                      ", ".join(f"{r.crop} {int(r.year)} {r.change:+.1%}" for r in jumps.itertuples()))
                     if len(jumps) else f"nessuna variazione oltre +-{ISTAT_JUMP:.0%}"))
    return out


# ======================================================================================
# 12. IMERG, SMAP
# ======================================================================================
def check_imerg(df: pd.DataFrame, end: str) -> list[Check]:
    miss = _missing_cols(df, ["date", "rain_mm"])
    if miss:
        return _skip(D_IMERG, N_IMERG, f"colonne mancanti: {', '.join(miss)}")
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"]).dt.normalize()
    d = d.drop_duplicates("date").sort_values("date")
    vals = pd.to_numeric(d["rain_mm"], errors="coerce")
    first = max(pd.Timestamp(imerg.FIRST_DAY), pd.Timestamp(d["date"].min()))
    last = pd.Timestamp(d["date"].max())
    exp = pd.date_range(first, last, freq="D")
    have = pd.DatetimeIndex(d.loc[vals.notna(), "date"])
    missing = exp.difference(have)
    out = [Check(D_IMERG, N_IMERG[0], WARN if len(missing) else OK,
                 f"{len(have)} giorni con valore su {len(exp)} attesi ({first:%Y-%m-%d}..{last:%Y-%m-%d}); "
                 f"mancanti {len(missing)}" + (f" (primi: {_fmt_dates(missing, 3)})" if len(missing) else ""))]
    lo, hi = IMERG_RANGE
    v = vals.dropna()
    nout = int(((v < lo) | (v > hi)).sum())
    out.append(Check(D_IMERG, N_IMERG[1], ERR if nout else OK,
                     f"min {v.min():.2f}, max {v.max():.2f} mm/g; attesi [{lo:g}, {hi:g}]; fuori: {nout}"
                     if len(v) else "nessun valore valido"))
    out.append(Check(D_IMERG, N_IMERG[2], WARN if last < pd.Timestamp(end) else OK,
                     f"ultimo giorno {last:%Y-%m-%d} (fine periodo meteo {end})"))
    return out


def check_smap(df: pd.DataFrame) -> list[Check]:
    miss = _missing_cols(df, ["date", "sm_am", "qual_am", "sm_pm", "qual_pm"])
    if miss:
        return _skip(D_SMAP, N_SMAP, f"colonne mancanti: {', '.join(miss)}")
    good = smap.GOOD_FLAGS
    gam = df["qual_am"].isin(good) & df["sm_am"].notna()
    gpm = df["qual_pm"].isin(good) & df["sm_pm"].notna()
    n_days = df["date"].nunique()
    n_good = int((gam | gpm).sum())
    vals = pd.concat([df.loc[gam, "sm_am"], df.loc[gpm, "sm_pm"]])
    lo, hi = SMAP_RANGE
    nout = int(((vals < lo) | (vals > hi)).sum())
    return [
        Check(D_SMAP, N_SMAP[0], OK,
              f"{n_good} giorni su {n_days} ({100 * n_good / max(n_days, 1):.1f}%) con almeno un passaggio "
              f"con flag {list(good)}; informativo"),
        Check(D_SMAP, N_SMAP[1], ERR if nout else OK,
              (f"{len(vals)} valori di qualita' raccomandata: min {vals.min():.3f}, max {vals.max():.3f} "
               f"m3/m3; attesi [{lo:g}, {hi:g}]; fuori: {nout}") if len(vals) else "nessun valore valido")]


# ======================================================================================
# Orchestrazione
# ======================================================================================
@dataclass
class Report:
    checks: list[Check]
    tables: dict[str, pd.DataFrame]
    notes: dict[str, str]
    lat: float
    lon: float
    generated: str


def run_checks(lat: float, lon: float) -> Report:
    checks: list[Check] = []
    tables: dict[str, pd.DataFrame] = {}
    notes: dict[str, str] = {}
    start, end = f"{config.START_YEAR}-01-01", f"{config.END_YEAR}-12-31"
    pdir = cache.processed_dir(lat, lon)

    pw, why_pw = _load("dati POWER", lambda: power.load(lat, lon))
    site, why_site = _load("power_site.json", lambda: power.load_site(lat, lon))
    elev = float(site["elevation_m"]) if site and "elevation_m" in site else None
    if pw is None:
        checks += _unavailable(D_POWER, N_POWER, why_pw)
    else:
        checks += check_power(pw, lat, elev, start, end)
    pw_clean = _clean_power(pw) if pw is not None and not _missing_cols(pw, ["date", *POWER_VARS]) else None
    last_weather_year = int(pw_clean["date"].dt.year.max()) if pw_clean is not None and len(pw_clean) \
        else config.END_YEAR

    # ARPA pioggia + confronto
    ar, why_ar = _load("arpa_rain_daily.csv", lambda: arpa.load(lat, lon))
    if ar is not None and _missing_cols(ar, ["date", "rain_mm", "complete"]):
        ar, why_ar = None, "arpa_rain_daily.csv: colonne mancanti " + ", ".join(
            _missing_cols(ar, ["date", "rain_mm", "complete"]))
    if ar is None:
        checks += _unavailable(D_ARPA, N_ARPA, why_ar)
    else:
        checks += check_arpa_completeness(D_ARPA, ar)
    rain_tables = []
    for ds, ref_name, ref, why in ((D_CMP_ARPA, "ARPA", ar, why_ar),):
        if pw_clean is None:
            checks += _skip(ds, N_RAIN_CMP, "POWER non disponibile")
        elif ref is None:
            checks += _unavailable(ds, N_RAIN_CMP, why)
        else:
            rf = _ref_frame(ref, ref["complete"].fillna(False).astype(bool))
            tab, st = rain_annual_table(pw_clean, rf, ref_name)
            rain_tables.append(tab)
            checks += check_rain_compare(ds, ref_name, tab, st)

    # IMERG
    im, why_im = _load("imerg_daily.csv", lambda: imerg.load(lat, lon))
    if im is not None and _missing_cols(im, ["date", "rain_mm"]):
        im, why_im = None, "imerg_daily.csv: colonne mancanti"
    if im is None:
        checks += _unavailable(D_IMERG, N_IMERG, why_im)
        if pw_clean is None:
            checks += _skip(D_CMP_IMERG, N_RAIN_CMP, "POWER non disponibile")
        else:
            checks += _skip(D_CMP_IMERG, N_RAIN_CMP, why_im)
    else:
        checks += check_imerg(im, end)
        if pw_clean is None:
            checks += _skip(D_CMP_IMERG, N_RAIN_CMP, "POWER non disponibile")
        else:
            rf = _ref_frame(im, pd.Series(True, index=im.index))
            tab, st = rain_annual_table(pw_clean, rf, "IMERG")
            rain_tables.append(tab)
            checks += check_rain_compare(D_CMP_IMERG, "IMERG", tab, st)
    tables["rain"] = pd.concat(rain_tables, ignore_index=True) if rain_tables else pd.DataFrame(columns=RAIN_COLS)

    # ET0
    if pw_clean is None:
        checks += _skip(D_ET0, N_ET0, "POWER non disponibile")
    elif elev is None:
        checks += _skip(D_ET0, N_ET0, why_site or "quota della cella POWER non disponibile")
    else:
        ann, mon, summ = et0_tables(pw_clean, lat, elev)
        tables["et0_annual"], tables["et0_monthly"] = ann, mon
        notes["et0"] = f"lat {lat:g}, quota {elev:g} m (cella POWER), G = 0, ea da UR media (FAO-56 eq. 19)"
        checks += check_et0(ann, summ)

    # ARPA temperature
    at, why_at = _load("arpa_temp_daily.csv", lambda: _read_csv(pdir / "arpa_temp_daily.csv"))
    if at is not None and _missing_cols(at, ["date", "tmax", "tmin", "complete"]):
        at, why_at = None, "arpa_temp_daily.csv: colonne mancanti " + ", ".join(
            _missing_cols(at, ["date", "tmax", "tmin", "complete"]))
    if at is None:
        checks += _unavailable(D_ARPA_T, N_ARPA, why_at)
        checks += _skip(D_CMP_T, N_TEMP_CMP, why_at)
    else:
        checks += check_arpa_completeness(D_ARPA_T, at)
        if pw_clean is None:
            checks += _skip(D_CMP_T, N_TEMP_CMP, "POWER non disponibile")
        else:
            tt, ts = temp_tables(pw_clean, at)
            tables["temp"] = tt
            checks += check_temp(tt, ts)

    # MODIS
    mo, why_mo = _load("modis_ndvi.csv", lambda: modis.load(lat, lon))
    if mo is None:
        checks += _unavailable(D_MODIS, N_MODIS, why_mo)
    else:
        res, tab = check_modis(mo, config.START_YEAR, config.END_YEAR)
        if tab is not None:
            tables["modis"] = tab
        checks += res

    # SoilGrids
    sg, why_sg = _load("soilgrids_agg.csv", lambda: _read_csv(pdir / "soilgrids_agg.csv"))
    if sg is None:
        checks += _unavailable(D_SOIL, N_SOIL, why_sg)
    else:
        checks += check_soil(sg)

    # ISTAT
    ist, why_is = _load("istat_yields.csv", lambda: _read_csv(cache.processed_dir(key="cremona", create=False) / "istat_yields.csv"))
    if ist is None:
        checks += _unavailable(D_ISTAT, N_ISTAT, why_is)
    else:
        checks += check_istat(ist, last_weather_year)
        if not _missing_cols(ist, ["year", "crop", "yield_t_ha"]):
            tables["istat"] = istat_detail(ist.dropna(subset=["yield_t_ha"]), last_weather_year)
        notes["istat"] = f"ultimo anno di meteo: {last_weather_year}"

    # SMAP
    sm, why_sm = _load("smap_daily.csv", lambda: smap.load(lat, lon))
    if sm is None:
        checks += _unavailable(D_SMAP, N_SMAP, why_sm)
    else:
        checks += check_smap(sm)

    return Report(checks, tables, notes, lat, lon, datetime.now().strftime("%Y-%m-%d %H:%M"))


# ======================================================================================
# Scrittura delle uscite
# ======================================================================================
def _cell(v: Any, fmt: str | None) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA or v is pd.NaT:
        return "-"
    if fmt and isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, bool):
        return format(v, fmt)
    return str(v).replace("|", "/").replace("\n", " ")


def md_table(df: pd.DataFrame, formats: dict[str, str] | None = None,
             headers: dict[str, str] | None = None) -> str:
    formats = formats or {}
    headers = headers or {}
    cols = list(df.columns)
    lines = ["| " + " | ".join(headers.get(c, c) for c in cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join(_cell(v, formats.get(c)) for c, v in zip(cols, row)) + " |")
    return "\n".join(lines)


def build_auto_block(rep: Report) -> str:
    counts = {s: sum(c.status == s for c in rep.checks) for s in (OK, WARN, ERR, NA)}
    L = [MARK_START, "",
         "## Controlli automatici di qualita' dei dati", "",
         f"Eseguito il {rep.generated} con `python -m fieldwise.qc --lat {rep.lat:g} --lon {rep.lon:g}`. "
         f"{len(rep.checks)} controlli: {counts[OK]} OK, {counts[WARN]} ATTENZIONE, {counts[ERR]} ERRORE, "
         f"{counts[NA]} NON DISPONIBILE. Questa parte e' rigenerata a ogni esecuzione: non modificarla a mano "
         f"(le decisioni vanno nella sezione Decisioni, in fondo al file).", "",
         "### Esiti", "",
         md_table(pd.DataFrame([asdict(c) for c in rep.checks]),
                  headers={"dataset": "Dataset", "name": "Controllo", "status": "Esito", "detail": "Dettaglio"}),
         ""]
    t = rep.tables
    L += ["### Pioggia annua: POWER contro riferimento", ""]
    if "rain" in t and len(t["rain"]):
        L += ["Totali `*_mm` sull'anno intero; colonne `*_common_mm`, scarto e rapporto ricalcolati solo "
              "sui giorni in cui il riferimento e' completo (ARPA `complete`) o presente (IMERG). Scarto = "
              "(POWER - rif) / rif. Anno confrontabile solo con almeno "
              f"{MIN_COMPLETE_PCT:g}% di giorni completi.", "",
              md_table(t["rain"], formats={
                  "year": "d", "power_total_mm": ".0f", "ref_total_mm": ".0f", "ref_complete_pct": ".1f",
                  "power_common_mm": ".0f", "ref_common_mm": ".0f", "n_common_days": "d", "rel_diff": "+.1%",
                  "ratio": ".2f", "wet_freq_power_pct": ".1f", "wet_freq_ref_pct": ".1f"}), ""]
    else:
        L += ["_Nessun confronto disponibile._", ""]
    L += ["### ET0: Penman-Monteith contro Hargreaves", ""]
    if "et0_annual" in t:
        L += [f"_{rep.notes.get('et0', '')}_", "", "Totali annui (mm) sui giorni con entrambi i metodi.", "",
              md_table(t["et0_annual"], formats={"year": "d", "n_days": "d", "et0_pm": ".0f",
                                                 "et0_hargreaves": ".0f", "ratio": ".3f"}), "",
              "Medie mensili climatologiche (mm/mese).", "",
              md_table(t["et0_monthly"].drop(columns=["n_years"]), formats={
                  "month": "d", "et0_pm": ".1f", "et0_hargreaves": ".1f", "diff_mm": "+.1f",
                  "rel_diff": "+.1%"}), ""]
    else:
        L += ["_Non disponibile._", ""]
    L += ["### Temperature: POWER contro ARPA", ""]
    if "temp" in t:
        L += ["Differenze medie POWER - ARPA (degC) sui giorni ARPA completi; `jja` = giugno-agosto; "
              f"giorni con tmax > {HOT_DAY_C:g} degC contati sugli stessi giorni.", "",
              md_table(t["temp"], formats={"year": "d", "n_days": "d", "n_jja": "d", "d_tmax": "+.2f",
                                           "d_tmin": "+.2f", "d_tmax_jja": "+.2f", "d_tmin_jja": "+.2f"}), ""]
    else:
        L += ["_Non disponibile (manca `arpa_temp_daily.csv` o il confronto e' saltato)._", ""]
    L += ["### MODIS NDVI per anno", ""]
    if "modis" in t:
        L += ["`center_ok` = pixel centrale con affidabilita' 0 o 1; `window_ok` = date con almeno meta' dei "
              "pixel della finestra buoni; `summer_usable` = date di giugno-agosto con pixel centrale "
              "utilizzabile; NDVI di luglio-agosto = media della finestra (`ndvi_window_mean_good`).", "",
              md_table(t["modis"], formats={"year": "d", "n_dates": "d", "expected": "d", "ndvi_min": ".3f",
                                            "ndvi_max": ".3f", "center_ok_pct": ".0f", "window_ok_pct": ".0f",
                                            "ndvi_julaug_mean": ".3f", "summer_usable_pct": ".0f"}), ""]
    else:
        L += ["_Non disponibile._", ""]
    L += ["### ISTAT: rese provinciali", ""]
    if "istat" in t:
        d = t["istat"].copy()
        d["segnalazioni"] = [", ".join(f for f, on in (("fuori intervallo", r.out_of_range),
                                                       ("provvisorio", r.provisional),
                                                       ("salto", r.jump)) if on)
                             for r in d.itertuples()]
        L += [f"_{rep.notes.get('istat', '')}_ (rese calcolate come produzione raccolta / superficie totale). "
              "Sintesi per coltura e righe con almeno una segnalazione.", "",
              md_table(istat_tables(t["istat"]), formats={"n_years": "d", "yield_min": ".1f",
                                                          "yield_max": ".1f", "yield_mean": ".1f"}), "",
              md_table(d.loc[d["segnalazioni"] != "", ["crop", "year", "yield_t_ha", "change", "segnalazioni"]],
                       formats={"year": "d", "yield_t_ha": ".2f", "change": "+.1%"}), ""]
    else:
        L += ["_Non disponibile._", ""]
    L.append(MARK_END)
    return "\n".join(L)


def write_checks_md(rep: Report, path=None) -> Any:
    """Scrive il blocco automatico in CHECKS.md senza toccare il resto (Decisioni compresa)."""
    path = path or (config.DATA_DIR / "CHECKS.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    block = build_auto_block(rep)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    pat = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), re.DOTALL)
    if pat.search(text):
        new = pat.sub(lambda _: block, text, count=1)
    elif text.strip():
        # file esistente senza marcatori: blocco subito dopo l'eventuale titolo
        lines = text.split("\n")
        i = 1 if lines and lines[0].startswith("# ") else 0
        new = "\n".join(lines[:i]) + ("\n\n" if i else "") + block + "\n\n" + "\n".join(lines[i:]).lstrip("\n")
    else:
        new = "# Controlli di qualita' dei dati\n\n" + block + "\n"
    outside = pat.sub("", new)
    if not re.search(r"^## Decisioni\b", outside, re.MULTILINE):
        new = new.rstrip("\n") + f"\n\n{DECISIONI_HEADING}\n\n{DECISIONI_PLACEHOLDER}\n"
    elif not new.endswith("\n"):
        new += "\n"
    path.write_text(new, encoding="utf-8")
    return path


def write_outputs(rep: Report) -> dict[str, Any]:
    pdir = cache.processed_dir(rep.lat, rep.lon)
    counts = {s: sum(c.status == s for c in rep.checks) for s in (OK, WARN, ERR, NA)}
    summary = {"lat": rep.lat, "lon": rep.lon, "generated": rep.generated, "counts": counts,
               "checks": [asdict(c) for c in rep.checks]}
    (pdir / "qc_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    rep.tables["rain"].to_csv(pdir / "qc_rain_annual.csv", index=False, float_format="%.4f")
    md = write_checks_md(rep)
    return {"md": md, "summary": pdir / "qc_summary.json", "rain": pdir / "qc_rain_annual.csv"}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Controllo qualita' dei dati in cache")
    ap.add_argument("--lat", type=float, default=config.PILOT_LAT)
    ap.add_argument("--lon", type=float, default=config.PILOT_LON)
    a = ap.parse_args(argv)
    rep = run_checks(a.lat, a.lon)
    paths = write_outputs(rep)
    for c in rep.checks:
        print(f"[{c.status}] {c.dataset} / {c.name}: {c.detail}")
    counts = {s: sum(c.status == s for c in rep.checks) for s in (OK, WARN, ERR, NA)}
    print("\n" + ", ".join(f"{k} {v}" for k, v in counts.items()))
    print(f"scritto: {paths['md']}")
    return 1 if counts[ERR] else 0


if __name__ == "__main__":
    sys.exit(main())
