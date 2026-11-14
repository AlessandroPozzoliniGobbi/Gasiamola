"""Test di `fieldwise.validation`: funzioni statistiche su dati sintetici dal risultato noto
(senza rete e senza cache) e `run_all` offline sui dati reali (saltato se la cache manca).

`run_all` viene eseguito su una COPIA della cartella `data/processed`: i file del repository
non vengono toccati. Il test e' marcato `slow` (bootstrap a blocchi, simulazioni del motore)."""
from __future__ import annotations

import math
import shutil

import numpy as np
import pandas as pd
import pytest

from fieldwise import config
from fieldwise import validation as val


# ----------------------------------------------------------------------------- correlazione
def test_correlazione_perfetta_e_intervallo_stretto():
    x = np.arange(1, 21, dtype=float)
    r = val.corr_stats(x, 3.0 * x + 2.0)
    assert r["n"] == 20
    assert r["pearson"] == pytest.approx(1.0)
    assert r["spearman"] == pytest.approx(1.0)
    lo, hi = r["pearson_ic95"]
    assert hi == pytest.approx(1.0, abs=1e-4) and lo > 0.99


def test_correlazione_anticorrelata_perfetta():
    x = np.arange(1, 11, dtype=float)
    r = val.corr_stats(x, -x)
    assert r["pearson"] == pytest.approx(-1.0)
    assert r["spearman"] == pytest.approx(-1.0)


def test_pearson_e_intervallo_di_fisher_su_un_caso_noto():
    # x = 1..5, y = 2,1,4,3,5: r di Pearson e rho di Spearman valgono entrambi 0,8 (a mano).
    x = [1, 2, 3, 4, 5]
    y = [2, 1, 4, 3, 5]
    r = val.corr_stats(x, y)
    assert r["n"] == 5
    assert r["pearson"] == pytest.approx(0.8)
    assert r["spearman"] == pytest.approx(0.8)
    # Fisher: z = atanh(0,8), errore standard 1/sqrt(n-3), 1,959964 e' il quantile al 97,5%
    z, se = math.atanh(0.8), 1.0 / math.sqrt(2.0)
    atteso = [math.tanh(z - 1.959964 * se), math.tanh(z + 1.959964 * se)]
    assert r["pearson_ic95"] == pytest.approx(atteso, abs=1e-9)
    # Bonett-Wright per Spearman: errore standard sqrt((1 + rho^2/2)/(n-3))
    se_s = math.sqrt((1 + 0.8 ** 2 / 2) / 2.0)
    atteso_s = [math.tanh(z - 1.959964 * se_s), math.tanh(z + 1.959964 * se_s)]
    assert r["spearman_ic95"] == pytest.approx(atteso_s, abs=1e-9)


def test_intervallo_contiene_la_stima_ed_e_in_meno_uno_piu_uno():
    rng = np.random.default_rng(1)
    x = rng.normal(size=30)
    y = 0.6 * x + rng.normal(scale=0.8, size=30)
    r = val.corr_stats(x, y)
    for k in ("pearson", "spearman"):
        lo, hi = r[f"{k}_ic95"]
        assert -1.0 <= lo <= r[k] <= hi <= 1.0


def test_intervallo_si_restringe_con_piu_dati():
    rng = np.random.default_rng(2)
    x = rng.normal(size=400)
    y = 0.5 * x + rng.normal(size=400)
    a = val.corr_stats(x[:20], y[:20])["pearson_ic95"]
    b = val.corr_stats(x, y)["pearson_ic95"]
    assert (b[1] - b[0]) < (a[1] - a[0])


def test_i_nan_si_scartano_a_coppie():
    x = np.array([1, 2, 3, 4, 5, 6, np.nan, 8.0])
    y = np.array([2, 4, 6, 8, 10, 12, 14, np.nan])
    r = val.corr_stats(x, y)
    assert r["n"] == 6
    assert r["pearson"] == pytest.approx(1.0)


def test_casi_degeneri_danno_nan_e_non_eccezioni():
    for x, y in (([1, 2, 3], [1, 2, 3]),                    # meno di 4 coppie
                 ([1, 1, 1, 1, 1], [1, 2, 3, 4, 5]),        # x costante
                 ([1, 2, 3, 4, 5], [7, 7, 7, 7, 7])):       # y costante
        r = val.corr_stats(x, y)
        assert math.isnan(r["pearson"]) and math.isnan(r["spearman"])
        assert all(math.isnan(v) for v in r["pearson_ic95"])


def test_bootstrap_a_blocchi_riproducibile_con_seme_fisso():
    rng = np.random.default_rng(3)
    x = rng.normal(size=48)
    y = 0.7 * x + rng.normal(scale=0.7, size=48)
    a = val.corr_stats(x, y, ci="block", block=6, n_boot=400, seed=11)
    b = val.corr_stats(x, y, ci="block", block=6, n_boot=400, seed=11)
    c = val.corr_stats(x, y, ci="block", block=6, n_boot=400, seed=12)
    assert a["pearson_ic95"] == b["pearson_ic95"] and a["spearman_ic95"] == b["spearman_ic95"]
    assert a["pearson_ic95"] != c["pearson_ic95"]
    assert a["metodo_ic"] == "block" and a["blocco"] == 6
    lo, hi = a["pearson_ic95"]
    assert -1.0 <= lo < hi <= 1.0


def test_bootstrap_a_blocchi_e_piu_largo_di_fisher_con_autocorrelazione_forte():
    # serie molto autocorrelate: il bootstrap a blocchi non puo' dare un intervallo piu' stretto
    # di Fisher in modo sistematico (e' il motivo per cui lo si usa sulle serie mensili)
    rng = np.random.default_rng(4)
    e = rng.normal(size=120)
    x = np.convolve(e, np.ones(8) / 8, mode="same")
    y = x + np.convolve(rng.normal(size=120), np.ones(8) / 8, mode="same")
    fisher = val.corr_stats(x, y)["pearson_ic95"]
    blocchi = val.corr_stats(x, y, ci="block", block=6, n_boot=500)["pearson_ic95"]
    assert (blocchi[1] - blocchi[0]) > 0.8 * (fisher[1] - fisher[0])


def test_autocorrelazione_a_un_passo():
    alt = np.array([1.0, -1.0] * 10)
    assert val._lag1(alt) == pytest.approx(-1.0)
    assert val._lag1(np.arange(20.0)) == pytest.approx(1.0)
    assert math.isnan(val._lag1([1.0, 2.0, 3.0]))


# ----------------------------------------------------------------------------- detrendizzazione
def test_detrend_di_una_retta_esatta_e_zero():
    anni = np.arange(2006, 2023)
    y = 0.12 * (anni - 2006) + 9.0
    assert np.allclose(val.detrend(anni, y), 0.0, atol=1e-9)


def test_detrend_restituisce_lo_scarto_dalla_retta():
    # lo scarto e' ortogonale a costante e pendenza (somma 0 e somma t*e = 0): la retta stimata
    # coincide con quella vera e il residuo con lo scarto
    t = np.arange(5, dtype=float)
    scarto = np.array([1.0, -2.0, 2.0, -2.0, 1.0])
    y = 5.0 + 2.0 * t + scarto
    assert np.allclose(val.detrend(2000 + t, y), scarto, atol=1e-9)


def test_detrend_ha_media_zero_e_conserva_la_lunghezza():
    rng = np.random.default_rng(5)
    anni = np.arange(2006, 2023)
    y = 0.3 * anni + rng.normal(size=anni.size)
    r = val.detrend(anni, y)
    assert r.shape == y.shape
    assert r.mean() == pytest.approx(0.0, abs=1e-9)


def test_confronto_istat_toglie_il_trend_prima_di_correlare():
    # La resa osservata e' trend + scarto; la simulata segue lo scarto: dopo la detrendizzazione la
    # correlazione e' quasi 1, mentre sui valori grezzi il trend la sporcherebbe.
    anni = np.arange(2006, 2023)
    scarto = np.sin(np.arange(anni.size) * 1.7)
    obs = pd.Series(9.0 + 0.2 * (anni - 2006) + scarto, index=anni)
    sim = pd.Series(0.5 + 0.1 * scarto, index=anni)
    out = val._istat_compare(obs, sim)
    assert out["anni"] == [2006, 2022]
    assert out["detrend"]["n"] == 17
    grezzo = float(np.corrcoef(obs.to_numpy(), sim.to_numpy())[0, 1])
    # (lo scarto sinusoidale non e' esattamente ortogonale al trend, quindi non si ottiene 1,000)
    assert out["detrend"]["pearson"] > 0.99 > grezzo
    assert out["differenze_prime"]["n"] == 16


def test_confronto_istat_con_pochi_anni_non_calcola():
    obs = pd.Series([1.0, 2.0, 3.0], index=[2006, 2007, 2008])
    out = val._istat_compare(obs, obs)
    assert "detrend" not in out


# ----------------------------------------------------------------------------- anomalie mensili
def _giornaliero(anni=(2015, 2016, 2017), clima=None, anom=None):
    """Serie giornaliera sintetica: valore = climatologia del mese + anomalia dell'anno-mese."""
    idx = pd.date_range(f"{anni[0]}-01-01", f"{anni[-1]}-12-31", freq="D")
    clima = clima or {m: 0.10 + 0.01 * m for m in range(1, 13)}
    anom = anom or {}
    v = [clima[d.month] + anom.get((d.year, d.month), 0.0) for d in idx]
    return pd.Series(v, index=idx)


def test_anomalie_mensili_recuperano_anomalie_note():
    anom = {(2015, 3): 0.05, (2016, 3): -0.02, (2017, 3): -0.03,      # somma 0 nel mese
            (2015, 7): -0.04, (2016, 7): 0.04, (2017, 7): 0.0}
    obs = _giornaliero(anom=anom)
    mod = _giornaliero()                                             # modello senza anomalie
    m = val.monthly_anomalies(obs, mod, "2015-01-01", "2017-12-31")
    assert len(m) == 36
    # marzo 2015: +0,05 rispetto alla media di marzo
    assert m.loc["2015-03-01", "obs_anom"] == pytest.approx(0.05)
    assert m.loc["2016-03-01", "obs_anom"] == pytest.approx(-0.02)
    assert m.loc["2016-07-01", "obs_anom"] == pytest.approx(0.04)
    assert np.allclose(m["mod_anom"], 0.0)
    # la climatologia si toglie: le anomalie di ogni mese dell'anno hanno media zero
    assert np.allclose(m.groupby(m.index.month)["obs_anom"].mean(), 0.0)
    # il ciclo stagionale scompare
    assert m["obs_anom"].abs().max() == pytest.approx(0.05)


def test_anomalie_mensili_scartano_i_mesi_con_pochi_giorni():
    obs = _giornaliero()
    mod = _giornaliero()
    obs.loc["2016-05-01":"2016-05-27"] = np.nan                       # restano 4 giorni di maggio 2016
    m = val.monthly_anomalies(obs, mod, "2015-01-01", "2017-12-31", min_days=5)
    assert pd.Timestamp("2016-05-01") not in m.index
    assert len(m) == 35
    m2 = val.monthly_anomalies(obs, mod, "2015-01-01", "2017-12-31", min_days=4)
    assert pd.Timestamp("2016-05-01") in m2.index


def test_anomalie_mensili_usano_solo_i_giorni_comuni():
    obs = _giornaliero()
    mod = _giornaliero()
    mod.loc["2015-02-01":"2015-02-28"] = np.nan                       # febbraio 2015 senza modello
    m = val.monthly_anomalies(obs, mod, "2015-01-01", "2017-12-31")
    assert pd.Timestamp("2015-02-01") not in m.index
    assert (m["n_giorni"] >= 5).all()


def test_anomalie_mensili_rispettano_il_periodo():
    obs, mod = _giornaliero(), _giornaliero()
    m = val.monthly_anomalies(obs, mod, "2016-01-01", "2016-12-31")
    assert len(m) == 12 and m.index.min() == pd.Timestamp("2016-01-01")


# ----------------------------------------------------------------------------- costanti di metodo
def test_scenario_rappresentativo_e_scenari_coerenti():
    assert val.SCENARIO_RAPPRESENTATIVO in val.SCENARI
    assert set(val.SCENARI) == {"solo_pioggia", "tetto_irriguo", "irrigazione_libera"}
    assert val.ISTAT_YEARS[0] < val.ISTAT_YEARS[1] <= 2022          # solo anni con pioggia affidabile


# ----------------------------------------------------------------------------- run_all (dati reali)
CHIAVI_RIEPILOGO = {"punto", "metodo", "smap", "ndvi", "istat", "robustezza_mais", "figure",
                    "tabelle", "non_validato"}


@pytest.fixture(scope="module")
def riepilogo(tmp_path_factory):
    """`run_all` offline su una copia di data/processed (i file del repository restano intatti)."""
    mp = pytest.MonkeyPatch()
    mp.setenv("FIELDWISE_OFFLINE", "1")
    pdir = config.PROCESSED_DIR / f"lat{config.PILOT_LAT:.3f}_lon{config.PILOT_LON:.3f}"
    if not (pdir / "validation_summary.json").exists() or not (config.PROCESSED_DIR / "cremona").exists():
        pytest.skip("cache del punto pilota assente (data/processed)")
    copia = tmp_path_factory.mktemp("processed") / "processed"
    shutil.copytree(config.PROCESSED_DIR, copia)
    mp.setattr(config, "PROCESSED_DIR", copia)
    try:
        yield val.run_all(config.PILOT_LAT, config.PILOT_LON, figures=False), copia, pdir
    except FileNotFoundError as e:
        pytest.skip(f"dati grezzi assenti: {e}")
    finally:
        mp.undo()


@pytest.mark.slow
def test_run_all_offline_produce_il_riepilogo_con_le_chiavi_attese(riepilogo):
    s, _, _ = riepilogo
    assert CHIAVI_RIEPILOGO <= set(s)
    assert s["punto"] == {"lat": config.PILOT_LAT, "lon": config.PILOT_LON}
    assert s["metodo"]["pioggia_power_uguale_default_fino_2022"] is True
    assert s["metodo"]["scenario_rappresentativo"] == "tetto_irriguo"
    assert len(s["smap"]["confronti"]) == 12
    assert len(s["ndvi"]["confronti"]) == 4 and s["ndvi"]["n_anni"] == 22
    assert {c["coltura"] for c in s["istat"]["confronti"]} == {"mais", "soia", "frumento"}
    assert len(s["robustezza_mais"]["confronti"]) == 9
    assert len(s["non_validato"]) >= 3


@pytest.mark.slow
def test_run_all_correlazioni_nel_dominio_e_intervalli_ordinati(riepilogo):
    s, _, _ = riepilogo
    for c in s["smap"]["confronti"]:
        a = c["anomalie"]
        assert -1 <= a["pearson"] <= 1
        assert a["pearson_ic95"][0] <= a["pearson"] <= a["pearson_ic95"][1]
    for c in s["istat"]["confronti"]:
        d = c["detrend"]
        assert d["n"] == 17
        assert d["pearson_ic95"][0] <= d["pearson"] <= d["pearson_ic95"][1]


@pytest.mark.slow
def test_run_all_scrive_i_file_solo_nella_copia(riepilogo):
    import json
    s, copia, pdir = riepilogo
    nuovo = copia / pdir.name / "validation_summary.json"
    assert nuovo.exists()
    for nome in ("validation_smap_mensile.csv", "validation_ndvi_annuale.csv", "validation_istat.csv"):
        assert (copia / pdir.name / nome).exists()
    # il riepilogo scritto e' quello restituito (stesse chiavi di primo livello) ed e' JSON valido
    scritto = json.loads(nuovo.read_text(encoding="utf-8"))
    assert set(scritto) == set(s)
    assert scritto["istat"]["scenario_rappresentativo"] == "tetto_irriguo"
