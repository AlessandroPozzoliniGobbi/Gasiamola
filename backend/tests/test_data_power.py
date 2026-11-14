"""Test del client NASA POWER, senza rete e senza toccare la cache vera."""
import json

import numpy as np
import pytest

from fieldwise import config
from fieldwise.data import cache, power

LAT, LON = 45.2, 10.0


def _fake_payload():
    days = ["20240101", "20240102", "20240103"]
    vals = {
        "T2M_MAX": [8.0, 9.0, -999.0],
        "T2M_MIN": [2.0, 3.0, 4.0],
        "T2M": [5.0, 6.0, 7.0],
        "PRECTOTCORR": [0.0, 12.5, -999.0],
        "ALLSKY_SFC_SW_DWN": [3.1, 2.2, 1.0],
        "RH2M": [80.0, 85.0, 90.0],
        "WS2M": [1.5, 2.5, 3.5],
    }
    units = {"T2M_MAX": "C", "T2M_MIN": "C", "T2M": "C", "PRECTOTCORR": "mm/day",
             "ALLSKY_SFC_SW_DWN": "MJ/m^2/day", "RH2M": "%", "WS2M": "m/s"}
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [10.0, 45.2, 170.78]},
        "properties": {"parameter": {k: dict(zip(days, v)) for k, v in vals.items()}},
        "header": {"title": "fake", "api": {"version": "v9.9", "name": "POWER Daily API"},
                   "sources": ["MERRA2", "SYN1DEG", "POWER"], "fill_value": -999.0,
                   "time_standard": "LST", "start": "20240101", "end": "20240103"},
        "messages": [],
        "parameters": {k: {"units": u, "longname": k} for k, u in units.items()},
    }


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.delenv("FIELDWISE_OFFLINE", raising=False)
    return tmp_path


@pytest.fixture
def fake_net(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append((url, params))
        return _Resp(_fake_payload())

    monkeypatch.setattr(power.requests, "get", fake_get)
    return calls


def test_fetch_writes_raw_meta_and_processed(tmp_cache, fake_net):
    path = power.fetch(LAT, LON, "20240101", "20240103")
    assert cache.is_cached(path)
    assert str(path).startswith(str(tmp_cache))
    meta = cache.read_meta(path)
    assert meta["product"] == "POWER daily point AG"
    assert "v9.9" in meta["version"] and "MERRA2" in meta["version"]
    assert "SYN1DEG" in meta["notes"] and "fill_value" in meta["notes"]
    assert meta["params"]["community"] == "AG"
    assert fake_net[0][1]["community"] == "AG"

    df = power.load(LAT, LON)
    assert list(df.columns) == ["date", "tmax", "tmin", "tmean", "rain", "srad", "rh", "wind"]
    assert len(df) == 3
    assert str(df["date"].dtype).startswith("datetime64")
    assert df["tmax"].isna().tolist() == [False, False, True]  # -999 -> NaN
    assert np.isnan(df["rain"].iloc[2]) and df["rain"].iloc[1] == 12.5
    assert df["tmin"].iloc[2] == 4.0  # nessun riempimento/interpolazione

    site = power.load_site(LAT, LON)
    assert site["lat_requested"] == LAT and site["lon_requested"] == LON
    assert site["elevation_m"] == 170.78 and site["fill_value"] == -999.0
    assert site["units"]["srad"] == "MJ/m^2/day" and site["units"]["rain"] == "mm/day"


def test_second_fetch_uses_cache(tmp_cache, fake_net):
    power.fetch(LAT, LON, "20240101", "20240103")
    power.fetch(LAT, LON, "20240101", "20240103")
    assert len(fake_net) == 1
    power.fetch(LAT, LON, "20240101", "20240103", force=True)
    assert len(fake_net) == 2


def test_offline_raises(tmp_cache, fake_net, monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    with pytest.raises(cache.OfflineError):
        power.fetch(LAT, LON, "20240101", "20240103")
    assert fake_net == []


def test_load_without_cache_raises(tmp_cache):
    with pytest.raises(cache.CacheMiss):
        power.load(LAT, LON)
    with pytest.raises(cache.CacheMiss):
        power.load_site(LAT, LON)


def test_retries_then_succeeds(tmp_cache, monkeypatch):
    monkeypatch.setattr(power.time, "sleep", lambda s: None)
    n = {"c": 0}

    def flaky(url, params=None, timeout=None):
        n["c"] += 1
        if n["c"] < 3:
            raise power.requests.ConnectionError("giu'")
        return _Resp(_fake_payload())

    monkeypatch.setattr(power.requests, "get", flaky)
    power.fetch(LAT, LON, "20240101", "20240103")
    assert n["c"] == 3
    assert json.loads((cache.processed_dir(LAT, LON) / "power_site.json").read_text())["lat_returned"] == 45.2
