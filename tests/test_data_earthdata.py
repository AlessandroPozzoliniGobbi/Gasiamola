"""Test dei client IMERG / SMAP: senza rete, senza credenziali, senza toccare la cache vera."""
from __future__ import annotations

import datetime as dt
import threading
import time

import h5py
import numpy as np
import pandas as pd
import pytest

from fieldwise import config
from fieldwise.data import cache, earthdata, imerg, smap

LAT, LON = 45.2, 10.0


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    """Cache temporanea; online di default; nessuna chiamata di rete ammessa."""
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setenv("FIELDWISE_OFFLINE", "0")
    monkeypatch.setattr(earthdata.time, "sleep", lambda s: None)
    return tmp_path


# ---------------------------------------------------------------- login

class _Auth:
    def __init__(self, ok):
        self.authenticated = ok


def test_login_fail_raises_auth_error(monkeypatch):
    import earthaccess
    from earthaccess.exceptions import LoginStrategyUnavailable

    tried = []

    def fake_login(strategy="all", **kw):
        tried.append(strategy)
        raise LoginStrategyUnavailable("nessuna credenziale")

    monkeypatch.setattr(earthaccess, "login", fake_login)
    with pytest.raises(earthdata.EarthdataAuthError) as ei:
        earthdata.login()
    assert tried == ["netrc", "environment"]          # mai "interactive" / "all"
    msg = str(ei.value)
    for needle in ("machine urs.earthdata.nasa.gov login", "chmod 600 ~/.netrc",
                   "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD", "EARTHDATA_TOKEN",
                   "NASA GESDISC DATA ARCHIVE"):
        assert needle in msg


def test_login_falls_back_to_environment(monkeypatch):
    import earthaccess
    from earthaccess.exceptions import LoginStrategyUnavailable

    def fake_login(strategy="all", **kw):
        if strategy == "netrc":
            raise LoginStrategyUnavailable("no netrc")
        return _Auth(True)

    monkeypatch.setattr(earthaccess, "login", fake_login)
    assert earthdata.login().authenticated is True


def test_login_unauthenticated_result_is_failure(monkeypatch):
    import earthaccess

    monkeypatch.setattr(earthaccess, "login", lambda strategy="all", **kw: _Auth(False))
    with pytest.raises(earthdata.EarthdataAuthError):
        earthdata.login()


def test_cli_without_credentials_prints_auth_message(monkeypatch, capsys):
    import earthaccess
    from earthaccess.exceptions import LoginStrategyUnavailable

    def fake_login(strategy="all", **kw):
        raise LoginStrategyUnavailable("x")

    monkeypatch.setattr(earthaccess, "login", fake_login)
    for mod in (imerg, smap):
        rc = mod.main(["--lat", "45.2", "--lon", "10.0"])
        err = capsys.readouterr().err
        assert rc == 1
        assert "EarthdataAuthError" in err and "~/.netrc" in err
        assert "Traceback" not in err


# ---------------------------------------------------------------- geometria

def test_imerg_cell_index_pilot_point_on_vertex():
    # 45.2 N e 10.0 E sono vertici della griglia da 0,1 gradi: si sceglie la cella a nord-est
    assert imerg.cell_index(LAT, LON) == (1900, 1352, 45.25, 10.05)


def test_imerg_cell_index_interior_and_edges():
    assert imerg.cell_index(45.17, 9.97) == (1899, 1351, 45.15, 9.95)
    assert imerg.cell_index(-89.99, -179.99) == (0, 0, -89.95, -179.95)
    assert imerg.cell_index(90.0, 180.0) == (3599, 1799, 89.95, 179.95)
    with pytest.raises(ValueError):
        imerg.cell_index(91, 0)


def test_smap_pixel_index_pilot_point():
    row, col, clat, clon = smap.pixel_index(LAT, LON)
    assert (row, col) == (234, 2035)
    assert clat == pytest.approx(45.2433, abs=1e-4)
    assert clon == pytest.approx(10.0363, abs=1e-4)
    # il punto sta dentro il pixel (a 9 km il centro dista al massimo ~0,06 gradi)
    assert abs(clat - LAT) < 0.07 and abs(clon - LON) < 0.07


def test_ease2_projection_reference_values():
    # valori di riferimento calcolati con pyproj (EPSG:6933) per il punto pilota
    x, y = smap.forward(LAT, LON)
    assert x == pytest.approx(964862.8025, abs=1e-3)
    assert y == pytest.approx(5198233.9902, abs=1e-3)
    # angolo in alto a sinistra della griglia: lat massima ~85,0446
    lat, lon = smap.inverse(smap.X0, smap.Y0)
    assert lat == pytest.approx(85.0446, abs=1e-4) and lon == pytest.approx(-180.0, abs=1e-9)
    # andata e ritorno
    for la, lo in [(45.2, 10.0), (-33.9, 151.2), (0.0, 0.0), (70.0, -120.0)]:
        la2, lo2 = smap.inverse(*smap.forward(la, lo))
        assert (la2, lo2) == pytest.approx((la, lo), abs=1e-9)
    # angolo in basso a destra della griglia = ultimo pixel
    assert smap.pixel_index(-85.0, 179.99)[:2] == (smap.N_ROWS - 1, smap.N_COLS - 1)
    assert smap.pixel_index(85.0, -179.99)[:2] == (0, 0)


# ---------------------------------------------------------------- IMERG: file finti

def _make_imerg_full(path, st, values):
    """Granulo IMERG finto con la struttura vera: precipitation(time=1, lon=3600, lat=1800)."""
    i0, j0 = st["i_lon0"], st["i_lat0"]
    with h5py.File(path, "w") as f:
        d = f.create_dataset("precipitation", shape=(1, 3600, 1800), dtype="f4",
                             chunks=(1, 100, 100), compression="gzip", fillvalue=-9999.9)
        for k, v in enumerate(values):
            d[0, i0 + k // 2, j0 + k % 2] = v
        d[0, i0 + 2, j0] = 99.0                 # celle vicine fuori blocco: l'ordine lon/lat conta
        d[0, i0, j0 + 2] = 77.0
        f.create_dataset("lon", data=(-179.95 + 0.1 * np.arange(3600)).astype("f4"))
        f.create_dataset("lat", data=-89.95 + 0.1 * np.arange(1800))


def _make_imerg_subset(path, values, lons, lats):
    """Sottoinsieme OPeNDAP finto: precipitation(1, 2, 2) in ordine (time, lon, lat)."""
    with h5py.File(path, "w") as f:
        f.create_dataset("precipitation", data=np.array(values, dtype="f4").reshape(1, 2, 2))
        f.create_dataset("lon", data=np.array(lons, dtype="f4"))
        f.create_dataset("lat", data=np.array(lats))


def _centers(st):
    return [st["cells"][0]["lon"], st["cells"][2]["lon"]], [st["cells"][0]["lat"], st["cells"][1]["lat"]]


def test_imerg_stencil_on_vertex_four_equal_weights():
    st = imerg.stencil(LAT, LON)
    assert [(c["lat"], c["lon"]) for c in st["cells"]] == [
        (45.15, 9.95), (45.25, 9.95), (45.15, 10.05), (45.25, 10.05)]
    assert [c["weight"] for c in st["cells"]] == [0.25] * 4
    assert (st["i_lon0"], st["i_lat0"]) == (1899, 1351)
    assert st["nearest"] == imerg.cell_column(45.25, 10.05)       # parita': nord-est
    assert st["nearest"] == "precip_lat45.250_lon10.050"


def test_imerg_stencil_cell_centre_weight_one():
    st = imerg.stencil(45.25, 10.05)
    w = {c["column"]: c["weight"] for c in st["cells"]}
    assert w[imerg.cell_column(45.25, 10.05)] == 1.0
    assert sum(w.values()) == pytest.approx(1.0) and sorted(w.values()) == [0.0, 0.0, 0.0, 1.0]
    assert st["nearest"] == imerg.cell_column(45.25, 10.05)


def test_imerg_stencil_generic_point_and_edges():
    st = imerg.stencil(45.17, 9.97)                 # cella contenente (45.15, 9.95): la piu' vicina
    w = {c["column"]: c["weight"] for c in st["cells"]}
    assert w[imerg.cell_column(45.15, 9.95)] == pytest.approx(0.64)
    assert w[imerg.cell_column(45.25, 10.05)] == pytest.approx(0.04)
    assert sum(w.values()) == pytest.approx(1.0)
    assert st["nearest"] == imerg.cell_column(45.15, 9.95)
    assert imerg.stencil(90.0, 180.0)["cells"][3]["weight"] == 1.0   # bordo della griglia
    assert imerg.stencil(-90.0, -180.0)["cells"][0]["weight"] == 1.0
    with pytest.raises(ValueError):
        imerg.stencil(91, 0)
    # con una sola richiesta: vincolo DAP4 sul blocco 2x2
    assert imerg.constraint(1899, 1351) == (
        "/precipitation[0][1899:1900][1351:1352];/lon[1899:1900];/lat[1351:1352]")


def test_imerg_extract_from_full_granule(tmp_path):
    st = imerg.stencil(LAT, LON)
    p = tmp_path / "full.nc4"
    _make_imerg_full(p, st, [1.0, 2.0, 3.0, 4.0])
    with h5py.File(p, "r") as h5:
        got = imerg.extract_block(h5, st)
    assert [got[c["column"]] for c in st["cells"]] == [1.0, 2.0, 3.0, 4.0]   # (lon0,lat0),(lon0,lat1),...


def test_imerg_extract_fill_value_becomes_nan(tmp_path):
    st = imerg.stencil(LAT, LON)
    p = tmp_path / "fill.nc4"
    _make_imerg_full(p, st, [5.0, -9999.9, 0.0, 2.0])
    with h5py.File(p, "r") as h5:
        got = imerg.extract_block(h5, st)
    cols = [c["column"] for c in st["cells"]]
    assert np.isnan(got[cols[1]]) and got[cols[2]] == 0.0 and got[cols[0]] == 5.0
    assert np.isnan(imerg.clean_precip(np.float32(-9999.9)))
    assert np.isnan(imerg.clean_precip(float("nan")))
    assert imerg.clean_precip(0.0) == 0.0          # zero e' pioggia zero, non dato mancante


def test_imerg_extract_from_opendap_subset_and_center_check(tmp_path):
    st = imerg.stencil(LAT, LON)
    lons, lats = _centers(st)
    ok = tmp_path / "sub.nc4"
    _make_imerg_subset(ok, [3.25, 1.0, 0.5, 2.0], lons, lats)
    with h5py.File(ok, "r") as h5:
        got = imerg.extract_block(h5, st)
    assert [got[c["column"]] for c in st["cells"]] == [3.25, 1.0, 0.5, 2.0]
    bad = tmp_path / "bad.nc4"                     # centri di un altro blocco -> si ferma
    _make_imerg_subset(bad, [3.25, 1.0, 0.5, 2.0], [x + 0.1 for x in lons], lats)
    with h5py.File(bad, "r") as h5, pytest.raises(ValueError, match="centri cella"):
        imerg.extract_block(h5, st)
    swapped = tmp_path / "swapped.nc4"             # lon e lat scambiati
    _make_imerg_subset(swapped, [3.25, 1.0, 0.5, 2.0], lats, lons)
    with h5py.File(swapped, "r") as h5, pytest.raises(ValueError, match="centri cella"):
        imerg.extract_block(h5, st)


def test_imerg_dap4_url():
    url = earthdata.dap4_url("https://opendap.earthdata.nasa.gov/x/f.nc4", imerg.constraint(1, 2))
    assert url.startswith("https://opendap.earthdata.nasa.gov/x/f.nc4.dap4.ce=") or ".dap.nc4?dap4.ce=" in url
    assert "[0][1:2][2:3]" in url


def _frame(st, rows):
    cols = [c["column"] for c in st["cells"]]
    return pd.DataFrame([{"date": pd.Timestamp(d), **dict(zip(cols, v))} for d, v in rows])


def test_imerg_combine_bilinear_nearest_and_missing_cell():
    nan = float("nan")
    st = imerg.stencil(LAT, LON)                    # vertice: 4 pesi da 0,25; nearest = NE (4o valore)
    df = imerg.combine(_frame(st, [("2020-01-01", [1.0, 2.0, 3.0, 6.0]),
                                   ("2020-01-02", [1.0, nan, 3.0, 6.0]),
                                   ("2020-01-03", [nan, nan, nan, nan])]), st)
    assert list(df.columns) == ["date", "rain_mm", "rain_mm_nearest", "n_cells_valid"]
    assert df["rain_mm"].iloc[0] == pytest.approx(3.0)              # media delle quattro
    assert df["rain_mm_nearest"].iloc[0] == 6.0
    assert np.isnan(df["rain_mm"].iloc[1]) and df["rain_mm_nearest"].iloc[1] == 6.0
    assert list(df["n_cells_valid"]) == [4, 3, 0]
    assert np.isnan(df["rain_mm"].iloc[2]) and np.isnan(df["rain_mm_nearest"].iloc[2])
    # al centro di una cella pesa solo quella: le altre mancanti non contano
    st1 = imerg.stencil(45.25, 10.05)
    d1 = imerg.combine(_frame(st1, [("2020-01-01", [4.0, nan, nan, nan])]), st1)
    assert d1["rain_mm"].iloc[0] == 4.0 and d1["n_cells_valid"].iloc[0] == 1
    # punto generico: pesi 0,64 / 0,16 / 0,16 / 0,04
    st2 = imerg.stencil(45.17, 9.97)
    d2 = imerg.combine(_frame(st2, [("2020-01-01", [10.0, 0.0, 0.0, 0.0])]), st2)
    assert d2["rain_mm"].iloc[0] == pytest.approx(6.4) and d2["rain_mm_nearest"].iloc[0] == 10.0


# ---------------------------------------------------------------- SMAP: file finti

def _smap_datasets(f, row, col, vals, full):
    shape = (smap.N_ROWS, smap.N_COLS) if full else (1, 1)
    for k, g in smap.GROUPS.items():
        grp = f.create_group(g["group"])
        kw = dict(chunks=(100, 100), compression="gzip") if full else {}
        for name, dtype, fill in ((g["sm"], "f4", -9999.0), (g["qual"], "u2", 65534),
                                  (g["row"], "u2", 65534), (g["col"], "u2", 65534),
                                  (g["lat"], "f4", -9999.0), (g["lon"], "f4", -9999.0)):
            grp.create_dataset(name, shape=shape, dtype=dtype, fillvalue=fill, **kw)
        v = vals[k]
        idx = (row, col) if full else (0, 0)
        grp[g["sm"]][idx] = v[0]
        grp[g["qual"]][idx] = v[1]
        grp[g["row"]][idx] = row
        grp[g["col"]][idx] = col
        clat, clon = smap.pixel_index(LAT, LON)[2:]
        grp[g["lat"]][idx] = clat
        grp[g["lon"]][idx] = clon


def _make_smap(path, row, col, vals, full):
    with h5py.File(path, "w") as f:
        _smap_datasets(f, row, col, vals, full)


@pytest.mark.parametrize("full", [True, False])
def test_smap_extract_full_and_subset(tmp_path, full):
    row, col, clat, clon = smap.pixel_index(LAT, LON)
    p = tmp_path / "s.h5"
    _make_smap(p, row, col, {"am": (0.27, 0), "pm": (0.31, 8)}, full)
    with h5py.File(p, "r") as h5:
        out = smap.extract_point(h5, row, col, clat, clon)
    assert out["sm_am"] == pytest.approx(0.27) and out["qual_am"] == 0
    assert out["sm_pm"] == pytest.approx(0.31) and out["qual_pm"] == 8


def test_smap_extract_fill_values_become_nan(tmp_path):
    row, col, clat, clon = smap.pixel_index(LAT, LON)
    p = tmp_path / "s.h5"
    _make_smap(p, row, col, {"am": (-9999.0, 65534), "pm": (0.2, 1)}, full=False)
    with h5py.File(p, "r") as h5:
        out = smap.extract_point(h5, row, col, clat, clon)
    assert np.isnan(out["sm_am"]) and np.isnan(out["qual_am"])
    assert out["sm_pm"] == pytest.approx(0.2) and out["qual_pm"] == 1


def test_smap_extract_wrong_pixel_index_raises(tmp_path):
    row, col, clat, clon = smap.pixel_index(LAT, LON)
    p = tmp_path / "s.h5"
    _make_smap(p, row + 1, col, {"am": (0.2, 0), "pm": (0.2, 0)}, full=False)   # indice != atteso
    with h5py.File(p, "r") as h5, pytest.raises(ValueError, match="indice di riga"):
        smap.extract_point(h5, row, col, clat, clon)


def test_smap_good_mean_uses_only_recommended_quality():
    nan = float("nan")
    assert smap.good_mean(0.2, 0, 0.4, 8) == pytest.approx(0.3)     # 0 e 8 sono buoni
    assert smap.good_mean(0.2, 1, 0.4, 0) == pytest.approx(0.4)     # bit 0 = non raccomandato
    assert smap.good_mean(0.2, 4, 0.4, 3) is not None and np.isnan(smap.good_mean(0.2, 4, 0.4, 3))
    assert np.isnan(smap.good_mean(nan, nan, nan, nan))
    assert np.isnan(smap.good_mean(nan, 0, 0.3, nan))               # umidita' mancante


def test_smap_constraint_covers_both_passes():
    ce = smap.constraint(234, 2035)
    assert "/Soil_Moisture_Retrieval_Data_AM/soil_moisture[234][2035]" in ce
    assert "/Soil_Moisture_Retrieval_Data_PM/soil_moisture_pm[234][2035]" in ce
    assert "/Soil_Moisture_Retrieval_Data_PM/retrieval_qual_flag_pm[234][2035]" in ce


# ---------------------------------------------------------------- ripresa da cache parziale

def _granule(day: dt.date, concept="G1"):
    return {"meta": {"concept-id": f"{concept}-{day}"},
            "umm": {"TemporalExtent": {"RangeDateTime": {
                        "BeginningDateTime": f"{day}T00:00:00.000Z"}},
                    "RelatedUrls": [{"Type": "USE SERVICE API",
                                     "URL": f"https://opendap.earthdata.nasa.gov/g/{day}"}]}}


def _days(a, b):
    out, d = [], a
    while d <= b:
        out.append(d)
        d += dt.timedelta(days=1)
    return out


@pytest.fixture
def fake_net(monkeypatch):
    """Login e ricerca CMR finti; registra le chiamate. Le estrazioni le fornisce il test."""
    calls = {"login": 0, "search": [], "extract": []}
    monkeypatch.setattr(earthdata, "login", lambda: calls.__setitem__("login", calls["login"] + 1))

    def search(short_name, version, start, end):
        calls["search"].append((short_name, version, start, end))
        return [_granule(d) for d in _days(start, end)]

    monkeypatch.setattr(earthdata, "search_granules", search)
    return calls


def _fake_row(fake_net, fail):
    st = imerg.stencil(LAT, LON)
    cols = [c["column"] for c in st["cells"]]

    def row(granule, stencil):
        d = earthdata.granule_date(granule)
        fake_net["extract"].append(d)
        if d == fail["day"]:
            raise RuntimeError("rete caduta")
        v = float(d.day) if d.day != 2 else float("nan")
        # quarta cella (nord-est) = d.day + 4; la prima mancante il 5
        vals = [v, v, v, v + 4.0]
        if d.day == 5:
            vals[0] = float("nan")
        return {"date": d, **dict(zip(cols, vals))}

    return row


def test_imerg_resume_from_partial_year(fake_net, monkeypatch):
    fail = {"day": dt.date(2020, 1, 3)}
    monkeypatch.setattr(imerg, "_row_from_subset", _fake_row(fake_net, fail))
    s, e = dt.date(2020, 1, 1), dt.date(2020, 1, 5)

    out = imerg.fetch(LAT, LON, s, e)                    # 1a corsa: un granulo fallisce
    assert fake_net["login"] == 1
    raw = cache.raw_dir("imerg", LAT, LON) / "imerg_2020.csv"
    meta = cache.read_meta(raw)
    assert meta["params"]["complete"] is False and meta["params"]["n_rows"] == 4
    assert meta["product"] == "GPM_3IMERGDF" and meta["version"] == "07"
    p = meta["params"]
    assert [(c["lat"], c["lon"], c["weight"]) for c in p["cells"]] == [
        (45.15, 9.95, 0.25), (45.25, 9.95, 0.25), (45.15, 10.05, 0.25), (45.25, 10.05, 0.25)]
    assert p["nearest_column"] == "precip_lat45.250_lon10.050" and "bilineare" in p["interpolation"]
    assert list(pd.read_csv(raw, nrows=0).columns) == ["date"] + [c["column"] for c in p["cells"]]
    assert p["variable"] == "precipitation" and p["units"] == "mm/day"
    assert p["doi"] == "10.5067/GPM/IMERGDF/DAY/07"

    fake_net["extract"].clear()
    fail["day"] = None
    imerg.fetch(LAT, LON, s, e)                          # 2a corsa: solo il granulo mancante
    assert fake_net["extract"] == [dt.date(2020, 1, 3)]
    assert cache.read_meta(raw)["params"]["complete"] is True

    n_search = len(fake_net["search"])
    fake_net["extract"].clear()
    imerg.fetch(LAT, LON, s, e)                          # 3a corsa: anno completo, niente rete
    assert fake_net["extract"] == [] and len(fake_net["search"]) == n_search

    imerg.fetch(LAT, LON, s, e, force=True)              # force: si riscarica tutto
    assert len(fake_net["extract"]) == 5

    df = imerg.load(LAT, LON)
    assert list(df.columns) == ["date", "rain_mm", "rain_mm_nearest", "n_cells_valid"] and len(df) == 5
    assert out == cache.processed_dir(LAT, LON) / "imerg_daily.csv"
    d = df.set_index(df["date"].dt.strftime("%Y-%m-%d"))
    assert np.isnan(d.loc["2020-01-02", "rain_mm"]) and d.loc["2020-01-02", "n_cells_valid"] == 0
    assert d.loc["2020-01-04", "rain_mm"] == pytest.approx(5.0)       # (4+4+4+8)/4
    assert d.loc["2020-01-04", "rain_mm_nearest"] == 8.0
    assert np.isnan(d.loc["2020-01-05", "rain_mm"]) and d.loc["2020-01-05", "n_cells_valid"] == 3
    assert d.loc["2020-01-05", "rain_mm_nearest"] == 9.0               # cella mancante, nearest intatta


def test_imerg_old_single_cell_raw_is_rejected_and_redownloaded(fake_net, monkeypatch):
    raw_dir = cache.raw_dir("imerg", LAT, LON)
    old = raw_dir / "imerg_2020.csv"
    pd.DataFrame({"date": ["2020-01-01", "2020-01-02", "2020-01-03"],
                  "precipitation": [1.0, 2.0, 3.0]}).to_csv(old, index=False)
    cache.write_meta(old, source="imerg", product="GPM_3IMERGDF", version="07", url="x",
                     params={"complete": True, "window_start": "2020-01-01", "window_end": "2020-01-03",
                             "cell_center_lat": 45.25, "cell_center_lon": 10.05, "year": 2020, "n_rows": 3})
    with pytest.raises(cache.CacheMiss):                 # il vecchio file non basta a costruire l'elaborato
        imerg.build_processed(LAT, LON)
    monkeypatch.setattr(imerg, "_row_from_subset", _fake_row(fake_net, {"day": None}))
    imerg.fetch(LAT, LON, dt.date(2020, 1, 1), dt.date(2020, 1, 3))
    assert fake_net["extract"] == [dt.date(2020, 1, d) for d in (1, 2, 3)]   # riscaricato, non riusato
    assert "precipitation" not in pd.read_csv(old, nrows=0).columns
    assert cache.read_meta(old)["params"]["format"] == imerg.RAW_FORMAT
    assert len(imerg.load(LAT, LON)) == 3


def test_smap_fetch_builds_processed_columns(fake_net, monkeypatch):
    table = {
        dt.date(2020, 6, 1): (0.20, 0, 0.30, 8),
        dt.date(2020, 6, 2): (0.25, 1, 0.35, 1),          # nessun passaggio di qualita' buona
        dt.date(2020, 6, 3): (float("nan"), float("nan"), 0.40, 0),
    }

    def row(granule, r, c, clat, clon):
        d = earthdata.granule_date(granule)
        a, qa, p, qp = table[d]
        return {"date": d, "sm_am": a, "qual_am": qa, "sm_pm": p, "qual_pm": qp}

    monkeypatch.setattr(smap, "_row_from_subset", row)
    out = smap.fetch(LAT, LON, dt.date(2020, 6, 1), dt.date(2020, 6, 3))
    df = smap.load(LAT, LON)
    assert out.name == "smap_daily.csv"
    assert list(df.columns) == ["date", "sm_am", "qual_am", "sm_pm", "qual_pm", "sm_good_mean"]
    assert df["sm_good_mean"].iloc[0] == pytest.approx(0.25)
    assert np.isnan(df["sm_good_mean"].iloc[1])
    assert df["sm_good_mean"].iloc[2] == pytest.approx(0.40)
    raw = cache.raw_dir("smap", LAT, LON) / "smap_2020.csv"
    meta = cache.read_meta(raw)
    assert meta["product"] == "SPL3SMP_E" and meta["version"] == "006"
    assert (meta["params"]["ease_row"], meta["params"]["ease_col"]) == (234, 2035)
    assert meta["params"]["pixel_center_lat"] == pytest.approx(45.2433, abs=1e-4)
    assert meta["params"]["doi"] == "10.5067/M20OXIZHY3RJ"


def test_all_extractions_failing_stops_and_keeps_nothing_complete(fake_net, monkeypatch):
    def row(*a):
        raise RuntimeError("giu'")

    monkeypatch.setattr(imerg, "_row_from_subset", row)
    with pytest.raises(earthdata.EarthdataRequestError, match="tutte le"):
        imerg.fetch(LAT, LON, dt.date(2020, 1, 1), dt.date(2020, 1, 3))


def test_auth_error_during_extraction_propagates(fake_net, monkeypatch):
    def row(*a):
        raise earthdata.EarthdataAuthError("401")

    monkeypatch.setattr(smap, "_row_from_subset", row)
    with pytest.raises(earthdata.EarthdataAuthError):
        smap.fetch(LAT, LON, dt.date(2020, 6, 1), dt.date(2020, 6, 2))


# ---------------------------------------------------------------- offline e cache

def test_offline_error_before_any_network(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")

    def boom(*a, **k):
        raise AssertionError("rete o login chiamati in modalita' offline")

    monkeypatch.setattr(earthdata, "login", boom)
    monkeypatch.setattr(earthdata, "search_granules", boom)
    for mod in (imerg, smap):
        with pytest.raises(cache.OfflineError):
            mod.fetch(LAT, LON)


def test_load_cache_miss():
    for mod in (imerg, smap):
        with pytest.raises(cache.CacheMiss):
            mod.load(LAT, LON)


def test_build_processed_without_raw_is_cache_miss():
    with pytest.raises(cache.CacheMiss):
        imerg.build_processed(LAT, LON)
    with pytest.raises(cache.CacheMiss):
        smap.build_processed(LAT, LON)


# ---------------------------------------------------------------- tentativi e parallelismo

def test_with_retry_backoff_and_failure():
    waits = []
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 4:
            raise OSError("temporaneo")
        return "ok"

    assert earthdata.with_retry(flaky, tries=5, wait=1.0, sleep=waits.append) == "ok"
    assert waits == [1.0, 2.0, 4.0]
    with pytest.raises(earthdata.EarthdataRequestError):
        earthdata.with_retry(lambda: (_ for _ in ()).throw(OSError("x")), tries=2,
                             wait=0.0, sleep=lambda s: None)


def test_with_retry_does_not_retry_auth_errors():
    n = {"i": 0}

    def bad():
        n["i"] += 1
        raise earthdata.EarthdataAuthError("401")

    with pytest.raises(earthdata.EarthdataAuthError):
        earthdata.with_retry(bad, tries=5, no_retry=(earthdata.EarthdataAuthError,),
                             sleep=lambda s: None)
    assert n["i"] == 1


def test_run_parallel_never_exceeds_eight_workers():
    lock, state = threading.Lock(), {"now": 0, "max": 0}

    def work(i):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.01)
        with lock:
            state["now"] -= 1
        if i == 3:
            raise ValueError("uno")
        return i

    res = earthdata.run_parallel(work, range(40), workers=100)
    assert state["max"] <= 8
    assert len(res) == 40 and sum(1 for _, _, e in res if e is not None) == 1
