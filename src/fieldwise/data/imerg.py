"""GPM IMERG Final Run giornaliero V07 (GES DISC): pioggia giornaliera di una cella da 0,1 gradi.

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

Cella: indice di colonna ``i_lon = floor((lon + 180) / 0.1)``, di riga ``i_lat = floor((lat + 90) / 0.1)``;
centri a -179,95 + 0,1 * i_lon e -89,95 + 0,1 * i_lat. Se il punto cade ESATTAMENTE su
un bordo tra due celle (come il punto pilota 45,2 / 10,0, che e' un vertice della
griglia) si sceglie per convenzione la cella a nord-est (bordo inferiore/occidentale
incluso), con una tolleranza di 1e-6 gradi per l'errore di arrotondamento.

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


def constraint(i_lon: int, i_lat: int) -> str:
    """Espressione di vincolo DAP4 per una sola cella (lon prima di lat)."""
    return f"/{VARIABLE}[0][{i_lon}][{i_lat}];/lon[{i_lon}];/lat[{i_lat}]"


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


def extract_point(h5, i_lon: int, i_lat: int, clat: float, clon: float) -> float:
    """Pioggia (mm/giorno) della cella da un file aperto con h5py.

    Il file puo' essere il sottoinsieme OPeNDAP (un solo elemento) o il granulo intero
    (3D time, lon, lat). Se il file contiene ``lon`` e ``lat`` si controlla il centro.
    """
    ds = h5[VARIABLE]
    arr = np.asarray(ds[...])
    if arr.size != 1 and arr.shape != (1, N_LON, N_LAT):
        raise ValueError(f"forma inattesa di {VARIABLE}: {arr.shape} (atteso (1, {N_LON}, {N_LAT}))")
    lon_c = lat_c = None
    if "lon" in h5 and "lat" in h5:
        lon_c = float(_pick(h5["lon"][...], (i_lon,)))
        lat_c = float(_pick(h5["lat"][...], (i_lat,)))
        if abs(lon_c - clon) > _CENTER_TOL or abs(lat_c - clat) > _CENTER_TOL:
            raise ValueError(
                f"centro cella letto ({lat_c}, {lon_c}) diverso da quello atteso ({clat}, {clon}): "
                "ordine delle dimensioni o indicizzazione non come previsto")
    return clean_precip(_pick(arr, (0, i_lon, i_lat)))


def _row_from_subset(granule, i_lon, i_lat, clat, clon) -> dict:
    url = earthdata.opendap_url(granule)

    def once():
        return earthdata.fetch_subset(url, constraint(i_lon, i_lat))

    content = earthdata.with_retry(once, what=f"OPeNDAP {granule['meta'].get('concept-id')}",
                                   no_retry=(earthdata.EarthdataAuthError,))
    with earthdata.open_h5_bytes(content) as h5:
        rain = extract_point(h5, i_lon, i_lat, clat, clon)
    return {"date": earthdata.granule_date(granule), "precipitation": rain}


def _row_from_download(granule, i_lon, i_lat, clat, clon) -> dict:
    import h5py

    def reader(path: Path) -> float:
        with h5py.File(path, "r") as h5:
            return extract_point(h5, i_lon, i_lat, clat, clon)

    rain = earthdata.with_retry(lambda: earthdata.download_and_read(granule, reader),
                                what="download granulo IMERG",
                                no_retry=(earthdata.EarthdataAuthError,))
    return {"date": earthdata.granule_date(granule), "precipitation": rain}


# ----------------------------------------------------------------------------------
# API pubblica
# ----------------------------------------------------------------------------------

def _raw_dir(lat: float, lon: float) -> Path:
    return cache.raw_dir("imerg", lat, lon)


def processed_path(lat: float, lon: float) -> Path:
    return cache.processed_dir(lat, lon) / PROCESSED_NAME


def build_processed(lat: float, lon: float) -> Path:
    """Unisce i CSV grezzi annuali in ``imerg_daily.csv`` (date, rain_mm)."""
    raw = _raw_dir(lat, lon)
    parts = []
    for p in sorted(raw.glob("imerg_*.csv")):
        if not cache.is_cached(p):
            continue
        parts.append(pd.read_csv(p, parse_dates=["date"]))
    if not parts:
        raise cache.CacheMiss(f"nessun dato IMERG grezzo in {raw} - per scaricarlo: "
                              f"python -m fieldwise.data.imerg --lat {lat} --lon {lon}")
    df = pd.concat(parts, ignore_index=True).drop_duplicates("date", keep="last")
    df = df.sort_values("date").rename(columns={VARIABLE: "rain_mm"})[["date", "rain_mm"]]
    out = processed_path(lat, lon)
    df.to_csv(out, index=False, date_format="%Y-%m-%d")
    return out


def fetch(lat: float, lon: float, start: dt.date | str | None = None,
          end: dt.date | str | None = None, force: bool = False,
          method: str = "opendap", workers: int = earthdata.MAX_WORKERS) -> Path:
    """Scarica (a riprese) IMERG per la cella del punto e scrive ``imerg_daily.csv``.

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
    i_lon, i_lat, clat, clon = cell_index(lat, lon)
    worker = _row_from_subset if method == "opendap" else _row_from_download
    params = {
        "lat": lat, "lon": lon, "i_lon": i_lon, "i_lat": i_lat,
        "cell_center_lat": clat, "cell_center_lon": clon, "cell_size_deg": RES,
        "variable": VARIABLE, "units": UNITS, "fill_value": FILL_VALUE,
        "fill_policy": "valori di riempimento e negativi salvati come vuoto (NaN)",
        "dimension_order": "time, lon, lat", "access": method, "doi": DOI,
        "tie_rule": "punto su bordo di cella -> cella a nord-est",
    }
    earthdata.fetch_years(
        raw=_raw_dir(lat, lon), prefix="imerg", source=SOURCE, short_name=SHORT_NAME,
        version=VERSION, url=f"https://doi.org/{DOI}", params=params, start=start, end=end,
        extract=lambda g: worker(g, i_lon, i_lat, clat, clon), force=force, workers=workers,
        notes="precipitazione giornaliera IMERG Final V07, cella da 0,1 gradi")
    return build_processed(lat, lon)


def load(lat: float, lon: float) -> pd.DataFrame:
    """Legge ``imerg_daily.csv`` dalla cache (mai la rete). CacheMiss se manca."""
    p = processed_path(lat, lon)
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
    print(f"{out}: {len(df)} giorni, {df['rain_mm'].notna().sum()} validi")
    return 0


if __name__ == "__main__":
    sys.exit(main())
