"""Test del client pioggia ARPA Lombardia, senza rete e senza toccare la cache vera."""
import math
import re

import numpy as np
import pandas as pd
import pytest
import requests

from fieldwise import config
from fieldwise.data import arpa, cache

LAT, LON = 45.2, 10.0


def _st(sid, name, lat, lng, start="1990-01-01T00:00:00.000", stop=None, tip="Precipitazione"):
    return {"idsensore": str(sid), "tipologia": tip, "idstazione": f"s{sid}", "nomestazione": name,
            "quota": "44", "datastart": start, "datastop": stop, "lat": str(lat), "lng": str(lng)}


# ------------------------------------------------------------------ geometria

def test_haversine_known_values():
    assert arpa.haversine_km(45.0, 10.0, 45.0, 10.0) == 0.0
    # 1 grado di latitudine = pi/180 * R
    assert arpa.haversine_km(45.0, 10.0, 46.0, 10.0) == pytest.approx(math.radians(1) * 6371.0088, rel=1e-9)
    # un grado di longitudine a 45N accorcia di ~cos(45)
    d = arpa.haversine_km(45.0, 10.0, 45.0, 11.0)
    assert d == pytest.approx(78.6, abs=0.3)
    assert arpa.haversine_km(45.0, 10.0, 46.0, 11.0) == arpa.haversine_km(46.0, 11.0, 45.0, 10.0)


# ------------------------------------------------------- scelta della stazione

def test_choose_nearest_when_coverage_equal():
    sts = [_st(1, "lontana", 45.40, 10.0), _st(2, "vicina", 45.21, 10.0), _st(3, "media", 45.30, 10.0)]
    out = arpa.choose_stations(sts, LAT, LON)
    assert [s["idsensore"] for s in out] == ["2"]
    assert out[0]["role"] == "primary"
    assert out[0]["dist_km"] == pytest.approx(arpa.haversine_km(LAT, LON, 45.21, 10.0))
    assert out[0]["coverage"] == pytest.approx(1.0)


def test_coverage_beats_proximity_and_filters():
    sts = [
        _st(1, "vicinissima ma recente", 45.201, 10.0, start="2015-01-01T00:00:00.000"),
        _st(2, "piena copertura", 45.30, 10.0),
        _st(3, "fuori raggio", 46.0, 10.0),                       # ~89 km
        _st(4, "altro tipo", 45.2005, 10.0, tip="Temperatura"),
    ]
    out = arpa.choose_stations(sts, LAT, LON)
    assert out[0]["idsensore"] == "2"
    assert all(s["idsensore"] not in ("3", "4") for s in out)


def test_secondary_fills_the_gap():
    sts = [
        _st(1, "primaria, chiusa nel 2012", 45.21, 10.0, stop="2012-12-31T00:00:00.000"),
        _st(2, "secondaria, dal 2013", 45.30, 10.0, start="2013-01-01T00:00:00.000"),
        _st(3, "piu' vicina ma inutile", 45.205, 10.0, start="2001-01-01T00:00:00.000",
            stop="2005-12-31T00:00:00.000"),
    ]
    out = arpa.choose_stations(sts, LAT, LON)
    assert [(s["idsensore"], s["role"]) for s in out] == [("1", "primary"), ("2", "secondary")]
    assert out[0]["coverage"] == pytest.approx(13 / 26, abs=0.01)


def test_no_candidates():
    assert arpa.choose_stations([_st(1, "lontana", 46.5, 10.0)], LAT, LON) == []


# ------------------------------------------------------------ dataset/catalogo

def test_parse_dataset_years_and_catalog():
    assert arpa.parse_dataset_years("Precipitazioni fino al 2010") == (0, 2010)
    assert arpa.parse_dataset_years("Precipitazioni dal 2011 al 2020") == (2011, 2020)
    assert arpa.parse_dataset_years("Precipitazioni dal 2021") == (2021, 9999)
    with pytest.raises(ValueError):
        arpa.parse_dataset_years("Precipitazioni boh")
    ds = arpa.datasets_from_catalog(_catalog())
    assert [d["id"] for d in ds] == ["old1-old1", "mid2-mid2", "new3-new3"]  # i dataset non pertinenti sono scartati
    assert arpa.dataset_for_year(ds, 2000)["id"] == "old1-old1"
    assert arpa.dataset_for_year(ds, 2011)["id"] == "mid2-mid2"
    assert arpa.dataset_for_year(ds, 2025)["id"] == "new3-new3"
    assert ds[0]["updated"].startswith("2025-05-07")


# ----------------------------------------------------------- aggregazione/QC

def _row(day, mid, rain, n_valid, n_tot=None):
    return {"giorno": f"{day}T00:00:00.000", "mezzanotte": str(mid), "pioggia": f"{rain:.2f}",
            "n_valid": str(n_valid), "n_tot": str(n_valid if n_tot is None else n_tot)}


def test_midnight_measure_belongs_to_previous_day():
    rows = [_row("2020-03-01", 0, 5.0, 143), _row("2020-03-02", 1, 1.5, 1),
            _row("2020-03-02", 0, 2.0, 143), _row("2020-03-03", 1, 0.0, 1)]
    d = arpa.rows_to_daily(rows).set_index("date")
    assert d.loc["2020-03-01", "rain_mm"] == pytest.approx(5.0 + 1.5)
    assert d.loc["2020-03-01", "n_obs"] == 144
    assert d.loc["2020-03-02", "n_obs"] == 144
    assert d.loc["2020-03-02", "rain_mm"] == pytest.approx(2.0)


def test_invalid_values_are_missing():
    # 100 righe totali, 40 non valide (stato != VA o sentinella -999): la somma server-side le esclude
    d = arpa.rows_to_daily([_row("2020-03-01", 0, 3.0, 60, n_tot=100)])
    assert d.loc[0, "n_obs"] == 60 and d.loc[0, "n_tot"] == 100
    # un giorno con sole misure non valide: nessuna pioggia nota, non 0
    out = arpa.build_daily({2020: [_row("2020-03-01", 0, 0.0, 0, n_tot=144)]}, "1", "X", 2020, 2020)
    r = out.set_index("date").loc["2020-03-01"]
    assert r["n_obs"] == 0 and np.isnan(r["rain_mm"]) and not r["complete"]


def test_completeness_threshold_and_missing_days():
    rows = [_row("2020-01-10", 0, 1.0, 144),   # completo
            _row("2020-01-11", 0, 1.0, 130),   # 130/144 = 90.3% -> completo
            _row("2020-01-12", 0, 1.0, 129),   # 129/144 = 89.6% -> incompleto
            _row("2020-01-13", 0, 1.0, 20)]
    out = arpa.build_daily({2020: rows}, "1", "X", 2020, 2020).set_index("date")
    assert len(out) == 366                      # anno bisestile, giorni senza righe inclusi
    assert out.loc["2020-01-10", "complete"] and out.loc["2020-01-11", "complete"]
    assert not out.loc["2020-01-12", "complete"] and not out.loc["2020-01-13", "complete"]
    assert (out["n_expected"] == 144).all()
    assert out.loc["2020-01-01", "n_obs"] == 0 and np.isnan(out.loc["2020-01-01", "rain_mm"])
    assert list(out.columns) == [c for c in arpa.COLUMNS if c != "date"]
    assert out.loc["2020-01-10", ["sensor_id", "station"]].tolist() == ["1", "X"]


def test_expected_follows_resolution():
    assert arpa.infer_expected(pd.Series([24] * 50 + [20, 3])) == 24
    assert arpa.infer_expected(pd.Series([144] * 50 + [100, 3])) == 144
    assert arpa.infer_expected(pd.Series([0, 0])) == 144
    hourly = [_row(f"2001-05-{d:02d}", 0, 0.0, 24) for d in range(1, 21)]
    out = arpa.build_daily({2001: hourly}, "1", "X", 2001, 2001)
    assert (out["n_expected"] == 24).all()
    assert out.loc[out["n_obs"] == 24, "complete"].all()


def test_sensor_activity_limits_the_days():
    out = arpa.build_daily({}, "1", "X", 2000, 2002, datastart="2001-06-01T00:00:00.000",
                           datastop="2001-06-30T00:00:00.000")
    assert out["date"].min() == pd.Timestamp("2001-06-01") and out["date"].max() == pd.Timestamp("2001-06-30")


# --------------------------------------------------------------- rete finta

def _catalog():
    def r(i, name, upd):
        return {"resource": {"id": i, "name": name, "data_updated_at": upd}}
    return {"results": [
        r("new3-new3", "Precipitazioni dal 2021", "2026-03-06T17:54:22.000Z"),
        r("old1-old1", "Precipitazioni fino al 2010", "2025-05-07T04:06:48.000Z"),
        r("mid2-mid2", "Precipitazioni dal 2011 al 2020", "2025-05-08T02:41:46.000Z"),
        r("rcp4-rcp4", "Esposizione precipitazioni intense RCP 4.5 2021-2040", "2024-06-20T00:00:00.000Z"),
    ]}


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
def fake_net(monkeypatch, tmp_cache):
    calls = []
    sleeps = []
    stations = [_st(2492, "Persico Dosimo", 45.18, 10.04), _st(9999, "lontana", 46.5, 10.0),
                _st(5, "temp", 45.2, 10.0, tip="Temperatura")]

    def fake_get(url, params=None, timeout=None):
        calls.append((url, dict(params or {})))
        if "catalog" in url:
            return _Resp(_catalog())
        if url.endswith(f"/{arpa.STATIONS_DATASET}.json"):
            return _Resp(stations)
        year = int(re.search(r"data>'(\d{4})-", params["$where"]).group(1))
        assert "idsensore='2492'" in params["$where"]
        return _Resp([_row(f"{year}-07-01", 0, 4.0, 143), _row(f"{year}-07-02", 1, 1.0, 1)])

    monkeypatch.setattr(arpa.requests, "get", fake_get)
    monkeypatch.setattr(arpa.time, "sleep", sleeps.append)
    return calls, sleeps


def test_fetch_end_to_end(fake_net, tmp_cache):
    calls, _ = fake_net
    out = arpa.fetch(LAT, LON, 2009, 2012)
    assert out == cache.processed_dir(LAT, LON) / "arpa_rain_daily.csv" and out.exists()
    # 1 anagrafica + 1 catalogo + 4 anni
    assert len(calls) == 6
    year_calls = [c for c in calls if "idsensore" in c[1].get("$where", "")]
    urls = [c[0] for c in year_calls]
    assert [u.split("/")[-1] for u in urls] == ["old1-old1.json", "old1-old1.json",
                                                 "mid2-mid2.json", "mid2-mid2.json"]
    p = year_calls[0][1]
    assert p["$group"] == "giorno,mezzanotte" and "sum(" in p["$select"] and "count(*)" in p["$select"]
    # cache grezza con metadati: product = dataset, version = id + ultimo aggiornamento
    raw = cache.raw_dir("arpa", LAT, LON) / "pioggia_old1-old1_sensore2492_2009.json"
    meta = cache.read_meta(raw)
    assert meta["product"] == "Precipitazioni fino al 2010"
    assert "old1-old1" in meta["version"] and "2025-05-07" in meta["version"]
    assert meta["params"]["sensor_id"] == "2492" and meta["params"]["dist_km"] > 0
    assert "ora solare" in meta["notes"]
    # elaborato
    df = arpa.load(LAT, LON)
    assert list(df.columns) == arpa.COLUMNS and len(df) == 365 * 3 + 366
    d = df.set_index("date")
    assert d.loc["2009-07-01", "rain_mm"] == pytest.approx(5.0)   # 4.0 + 1.0 della mezzanotte del 2 luglio
    assert d.loc["2009-07-01", "complete"] and d.loc["2009-07-01", "n_obs"] == 144
    assert set(df["sensor_id"]) == {"2492"} and set(df["station"]) == {"Persico Dosimo"}


def test_second_fetch_uses_cache_and_force_refetches(fake_net, tmp_cache):
    calls, _ = fake_net
    arpa.fetch(LAT, LON, 2010, 2011)
    n = len(calls)
    arpa.fetch(LAT, LON, 2010, 2011)
    assert len(calls) == n
    arpa.fetch(LAT, LON, 2010, 2011, force=True)
    assert len(calls) == 2 * n


def test_retries_with_increasing_wait_then_fails(monkeypatch, tmp_cache):
    sleeps = []
    attempts = []

    def boom(url, params=None, timeout=None):
        attempts.append(1)
        raise requests.ConnectionError("giu'")

    monkeypatch.setattr(arpa.requests, "get", boom)
    monkeypatch.setattr(arpa.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="3 tentativi"):
        arpa.fetch(LAT, LON, 2010, 2010)
    assert len(attempts) == 3
    assert sleeps == [arpa.BACKOFF, 2 * arpa.BACKOFF]


def test_retry_recovers(monkeypatch, tmp_cache):
    state = {"n": 0}

    def flaky(url, params=None, timeout=None):
        state["n"] += 1
        if state["n"] < 3:
            raise requests.Timeout("lento")
        return _Resp([])

    monkeypatch.setattr(arpa.requests, "get", flaky)
    monkeypatch.setattr(arpa.time, "sleep", lambda s: None)
    assert arpa._get("http://x", {}) == []
    assert state["n"] == 3


def test_pause_between_requests(fake_net, tmp_cache):
    _, sleeps = fake_net
    arpa.fetch(LAT, LON, 2010, 2010)
    assert sleeps and all(s == arpa.PAUSE for s in sleeps)


def test_offline_raises_before_any_request(monkeypatch, tmp_cache):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")

    def no_net(*a, **k):
        raise AssertionError("rete usata in modalita' offline")

    monkeypatch.setattr(arpa.requests, "get", no_net)
    with pytest.raises(cache.OfflineError):
        arpa.fetch(LAT, LON)


def test_load_without_cache_raises_cachemiss(tmp_cache, monkeypatch):
    def no_net(*a, **k):
        raise AssertionError("load() non deve usare la rete")

    monkeypatch.setattr(arpa.requests, "get", no_net)
    with pytest.raises(cache.CacheMiss):
        arpa.load(LAT, LON)


def test_load_works_offline_after_fetch(fake_net, tmp_cache, monkeypatch):
    arpa.fetch(LAT, LON, 2010, 2010)
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    assert len(arpa.load(LAT, LON)) == 365


# =============================================================== temperatura

def _trow(day, mid, tmax, tmin, somma, n_valid, n_tot=None):
    r = {"giorno": f"{day}T00:00:00.000", "mezzanotte": str(mid), "somma": f"{somma:.2f}",
         "n_valid": str(n_valid), "n_tot": str(n_valid if n_tot is None else n_tot)}
    if tmax is not None:          # Socrata omette max/min se nessun valore valido
        r["tmax"], r["tmin"] = f"{tmax:.2f}", f"{tmin:.2f}"
    return r


def test_temp_select_clause_and_validity_rules():
    p = arpa._temp_year_params("2485", 2003)
    sel = p["$select"]
    assert "max(case(" in sel and "min(case(" in sel and "sum(" in sel and "count(*)" in sel
    assert "stato='VA'" in sel and "valore>-50" in sel and "valore<60" in sel   # niente -999, niente 145 °C
    assert p["$group"] == "giorno,mezzanotte"
    assert "idsensore='2485'" in p["$where"] and "data>'2003-01-01T00:00:00'" in p["$where"]
    assert "data<='2004-01-01T00:00:00'" in p["$where"]


def test_temp_midnight_belongs_to_previous_day_and_extremes_compose():
    rows = [_trow("2020-07-01", 0, 31.0, 18.0, 143 * 25.0, 143),
            _trow("2020-07-02", 1, 33.5, 33.5, 33.5, 1),      # misura delle 00:00 del 2 luglio: e' del 1
            _trow("2020-07-02", 0, 29.0, 17.0, 143 * 24.0, 143)]
    d = arpa.temp_rows_to_daily(rows).set_index("date")
    r = d.loc["2020-07-01"]
    assert r["tmax"] == 33.5 and r["tmin"] == 18.0 and r["n_obs"] == 144
    assert r["tmean"] == pytest.approx((143 * 25.0 + 33.5) / 144)
    assert d.loc["2020-07-02", "tmax"] == 29.0 and d.loc["2020-07-02", "n_obs"] == 143


def test_temp_invalid_values_are_missing():
    # sensore bloccato (145.3 'VA') o sentinella: il server non li conta, il giorno non ha misure valide
    out = arpa.build_daily_temp({2020: [_trow("2020-07-01", 0, None, None, 0.0, 0, n_tot=144)]},
                                "1", "X", 2020, 2020).set_index("date")
    r = out.loc["2020-07-01"]
    assert r["n_obs"] == 0 and not r["complete"]
    assert np.isnan(r["tmax"]) and np.isnan(r["tmin"]) and np.isnan(r["tmean"])
    # giorno parzialmente valido: statistiche sui soli valori validi
    d = arpa.temp_rows_to_daily([_trow("2020-07-02", 0, 28.0, 16.0, 60 * 22.0, 60, n_tot=100)])
    assert d.loc[0, "n_obs"] == 60 and d.loc[0, "n_tot"] == 100 and d.loc[0, "tmean"] == pytest.approx(22.0)


def test_temp_completeness_threshold_and_columns():
    rows = [_trow("2020-01-10", 0, 5.0, 0.0, 144 * 2.0, 144),
            _trow("2020-01-11", 0, 5.0, 0.0, 130 * 2.0, 130),   # 90.3% -> completo
            _trow("2020-01-12", 0, 5.0, 0.0, 129 * 2.0, 129)]   # 89.6% -> incompleto
    out = arpa.build_daily_temp({2020: rows}, "7", "Stz", 2020, 2020)
    assert list(out.columns) == arpa.TEMP_COLUMNS
    assert len(out) == 366
    o = out.set_index("date")
    assert o.loc["2020-01-10", "complete"] and o.loc["2020-01-11", "complete"]
    assert not o.loc["2020-01-12", "complete"] and not o.loc["2020-01-01", "complete"]
    assert (o["n_expected"] == 144).all() and np.isnan(o.loc["2020-01-01", "tmax"])
    assert o.loc["2020-01-10", ["sensor_id", "station"]].tolist() == ["7", "Stz"]
    hourly = [_trow(f"2001-05-{d:02d}", 0, 20.0, 10.0, 24 * 15.0, 24) for d in range(1, 21)]
    assert (arpa.build_daily_temp({2001: hourly}, "7", "Stz", 2001, 2001)["n_expected"] == 24).all()


def test_choose_temperature_station_ignores_other_types():
    sts = [_st(1, "pluvio vicino", 45.2005, 10.0),
           _st(2, "termo stessa stazione", 45.18, 10.04, tip="Temperatura"),
           _st(3, "termo lontano", 45.40, 10.0, tip="Temperatura"),
           _st(4, "termo fuori raggio", 46.5, 10.0, tip="Temperatura")]
    out = arpa.choose_stations(sts, LAT, LON, tipologia=arpa.TEMP_TYPE)
    assert [s["idsensore"] for s in out] == ["2"]
    assert [s["idsensore"] for s in arpa.choose_stations(sts, LAT, LON)] == ["1"]   # default: pioggia


def test_temperature_catalog_datasets():
    cat = {"results": [
        {"resource": {"id": "t3", "name": "Temperatura dal 2021", "data_updated_at": "2026-03-06T00:00:00Z"}},
        {"resource": {"id": "t1", "name": "Temperatura fino al 2010", "data_updated_at": "2025-05-06T00:00:00Z"}},
        {"resource": {"id": "t2", "name": "Temperatura dal 2011 al 2020", "data_updated_at": "2025-05-07T00:00:00Z"}},
        {"resource": {"id": "x", "name": "Atles Climatic de temperatura", "data_updated_at": "2026-01-01T00:00:00Z"}},
        {"resource": {"id": "p", "name": "Precipitazioni dal 2021", "data_updated_at": "2026-01-01T00:00:00Z"}},
    ]}
    ds = arpa.datasets_from_catalog(cat, arpa.TEMP_DATASET_NAME_RE)
    assert [d["id"] for d in ds] == ["t1", "t2", "t3"]
    assert arpa.dataset_for_year(ds, 2015)["id"] == "t2"


@pytest.fixture
def fake_net_both(monkeypatch, tmp_cache):
    """Rete finta per pioggia e temperatura: instrada in base all'URL e ai parametri."""
    calls = []
    stations = [_st(2492, "Persico Dosimo", 45.18, 10.04),
                _st(2485, "Persico Dosimo", 45.18, 10.04, tip="Temperatura"),
                _st(9938, "Cremona Fatebenefratelli", 45.13, 10.02, start="2006-04-10T00:00:00.000",
                    tip="Temperatura"),
                _st(9999, "lontana", 46.5, 10.0, tip="Temperatura")]
    tcat = {"results": [
        {"resource": {"id": "tt1-tt1", "name": "Temperatura fino al 2010", "data_updated_at": "2025-05-06T04:00:00Z"}},
        {"resource": {"id": "tt2-tt2", "name": "Temperatura dal 2011 al 2020", "data_updated_at": "2025-05-07T04:00:00Z"}},
        {"resource": {"id": "tt3-tt3", "name": "Temperatura dal 2021", "data_updated_at": "2026-03-06T04:00:00Z"}},
    ]}

    def fake_get(url, params=None, timeout=None):
        params = dict(params or {})
        calls.append((url, params))
        if "catalog" in url:
            return _Resp(tcat if params["q"] == "Temperatura" else _catalog())
        if url.endswith(f"/{arpa.STATIONS_DATASET}.json"):
            tip = re.search(r"tipologia='(\w+)'", params["$where"]).group(1)
            return _Resp([s for s in stations if s["tipologia"] == tip])
        year = int(re.search(r"data>'(\d{4})-", params["$where"]).group(1))
        if "tmax" in params["$select"]:
            sid = re.search(r"idsensore='(\d+)'", params["$where"]).group(1)
            assert sid in ("2485", "9938")
            tmax = 30.0 if sid == "2485" else 36.0
            return _Resp([_trow(f"{year}-07-01", 0, tmax, 15.0, 143 * 22.0, 143),
                          _trow(f"{year}-07-02", 1, 24.0, 24.0, 24.0, 1)])
        assert "idsensore='2492'" in params["$where"]
        return _Resp([_row(f"{year}-07-01", 0, 4.0, 143), _row(f"{year}-07-02", 1, 1.0, 1)])

    monkeypatch.setattr(arpa.requests, "get", fake_get)
    monkeypatch.setattr(arpa.time, "sleep", lambda s: None)
    return calls


def test_fetch_temperature_end_to_end(fake_net_both, tmp_cache):
    calls = fake_net_both
    out = arpa.fetch_temperature(LAT, LON, 2009, 2012)
    assert out == cache.processed_dir(LAT, LON) / "arpa_temp_daily.csv" and out.exists()
    assert len(calls) == 6                        # anagrafica + catalogo + 4 anni
    datasets = [c[0].split("/")[-1] for c in calls if "tmax" in c[1].get("$select", "")]
    assert datasets == ["tt1-tt1.json", "tt1-tt1.json", "tt2-tt2.json", "tt2-tt2.json"]
    raw = cache.raw_dir("arpa", LAT, LON) / "temperatura_tt1-tt1_sensore2485_2009.json"
    meta = cache.read_meta(raw)
    assert meta["product"] == "Temperatura fino al 2010"
    assert "tt1-tt1" in meta["version"] and "2025-05-06" in meta["version"]
    assert meta["params"]["sensor_id"] == "2485" and "ora solare" in meta["notes"]
    df = arpa.load_temperature(LAT, LON)
    assert list(df.columns) == arpa.TEMP_COLUMNS and len(df) == 365 * 3 + 366
    r = df.set_index("date").loc["2009-07-01"]
    assert r["tmax"] == 30.0 and r["tmin"] == 15.0 and r["n_obs"] == 144 and r["complete"]
    assert r["tmean"] == pytest.approx((143 * 22.0 + 24.0) / 144)
    assert set(df["sensor_id"]) == {"2485"}


def test_stations_json_keeps_rain_and_temperature(fake_net_both, tmp_cache):
    import json
    d = cache.processed_dir(LAT, LON)
    arpa.fetch(LAT, LON, 2010, 2010)
    arpa.fetch_temperature(LAT, LON, 2010, 2010)          # dopo la pioggia
    info = json.loads((d / "arpa_stations.json").read_text(encoding="utf-8"))
    assert info["stations"][0]["sensor_id"] == "2492" and info["datasets"][0]["id"] == "old1-old1"
    assert info["temperature"]["stations"][0]["sensor_id"] == "2485"
    arpa.fetch(LAT, LON, 2010, 2010, force=True)          # pioggia di nuovo: non perde la temperatura
    info = json.loads((d / "arpa_stations.json").read_text(encoding="utf-8"))
    assert info["temperature"]["stations"][0]["sensor_id"] == "2485"
    assert info["stations"][0]["sensor_id"] == "2492"
    assert len(arpa.load(LAT, LON)) == 365 and len(arpa.load_temperature(LAT, LON)) == 365


def test_temperature_second_fetch_uses_cache(fake_net_both, tmp_cache):
    calls = fake_net_both
    arpa.fetch_temperature(LAT, LON, 2010, 2011)
    n = len(calls)
    arpa.fetch_temperature(LAT, LON, 2010, 2011)
    assert len(calls) == n


def test_temperature_offline_and_cachemiss(monkeypatch, tmp_cache):
    def no_net(*a, **k):
        raise AssertionError("rete usata")

    monkeypatch.setattr(arpa.requests, "get", no_net)
    with pytest.raises(cache.CacheMiss):
        arpa.load_temperature(LAT, LON)
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    with pytest.raises(cache.OfflineError):
        arpa.fetch_temperature(LAT, LON)


def test_cli_variable_temperature(fake_net_both, tmp_cache, capsys):
    arpa.main(["--lat", str(LAT), "--lon", str(LON), "--variable", "temperature",
               "--start-year", "2010", "--end-year", "2010"])
    out = capsys.readouterr().out
    assert "arpa_temp_daily.csv" in out and "2485" in out
    arpa.main(["--lat", str(LAT), "--lon", str(LON), "--start-year", "2010", "--end-year", "2010"])
    assert "arpa_rain_daily.csv" in capsys.readouterr().out


def test_explicit_sensor_leaves_automatic_outputs_untouched(fake_net_both, tmp_cache):
    import json
    d = cache.processed_dir(LAT, LON)
    arpa.fetch_temperature(LAT, LON, 2010, 2010)
    auto_csv = (d / "arpa_temp_daily.csv").read_bytes()
    auto_json = (d / "arpa_stations.json").read_bytes()
    out = arpa.fetch_temperature(LAT, LON, 2010, 2010, sensor_id="9938")
    assert out == d / "arpa_temp_daily_9938.csv" and out.exists()
    # i grezzi portano il sensore nel nome
    assert (cache.raw_dir("arpa", LAT, LON) / "temperatura_tt1-tt1_sensore9938_2010.json").exists()
    # l'automatico non cambia
    assert (d / "arpa_temp_daily.csv").read_bytes() == auto_csv
    assert (d / "arpa_stations.json").read_bytes() == auto_json
    ex = arpa.load_temperature(LAT, LON, sensor_id="9938")
    assert set(ex["sensor_id"]) == {"9938"} and ex.set_index("date").loc["2010-07-01", "tmax"] == 36.0
    assert set(arpa.load_temperature(LAT, LON)["sensor_id"]) == {"2485"}
    meta = json.loads((d / "arpa_temp_station_9938.json").read_text(encoding="utf-8"))
    assert meta["stations"][0]["role"] == "explicit" and meta["stations"][0]["dist_km"] > 0
    # sensore sconosciuto e CacheMiss per un sensore non scaricato
    with pytest.raises(RuntimeError, match="non trovato"):
        arpa.fetch_temperature(LAT, LON, 2010, 2010, sensor_id="1")
    with pytest.raises(cache.CacheMiss):
        arpa.load_temperature(LAT, LON, sensor_id="31337")


def test_cli_sensor_id(fake_net_both, tmp_cache, capsys):
    arpa.main(["--lat", str(LAT), "--lon", str(LON), "--variable", "temperature", "--sensor-id", "9938",
               "--start-year", "2010", "--end-year", "2010"])
    assert "arpa_temp_daily_9938.csv" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        arpa.main(["--lat", str(LAT), "--lon", str(LON), "--sensor-id", "9938"])
