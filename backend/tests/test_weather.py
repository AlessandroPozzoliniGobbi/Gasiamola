"""Test di ``fieldwise.weather`` (tabella meteo del motore, letta solo dalla cache).

I test sui dati reali del punto pilota sono saltati se la cache manca. Nessuna rete:
si lavora sempre con FIELDWISE_OFFLINE=1.
"""
import numpy as np
import pandas as pd
import pytest

from fieldwise import config, weather
from fieldwise.data import cache

PILOT = (45.2, 10.0)
ENGINE = ["date", "tmax", "tmin", "tmean", "rain", "srad", "rh", "wind", "et0"]
RELIABLE_YEARS = list(range(2000, 2023))      # data/CHECKS.md, D1: POWER affidabile 2000-2022


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")


def _pilot_file(name):
    return config.PROCESSED_DIR / cache.point_key(*PILOT) / name


@pytest.fixture(scope="module")
def forcing():
    """Tabella del punto pilota; salta se la cache e' incompleta."""
    import os
    old = os.environ.get("FIELDWISE_OFFLINE")
    os.environ["FIELDWISE_OFFLINE"] = "1"
    try:
        return weather.load_forcing(*PILOT)
    except cache.CacheMiss as e:
        pytest.skip(f"cache del punto pilota assente: {e}")
    finally:
        if old is None:
            os.environ.pop("FIELDWISE_OFFLINE", None)
        else:
            os.environ["FIELDWISE_OFFLINE"] = old


# =============================================================================
# Dati reali del punto pilota
# =============================================================================

class TestTabellaPilota:
    def test_colonne_motore_e_provenienza(self, forcing):
        assert list(forcing.columns[:len(ENGINE)]) == ENGINE
        for c in ("rain_source", "rain_trusted", "temp_source", "temp_trusted"):
            assert c in forcing.columns

    def test_una_riga_per_giorno(self, forcing):
        expected = pd.date_range("2000-01-01", "2025-12-31", freq="D")
        assert len(forcing) == len(expected) == 9497
        d = pd.to_datetime(forcing["date"])
        assert d.is_unique and d.is_monotonic_increasing
        assert d.iloc[0] == pd.Timestamp("2000-01-01") and d.iloc[-1] == pd.Timestamp("2025-12-31")
        assert (d.values == expected.values).all()

    def test_nessun_nan_nelle_colonne_del_motore(self, forcing):
        assert not forcing[ENGINE].isna().any().any()
        assert np.isfinite(forcing[ENGINE[1:]].to_numpy(dtype=float)).all()

    def test_vincoli_fisici(self, forcing):
        assert (forcing["tmin"] <= forcing["tmax"]).all()
        assert (forcing["tmin"] <= forcing["tmean"] + 1e-9).all()
        assert (forcing["tmean"] <= forcing["tmax"] + 1e-9).all()
        assert (forcing["rain"] >= 0).all()
        assert (forcing["et0"] >= 0).all()
        assert (forcing["srad"] >= 0).all()
        assert ((forcing["rh"] >= 0) & (forcing["rh"] <= 100)).all()
        assert (forcing["wind"] >= 0).all()

    def test_et0_plausibile(self, forcing):
        # clima della Pianura Padana: ET0 media annua circa 800-1100 mm
        annual = forcing.groupby(pd.to_datetime(forcing["date"]).dt.year)["et0"].sum()
        assert annual.between(600, 1400).all()

    def test_available_years_esatti(self, forcing):
        yrs = weather.available_years(forcing)
        assert yrs == RELIABLE_YEARS
        assert len(yrs) == 23

    def test_provenienza_distingue_gli_anni_affidabili(self, forcing):
        year = pd.to_datetime(forcing["date"]).dt.year
        trusted = forcing["rain_trusted"].astype(bool)
        assert trusted[year <= 2022].all()
        assert not trusted[year > 2022].any()
        assert set(forcing["rain_source"].unique()) == {"power"}
        assert set(forcing["temp_source"].unique()) == {"power"}
        assert forcing["temp_trusted"].astype(bool).all()

    def test_available_years_segue_la_provenienza(self, forcing):
        # un solo giorno non affidabile in un anno lo esclude dall'ensemble
        f = forcing.copy()
        f.loc[pd.to_datetime(f["date"]) == "2010-06-15", "rain_trusted"] = False
        assert 2010 not in weather.available_years(f)
        # un NaN nelle colonne del motore lo esclude
        f = forcing.copy()
        f.loc[pd.to_datetime(f["date"]) == "2011-03-01", "et0"] = np.nan
        assert 2011 not in weather.available_years(f)
        # un giorno mancante (anno incompleto) lo esclude
        f = forcing[pd.to_datetime(forcing["date"]) != "2012-07-01"]
        assert 2012 not in weather.available_years(f)

    def test_fonti_alternative_coerenti(self, forcing):
        f = weather.load_forcing(*PILOT, rain_source="power")
        assert f["rain_trusted"].astype(bool).all()
        # stessa pioggia di default: cambia solo l'affidabilita' dichiarata
        np.testing.assert_allclose(f["rain"].to_numpy(), forcing["rain"].to_numpy())
        assert len(weather.available_years(f)) == 26

    def test_pioggia_non_in_cache_imerg(self):
        if _pilot_file("imerg_daily.csv").exists():
            pytest.skip("IMERG presente in cache: il caso CacheMiss non e' verificabile")
        if not _pilot_file("power_daily.csv").exists():
            pytest.skip("cache del punto pilota assente")
        with pytest.raises(cache.CacheMiss):
            weather.load_forcing(*PILOT, rain_source="imerg")

    def test_fonte_inesistente_errore_chiaro(self, forcing):
        with pytest.raises(ValueError, match="rain_source"):
            weather.load_forcing(*PILOT, rain_source="pioggia_magica")
        with pytest.raises(ValueError, match="temp_source"):
            weather.load_forcing(*PILOT, temp_source="stazione_inesistente")


# =============================================================================
# Cartelle vuote: nessun dato in cache
# =============================================================================

def test_cache_vuota_solleva_cachemiss(tmp_path, monkeypatch):
    raw, proc = tmp_path / "raw", tmp_path / "processed"
    raw.mkdir()
    proc.mkdir()
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "PROCESSED_DIR", proc)
    with pytest.raises(cache.CacheMiss):
        weather.load_forcing(*PILOT)
    with pytest.raises(cache.CacheMiss):
        weather.load_forcing(*PILOT, rain_source="imerg")
    # nessun dato scaricato o inventato: nessun file creato
    assert not list(proc.rglob("*.csv"))


def test_cache_vuota_altro_punto(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    with pytest.raises(cache.CacheMiss):
        weather.load_forcing(40.0, 15.0)
