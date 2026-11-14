"""Test del client ISTAT: nessuna rete, solo cartelle temporanee."""
import pytest

from fieldwise import config
from fieldwise.data import cache, istat

HEADER = ("DATAFLOW,FREQ,REF_AREA,DATA_TYPE,TYPE_OF_CROP,DESTINATION_WINEGRAPES,TIME_PERIOD,"
          "OBS_VALUE,OBS_STATUS,NOTE_DS,NOTE_REF_AREA,NOTE_DATA_TYPE,NOTE_TYPE_OF_CROP_EUCODE,"
          "NOTE_TYPE_OF_CROP,NOTE_DESTINATION_WINEGRAPES,NOTE_TIME_PERIOD,BASE_PER,UNIT_MEAS,UNIT_MULT")
FLOW = "IT1:101_1015_DF_DCSP_COLTIVAZIONI_2(1.0)"


def _row(dtype, crop, year, value):
    return f"{FLOW},A,ITC4A,{dtype},{crop},ALL,{year},{value},,,,,,,,,,,"


FAKE_CSV = "\n".join([
    HEADER,
    _row("ART", "MAIZE", 2012, 38000),
    _row("HP_Q_EXT", "MAIZE", 2012, 3648000),
    _row("TP_QUIN_EXT", "MAIZE", 2012, 3648000),
    _row("ART", "MAIZE", 2022, 22450),
    _row("HP_Q_EXT", "MAIZE", 2022, 2132750),
    _row("ART", "SOYA", 2022, 8360),
    _row("TP_QUIN_EXT", "SOYA", 2022, 292600),          # solo produzione totale
    _row("ART", "COMMEAT", 2022, 8135),
    _row("HP_Q_EXT", "COMMEAT", 2022, 569450),
    _row("ART", "APPLE", 2022, 28),                       # coltura non richiesta
    _row("HP_Q_EXT", "APPLE", 2022, 100),
]) + "\n"


class FakeClock:
    def __init__(self):
        self.t = 1000.0
        self.sleeps = []

    def time(self):
        return self.t

    def sleep(self, s):
        self.sleeps.append(s)
        self.t += s


class FakeResponse:
    def __init__(self, status=200, content=b""):
        self.status_code = status
        self.content = content


class FakeSession:
    def __init__(self, responses, clock=None):
        self.responses = list(responses)
        self.calls = []
        self.clock = clock

    def get(self, url, headers=None, timeout=None):
        self.calls.append((self.clock.t if self.clock else None, url))
        return self.responses.pop(0)


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.delenv("FIELDWISE_OFFLINE", raising=False)
    monkeypatch.setattr(istat, "_LIMITER", None)
    return tmp_path


@pytest.fixture
def clock():
    return FakeClock()


def _limiter(clock):
    return istat.RateLimiter(15.0, clock=clock.time, sleep=clock.sleep)


# ---------------------------------------------------------------- elaborazione

def test_quintals_to_tonnes_and_yield():
    df = istat.parse_sdmx_csv(FAKE_CSV)
    r = df[(df.crop == "mais") & (df.year == 2012)].iloc[0]
    assert r.production_t == pytest.approx(364800.0)       # 3.648.000 q x 0,1
    assert r.area_ha == 38000
    assert r.yield_t_ha == pytest.approx(9.6)               # 364800 t / 38000 ha
    assert list(df.columns) == istat.COLUMNS
    assert df.dataflow.iloc[0] == "101_1015_DF_DCSP_COLTIVAZIONI_2(1.0)"
    assert "calcolata" in r.note and "umidita" in r.note


def test_only_requested_crops_and_names():
    df = istat.parse_sdmx_csv(FAKE_CSV)
    assert set(df.crop) == {"mais", "soia", "frumento"}
    y22 = df[df.year == 2022].set_index("crop").yield_t_ha
    assert y22["mais"] == pytest.approx(2132750 * 0.1 / 22450)
    assert y22["frumento"] == pytest.approx(7.0)


def test_total_production_fallback_is_noted():
    df = istat.parse_sdmx_csv(FAKE_CSV)
    r = df[df.crop == "soia"].iloc[0]
    assert r.production_t == pytest.approx(29260.0)
    assert r.yield_t_ha == pytest.approx(3.5)
    assert "produzione totale" in r.note


def test_zero_or_missing_area_gives_nan_yield():
    csv = "\n".join([HEADER, _row("ART", "MAIZE", 2020, 0), _row("HP_Q_EXT", "MAIZE", 2020, 10)])
    df = istat.parse_sdmx_csv(csv)
    assert df.yield_t_ha.isna().all()


# ------------------------------------------------------------ limitatore

def test_rate_limiter_enforces_15s(clock):
    lim = _limiter(clock)
    lim.wait()
    clock.t += 4
    lim.wait()
    clock.t += 20            # gia' oltre 15 s: nessuna attesa
    lim.wait()
    assert clock.sleeps == [pytest.approx(11.0)]
    assert lim.min_interval >= 15


def test_rate_limiter_across_processes(clock, tmp_path):
    state = tmp_path / "last.txt"
    istat.RateLimiter(15.0, clock=clock.time, sleep=clock.sleep, state_file=state).wait()
    clock.t += 5
    istat.RateLimiter(15.0, clock=clock.time, sleep=clock.sleep, state_file=state).wait()
    assert clock.sleeps == [pytest.approx(10.0)]


def test_retries_also_respect_the_interval(clock):
    sess = FakeSession([FakeResponse(500), FakeResponse(503), FakeResponse(200, b"ok")], clock)
    out = istat.http_get("http://x", session=sess, lim=_limiter(clock))
    assert out == b"ok"
    times = [t for t, _ in sess.calls]
    assert len(times) == 3
    assert all(b - a >= 15 for a, b in zip(times, times[1:]))


def test_http_429_stops_without_retry(clock):
    sess = FakeSession([FakeResponse(429), FakeResponse(200, b"ok")], clock)
    with pytest.raises(istat.IstatError, match="429"):
        istat.http_get("http://x", session=sess, lim=_limiter(clock))
    assert len(sess.calls) == 1


# ----------------------------------------------------------------- cache

def test_fetch_saves_raw_with_meta_and_never_repeats(tmp_cache, clock):
    sess = FakeSession([FakeResponse(200, FAKE_CSV.encode()), FakeResponse(200, FAKE_CSV.encode())], clock)
    p = istat.fetch("Cremona", session=sess, lim=_limiter(clock))
    assert p.parent == config.RAW_DIR / "istat" / "cremona"
    meta = cache.read_meta(p)
    assert meta["version"] == "1.0"
    assert "101_1015_DF_DCSP_COLTIVAZIONI_2" in meta["product"]
    assert meta["url"].endswith("/A.ITC4A...")
    # seconda chiamata: dalla cache, nessuna richiesta
    assert istat.fetch("Cremona", session=sess, lim=_limiter(clock)) == p
    assert len(sess.calls) == 1
    # force: nuova richiesta
    istat.fetch("Cremona", force=True, session=sess, lim=_limiter(clock))
    assert len(sess.calls) == 2


def test_fetch_rejects_non_csv_answer(tmp_cache, clock):
    sess = FakeSession([FakeResponse(200, b"<html>errore</html>")], clock)
    with pytest.raises(istat.IstatError):
        istat.fetch("Cremona", session=sess, lim=_limiter(clock))
    assert not cache.is_cached(istat.raw_path("Cremona"))


def test_load_writes_processed_csv(tmp_cache, clock):
    sess = FakeSession([FakeResponse(200, FAKE_CSV.encode())], clock)
    istat.fetch("Cremona", session=sess, lim=_limiter(clock))
    df = istat.load("Cremona")
    out = config.PROCESSED_DIR / "cremona" / "istat_yields.csv"
    assert out.exists()
    assert len(df) == 4
    import pandas as pd
    assert list(pd.read_csv(out).columns) == istat.COLUMNS


def test_offline_error(tmp_cache, monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    with pytest.raises(cache.OfflineError):
        istat.fetch("Cremona")


def test_cache_miss(tmp_cache):
    with pytest.raises(cache.CacheMiss):
        istat.load("Cremona")


def test_unknown_province(tmp_cache):
    with pytest.raises(ValueError):
        istat.fetch("Atlantide")
