"""Test del client ECOSTRESS (AppEEARS): senza rete, senza credenziali vere, cache temporanea."""
from __future__ import annotations

import json

import pandas as pd
import pytest

from fieldwise import config
from fieldwise.data import cache, ecostress

P = "ECO_L3T_JET_002_"
HEADER = ("Category,ID,Latitude,Longitude,Date,ECOSTRESS_Tile,"
          f"{P}ETdaily,{P}ETinstUncertainty,{P}PTJPLSMinst,{P}cloud,{P}water")
ROWS = [
    # valido
    "WC,P01,45.1,9.9,2019-07-10 12:00:00 UTC,32TNR,3.5,20.0,30.0,0.0,0.0",
    # stesso passaggio, altra tile (punto sul bordo): si tiene
    "WC,P01,45.1,9.9,2019-07-10 12:00:00 UTC,32TPR,3.7,21.0,31.0,0.0,0.0",
    # 23:30 UTC di luglio = 01:30 del giorno dopo a Roma (UTC+2)
    "WC,P02,45.2,9.8,2019-07-10 23:30:00 UTC,32TNR,2.0,10.0,15.0,0.0,0.0",
    # nube (con valore mancante)
    "WC,P02,45.2,9.8,2019-07-12 10:00:00 UTC,32TNR,,,,1.0,0.0",
    # acqua
    "WC,P02,45.2,9.8,2019-07-14 10:00:00 UTC,32TNR,0.5,5.0,5.0,0.0,1.0",
    # senza valore e senza nube
    "WC,P03,45.3,9.7,2019-07-15 10:00:00 UTC,32TNR,,,,0.0,0.0",
]
SECRET = "parola-segreta-di-prova"


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path / "processed")
    monkeypatch.setenv("FIELDWISE_OFFLINE", "0")
    monkeypatch.setattr(ecostress.time, "sleep", lambda s: None)
    return tmp_path


def put_raw(name="x-results.csv", rows=ROWS):
    raw = ecostress.raw_dir()
    f = raw / name
    f.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    cache.write_meta(f, source="AppEEARS (LP DAAC)", product=ecostress.PRODUCT,
                     version=ecostress.VERSION, url="https://esempio.invalid/x")
    return f


class NoNetwork:
    """requests.post/get/Session sostituiti: qualsiasi chiamata fa fallire il test."""
    def __call__(self, *a, **k):
        raise AssertionError("rete usata")


def block_network(monkeypatch):
    monkeypatch.setattr(ecostress.requests, "post", NoNetwork())
    monkeypatch.setattr(ecostress.requests, "get", NoNetwork())
    monkeypatch.setattr(ecostress.requests, "Session", NoNetwork())


# ---------------------------------------------------------------- load / CacheMiss
def test_load_senza_cache_solleva_cachemiss_e_non_usa_la_rete(monkeypatch):
    block_network(monkeypatch)
    with pytest.raises(cache.CacheMiss, match="ecostress"):
        ecostress.load()
    # non crea cartelle in lettura
    assert not (config.PROCESSED_DIR / ecostress.KEY).exists()


def test_build_processed_senza_grezzi_solleva_cachemiss():
    with pytest.raises(cache.CacheMiss):
        ecostress.build_processed()


def test_grezzo_senza_meta_non_e_valido():
    f = put_raw()
    cache.meta_path(f).unlink()
    with pytest.raises(cache.CacheMiss):
        ecostress.build_processed()


# ---------------------------------------------------------------- lettura
def test_build_e_load_qualita_data_locale_e_tile(monkeypatch):
    block_network(monkeypatch)
    put_raw()
    out = ecostress.build_processed()
    assert out == config.PROCESSED_DIR / "cremona" / "ecostress_et.csv"
    d = ecostress.load()
    assert list(d.columns) == ecostress.PROCESSED_COLUMNS
    assert len(d) == len(ROWS)                       # le due tile dello stesso passaggio restano
    q = d.set_index(["punto", "data_ora_passaggio", "tile"])["qualita"]
    assert q[("P01", "2019-07-10 12:00:00 UTC", "32TNR")] == "valido"
    assert q[("P01", "2019-07-10 12:00:00 UTC", "32TPR")] == "valido"
    assert q[("P02", "2019-07-12 10:00:00 UTC", "32TNR")] == "nube"
    assert q[("P02", "2019-07-14 10:00:00 UTC", "32TNR")] == "acqua"
    assert q[("P03", "2019-07-15 10:00:00 UTC", "32TNR")] == "senza_valore_non_nube"
    # giorno in ora locale: 23:30 UTC del 10 luglio e' l'11 luglio a Roma
    r = d[(d["punto"] == "P02") & (d["data_ora_passaggio"].str.contains("23:30"))].iloc[0]
    assert r["data"] == pd.Timestamp("2019-07-11") and r["et_mm_giorno"] == pytest.approx(2.0)
    assert d[d["punto"] == "P01"]["data"].eq(pd.Timestamp("2019-07-10")).all()


def test_valid_passages_filtra_qualita_e_anno():
    put_raw(rows=ROWS + ["WC,P01,45.1,9.9,2023-06-01 10:00:00 UTC,32TNR,4.0,20,30,0.0,0.0"])
    ecostress.build_processed()
    d = ecostress.load()
    v = ecostress.valid_passages(d)
    assert set(v["qualita"]) == {"valido"} and len(v) == 4          # 3 del 2019 + 1 del 2023
    assert len(ecostress.valid_passages(d, last_year=2022)) == 3
    assert v["et_mm_giorno"].notna().all()


def test_i_punti_sono_31_con_id_unici_e_nella_provincia():
    ids = [p[0] for p in ecostress.PUNTI]
    assert len(ids) == len(set(ids)) == 31 and ids[0] == "P00"
    assert all(44.9 < lat < 45.5 and 9.5 < lon < 10.5 for _, lat, lon in ecostress.PUNTI)
    b = ecostress.request_body()
    assert b["task_type"] == "point" and len(b["params"]["coordinates"]) == 31
    assert {l["layer"] for l in b["params"]["layers"]} == set(ecostress.LAYERS)
    assert all(l["product"] == "ECO_L3T_JET.002" for l in b["params"]["layers"])


# ---------------------------------------------------------------- offline e cache gia' piena
def test_fetch_offline_senza_cache_non_tocca_la_rete(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    block_network(monkeypatch)
    with pytest.raises(cache.OfflineError):
        ecostress.fetch()


def test_fetch_con_grezzi_in_cache_non_usa_la_rete_nemmeno_offline(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    block_network(monkeypatch)
    put_raw()
    out = ecostress.fetch()
    assert out.exists() and len(ecostress.load()) == len(ROWS)


def test_fetch_force_offline_solleva_offline(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    block_network(monkeypatch)
    put_raw()
    with pytest.raises(cache.OfflineError):
        ecostress.fetch(force=True)


# ---------------------------------------------------------------- credenziali
def test_credenziali_da_netrc_e_mai_nel_messaggio(tmp_path, monkeypatch):
    f = tmp_path / "netrc"
    f.write_text(f"machine {ecostress.EARTHDATA_HOST} login utente-finto password {SECRET}\n")
    monkeypatch.setenv("NETRC", str(f))
    assert ecostress._credentials() == ("utente-finto", SECRET)
    f.write_text("machine altro.host login a password b\n")
    with pytest.raises(RuntimeError) as e:
        ecostress._credentials()
    assert SECRET not in str(e.value)
    monkeypatch.setenv("NETRC", str(tmp_path / "non_esiste"))
    with pytest.raises(RuntimeError, match="credenziali"):
        ecostress._credentials()


class FakeResp:
    def __init__(self, obj=None, content=b"", status=200):
        self._obj, self.content, self.status_code = obj, content, status

    def raise_for_status(self):
        pass

    def json(self):
        return self._obj


class FakeSession:
    """AppEEARS finto: task subito 'done', un CSV di risultati nel bundle."""
    def __init__(self):
        self.calls = []

    def post(self, url, json=None, timeout=None):
        self.calls.append(("post", url))
        return FakeResp({"task_id": "T1", "status": "pending"})

    def get(self, url, timeout=None):
        self.calls.append(("get", url))
        if url.endswith("task/T1"):
            return FakeResp({"status": "done"})
        if url.endswith("bundle/T1"):
            return FakeResp({"files": [{"file_name": "sub/prod-results.csv", "file_id": "F1"},
                                       {"file_name": "sub/immagine.png", "file_id": "F2"}]})
        assert url.endswith("bundle/T1/F1")
        return FakeResp(content=(HEADER + "\n" + "\n".join(ROWS) + "\n").encode())


def test_fetch_completo_con_appeears_finto(monkeypatch):
    s = FakeSession()
    out = ecostress.fetch(session=s)
    assert out.exists() and len(ecostress.load()) == len(ROWS)
    raw = ecostress.raw_dir()
    meta = cache.read_meta(raw / "prod-results.csv")
    assert meta["product"] == "ECO_L3T_JET.002" and meta["params"]["task_id"] == "T1"
    assert meta["params"]["units_ETdaily"] == "mm/giorno"
    assert json.loads((raw / "task.json").read_text())["task_id"] == "T1"
    assert not (raw / "immagine.png").exists()                # solo csv/json/txt/xml
    assert sum(1 for c in s.calls if c[0] == "post") == 1     # un solo task creato
    # seconda chiamata: grezzi in cache, nessuna richiesta
    s2 = FakeSession()
    ecostress.fetch(session=s2)
    assert s2.calls == []
