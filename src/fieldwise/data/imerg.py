"""GPM IMERG Final Run giornaliero V07 (GES DISC): pioggia giornaliera del blocco 2x2 di celle da 0,1 gradi attorno a un punto.

Prodotto: ``GPM_3IMERGDF`` versione ``07`` (DOI 10.5067/GPM/IMERGDF/DAY/07), un granulo
NetCDF-4 al giorno, griglia globale 3600 x 1800 a 0,1 gradi. Verificato in CMR (metadati
pubblici delle variabili UMM-Var): ``precipitation`` ha dimensioni (time=1, lon=3600,
lat=1800) IN QUESTO ORDINE (lon prima di lat), unita' mm/day, valore di riempimento
-9999.9 (float32). Questo e' il valore giornaliero in mm/giorno: nessuna conversione.

Via di accesso scelta: (a) OPeNDAP con sottoinsieme di una sola cella. Motivo: 26 anni
sono ~9 250 granuli da ~30 MB (~270 GB); con OPeNDAP ogni richiesta e' un file di pochi kB.
Il link OPeNDAP ("USE SERVICE API", host opendap.earthdata.nasa.gov) e' in ogni granulo
restituito da CMR. La richiesta e' DAP4: ``<url>.dap.nc4?dap4.ce=/precipitation[0][i_lon][i_lat];/lon[i_lon];/lat[i_lat]``,
con la sessione autenticata di earthaccess. Si richiedono anche ``lon`` e ``lat`` della
cella e si controlla che coincidano con il centro atteso: se l'ordine delle dimensioni o
l'indicizzazione fossero diversi da quanto previsto, il client si ferma invece di
scrivere dati di un'altra cella. ``--method download`` (ultima risorsa) scarica il granulo
intero, lo legge e lo cancella.

Blocco 2x2: per il punto si estraggono, con UNA sola richiesta OPeNDAP per granulo, le
quattro celle i cui centri circondano il punto (``/precipitation[0][i:i+1][j:j+1]``,
intervalli DAP4 inclusivi) insieme a ``lon`` e ``lat`` del blocco. Indice di colonna del
primo centro ``i0 = floor((lon + 180) / 0.1 - 0.5)``, di riga ``j0 = floor((lat + 90) / 0.1 - 0.5)``;
centri a -179,95 + 0,1 * i e -89,95 + 0,1 * j. Pesi bilineari ``(1-fx)(1-fy)``, ``fx(1-fy)``,
``(1-fx)fy``, ``fx fy`` con fx, fy frazioni di cella (0,5 e 0,5 su un vertice: quattro pesi da
0,25; 0 e 0 al centro di una cella: peso 1 su quella). Tolleranza 1e-6 gradi per
l'arrotondamento. Cella piu' vicina (``rain_mm_nearest``): quella con il centro piu' vicino;
a parita' (bordo) la cella a nord-est. Ai bordi della griglia il blocco viene spostato
all'interno (peso 1 sulla cella di bordo). ``--method download`` (ultima risorsa) scarica il
granulo intero, lo legge e lo cancella.

Grezzi: ``imerg_<anno>.csv`` con una colonna per cella (``precip_lat<clat>_lon<clon>``); i file
nel vecchio formato a una cella non sono validi e vengono riscaricati.
Elaborato: ``imerg_daily.csv`` con ``date, rain_mm`` (bilineare, NaN se manca una cella con
peso non nullo), ``rain_mm_nearest``, ``n_cells_valid`` (celle valide tra le quattro).

Uso::

    python -m fieldwise.data.imerg --lat 45.2 --lon 10.0 [--start 2000-06-01 --end 2025-12-31]
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .. import config
from . import cache, earthdata

SHORT_NAME = "GPM_3IMERGDF"
VERSION = "07"
DOI = "10.5067/GPM/IMERGDF/DAY/07"
SOURCE = "imerg"
VARIABLE = "precipitation"
UNITS = "mm/day"
FILL_VALUE = -9999.9
N_LON, N_LAT = 3600, 1800
RES = 0.1
TOL = 1e-6                      # gradi: tolleranza per i punti sul bordo di una cella
FIRST_DAY = dt.date(2000, 6, 1)  # primo giorno del Final Run IMERG con GPM (CMR parte dal 1998-01-01)
PROCESSED_NAME = "imerg_daily.csv"
_CENTER_TOL = 0.01              # gradi: scarto massimo ammesso tra centro atteso e centro letto


# ----------------------------------------------------------------------------------
# geometria
# ----------------------------------------------------------------------------------

def cell_index(lat: float, lon: float) -> tuple[int, int, float, float]:
    """(i_lon, i_lat, lat_centro, lon_centro) della cella IMERG che contiene il punto."""
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"coordinate fuori intervallo: lat={lat}, lon={lon}")
    i_lon = int(math.floor((lon + 180.0) / RES + TOL / RES))
    i_lat = int(math.floor((lat + 90.0) / RES + TOL / RES))
    i_lon = min(max(i_lon, 0), N_LON - 1)
    i_lat = min(max(i_lat, 0), N_LAT - 1)
    clon = round(-180.0 + RES / 2 + RES * i_lon, 6)
    clat = round(-90.0 + RES / 2 + RES * i_lat, 6)
    return i_lon, i_lat, clat, clon


def _center(i: int, origin: float) -> float:
    return round(origin + RES / 2 + RES * i, 6)


def _frac(x: float, n: int) -> tuple[int, float]:
    """(indice del primo centro, frazione 0..1 verso il successivo) per la coordinata x in celle."""
    u = x - 0.5
    i = int(math.floor(u + TOL / RES))
    f = u - i
    if i < 0:
        return 0, 0.0
    if i >= n - 1:
        return n - 2, 1.0
    if f < TOL / RES:
        f = 0.0
    elif f > 1 - TOL / RES:
        f = 1.0
    return i, f


def cell_column(clat: float, clon: float) -> str:
    """Nome della colonna grezza di una cella: contiene le coordinate del centro."""
    return f"precip_lat{clat:.3f}_lon{clon:.3f}"


def stencil(lat: float, lon: float) -> dict:
    """Blocco 2x2 di celle che circondano il punto, con pesi bilineari.

    Ritorna ``{"i_lon0", "i_lat0", "cells": [4 dict], "nearest": colonna}``; ogni cella ha
    ``i_lon, i_lat, lat, lon, weight, column``. Ordine: (lon0,lat0), (lon0,lat1), (lon1,lat0),
    (lon1,lat1), cioe' l'ordine del sottoinsieme (lon, lat).
    """
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        raise ValueError(f"coordinate fuori intervallo: lat={lat}, lon={lon}")
    i0, fx = _frac((lon + 180.0) / RES, N_LON)
    j0, fy = _frac((lat + 90.0) / RES, N_LAT)
    cells = []
    for di, wx in ((0, 1 - fx), (1, fx)):
        for dj, wy in ((0, 1 - fy), (1, fy)):
            clat, clon = _center(j0 + dj, -90.0), _center(i0 + di, -180.0)
            cells.append({"i_lon": i0 + di, "i_lat": j0 + dj, "lat": clat, "lon": clon,
                          "weight": round(wx * wy, 9), "column": cell_column(clat, clon)})
    near_i = 1 if fx >= 0.5 - TOL / RES else 0      # a parita' -> est
    near_j = 1 if fy >= 0.5 - TOL / RES else 0      # a parita' -> nord
    return {"i_lon0": i0, "i_lat0": j0, "cells": cells, "nearest": cells[2 * near_i + near_j]["column"]}


def constraint(i_lon: int, i_lat: int) -> str:
    """Espressione di vincolo DAP4 per il blocco 2x2 che parte da (i_lon, i_lat) (lon prima di lat)."""
    return (f"/{VARIABLE}[0][{i_lon}:{i_lon + 1}][{i_lat}:{i_lat + 1}];"
            f"/lon[{i_lon}:{i_lon + 1}];/lat[{i_lat}:{i_lat + 1}]")


# ----------------------------------------------------------------------------------
# estrazione
# ----------------------------------------------------------------------------------

def _pick(arr: np.ndarray, idx: tuple[int, ...]):
    """Valore scalare: da un sottoinsieme (un solo elemento) o da un array intero."""
    arr = np.asarray(arr)
    if arr.size == 1:
        return arr.reshape(-1)[0]
    return arr[idx]


def clean_precip(value) -> float:
    """mm/giorno, NaN se riempimento (-9999.9), non finito o negativo."""
    v = float(value)
    if not math.isfinite(v) or v <= -9999.0 or v < 0.0:
        return float("nan")
    return v


def extract_block(h5, st: dict) -> dict[str, float]:
    """Pioggia (mm/giorno) delle quattro celle del blocco da un file aperto con h5py.

    Il file puo' essere il sottoinsieme OPeNDAP (2x2 elementi, ordine lon, lat) o il granulo
    intero (3D time, lon, lat). Se il file contiene ``lon`` e ``lat`` si controllano i centri
    di tutte e quattro le celle. Ritorna ``{colonna: mm}``.
    """
    i0, j0 = st["i_lon0"], st["i_lat0"]
    arr = np.asarray(h5[VARIABLE][...])
    if arr.shape == (1, N_LON, N_LAT):
        block = arr[0, i0:i0 + 2, j0:j0 + 2]
        lon_idx, lat_idx = slice(i0, i0 + 2), slice(j0, j0 + 2)
    elif arr.size == 4:
        block = arr.reshape(2, 2)
        lon_idx = lat_idx = slice(0, 2)
    else:
        raise ValueError(f"forma inattesa di {VARIABLE}: {arr.shape} "
                         f"(atteso (1, {N_LON}, {N_LAT}) oppure un blocco 2x2)")
    if "lon" in h5 and "lat" in h5:
        lons = np.asarray(h5["lon"][...], dtype=float).reshape(-1)
        lats = np.asarray(h5["lat"][...], dtype=float).reshape(-1)
        lons, lats = lons[lon_idx], lats[lat_idx]
        exp_lon = [st["cells"][0]["lon"], st["cells"][2]["lon"]]
        exp_lat = [st["cells"][0]["lat"], st["cells"][1]["lat"]]
        if (lons.shape != (2,) or lats.shape != (2,)
                or np.any(np.abs(lons - exp_lon) > _CENTER_TOL)
                or np.any(np.abs(lats - exp_lat) > _CENTER_TOL)):
            raise ValueError(
                f"centri cella letti (lat {lats.tolist()}, lon {lons.tolist()}) diversi da quelli attesi "
                f"(lat {exp_lat}, lon {exp_lon}): ordine delle dimensioni o indicizzazione non come previsto")
    out = {}
    for k, c in enumerate(st["cells"]):
        out[c["column"]] = clean_precip(block[k // 2, k % 2])
    return out


def _row_from_subset(granule, st: dict) -> dict:
    url = earthdata.opendap_url(granule)

    def once():
        return earthdata.fetch_subset(url, constraint(st["i_lon0"], st["i_lat0"]))

    content = earthdata.with_retry(once, what=f"OPeNDAP {granule['meta'].get('concept-id')}",
                                   no_retry=(earthdata.EarthdataAuthError,))
    with earthdata.open_h5_bytes(content) as h5:
        vals = extract_block(h5, st)
    return {"date": earthdata.granule_date(granule), **vals}


def _row_from_download(granule, st: dict) -> dict:
    import h5py

    def reader(path: Path) -> dict:
        with h5py.File(path, "r") as h5:
            return extract_block(h5, st)

    vals = earthdata.with_retry(lambda: earthdata.download_and_read(granule, reader),
                                what="download granulo IMERG",
                                no_retry=(earthdata.EarthdataAuthError,))
    return {"date": earthdata.granule_date(granule), **vals}


# ----------------------------------------------------------------------------------
# API pubblica
# ----------------------------------------------------------------------------------

def _raw_dir(lat: float, lon: float) -> Path:
    return cache.raw_dir("imerg", lat, lon)


def processed_path(lat: float, lon: float, create: bool = True) -> Path:
    return cache.processed_dir(lat, lon, create=create) / PROCESSED_NAME


RAW_FORMAT = "block2x2-v1"


def _raw_valid(path: Path, st: dict) -> bool:
    """File grezzo nel formato a blocco 2x2 per questo punto (no vecchio formato a una cella)."""
    if not cache.is_cached(path):
        return False
    params = cache.read_meta(path).get("params", {})
    if params.get("format") != RAW_FORMAT:
        return False
    try:
        cols = list(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return False
    return cols == ["date"] + [c["column"] for c in st["cells"]]


def _drop_invalid_raw(raw: Path, st: dict, log=print) -> None:
    for p in sorted(raw.glob("imerg_*.csv")):
        if cache.is_cached(p) and not _raw_valid(p, st):
            log(f"{p.name}: formato grezzo non valido (vecchio formato a una cella): da riscaricare")
            p.unlink()
            p.with_name(p.name + ".meta.json").unlink(missing_ok=True)


def combine(df: pd.DataFrame, st: dict) -> pd.DataFrame:
    """Dalle quattro colonne di cella a date, rain_mm, rain_mm_nearest, n_cells_valid."""
    cols = [c["column"] for c in st["cells"]]
    vals = df[cols].to_numpy(dtype=float)
    w = np.array([c["weight"] for c in st["cells"]], dtype=float)
    need = w > 0
    bil = np.where(np.isnan(vals[:, need]).any(axis=1), np.nan,
                   np.nansum(np.where(need, vals * w, 0.0), axis=1))
    return pd.DataFrame({
        "date": df["date"].to_numpy(),
        "rain_mm": bil,
        "rain_mm_nearest": df[st["nearest"]].to_numpy(dtype=float),
        "n_cells_valid": (~np.isnan(vals)).sum(axis=1).astype(int),
    })


def build_processed(lat: float, lon: float) -> Path:
    """Unisce i CSV grezzi annuali in ``imerg_daily.csv``."""
    raw = _raw_dir(lat, lon)
    st = stencil(lat, lon)
    parts = []
    for p in sorted(raw.glob("imerg_*.csv")):
        if not _raw_valid(p, st):
            continue
        parts.append(pd.read_csv(p, parse_dates=["date"]))
    if not parts:
        raise cache.CacheMiss(f"nessun dato IMERG grezzo valido in {raw} - per scaricarlo: "
                              f"python -m fieldwise.data.imerg --lat {lat} --lon {lon}")
    df = pd.concat(parts, ignore_index=True).drop_duplicates("date", keep="last")
    df = combine(df.sort_values("date"), st)
    out = processed_path(lat, lon)
    df.to_csv(out, index=False, date_format="%Y-%m-%d")
    return out


def fetch(lat: float, lon: float, start: dt.date | str | None = None,
          end: dt.date | str | None = None, force: bool = False,
          method: str = "opendap", workers: int = earthdata.MAX_WORKERS) -> Path:
    """Scarica (a riprese) IMERG per il blocco 2x2 del punto e scrive ``imerg_daily.csv``.

    Ritorna il percorso di ``imerg_daily.csv``. Chiama ``cache.ensure_online()`` e
    ``earthdata.login()`` prima di qualsiasi rete. ``method``: "opendap" (default) o
    "download" (granulo intero, poi cancellato).
    """
    cache.ensure_online("IMERG GPM_3IMERGDF V07")
    earthdata.login()
    if method not in ("opendap", "download"):
        raise ValueError("method deve essere 'opendap' o 'download'")
    start = _as_date(start, FIRST_DAY)
    end = _as_date(end, dt.date(config.END_YEAR, 12, 31))
    start = max(start, FIRST_DAY)
    st = stencil(lat, lon)
    worker = _row_from_subset if method == "opendap" else _row_from_download
    _drop_invalid_raw(_raw_dir(lat, lon), st)
    params = {
        "format": RAW_FORMAT, "lat": lat, "lon": lon,
        "interpolation": "bilineare dei centri delle quattro celle piu' vicine",
        "cells": [{k: c[k] for k in ("column", "i_lon", "i_lat", "lat", "lon", "weight")}
                  for c in st["cells"]],
        "nearest_column": st["nearest"], "i_lon0": st["i_lon0"], "i_lat0": st["i_lat0"],
        "cell_size_deg": RES,
        "variable": VARIABLE, "units": UNITS, "fill_value": FILL_VALUE,
        "fill_policy": "valori di riempimento e negativi salvati come vuoto (NaN)",
        "dimension_order": "time, lon, lat", "access": method, "doi": DOI,
        "tie_rule": "cella piu' vicina a parita' -> nord-est",
    }
    earthdata.fetch_years(
        raw=_raw_dir(lat, lon), prefix="imerg", source=SOURCE, short_name=SHORT_NAME,
        version=VERSION, url=f"https://doi.org/{DOI}", params=params, start=start, end=end,
        extract=lambda g: worker(g, st), force=force, workers=workers,
        notes="precipitazione giornaliera IMERG Final V07, blocco 2x2 di celle da 0,1 gradi")
    return build_processed(lat, lon)


def load(lat: float, lon: float) -> pd.DataFrame:
    """Legge ``imerg_daily.csv`` dalla cache (mai la rete). CacheMiss se manca."""
    p = processed_path(lat, lon, create=False)
    if not p.exists():
        raise cache.CacheMiss(f"dato non in cache: {p} - per scaricarlo: "
                              f"python -m fieldwise.data.imerg --lat {lat} --lon {lon}")
    df = pd.read_csv(p, parse_dates=["date"])
    return df


def _as_date(v, default: dt.date) -> dt.date:
    if v is None:
        return default
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scarica IMERG Final giornaliero V07 per un punto.")
    ap.add_argument("--lat", type=float, default=config.PILOT_LAT)
    ap.add_argument("--lon", type=float, default=config.PILOT_LON)
    ap.add_argument("--start", default=None, help="AAAA-MM-GG (default 2000-06-01)")
    ap.add_argument("--end", default=None, help="AAAA-MM-GG (default 2025-12-31)")
    ap.add_argument("--force", action="store_true", help="riscarica anche gli anni completi")
    ap.add_argument("--method", choices=("opendap", "download"), default="opendap")
    ap.add_argument("--workers", type=int, default=earthdata.MAX_WORKERS)
    a = ap.parse_args(argv)
    try:
        out = fetch(a.lat, a.lon, a.start, a.end, force=a.force, method=a.method,
                    workers=a.workers)
    except (earthdata.EarthdataAuthError, earthdata.EarthdataRequestError,
            cache.OfflineError, cache.CacheMiss, ValueError) as exc:
        print(f"ERRORE ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    df = pd.read_csv(out)
    print(f"{out}: {len(df)} giorni, {df['rain_mm'].notna().sum()} validi (bilineare), "
          f"{df['rain_mm_nearest'].notna().sum()} validi (cella piu' vicina)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
