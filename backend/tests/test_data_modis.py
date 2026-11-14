"""Test del client MODIS: nessuna rete (requests.get sostituito), cartelle temporanee."""
from __future__ import annotations

import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest
import requests

from fieldwise import config
from fieldwise.data import cache, modis

LAT, LON = 45.2, 10.0
N = 3                      # griglia finta 3x3: centro = (riga 1, colonna 1) = pixel 4
N_DATES = 25               # -> blocchi da 10, 10, 5


def _dates():
    out = []
    d0 = dt.date(2021, 1, 1)
    for i in range(N_DATES):
        d = d0 + dt.timedelta(days=16 * i)
        out.append({"modis_date": f"A{d.year}{d.timetuple().tm_yday:03d}",
                    "calendar_date": d.isoformat()})
    return out


DATES = _dates()


def pixel_values(date_idx):
    """(ndvi grezzo, affidabilita', vi_quality) dei 9 pixel di una data.

    Data 0: tutti buoni tranne: pixel 0 fill, pixel 1 neve (2), pixel 2 nuvole (3),
    pixel 3 marginale (1), pixel 4 (centro) = 6000 buono, pixel 5 senza dato (-1).
    Le altre date: tutti 5000 e affidabilita' 0.
    """
    if date_idx != 0:
        return [5000] * 9, [0] * 9, [2116] * 9
    ndvi = [-3000, 9000, 9000, 4000, 6000, 8000, 7000, 8000, 7000]
    rel = [0, 2, 3, 1, 0, -1, 0, 0, 0]
    return ndvi, rel, [2116] * 9


class FakeService:
    def __init__(self, fail_from_block=None):
        self.calls = []
        self.fail_from_block = fail_from_block   # indice di blocco da cui simulare errori

    def __call__(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        path = url.replace(modis.BASE_URL, "")
        if path == "products":
            return _Resp({"products": [
                {"product": "MOD09A1", "description": "altro", "frequency": "8-Day",
                 "resolution_meters": 500},
                {"product": "MOD13Q1", "description": "MODIS/Terra Vegetation Indices 16-Day",
                 "frequency": "16-Day", "resolution_meters": 250}]})
        if path == "MOD13Q1/bands":
            return _Resp({"bands": [
                {"band": "250m_16_days_NDVI", "fill_value": "-3000", "scale_factor": "0.0001"},
                {"band": "250m_16_days_pixel_reliability", "fill_value": "-1"},
                {"band": "250m_16_days_VI_Quality", "fill_value": "-1"},
                {"band": "250m_16_days_EVI", "fill_value": "-3000"}]})
        if path == "MOD13Q1/dates":
            return _Resp({"dates": DATES})
        assert path == "MOD13Q1/subset"
        assert params["kmAboveBelow"] == 1 and params["kmLeftRight"] == 1
        sel = [d for d in DATES if params["startDate"] <= d["modis_date"] <= params["endDate"]]
        assert 0 < len(sel) <= 10
        if self.fail_from_block is not None and DATES.index(sel[0]) >= self.fail_from_block * 10:
            raise requests.ConnectionError("rete assente")
        k = {"250m_16_days_NDVI": 0, "250m_16_days_pixel_reliability": 1,
             "250m_16_days_VI_Quality": 2}[params["band"]]
        return _Resp({
            "nrows": N, "ncols": N, "band": params["band"],
            "scale": "0.0001" if k == 0 else "Not Available",
            "subset": [{"modis_date": d["modis_date"], "calendar_date": d["calendar_date"],
                        "band": params["band"], "tile": "h18v04",
                        "data": pixel_values(DATES.index(d))[k]} for d in sel]})

    def subset_calls(self):
        return [c for c in self.calls if c[0].endswith("/subset")]


class _Resp:
    def __init__(self, obj):
        self._obj = obj

    def raise_for_status(self):
        pass

    def json(self):
        return self._obj


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.delenv("FIELDWISE_OFFLINE", raising=False)
    monkeypatch.setattr(modis.time, "sleep", lambda s: None)
    return tmp_path


def run_fetch(monkeypatch, service=None, **kw):
    service = service or FakeService()
    monkeypatch.setattr(modis.requests, "get", service)
    path = modis.fetch(LAT, LON, start="2021-01-01", end="2030-12-31", **kw)
    return path, service


def test_fetch_scale_fill_and_files(monkeypatch):
    path, svc = run_fetch(monkeypatch)
    assert path.name == "modis_ndvi.csv" and path.exists()
    # 3 blocchi x 3 bande
    assert len(svc.subset_calls()) == 9
    raw = cache.raw_dir("modis", LAT, LON)
    blocks = sorted(raw.glob("MOD13Q1_*[0-9].json"))
    assert len(blocks) == 3
    for b in blocks:
        meta = cache.read_meta(b)
        assert meta["product"] == "MOD13Q1" and meta["params"]["kmAboveBelow"] == 1
        assert "Vegetation Indices" in meta["version"]
    px = modis.load_pixels(LAT, LON)
    assert len(px) == N_DATES * 9
    assert list(px.columns) == ["date", "pixel", "row", "col", "ndvi", "reliability", "vi_quality"]
    d0 = px[px["date"] == pd.Timestamp(DATES[0]["calendar_date"])].set_index("pixel")
    assert d0.loc[4, "ndvi"] == pytest.approx(0.6)          # scala 0.0001
    assert np.isnan(d0.loc[0, "ndvi"])                       # fill -3000 -> NaN
    assert (d0.loc[4, "row"], d0.loc[4, "col"]) == (1, 1)
    assert d0.loc[5, "reliability"] == -1


def test_quality_filter_and_window_aggregation(monkeypatch):
    run_fetch(monkeypatch)
    s = modis.load(LAT, LON)
    assert len(s) == N_DATES
    assert list(s.columns) == ["date", "ndvi_center", "reliability_center", "vi_quality_center",
                               "ndvi_window_mean_good", "ndvi_window_median_good",
                               "n_good", "n_pixels"]
    r = s.iloc[0]
    # good = affidabilita' 0 o 1 e NDVI valido: pixel 3 (0.4, marginale), 4 (0.6),
    # 6 (0.7), 7 (0.8), 8 (0.7); esclusi 0 (fill), 1 (neve), 2 (nuvole), 5 (-1)
    assert r["n_good"] == 5 and r["n_pixels"] == 9
    assert r["ndvi_center"] == pytest.approx(0.6) and r["reliability_center"] == 0
    assert r["ndvi_window_mean_good"] == pytest.approx(np.mean([0.4, 0.6, 0.7, 0.8, 0.7]))
    assert r["ndvi_window_median_good"] == pytest.approx(0.7)
    assert r["vi_quality_center"] == 2116
    r1 = s.iloc[1]
    assert r1["n_good"] == 9 and r1["ndvi_window_mean_good"] == pytest.approx(0.5)


def test_no_good_pixels_gives_nan(monkeypatch):
    def all_bad(i):
        return [5000] * 9, [3] * 9, [2116] * 9
    monkeypatch.setitem(globals(), "pixel_values", all_bad)
    run_fetch(monkeypatch)
    s = modis.load(LAT, LON)
    assert (s["n_good"] == 0).all() and s["ndvi_window_mean_good"].isna().all()
    assert s["ndvi_center"].notna().all()


def test_resume_from_partial_cache(monkeypatch):
    # prima esecuzione: il terzo blocco (indice 2) fallisce -> RuntimeError dopo 3 tentativi
    svc1 = FakeService(fail_from_block=2)
    monkeypatch.setattr(modis.requests, "get", svc1)
    with pytest.raises(RuntimeError):
        modis.fetch(LAT, LON, start="2021-01-01", end="2030-12-31")
    raw = cache.raw_dir("modis", LAT, LON)
    assert len(list(raw.glob("MOD13Q1_*[0-9].json"))) == 2
    assert not (cache.processed_dir(LAT, LON) / "modis_ndvi.csv").exists()
    # seconda esecuzione: solo il blocco mancante (3 richieste, una per banda)
    _, svc2 = run_fetch(monkeypatch)
    assert len(svc2.subset_calls()) == 3
    first = svc2.subset_calls()[0][1]["startDate"]
    assert first == DATES[20]["modis_date"]
    assert len(modis.load(LAT, LON)) == N_DATES
    # terza esecuzione: nessuna richiesta di dati
    _, svc3 = run_fetch(monkeypatch)
    assert svc3.subset_calls() == []
    # force: riscarica tutto
    _, svc4 = run_fetch(monkeypatch, force=True)
    assert len(svc4.subset_calls()) == 9


def test_block_without_meta_is_redownloaded(monkeypatch):
    run_fetch(monkeypatch)
    raw = cache.raw_dir("modis", LAT, LON)
    victim = sorted(raw.glob("MOD13Q1_*[0-9].json"))[0]
    cache.meta_path(victim).unlink()
    _, svc = run_fetch(monkeypatch)
    assert len(svc.subset_calls()) == 3 and cache.is_cached(victim)


def test_retry_with_growing_wait(monkeypatch):
    waits = []
    monkeypatch.setattr(modis.time, "sleep", waits.append)
    n = {"k": 0}

    def flaky(url, params=None, headers=None, timeout=None):
        n["k"] += 1
        if n["k"] < 3:
            raise requests.Timeout("lento")
        return _Resp({"ok": True})

    monkeypatch.setattr(modis.requests, "get", flaky)
    assert modis._get_json("http://x") == {"ok": True}
    assert waits == [modis.BACKOFF_S, 2 * modis.BACKOFF_S]

    def always(url, params=None, headers=None, timeout=None):
        n["k"] += 1
        raise requests.ConnectionError("giu'")

    n["k"] = 0
    monkeypatch.setattr(modis.requests, "get", always)
    with pytest.raises(RuntimeError):
        modis._get_json("http://x")
    assert n["k"] == modis.RETRIES


def test_offline_error_no_network(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    called = []
    monkeypatch.setattr(modis.requests, "get", lambda *a, **k: called.append(1))
    with pytest.raises(cache.OfflineError):
        modis.fetch(LAT, LON)
    assert called == []


def test_load_cache_miss():
    with pytest.raises(cache.CacheMiss):
        modis.load(LAT, LON)
    with pytest.raises(cache.CacheMiss):
        modis.load_pixels(LAT, LON)


def test_load_works_offline_after_fetch(monkeypatch):
    run_fetch(monkeypatch)
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    monkeypatch.setattr(modis.requests, "get", lambda *a, **k: pytest.fail("rete usata"))
    assert len(modis.load(LAT, LON)) == N_DATES


def test_date_window_filter(monkeypatch):
    svc = FakeService()
    monkeypatch.setattr(modis.requests, "get", svc)
    modis.fetch(LAT, LON, start="2021-01-01", end=DATES[4]["calendar_date"])
    assert len(modis.load(LAT, LON)) == 5
    assert len(svc.subset_calls()) == 3          # un solo blocco x 3 bande
