"""Test di ``fieldwise.qc``: senza rete, con piccoli dati finti in cartelle temporanee."""
import json

import numpy as np
import pandas as pd
import pytest

from fieldwise import config, qc
from fieldwise.qc import ERR, NA, OK, WARN

LAT, LON = 45.2, 10.0
START, END = "2020-01-01", "2021-12-31"


# ---------------------------------------------------------------------------------------
# fixture e costruttori di dati finti
# ---------------------------------------------------------------------------------------
@pytest.fixture
def env(tmp_path, monkeypatch):
    """Cartelle di dati temporanee e periodo ridotto 2020-2021."""
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "data" / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "data" / "processed")
    monkeypatch.setattr(config, "START_YEAR", 2020)
    monkeypatch.setattr(config, "END_YEAR", 2021)
    pdir = config.PROCESSED_DIR / f"lat{LAT:.3f}_lon{LON:.3f}"
    pdir.mkdir(parents=True)
    (config.PROCESSED_DIR / "cremona").mkdir()
    return tmp_path, pdir


def make_power(start=START, end=END):
    d = pd.date_range(start, end, freq="D")
    doy = d.day_of_year.to_numpy()
    tmean = 12 + 10 * np.sin(2 * np.pi * (doy - 110) / 365)
    return pd.DataFrame({
        "date": d, "tmax": tmean + 5, "tmin": tmean - 5, "tmean": tmean,
        "rain": np.where(doy % 4 == 0, 6.0, 0.0),
        "srad": 4 + 12 * np.sin(np.pi * (doy - 1) / 365),
        "rh": 70.0, "wind": 1.5})


def make_arpa(power, factor=1.0, complete=True):
    """ARPA finto: pioggia = POWER / factor (cosi' POWER = ARPA * factor)."""
    f = factor if np.isscalar(factor) else pd.Series(factor).reindex(power["date"].dt.year).to_numpy()
    return pd.DataFrame({"date": power["date"], "rain_mm": power["rain"].to_numpy() / f,
                         "n_obs": 24, "n_expected": 24, "complete": complete,
                         "sensor_id": "1", "station": "finta"})


def by_name(checks, name, dataset=None):
    hits = [c for c in checks if c.name == name and (dataset is None or c.dataset == dataset)]
    assert len(hits) == 1, f"{name!r}: {len(hits)} risultati"
    return hits[0]


def power_checks(df, elev=170.78):
    return qc.check_power(df, LAT, elev, START, END)


# ---------------------------------------------------------------------------------------
# 1-4. POWER
# ---------------------------------------------------------------------------------------
def test_power_pulito_tutto_ok():
    checks = power_checks(make_power())
    assert len(checks) == len(qc.N_POWER) + 0
    assert {c.status for c in checks} == {OK}


def test_power_giorni_mancanti_errore_e_buco_piu_lungo():
    df = make_power()
    df = df.drop(index=[10, 11, 12, 200]).reset_index(drop=True)
    c = by_name(power_checks(df), "Completezza giornaliera")
    assert c.status == ERR
    assert "mancanti 4" in c.detail and "buco piu' lungo 3 giorni" in c.detail


def test_power_nan_attenzione():
    df = make_power()
    df.loc[[5, 6], "tmax"] = np.nan
    checks = power_checks(df)
    c = by_name(checks, "Valori mancanti")
    assert c.status == WARN and "tmax 2" in c.detail
    assert by_name(checks, "Completezza giornaliera").status == OK


def test_power_sentinella_errore():
    df = make_power()
    df.loc[3, "srad"] = -999.0
    c = by_name(power_checks(df), "Sentinelle")
    assert c.status == ERR and "srad 1" in c.detail


@pytest.mark.parametrize("col,val,name", [
    ("tmax", 55.0, "Intervallo tmax"),
    ("tmin", -41.0, "Intervallo tmin"),
    ("rain", 310.0, "Intervallo pioggia"),
    ("rain", -1.0, "Intervallo pioggia"),
    ("srad", 36.0, "Intervallo radiazione"),
    ("rh", 101.0, "Intervallo umidita'"),
    ("wind", 21.0, "Intervallo vento"),
])
def test_power_fuori_intervallo_errore(col, val, name):
    df = make_power()
    df.loc[100, col] = val
    # tenere coerenti le temperature: il test guarda solo il controllo dell'intervallo
    assert by_name(power_checks(df), name).status == ERR


def test_power_dentro_intervallo_ok_ai_limiti():
    df = make_power()
    df.loc[100, ["tmax", "tmean", "tmin"]] = [50.0, 45.0, 40.0]
    df.loc[101, "rh"] = 100.0
    df.loc[102, "wind"] = 20.0
    checks = power_checks(df)
    assert by_name(checks, "Intervallo tmax").status == OK
    assert by_name(checks, "Intervallo umidita'").status == OK
    assert by_name(checks, "Intervallo vento").status == OK


def test_power_pioggia_oltre_150_attenzione_con_cinque_giorni():
    df = make_power()
    for i, v in zip([10, 20, 30, 40, 50, 60], [260, 200, 180, 170, 160, 155]):
        df.loc[i, "rain"] = v
    c = by_name(power_checks(df), "Intervallo pioggia")
    assert c.status == WARN
    assert df.loc[10, "date"].strftime("%Y-%m-%d") + " 260.0" in c.detail
    assert df.loc[50, "date"].strftime("%Y-%m-%d") + " 160.0" in c.detail
    assert df.loc[60, "date"].strftime("%Y-%m-%d") not in c.detail  # solo i primi cinque


def test_power_radiazione_oltre_cielo_sereno_errore():
    df = make_power()
    df.loc[0, "srad"] = 20.0  # 1 gennaio a 45 N: Rso circa 7.6 MJ, ma ancora < 35
    c = by_name(power_checks(df), "Radiazione / cielo sereno")
    assert c.status == ERR
    assert by_name(power_checks(df), "Intervallo radiazione").status == OK


def test_power_senza_quota_rapporto_cielo_sereno_non_disponibile():
    c = by_name(power_checks(make_power(), elev=None), "Radiazione / cielo sereno")
    assert c.status == NA


def test_power_coerenza_temperature():
    df = make_power()
    assert by_name(power_checks(df), "Coerenza tmin <= tmean <= tmax").status == OK
    df.loc[7, "tmean"] = df.loc[7, "tmax"] + 0.04   # dentro tolleranza
    assert by_name(power_checks(df), "Coerenza tmin <= tmean <= tmax").status == OK
    df.loc[8, "tmean"] = df.loc[8, "tmax"] + 0.2    # fuori
    df.loc[9, "tmean"] = df.loc[9, "tmin"] - 0.2
    c = by_name(power_checks(df), "Coerenza tmin <= tmean <= tmax")
    assert c.status == ERR and c.detail.startswith("2 giorni")


def test_power_colonne_mancanti_non_solleva():
    checks = power_checks(make_power().drop(columns=["wind"]))
    assert {c.status for c in checks} == {NA}


# ---------------------------------------------------------------------------------------
# 5. pioggia annua POWER contro riferimento
# ---------------------------------------------------------------------------------------
def rain_table(factor_by_year, complete=True, years=("2020", "2021")):
    pw = make_power()
    ar = make_arpa(pw, factor={2020: factor_by_year[0], 2021: factor_by_year[1]}, complete=complete)
    rf = qc._ref_frame(ar, ar["complete"])
    return qc.rain_annual_table(pw, rf, "ARPA")


def test_pioggia_soglia_25_percento():
    tab, _ = rain_table((1.24, 1.26))
    r = tab.set_index("year")
    assert r.loc[2020, "esito"] == OK and r.loc[2020, "rel_diff"] == pytest.approx(0.24)
    assert r.loc[2021, "esito"] == WARN and r.loc[2021, "rel_diff"] == pytest.approx(0.26)
    # scarto negativo: stessa soglia in valore assoluto
    tab, _ = rain_table((0.70, 0.76))
    r = tab.set_index("year")
    assert r.loc[2020, "esito"] == WARN and r.loc[2021, "esito"] == OK


def test_pioggia_check_segnala_gli_anni_oltre_soglia():
    tab, st = rain_table((1.0, 1.4))
    checks = qc.check_rain_compare("POWER vs ARPA pioggia", "ARPA", tab, st)
    c = by_name(checks, "Pioggia annua")
    assert c.status == WARN and "2021 +40%" in c.detail and "2020" not in c.detail.split("anni oltre")[1]
    tab, st = rain_table((1.0, 1.1))
    assert by_name(qc.check_rain_compare("x", "ARPA", tab, st), "Pioggia annua").status == OK


def test_pioggia_regola_80_percento_di_giorni_completi():
    pw = make_power()
    # 2021: 365 giorni; 292 completi = 80.0% -> confrontabile; 291 -> non confrontabile
    for n_complete, expected in ((292, "confrontabile"), (291, "non confrontabile")):
        ar = make_arpa(pw, factor=1.5)  # scarto +50% in ogni anno
        mask = (ar["date"].dt.year == 2021).to_numpy()
        idx = np.flatnonzero(mask)
        ar.loc[idx[n_complete:], "complete"] = False
        ar.loc[idx[n_complete:], "rain_mm"] = 999.0   # non deve entrare nei totali comuni
        tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
        r = tab.set_index("year").loc[2021]
        assert r["ref_complete_pct"] == pytest.approx(100 * n_complete / 365)
        if expected == "confrontabile":
            assert r["esito"] == WARN  # +50%
            assert 2021 in st["comparable"]
        else:
            assert r["esito"] == "non confrontabile"
            assert 2021 not in st["comparable"]
        # totali ricalcolati solo sui giorni completi: l'ARPA da 999 mm/g non c'e'
        assert r["ref_common_mm"] < 999.0 * 5
        assert r["ref_total_mm"] > r["ref_common_mm"]
        assert r["n_common_days"] == n_complete


def test_pioggia_anno_non_confrontabile_non_genera_attenzione():
    pw = make_power()
    ar = make_arpa(pw, factor=3.0)
    ar.loc[ar["date"].dt.year == 2020, "complete"] = False   # 0% completi nel 2020
    tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
    assert tab.set_index("year").loc[2020, "esito"] == "non confrontabile"
    c = by_name(qc.check_rain_compare("x", "ARPA", tab, st), "Pioggia annua")
    assert "2020" in c.detail and "non confrontabili" in c.detail
    assert c.status == WARN and "2021 +200%" in c.detail  # il 2021 e' confrontabile e segnalato


def test_pioggia_nessun_anno_confrontabile_non_disponibile():
    pw = make_power()
    ar = make_arpa(pw, complete=False)
    tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
    checks = qc.check_rain_compare("x", "ARPA", tab, st)
    assert {c.status for c in checks} == {NA}


def test_pioggia_salto_di_regime():
    pw = make_power("2021-01-01", "2024-12-31")
    f = {2021: 1.0, 2022: 1.0, 2023: 1.5, 2024: 1.5}
    ar = make_arpa(pw, factor=f)
    tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
    assert st["ratio_early"] == pytest.approx(1.0) and st["ratio_late"] == pytest.approx(1.5)
    c = by_name(qc.check_rain_compare("x", "ARPA", tab, st), "Rapporto annuo nel tempo")
    assert c.status == WARN and "+50%" in c.detail
    ar = make_arpa(pw, factor=1.1)
    tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
    assert by_name(qc.check_rain_compare("x", "ARPA", tab, st), "Rapporto annuo nel tempo").status == OK


def test_pioggia_correlazione_mensile_e_giorni_piovosi():
    pw = make_power()
    pw["rain"] = np.where(pw["date"].dt.day % 3 == 0, 4.0, 0.0) * (1 + pw["date"].dt.month / 6)
    ar = make_arpa(pw, factor=1.0)
    tab, st = qc.rain_annual_table(pw, qc._ref_frame(ar, ar["complete"]), "ARPA")
    assert st["corr_monthly"] == pytest.approx(1.0) and st["n_months"] == 24
    assert (tab["wet_freq_power_pct"] == tab["wet_freq_ref_pct"]).all()
    checks = qc.check_rain_compare("x", "ARPA", tab, st)
    assert by_name(checks, "Correlazione dei totali mensili").status == OK
    assert by_name(checks, "Giorni piovosi (>= 1 mm)").status == OK


def test_pioggia_imerg_stesso_criterio():
    pw = make_power()
    im = pd.DataFrame({"date": pw["date"], "rain_mm": pw["rain"] / 1.5})
    im.loc[im["date"].dt.year == 2020, "rain_mm"] = np.nan   # 2020 senza IMERG
    rf = qc._ref_frame(im, pd.Series(True, index=im.index))
    tab, st = qc.rain_annual_table(pw, rf, "IMERG")
    r = tab.set_index("year")
    assert r.loc[2020, "esito"] == "non confrontabile" and r.loc[2021, "esito"] == WARN
    assert set(tab["reference"]) == {"IMERG"}


# ---------------------------------------------------------------------------------------
# 6. ET0
# ---------------------------------------------------------------------------------------
def test_et0_tabelle_e_rapporto():
    pw = make_power("2020-01-01", "2020-12-31")
    ann, mon, summ = qc.et0_tables(pw, LAT, 170.78)
    assert len(ann) == 1 and len(mon) == 12
    assert 400 < ann.loc[0, "et0_pm"] < 1500 and ann.loc[0, "ratio"] > 0
    assert -1 <= summ["corr"] <= 1


def test_et0_rapporto_fuori_intervallo_attenzione():
    ann = pd.DataFrame({"year": [2020, 2021], "n_days": [366, 365],
                        "et0_pm": [900.0, 900.0], "et0_hargreaves": [990.0, 1260.0]})
    ann["ratio"] = ann["et0_hargreaves"] / ann["et0_pm"]
    summ = {"pm_mean": 900.0, "hg_mean": 1125.0, "ratio_mean": 1.25, "corr": 0.97, "n_years": 2,
            "worst_month": "luglio", "worst_rel": 0.4, "worst_mm": 20.0}
    c = qc.check_et0(ann, summ)[0]
    assert c.status == WARN and "2021 1.40" in c.detail
    ann.loc[1, ["et0_hargreaves", "ratio"]] = [1170.0, 1.30]   # 1,30 e' dentro l'intervallo
    assert qc.check_et0(ann, summ)[0].status == OK
    ann.loc[0, ["et0_hargreaves", "ratio"]] = [750.0, 750 / 900]   # 0,833 < 0,85
    assert qc.check_et0(ann, summ)[0].status == WARN


# ---------------------------------------------------------------------------------------
# 7-8. temperature, completezza ARPA
# ---------------------------------------------------------------------------------------
def make_arpa_temp(power, d_tmax=0.0, d_tmin=0.0):
    """ARPA tale che POWER - ARPA = (d_tmax, d_tmin) in ogni giorno."""
    return pd.DataFrame({"date": power["date"], "tmax": power["tmax"] - d_tmax,
                         "tmin": power["tmin"] - d_tmin, "tmean": power["tmean"],
                         "n_obs": 24, "n_expected": 24, "complete": True,
                         "sensor_id": "1", "station": "finta"})


def test_temperature_soglia_estiva_di_1_grado():
    pw = make_power()
    for d, status in ((-0.9, OK), (-1.1, WARN), (1.3, WARN), (0.0, OK)):
        tab, s = qc.temp_tables(pw, make_arpa_temp(pw, d_tmax=d, d_tmin=0.4))
        assert s["d_tmax_jja"] == pytest.approx(d) and s["d_tmin"] == pytest.approx(0.4)
        assert by_name(qc.check_temp(tab, s), "Differenza tmax/tmin").status == status


def test_temperature_solo_giorni_arpa_completi_e_giorni_caldi():
    pw = make_power()
    pw.loc[[200, 201, 202], "tmax"] = 37.0
    at = make_arpa_temp(pw)
    at.loc[at.index[[201, 202]], "tmax"] = 34.0          # ARPA piu' fresca in due giorni
    at.loc[at.index[202], "complete"] = False            # ... ma uno e' incompleto
    at.loc[at.index[202], "tmax"] = 10.0                 # e il suo valore non deve contare
    tab, s = qc.temp_tables(pw, at)
    assert s["n"] == len(pw) - 1
    assert s["hot_power"] == 2 and s["hot_arpa"] == 1    # giorni 200 e 201 (POWER), solo 200 (ARPA)
    assert tab["n_days"].sum() == len(pw) - 1


def test_temperature_nessun_giorno_in_comune_non_disponibile():
    pw = make_power()
    at = make_arpa_temp(pw)
    at["complete"] = False
    tab, s = qc.temp_tables(pw, at)
    assert {c.status for c in qc.check_temp(tab, s)} == {NA}


def test_arpa_completezza_per_anno():
    pw = make_power()
    ar = make_arpa(pw)
    assert qc.check_arpa_completeness("ARPA pioggia", ar)[0].status == OK
    idx = np.flatnonzero((ar["date"].dt.year == 2020).to_numpy())
    ar.loc[idx[: int(0.15 * len(idx))], "complete"] = False   # 85% completi
    c = qc.check_arpa_completeness("ARPA pioggia", ar)[0]
    assert c.status == WARN and "2020 85%" in c.detail
    ar.loc[idx[: int(0.09 * len(idx))], "complete"] = False
    ar.loc[idx[int(0.09 * len(idx)):], "complete"] = True      # circa 91% completi
    assert qc.check_arpa_completeness("ARPA pioggia", ar)[0].status == OK


# ---------------------------------------------------------------------------------------
# 9. MODIS
# ---------------------------------------------------------------------------------------
def make_modis(years=(2020, 2021), ndvi=0.6, reliability=0):
    dates = [pd.Timestamp(f"{y}-01-01") + pd.Timedelta(days=16 * k) for y in years for k in range(23)]
    n = len(dates)
    return pd.DataFrame({"date": dates, "ndvi_center": ndvi, "reliability_center": reliability,
                         "vi_quality_center": 0, "ndvi_window_mean_good": ndvi,
                         "ndvi_window_median_good": ndvi, "n_good": 70, "n_pixels": 81}).head(n)


def test_modis_pulito():
    checks, tab = qc.check_modis(make_modis(), 2020, 2021)
    assert len(checks) == len(qc.N_MODIS)
    assert by_name(checks, "Date per anno").status == OK
    assert by_name(checks, "Intervallo NDVI").status == OK
    assert by_name(checks, "Date utilizzabili in estate").status == OK
    assert by_name(checks, "NDVI medio luglio-agosto").status == OK
    assert list(tab["n_dates"]) == [23, 23]


def test_modis_poche_date_attenzione_e_anno_assente():
    df = make_modis(years=(2020, 2021))
    df = df[~((df["date"].dt.year == 2021) & (df["date"].dt.day_of_year > 200))]   # ~13 date nel 2021
    c = by_name(qc.check_modis(df, 2020, 2021)[0], "Date per anno")
    assert c.status == WARN and "2021" in c.detail
    # anno assente nel periodo atteso
    c = by_name(qc.check_modis(make_modis(years=(2020,)), 2020, 2021)[0], "Date per anno")
    assert c.status == WARN and "2021 (0)" in c.detail


def test_modis_ndvi_fuori_intervallo_errore():
    df = make_modis()
    df.loc[3, "ndvi_center"] = 1.2
    assert by_name(qc.check_modis(df, 2020, 2021)[0], "Intervallo NDVI").status == ERR
    df = make_modis()
    df.loc[3, "ndvi_window_mean_good"] = -0.3
    assert by_name(qc.check_modis(df, 2020, 2021)[0], "Intervallo NDVI").status == ERR
    df = make_modis()
    df.loc[3, "ndvi_center"] = -0.2   # al limite: ok
    assert by_name(qc.check_modis(df, 2020, 2021)[0], "Intervallo NDVI").status == OK


def test_modis_estate_poco_utilizzabile_attenzione():
    df = make_modis()
    summer = df["date"].dt.month.isin([6, 7, 8]) & (df["date"].dt.year == 2020)
    df.loc[summer, "reliability_center"] = 3          # nuvole
    c = by_name(qc.check_modis(df, 2020, 2021)[0], "Date utilizzabili in estate")
    assert c.status == WARN and "2020 0%" in c.detail
    # marginale (1) conta come utilizzabile
    df.loc[summer, "reliability_center"] = 1
    assert by_name(qc.check_modis(df, 2020, 2021)[0], "Date utilizzabili in estate").status == OK


def test_modis_percentuali_pixel_centrale_e_finestra():
    df = make_modis()
    df.loc[df.index[:23], "reliability_center"] = 2
    df.loc[df.index[:23], "n_good"] = 10     # 10/81 < meta'
    checks, _ = qc.check_modis(df, 2020, 2021)
    assert "50.0%" in by_name(checks, "Pixel centrale buono/marginale").detail
    assert "50.0%" in by_name(checks, "Finestra con almeno meta' pixel buoni").detail


# ---------------------------------------------------------------------------------------
# 10. SoilGrids
# ---------------------------------------------------------------------------------------
def make_soil(sand=33.0, clay=26.0, silt=41.0, bdod=1.45, om=2.5):
    rows = []
    for layer in ("0-30cm", "30-100cm"):
        for prop, v in (("sand", sand), ("clay", clay), ("silt", silt), ("bdod", bdod), ("om", om)):
            rows.append({"property": prop, "layer": layer, "top_cm": 0, "bottom_cm": 30, "mean": v,
                         "q05": v * 0.3, "q95": v * 2.0, "unit": "x"})
    return pd.DataFrame(rows)


def test_soilgrids_ok():
    checks = qc.check_soil(make_soil())
    assert {c.status for c in checks} == {OK}


def test_soilgrids_somma_granulometria():
    assert by_name(qc.check_soil(make_soil(sand=30.0)), "Sabbia + argilla + limo").status == ERR   # 97
    assert by_name(qc.check_soil(make_soil(sand=34.5)), "Sabbia + argilla + limo").status == OK    # 101.5


def test_soilgrids_densita_apparente():
    assert by_name(qc.check_soil(make_soil(bdod=1.9)), "Densita' apparente").status == ERR
    assert by_name(qc.check_soil(make_soil(bdod=0.9)), "Densita' apparente").status == ERR


def test_soilgrids_sostanza_organica_attenzione_con_intervallo():
    c = by_name(qc.check_soil(make_soil(om=3.6)), "Sostanza organica 0-30 cm")
    assert c.status == WARN
    assert "3.60%" in c.detail and "1.08-7.20%" in c.detail     # q05-q95
    assert by_name(qc.check_soil(make_soil(om=3.0)), "Sostanza organica 0-30 cm").status == OK


# ---------------------------------------------------------------------------------------
# 11. ISTAT
# ---------------------------------------------------------------------------------------
def make_istat(years=range(2015, 2023), over=None):
    rows = []
    base = {"mais": 11.0, "soia": 3.8, "frumento": 6.0}
    for crop, v in base.items():
        for i, y in enumerate(years):
            rows.append({"year": y, "crop": crop, "yield_t_ha": v + 0.1 * (i % 2)})
    df = pd.DataFrame(rows)
    for (crop, y), v in (over or {}).items():
        df.loc[(df["crop"] == crop) & (df["year"] == y), "yield_t_ha"] = v
    return df


def test_istat_ok():
    checks = qc.check_istat(make_istat(), last_weather_year=2025)
    assert {c.status for c in checks} == {OK}
    assert "mais 2015-2022 (8 anni)" in by_name(checks, "Anni presenti per coltura").detail


@pytest.mark.parametrize("crop,val", [("mais", 17.0), ("mais", 4.5), ("soia", 6.5), ("soia", 1.0),
                                      ("frumento", 9.5), ("frumento", 2.9)])
def test_istat_rese_fuori_intervallo_errore(crop, val):
    c = by_name(qc.check_istat(make_istat(over={(crop, 2018): val}), 2025), "Rese in intervalli plausibili")
    assert c.status == ERR and crop in c.detail and "2018" in c.detail


def test_istat_anni_oltre_ultimo_anno_di_meteo():
    c = by_name(qc.check_istat(make_istat(years=range(2020, 2027)), 2025),
                "Anni successivi all'ultimo anno di meteo")
    assert c.status == WARN and "2026" in c.detail and "2025" in c.detail
    assert by_name(qc.check_istat(make_istat(), 2025), "Anni successivi all'ultimo anno di meteo").status == OK


def test_istat_salti_oltre_30_percento():
    df = make_istat(over={("mais", 2018): 15.0})    # da ~11 a 15: +36%, poi ritorno: -27%
    c = by_name(qc.check_istat(df, 2025), "Salti annui > 30%")
    assert c.status == WARN and "mais 2018" in c.detail
    # 25% non basta
    df = make_istat(over={("mais", 2018): 13.5})
    assert by_name(qc.check_istat(df, 2025), "Salti annui > 30%").status == OK
    # anni non consecutivi: nessun salto
    df = make_istat().query("not (crop == 'mais' and year == 2017)")
    df.loc[(df["crop"] == "mais") & (df["year"] == 2018), "yield_t_ha"] = 15.0
    c = by_name(qc.check_istat(df, 2025), "Salti annui > 30%")
    assert "mais 2018" not in c.detail


def test_istat_coltura_assente_attenzione():
    df = make_istat().query("crop != 'soia'")
    c = by_name(qc.check_istat(df, 2025), "Anni presenti per coltura")
    assert c.status == WARN and "soia" in c.detail


# ---------------------------------------------------------------------------------------
# 12. IMERG, SMAP
# ---------------------------------------------------------------------------------------
def test_imerg_controlli():
    d = pd.date_range("2020-01-01", "2021-12-31", freq="D")
    df = pd.DataFrame({"date": d, "rain_mm": 2.0})
    checks = qc.check_imerg(df, "2021-12-31")
    assert {c.status for c in checks} == {OK}
    bad = df.copy()
    bad.loc[5, "rain_mm"] = 450.0
    assert by_name(qc.check_imerg(bad, "2021-12-31"), "Intervallo valori").status == ERR
    gap = df.drop(index=[10, 11])
    assert by_name(qc.check_imerg(gap, "2021-12-31"), "Completezza giornaliera").status == WARN
    nan = df.copy()
    nan.loc[3, "rain_mm"] = np.nan
    assert by_name(qc.check_imerg(nan, "2021-12-31"), "Completezza giornaliera").status == WARN
    short = df[df["date"] <= "2021-09-30"]
    c = by_name(qc.check_imerg(short, "2021-12-31"), "Ultimo giorno disponibile")
    assert c.status == WARN and "2021-09-30" in c.detail


def test_smap_controlli():
    d = pd.date_range("2020-01-01", periods=10, freq="D")
    df = pd.DataFrame({"date": d, "sm_am": 0.25, "qual_am": 0, "sm_pm": 0.3, "qual_pm": 8})
    df.loc[:4, ["qual_am", "qual_pm"]] = 1            # 5 giorni senza qualita' raccomandata
    checks = qc.check_smap(df)
    c = by_name(checks, "Giorni con passaggio di qualita' raccomandata")
    assert "5 giorni su 10 (50.0%)" in c.detail
    assert by_name(checks, "Intervallo valori").status == OK
    df.loc[7, "sm_am"] = 0.7
    assert by_name(qc.check_smap(df), "Intervallo valori").status == ERR
    df.loc[7, "sm_am"] = 0.01
    assert by_name(qc.check_smap(df), "Intervallo valori").status == ERR
    # un valore fuori intervallo ma con flag non raccomandato non conta
    df.loc[7, ["sm_am", "qual_am"]] = [0.9, 1]
    assert by_name(qc.check_smap(df), "Intervallo valori").status == OK


# ---------------------------------------------------------------------------------------
# esecuzione completa: dataset assenti, uscite, sezione Decisioni, codice di uscita
# ---------------------------------------------------------------------------------------
def write_fake_cache(pdir, with_arpa=True, with_soil=True, with_istat=True, with_temp=False):
    pw = make_power()
    pw.to_csv(pdir / "power_daily.csv", index=False)
    (pdir / "power_site.json").write_text(json.dumps({"elevation_m": 170.78}))
    if with_arpa:
        make_arpa(pw, factor={2020: 1.0, 2021: 1.4}).to_csv(pdir / "arpa_rain_daily.csv", index=False)
    if with_temp:
        make_arpa_temp(pw, d_tmax=-0.5).to_csv(pdir / "arpa_temp_daily.csv", index=False)
    if with_soil:
        make_soil().to_csv(pdir / "soilgrids_agg.csv", index=False)
    if with_istat:
        make_istat(years=range(2020, 2027)).to_csv(
            config.PROCESSED_DIR / "cremona" / "istat_yields.csv", index=False)
    return pw


def test_tutto_assente_non_disponibile_senza_errori(env, capsys):
    tmp, pdir = env
    rep = qc.run_checks(LAT, LON)
    assert rep.checks and {c.status for c in rep.checks} == {NA}
    datasets = {c.dataset for c in rep.checks}
    assert {"POWER", "ARPA pioggia", "ARPA temperature", "MODIS NDVI", "SoilGrids", "ISTAT", "IMERG",
            "SMAP", "POWER vs ARPA pioggia", "POWER vs IMERG", "POWER ET0",
            "POWER vs ARPA temperature"} <= datasets
    assert all(c.detail for c in rep.checks)
    # ogni dataset ha la riga di disponibilita' con il motivo
    avail = [c for c in rep.checks if c.name == "Disponibilita'"]
    assert all("assente" in c.detail for c in avail)
    assert qc.main(["--lat", str(LAT), "--lon", str(LON)]) == 0
    assert (config.DATA_DIR / "CHECKS.md").exists()


def test_dataset_assente_salta_i_controlli_dipendenti(env):
    tmp, pdir = env
    write_fake_cache(pdir, with_arpa=False)
    rep = qc.run_checks(LAT, LON)
    by = lambda ds, n: by_name(rep.checks, n, ds)
    assert by("ARPA pioggia", "Disponibilita'").status == NA
    for n in qc.N_RAIN_CMP:
        c = by("POWER vs ARPA pioggia", n)
        assert c.status == NA and "saltato" in c.detail and "arpa" in c.detail.lower()
    assert by("POWER", "Completezza giornaliera").status == OK            # il resto prosegue
    assert by("SoilGrids", "Densita' apparente").status == OK
    assert by("POWER ET0", "Penman-Monteith vs Hargreaves").status in (OK, WARN)
    assert by("MODIS NDVI", "Date per anno").status == NA
    assert by("POWER vs ARPA temperature", "Differenza tmax/tmin").status == NA
    assert rep.tables["rain"].empty


def test_run_completa_scrive_le_uscite(env):
    tmp, pdir = env
    write_fake_cache(pdir, with_temp=True)
    rc = qc.main(["--lat", str(LAT), "--lon", str(LON)])
    assert rc == 0
    summary = json.loads((pdir / "qc_summary.json").read_text())
    assert summary["counts"][ERR] == 0 and summary["checks"]
    assert {"dataset", "name", "status", "detail"} == set(summary["checks"][0])
    rain = pd.read_csv(pdir / "qc_rain_annual.csv")
    assert list(rain.columns) == qc.RAIN_COLS and sorted(rain["year"]) == [2020, 2021]
    r = rain.set_index("year")
    assert r.loc[2020, "esito"] == OK and r.loc[2021, "esito"] == WARN     # +0% e +40%
    md = (config.DATA_DIR / "CHECKS.md").read_text()
    assert md.count(qc.MARK_START) == 1 and md.count(qc.MARK_END) == 1
    assert md.index(qc.MARK_START) < md.index(qc.MARK_END) < md.index("## Decisioni")
    assert "| Dataset | Controllo | Esito | Dettaglio |" in md
    assert md.rstrip().endswith("Da compilare")


def test_codice_di_uscita_1_con_un_errore(env, capsys):
    tmp, pdir = env
    pw = write_fake_cache(pdir)
    pw2 = pw.copy()
    pw2.loc[4, "tmax"] = -999.0
    pw2.to_csv(pdir / "power_daily.csv", index=False)
    assert qc.main(["--lat", str(LAT), "--lon", str(LON)]) == 1
    summary = json.loads((pdir / "qc_summary.json").read_text())
    assert summary["counts"][ERR] >= 1
    assert "[ERRORE]" in capsys.readouterr().out


def test_sezione_decisioni_scritta_a_mano_sopravvive(env):
    tmp, pdir = env
    write_fake_cache(pdir)
    path = config.DATA_DIR / "CHECKS.md"
    qc.main(["--lat", str(LAT), "--lon", str(LON)])
    first = path.read_text()
    assert first.count("## Decisioni") == 1 and "Da compilare" in first

    hand = ("## Decisioni\n\n- D-QC1: la pioggia ARPA e' il riferimento.\n- Escludere 2026 dalla "
            "validazione ISTAT.\n\n### Sotto-sezione\n\nTesto libero | con pipe.\n")
    text = first.replace("## Decisioni\n\nDa compilare\n", hand)
    text = text.replace(qc.MARK_START, "Nota scritta a mano prima del blocco.\n\n" + qc.MARK_START, 1)
    path.write_text(text)

    # i dati cambiano: la parte automatica deve cambiare, il resto no
    make_soil(om=4.0).to_csv(pdir / "soilgrids_agg.csv", index=False)
    qc.main(["--lat", str(LAT), "--lon", str(LON)])
    second = path.read_text()
    assert hand in second
    assert second.count("## Decisioni") == 1 and "Da compilare" not in second
    assert "Nota scritta a mano prima del blocco." in second
    assert second.count(qc.MARK_START) == 1 and second.count(qc.MARK_END) == 1
    assert "media 4.00%" in second and "media 2.50%" not in second
    # una terza esecuzione senza cambiamenti di dati lascia identico tutto cio' che sta fuori dai marcatori
    qc.main(["--lat", str(LAT), "--lon", str(LON)])
    third = path.read_text()
    assert third.split(qc.MARK_END, 1)[1] == second.split(qc.MARK_END, 1)[1]
    assert third.split(qc.MARK_START, 1)[0] == second.split(qc.MARK_START, 1)[0]


def test_decisioni_creata_solo_se_manca(env):
    tmp, pdir = env
    write_fake_cache(pdir)
    path = config.DATA_DIR / "CHECKS.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    # file esistente con marcatori ma senza sezione Decisioni: viene aggiunta in fondo
    path.write_text(f"# Titolo\n\nIntro mia.\n\n{qc.MARK_START}\nvecchio\n{qc.MARK_END}\n\nCoda mia.\n")
    qc.main(["--lat", str(LAT), "--lon", str(LON)])
    t = path.read_text()
    assert "vecchio" not in t and "Intro mia." in t and "Coda mia." in t
    assert t.rstrip().endswith("## Decisioni\n\nDa compilare")
    # file esistente senza marcatori: blocco inserito, testo mantenuto
    path.write_text("# Titolo\n\nSolo testo mio.\n\n## Decisioni\n\nScelta X.\n")
    qc.main(["--lat", str(LAT), "--lon", str(LON)])
    t = path.read_text()
    assert t.startswith("# Titolo") and "Solo testo mio." in t and "Scelta X." in t
    assert t.count("## Decisioni") == 1 and "Da compilare" not in t and qc.MARK_START in t


def test_md_table_escape_e_nan():
    df = pd.DataFrame({"a": [1.5, np.nan], "b": ["x|y", "z"]})
    out = qc.md_table(df, formats={"a": ".2f"})
    assert "1.50" in out and "x/y" in out and "| - |" in out
