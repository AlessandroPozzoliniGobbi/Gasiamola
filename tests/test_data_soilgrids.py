"""Test del client SoilGrids: nessuna rete, cartelle temporanee, risposte finte."""
from __future__ import annotations

import io
import json

import numpy as np
import pytest
import requests
from PIL import Image, TiffImagePlugin

from fieldwise import config
from fieldwise.data import cache, soilgrids as sg

LAT, LON = 45.2, 10.0

# valori "mappati" finti per profondita' (0-5, 5-15, 15-30, 30-60, 60-100, 100-200 cm)
SAND = [300, 320, 340, 400, 450, 500]       # g/kg
CLAY = [200, 210, 220, 230, 240, 250]       # g/kg
SOC = [200, 150, 100, 60, 40, 20]           # dg/kg
BDOD = [120, 130, 140, 150, 155, 160]       # cg/cm3
CFVO = [50, 50, 60, 70, 80, 90]             # cm3/dm3
UNC = 40


def mapped(prop: str, i: int, stat: str) -> int:
    base = {"sand": SAND, "clay": CLAY, "silt": [1000 - s - c for s, c in zip(SAND, CLAY)],
            "soc": SOC, "bdod": BDOD, "cfvo": CFVO}[prop][i]
    return {"mean": base, "Q0.05": base - 50, "Q0.5": base, "Q0.95": base + 50,
            "uncertainty": UNC}[stat]


# ----------------------------------------------------------------------------- finti REST

def rest_payload(prop: str, null: bool = False) -> dict:
    um = sg.UNITS[prop]
    depths = []
    for i, (t, b) in enumerate(sg.DEPTHS):
        vals = {s: (None if null else mapped(prop, i, s)) for s in sg.STATS}
        depths.append({"range": {"top_depth": t, "bottom_depth": b, "unit_depth": "cm"},
                       "label": f"{t}-{b}cm", "values": vals})
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [LON, LAT]},
            "properties": {"layers": [{"name": prop,
                                       "unit_measure": {"d_factor": um["d_factor"],
                                                        "mapped_units": um["mapped"],
                                                        "target_units": um["unit"],
                                                        "uncertainty_unit": "%"},
                                       "depths": depths}]}}


class FakeResp:
    def __init__(self, payload=None, content=b"", ctype="application/json"):
        self._payload, self.content = payload, content
        self.headers = {"Content-Type": ctype}
        self.text = content[:200].decode("latin1") if content else ""

    def json(self):
        return self._payload


# ----------------------------------------------------------------------------- finti WCS

def make_tiff(arr: np.ndarray, origin_lon: float, origin_lat: float, d: float) -> bytes:
    ifd = TiffImagePlugin.ImageFileDirectory_v2()
    ifd[33922] = (0.0, 0.0, 0.0, origin_lon, origin_lat, 0.0)
    ifd[33550] = (d, d, 0.0)
    buf = io.BytesIO()
    Image.fromarray(arr.astype(np.int32), mode="I").save(buf, format="TIFF", tiffinfo=ifd)
    return buf.getvalue()


N, D = 9, 0.0025
ORIGIN = (9.989, 45.211)   # il punto cade nel pixel (riga 4, colonna 4), lontano dai bordi


def wcs_tiff(cov: str, dead: set[tuple[int, int]]) -> bytes:
    prop, depth, stat = cov.split("_")
    i = [f"{t}-{b}cm" for t, b in sg.DEPTHS].index(depth)
    arr = np.full((N, N), mapped(prop, i, stat), dtype=np.int64) + np.arange(N)[None, :]
    for r, c in dead:
        arr[r, c] = 0
    return make_tiff(arr, ORIGIN[0], ORIGIN[1], D)


@pytest.fixture
def tmpcache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setattr(config, "offline", lambda: False)
    monkeypatch.setattr(sg, "_sleep", lambda s: None)
    return tmp_path


@pytest.fixture
def rest_ok(tmpcache, monkeypatch):
    calls = []

    def fake(url, params=None, timeout=None):
        assert url == sg.REST_URL
        prop = dict((k, v) for k, v in params if k == "property")["property"]
        calls.append(prop)
        return FakeResp(rest_payload(prop))

    monkeypatch.setattr(sg, "_http_get", fake)
    return calls


def fake_wcs_http(dead, rest_fails=True, counter=None):
    def fake(url, params=None, timeout=None):
        if url == sg.REST_URL:
            if counter is not None:
                counter["rest"] += 1
            raise requests.ConnectTimeout("simulato")
        assert url == sg.WCS_URL
        cov = dict(params)["COVERAGEID"]
        if counter is not None:
            counter["wcs"] += 1
        return FakeResp(content=wcs_tiff(cov, dead), ctype="image/tiff")
    return fake


# ----------------------------------------------------------------------------- REST: conversione

def test_rest_unit_conversion(rest_ok):
    path = sg.fetch(LAT, LON)
    assert path.name == "soilgrids_rest.json" and cache.is_cached(path)
    meta = cache.read_meta(path)
    assert meta["product"] == "SoilGrids 250m" and meta["version"] == "2.0"
    assert "via=rest" in meta["notes"]

    df = sg.load(LAT, LON)
    assert list(df.columns) == ["property", "depth_label", "top_cm", "bottom_cm", "mapped_mean",
                                "mean", "q05", "q50", "q95", "uncertainty", "unit"]
    row = lambda p, lab: df[(df.property == p) & (df.depth_label == lab)].iloc[0]
    r = row("sand", "0-5cm")
    assert r.mapped_mean == 300 and r["mean"] == pytest.approx(30.0)
    assert r.q05 == pytest.approx(25.0) and r.q95 == pytest.approx(35.0) and r.unit == "%"
    assert r.uncertainty == UNC                               # non convertita
    r = row("soc", "0-5cm")
    assert r["mean"] == pytest.approx(20.0) and r.unit == "g/kg"       # 200 dg/kg
    r = row("soc_pct", "0-5cm")
    assert r["mean"] == pytest.approx(2.0) and r.unit == "%"           # 20 g/kg = 2 %
    r = row("bdod", "30-60cm")
    assert r["mean"] == pytest.approx(1.50) and r.unit == "g/cm3"      # 150 cg/cm3
    r = row("cfvo", "60-100cm")
    assert r["mean"] == pytest.approx(8.0) and r.unit == "% vol"       # 80 cm3/dm3
    assert len(df) == 7 * 6
    assert sorted(set(rest_ok)) == sorted(sg.PROPERTIES)


def test_rest_cache_hit_has_no_network(rest_ok, monkeypatch):
    sg.fetch(LAT, LON)
    n = len(rest_ok)
    monkeypatch.setattr(sg, "_http_get", lambda *a, **k: pytest.fail("rete usata"))
    sg.fetch(LAT, LON)
    assert len(rest_ok) == n


# ----------------------------------------------------------------------------- aggregazione

def test_weighted_aggregation_by_hand(rest_ok):
    sg.fetch(LAT, LON)
    agg = sg.load_aggregated(LAT, LON)
    assert list(agg.columns) == ["property", "layer", "top_cm", "bottom_cm", "mean", "q05",
                                 "q95", "unit"]
    g = lambda p, lay: agg[(agg.property == p) & (agg.layer == lay)].iloc[0]
    # sabbia 0-30: (5*30 + 10*32 + 15*34) / 30 = 980/30
    assert g("sand", "0-30cm")["mean"] == pytest.approx(980 / 30)
    assert g("sand", "0-30cm").q05 == pytest.approx(980 / 30 - 5.0)      # media pesata dei q05
    assert g("sand", "0-30cm").q95 == pytest.approx(980 / 30 + 5.0)
    # sabbia 30-100: (30*40 + 40*45) / 70
    assert g("sand", "30-100cm")["mean"] == pytest.approx(3000 / 70)
    assert g("sand", "100-200cm")["mean"] == pytest.approx(50.0)
    # carbonio organico 0-30 in g/kg: (5*20 + 10*15 + 15*10)/30 = 400/30 ; in %: /10
    assert g("soc", "0-30cm")["mean"] == pytest.approx(400 / 30)
    assert g("soc_pct", "0-30cm")["mean"] == pytest.approx(400 / 300)
    # sostanza organica = C% x 1,724
    assert g("om", "0-30cm")["mean"] == pytest.approx(400 / 300 * 1.724)
    assert g("om", "0-30cm").unit == "%"
    # densita' apparente 0-30: (5*1.2 + 10*1.3 + 15*1.4)/30 = 40/30
    assert g("bdod", "0-30cm")["mean"] == pytest.approx(40 / 30)
    # orizzonti: 3 per ognuna delle 7 proprieta' + om
    assert len(agg) == 3 * 8
    assert (cache.processed_dir(LAT, LON) / "soilgrids_agg.csv").exists()


def test_aggregate_rejects_incomplete_layers(rest_ok):
    sg.fetch(LAT, LON)
    df = sg.load(LAT, LON)
    with pytest.raises(sg.SoilGridsError):
        sg.aggregate(df[df.depth_label != "15-30cm"])


# ----------------------------------------------------------------------------- robustezza REST

def test_rest_retries_with_increasing_waits(tmpcache, monkeypatch):
    waits, state = [], {"n": 0}
    monkeypatch.setattr(sg, "_sleep", waits.append)

    def flaky(url, params=None, timeout=None):
        state["n"] += 1
        if state["n"] <= 3:
            raise requests.ReadTimeout("simulato")
        return FakeResp(rest_payload(dict(params)["property"]))

    monkeypatch.setattr(sg, "_http_get", flaky)
    path = sg.fetch(LAT, LON)
    assert path.name == "soilgrids_rest.json"
    assert waits == list(sg.REST_WAITS[:3]) and waits == sorted(waits)


def test_rest_null_pixel_moves_to_nearest_valid(tmpcache, monkeypatch):
    def fake(url, params=None, timeout=None):
        p = dict(params)
        # il punto richiesto e i vicini a 250 m a nord/est/ovest non hanno dato; il sud si'
        null = float(p["lat"]) >= LAT - 1e-9
        return FakeResp(rest_payload(p["property"], null=null))

    monkeypatch.setattr(sg, "_http_get", fake)
    path = sg.fetch(LAT, LON)
    info = sg.pixel_info(LAT, LON)
    assert info["via"] == "rest" and info["shift_m"] == pytest.approx(250.0)
    assert info["queried_lat"] < LAT
    assert "spostato" in cache.read_meta(path)["notes"]


# ----------------------------------------------------------------------------- ripiego WCS

def test_wcs_fallback_when_rest_dead(tmpcache, monkeypatch):
    counter = {"rest": 0, "wcs": 0}
    monkeypatch.setattr(sg, "_http_get", fake_wcs_http(set(), counter=counter))
    path = sg.fetch(LAT, LON)
    assert counter["rest"] == sg.REST_ATTEMPTS          # 5 tentativi, poi ripiego
    assert counter["wcs"] == 6 * 6 * 5                  # proprieta' x profondita' x statistiche
    assert path.name == "soilgrids_wcs.json"
    meta = cache.read_meta(path)
    assert "via=wcs" in meta["notes"] and "nessuno spostamento" in meta["notes"]
    info = sg.pixel_info(LAT, LON)
    assert (info["pixel_row"], info["pixel_col"]) == (4, 4) and info["shift_m"] == 0.0
    df = sg.load(LAT, LON)
    r = df[(df.property == "sand") & (df.depth_label == "0-5cm")].iloc[0]
    assert r.mapped_mean == 304 and r["mean"] == pytest.approx(30.4)      # base 300 + colonna 4
    assert not (path.parent / "soilgrids_rest.json").exists()


def test_wcs_nodata_pixel_moves_to_nearest_valid(tmpcache, monkeypatch):
    monkeypatch.setattr(sg, "_http_get", fake_wcs_http({(4, 4)}))
    path = sg.fetch(LAT, LON)
    info = sg.pixel_info(LAT, LON)
    assert not info["own_pixel_valid"]
    assert (info["pixel_row"], info["pixel_col"]) == (4, 3)     # vicino piu' prossimo (~180 m)
    assert 150 < info["shift_m"] < 210
    assert info["shift_m"] <= sg.MAX_SHIFT_M
    assert "spostato" in cache.read_meta(path)["notes"]
    df = sg.load(LAT, LON)
    assert df[(df.property == "sand") & (df.depth_label == "0-5cm")].iloc[0].mapped_mean == 303


def test_wcs_no_valid_pixel_within_limit(tmpcache, monkeypatch):
    everything = {(r, c) for r in range(N) for c in range(N)}
    monkeypatch.setattr(sg, "_http_get", fake_wcs_http(everything))
    with pytest.raises(sg.SoilGridsError):
        sg.fetch(LAT, LON)


# ----------------------------------------------------------------------------- offline / cache

def test_offline_blocks_network(tmpcache, monkeypatch):
    monkeypatch.setattr(config, "offline", lambda: True)
    monkeypatch.setattr(sg, "_http_get", lambda *a, **k: pytest.fail("rete usata"))
    with pytest.raises(cache.OfflineError):
        sg.fetch(LAT, LON)
    with pytest.raises(cache.OfflineError):
        sg.fetch(LAT, LON, force=True)


def test_offline_env_variable(tmpcache, monkeypatch):
    monkeypatch.undo()  # ripristina config.offline reale, poi rimette cartelle temporanee
    monkeypatch.setattr(config, "RAW_DIR", tmpcache / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmpcache / "processed")
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    with pytest.raises(cache.OfflineError):
        sg.fetch(LAT, LON)


def test_load_without_cache_raises_cachemiss(tmpcache, monkeypatch):
    monkeypatch.setattr(sg, "_http_get", lambda *a, **k: pytest.fail("load ha usato la rete"))
    with pytest.raises(cache.CacheMiss):
        sg.load(LAT, LON)
    with pytest.raises(cache.CacheMiss):
        sg.load_aggregated(LAT, LON)
    with pytest.raises(cache.CacheMiss):
        sg.pixel_info(LAT, LON)


def test_raw_without_meta_is_not_valid(tmpcache):
    d = cache.raw_dir("soilgrids", LAT, LON)
    (d / "soilgrids_rest.json").write_text(json.dumps({"via": "rest"}), encoding="utf-8")
    with pytest.raises(cache.CacheMiss):
        sg.load(LAT, LON)


def test_load_works_offline_after_fetch(rest_ok, monkeypatch):
    sg.fetch(LAT, LON)
    monkeypatch.setattr(config, "offline", lambda: True)
    assert len(sg.load(LAT, LON)) == 42
    assert len(sg.load_aggregated(LAT, LON)) == 24
