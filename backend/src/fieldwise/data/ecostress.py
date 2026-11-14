"""ECOSTRESS evapotraspirazione giornaliera (ECO_L3T_JET.002, 70 m) per punti, via AppEEARS (LP DAAC).

Prodotto: ``ECO_L3T_JET`` versione ``002`` (Collection 2, ECOSTRESS Tiled Evapotranspiration
Ensemble). Layer richiesti: ``ETdaily`` (evapotraspirazione giornaliera), ``ETinstUncertainty``,
``PTJPLSMinst``, ``cloud``, ``water``. Pixel 70 m, passaggi a orari variabili (la ISS non e'
eliosincrona), dal 2018-07 (inizio della richiesta 2018-07-01; fine 2022-12-31, cioe' l'ultimo
anno con pioggia POWER affidabile, vedi ``reports/validation.md``).

**Unita' di ETdaily: mm/giorno.** Guida utente "ECOSTRESS Collection 2 Level-1-2-3-4 Gridded and
Tiled Data Products User Guide", versione 2 (4 aprile 2023, G. Halverson; LP DAAC), par. 5.4,
p. 16: la mediana dei quattro modelli "is upscaled to a daily ET estimate in millimeters per day
and recorded in the L3T JET product as ETdaily"; ETdaily "represents the integrated ET between
sunrise and sunset". **Incoerenza della documentazione:** la tabella 10 della stessa guida e il
catalogo del prodotto (.002, AppEEARS/Earthdata) raggruppano ETdaily sotto "W m-2". Qui vale la
lettura del testo (mm/giorno), l'unica compatibile con i valori (0-5,8, ciclo stagionale); la
lettura in W m-2 medi darebbe circa 0,09 mm/giorno in piena estate, impossibile per un mais.
Le correlazioni non dipendono dall'unita'; lo scarto medio si'. Non verificato con un altro
canale (es. paper di validazione): solo il testo della guida.

Qualita' (colonna ``qualita`` dell'elaborato): ``nube`` (maschera ``cloud`` = 1), ``acqua``
(``water`` = 1), ``senza_valore_non_nube`` (nessun valore di ETdaily) e ``valido``. Solo i
``valido`` vanno usati. ETdaily e' una stima modellata (mediana di quattro modelli, par. 5.4) e non
una misura: errore dichiarato in letteratura dell'ordine di 1,5 mm/giorno sui valori giornalieri
(non riletto in questa sessione).

Punti: 31 (``PUNTI``): il pilota (45,2; 10,0) e 30 punti a caso (seme 20261114) su pixel a 10 m
di ESA WorldCover 2021 v200 classe 40 (seminativo) dentro la provincia di Cremona. Non sono
campi noti: la coltura di ogni punto-anno non e' un dato di questo client.

Accesso: AppEEARS (https://appeears.earthdatacloud.nasa.gov/api/), richiesta ``point``. Login
con le credenziali Earthdata di ``~/.netrc`` (host ``urs.earthdata.nasa.gov``, lette col modulo
``netrc``, mai stampate ne' scritte nei metadati). Il file indicato dalla variabile ``NETRC``
ha la precedenza. ``fetch()`` non fa rete se i grezzi sono gia' in cache (senza ``force``).

Cache (contratto in ``fieldwise.data.cache``): grezzi in ``data/raw/ecostress/cremona/`` (CSV dei
risultati, XML dei metadati, richiesta, lista dei granuli, ciascuno col suo ``.meta.json``);
elaborato in ``data/processed/cremona/ecostress_et.csv`` con ``build_processed()``.

Uso::

    python -m fieldwise.data.ecostress            # scarica (se manca) e ricostruisce l'elaborato
    python -m fieldwise.data.ecostress --rebuild  # solo l'elaborato, dai grezzi, senza rete
"""
from __future__ import annotations

import argparse
import json
import netrc
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from . import cache

API = "https://appeears.earthdatacloud.nasa.gov/api/"
PRODUCT = "ECO_L3T_JET.002"
SHORT_NAME = "ECO_L3T_JET"
VERSION = "002"
SOURCE = "ecostress"
KEY = "cremona"
LAYERS = ("ETdaily", "ETinstUncertainty", "PTJPLSMinst", "cloud", "water")
EARTHDATA_HOST = "urs.earthdata.nasa.gov"
START = "07-01-2018"          # formato AppEEARS MM-GG-AAAA
END = "12-31-2022"
UNITS = "mm/giorno"
PROCESSED_NAME = "ecostress_et.csv"
STATE_NAME = "task.json"
TIMEZONE = "Europe/Rome"
ORIGINE = "WorldCover2021_v200_cl40_seme20261114"

# (id, lat, lon): pilota + 30 punti a caso su seminativi (WorldCover 2021, classe 40)
PUNTI = (
    ("P00", 45.2, 10.0),
    ("P01", 45.160458, 9.929292), ("P02", 45.342458, 9.637042), ("P03", 45.331708, 9.868875),
    ("P04", 45.212625, 10.141125), ("P05", 45.326375, 9.885625), ("P06", 45.304792, 9.682542),
    ("P07", 45.256292, 9.753792), ("P08", 45.225875, 9.801542), ("P09", 45.162458, 10.171125),
    ("P10", 45.215875, 10.319625), ("P11", 45.319458, 9.923958), ("P12", 45.086375, 10.328125),
    ("P13", 45.235875, 9.833958), ("P14", 45.225125, 9.996875), ("P15", 45.307708, 9.906875),
    ("P16", 45.169125, 10.265292), ("P17", 45.075542, 10.126125), ("P18", 45.125542, 10.126625),
    ("P19", 45.244125, 10.071042), ("P20", 45.204875, 10.238792), ("P21", 45.163125, 10.111125),
    ("P22", 45.185708, 9.955542), ("P23", 45.207375, 9.932042), ("P24", 45.253625, 9.739625),
    ("P25", 45.299792, 9.939542), ("P26", 45.026625, 10.260792), ("P27", 45.269292, 9.875458),
    ("P28", 45.138125, 10.252292), ("P29", 45.285542, 9.780958), ("P30", 45.255375, 9.871875),
)

PROCESSED_COLUMNS = ["punto", "data_ora_passaggio", "tile", "data", "et_mm_giorno", "et_incertezza_wm2",
                     "et_ptjpl_sm_inst_wm2", "nubi", "acqua", "qualita"]
_PREFIX = "ECO_L3T_JET_002_"


# ----------------------------------------------------------------------------------
# percorsi
# ----------------------------------------------------------------------------------

def raw_dir(create: bool = True) -> Path:
    return cache.raw_dir(SOURCE, key=KEY, create=create)


def processed_path(create: bool = True) -> Path:
    return cache.processed_dir(key=KEY, create=create) / PROCESSED_NAME


def _results_files() -> list[Path]:
    return [f for f in sorted(raw_dir(create=False).glob("*results.csv")) if cache.is_cached(f)]


# ----------------------------------------------------------------------------------
# elaborazione (nessuna rete)
# ----------------------------------------------------------------------------------

def _col(d: pd.DataFrame, name: str):
    return d[_PREFIX + name] if (_PREFIX + name) in d.columns else pd.Series(np.nan, index=d.index)


def parse_results(d: pd.DataFrame) -> pd.DataFrame:
    """Dal CSV dei risultati AppEEARS alla tabella elaborata (una riga per punto e passaggio).

    ``data_ora_passaggio`` e' in UTC come nel CSV ("AAAA-MM-GG hh:mm:ss UTC"); ``data`` e' il
    giorno in ora locale (Europe/Rome), che e' il giorno a cui riferire l'ET giornaliera.
    Un punto sul bordo tra due tile compare due volte per lo stesso passaggio (tile diverse,
    valori leggermente diversi): le righe si tengono entrambe, come nelle prove, e ``tile`` le
    distingue (2457 righe su 20194, il 12%).
    """
    et = pd.to_numeric(_col(d, "ETdaily"), errors="coerce")
    nubi = pd.to_numeric(_col(d, "cloud"), errors="coerce")
    acqua = pd.to_numeric(_col(d, "water"), errors="coerce")
    out = pd.DataFrame({
        "punto": d["ID"].astype(str),
        "data_ora_passaggio": d["Date"].astype(str),
        "tile": d["ECOSTRESS_Tile"].astype(str) if "ECOSTRESS_Tile" in d.columns else "",
        "et_mm_giorno": et,
        "et_incertezza_wm2": pd.to_numeric(_col(d, "ETinstUncertainty"), errors="coerce"),
        "et_ptjpl_sm_inst_wm2": pd.to_numeric(_col(d, "PTJPLSMinst"), errors="coerce"),
        "nubi": nubi, "acqua": acqua})
    t = pd.to_datetime(out["data_ora_passaggio"].str.replace(" UTC", "", regex=False), utc=True)
    out["data"] = t.dt.tz_convert(TIMEZONE).dt.tz_localize(None).dt.normalize()
    out["qualita"] = np.where(nubi == 1, "nube", np.where(acqua == 1, "acqua", np.where(
        et.isna(), "senza_valore_non_nube", "valido")))
    return out[PROCESSED_COLUMNS]


def build_processed() -> Path:
    """Unisce i CSV grezzi dei risultati in ``ecostress_et.csv``. CacheMiss se non ce ne sono."""
    fs = _results_files()
    if not fs:
        raise cache.CacheMiss(f"nessun CSV dei risultati ECOSTRESS in cache in {raw_dir(create=False)}"
                              " - per scaricarlo: python -m fieldwise.data.ecostress")
    d = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
    out = parse_results(d).drop_duplicates(["punto", "data_ora_passaggio", "tile"], keep="last")
    out = out.sort_values(["punto", "data_ora_passaggio", "tile"]).reset_index(drop=True)
    p = processed_path()
    out.to_csv(p, index=False, date_format="%Y-%m-%d")
    return p


def load() -> pd.DataFrame:
    """Legge ``ecostress_et.csv`` dalla cache (mai la rete). CacheMiss se manca.

    Una riga per punto e passaggio; solo ``qualita == "valido"`` e' utilizzabile (vedi
    ``valid_passages``).
    """
    p = processed_path(create=False)
    if not p.exists():
        raise cache.CacheMiss(f"dato non in cache: {p} - per ricostruirlo dai grezzi o scaricarlo: "
                              "python -m fieldwise.data.ecostress")
    return pd.read_csv(p, parse_dates=["data"])


def valid_passages(df: pd.DataFrame, last_year: int | None = None) -> pd.DataFrame:
    """Passaggi con ET valida (non nube, non acqua, con valore), eventualmente fino a ``last_year``."""
    v = df[(df["qualita"] == "valido") & df["et_mm_giorno"].notna()].copy()
    if last_year is not None:
        v = v[v["data"].dt.year <= last_year]
    return v.reset_index(drop=True)


# ----------------------------------------------------------------------------------
# AppEEARS
# ----------------------------------------------------------------------------------

def _credentials() -> tuple[str, str]:
    """(utente, password) Earthdata da ~/.netrc (o dal file in NETRC). Mai stampati."""
    try:
        auth = netrc.netrc(os.environ.get("NETRC") or None).authenticators(EARTHDATA_HOST)
    except (FileNotFoundError, netrc.NetrcParseError) as exc:
        raise RuntimeError(f"credenziali Earthdata non leggibili da ~/.netrc ({type(exc).__name__}): "
                           f"servono una riga 'machine {EARTHDATA_HOST} login <utente> password <...>'") from None
    if not auth or not auth[0] or not auth[2]:
        raise RuntimeError(f"nessuna credenziale per {EARTHDATA_HOST} in ~/.netrc")
    return auth[0], auth[2]


def _retry(fn, tries: int = 6, wait: float = 2.0, what: str = "operazione"):
    err = None
    for i in range(tries):
        try:
            return fn()
        except Exception as exc:     # noqa: BLE001 - rete, 429, 5xx
            err = exc
            time.sleep(min(60.0, wait * 2 ** i))
    raise RuntimeError(f"{what} fallita dopo {tries} tentativi: {type(err).__name__}: {str(err)[:200]}")


def _session() -> requests.Session:
    cache.ensure_online("AppEEARS")
    user, pwd = _credentials()
    r = _retry(lambda: requests.post(API + "login", auth=(user, pwd), timeout=60), what="login AppEEARS")
    r.raise_for_status()
    s = requests.Session()
    s.headers["Authorization"] = "Bearer " + r.json()["token"]
    return s


def request_body(punti=PUNTI) -> dict:
    return {"task_type": "point", "task_name": "fieldwise_ecostress_jet_cremona",
            "params": {"dates": [{"startDate": START, "endDate": END}],
                       "layers": [{"product": PRODUCT, "layer": layer} for layer in LAYERS],
                       "coordinates": [{"id": i, "longitude": float(lon), "latitude": float(lat),
                                        "category": ORIGINE[:30]} for i, lat, lon in punti]}}


def _submit(s, state: Path) -> str:
    if state.exists():
        return json.loads(state.read_text())["task_id"]
    body = request_body()
    r = _retry(lambda: s.post(API + "task", json=body, timeout=120), what="invio del task AppEEARS")
    r.raise_for_status()
    tid = r.json()["task_id"]
    state.write_text(json.dumps({"task_id": tid, "body": body}))
    return tid


def _wait_and_download(s, tid: str, raw: Path, max_minutes: float):
    t0 = time.time()
    wait = 30.0
    while True:
        r = _retry(lambda: s.get(API + "task/" + tid, timeout=60), what="stato del task")
        if r.status_code == 401:
            s = _session()
            continue
        j = r.json()
        stato = j.get("status")
        if stato == "done":
            break
        if stato in ("error", "deleted") or (time.time() - t0) / 60.0 > max_minutes:
            raise RuntimeError(f"task AppEEARS fermo: stato {stato}")
        time.sleep(wait)
        wait = min(300.0, wait * 1.5)
    bundle = _retry(lambda: s.get(API + "bundle/" + tid, timeout=60), what="elenco file").json()
    for f in bundle["files"]:
        name = Path(f["file_name"]).name
        if not name.endswith((".csv", ".json", ".txt", ".xml")):
            continue
        dst = raw / name
        url = API + f"bundle/{tid}/{f['file_id']}"
        rr = _retry(lambda: s.get(url, timeout=600), what=f"download di {name}")
        rr.raise_for_status()
        dst.write_bytes(rr.content)
        cache.write_meta(dst, source="AppEEARS (LP DAAC)", product=PRODUCT, version=VERSION, url=url,
                         params={"task_id": tid, "layers": list(LAYERS), "dates": [START, END],
                                 "units_ETdaily": UNITS},
                         notes="ETdaily in mm/giorno (guida utente Collection 2 v2, par. 5.4 p. 16); "
                               "tab. 10 e catalogo dicono W m-2")


def fetch(force: bool = False, max_minutes: float = 240.0, session=None) -> Path:
    """Scarica (se manca) il task AppEEARS e scrive ``ecostress_et.csv``. Ritorna il suo percorso.

    Con i grezzi gia' in cache e senza ``force`` non fa nessuna richiesta di rete (e non
    controlla ``FIELDWISE_OFFLINE``). Altrimenti chiama ``cache.ensure_online()`` prima del
    login. Il task e' ripreso da ``task.json`` se gia' inviato (riprendibile).
    """
    if _results_files() and not force:
        return build_processed()
    cache.ensure_online("AppEEARS ECO_L3T_JET.002")
    raw = raw_dir()
    state = raw / STATE_NAME
    if force and state.exists():
        state.unlink()
    s = session or _session()
    tid = _submit(s, state)
    _wait_and_download(s, tid, raw, max_minutes)
    return build_processed()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ECOSTRESS ET (ECO_L3T_JET.002) per i punti del Cremonese.")
    ap.add_argument("--rebuild", action="store_true", help="solo l'elaborato dai grezzi, senza rete")
    ap.add_argument("--force", action="store_true", help="riscarica anche se i grezzi ci sono")
    ap.add_argument("--max-min", type=float, default=240.0)
    a = ap.parse_args(argv)
    try:
        out = build_processed() if a.rebuild else fetch(force=a.force, max_minutes=a.max_min)
    except (cache.OfflineError, cache.CacheMiss, RuntimeError) as exc:
        print(f"ERRORE ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    d = pd.read_csv(out)
    print(f"{out}: {len(d)} righe, {int((d['qualita'] == 'valido').sum())} valide, {d['punto'].nunique()} punti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
