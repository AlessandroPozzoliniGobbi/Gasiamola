"""SMAP Enhanced L3 Radiometer 9 km EASE-Grid 2.0 Soil Moisture, giornaliero (NSIDC DAAC).

Prodotto: ``SPL3SMP_E`` versione ``006`` (DOI 10.5067/M20OXIZHY3RJ), un granulo HDF5 al
giorno dal 2015-03-31. Guida utente: https://nsidc.org/sites/default/files/documents/user-guide/spl3smp_e-v006-userguide.pdf

Struttura (verificata in CMR, UMM-Var): gruppo ``Soil_Moisture_Retrieval_Data_AM`` con
``soil_moisture`` (float32, cm3/cm3 = m3/m3, riempimento -9999), ``retrieval_qual_flag``
(uint16, riempimento 65534), ``EASE_row_index``, ``EASE_column_index``, ``latitude``,
``longitude``; gruppo ``Soil_Moisture_Retrieval_Data_PM`` con gli stessi campi col suffisso
``_pm`` (``soil_moisture_pm``, ``retrieval_qual_flag_pm``, ``latitude_pm``...). Tutti gli
array globali sono 2D (1624 righe x 3856 colonne). AM = passaggi discendenti (~6:00 ora
locale), PM = ascendenti (~18:00).

``retrieval_qual_flag`` (guida utente v006, Tabella 6; bit 0 = meno significativo):

* bit 0: 0 = retrieval di qualita' raccomandata, 1 = non raccomandata;
* bit 1: 0 = retrieval tentato, 1 = saltato;
* bit 2: 0 = retrieval riuscito, 1 = non riuscito;
* bit 3: 0 = stato gelo/disgelo riuscito, 1 = non riuscito;
* bit 4-15: non usati.

La guida (sez. 2.5.3, "proper data usage") raccomanda di usare solo i valori 0 oppure 8
("8 perche' un retrieval di gelo/disgelo fallito non pregiudica l'umidita'"). Qui
``sm_good_mean`` e' la media dei passaggi (AM, PM) con flag in {0, 8}; NaN se nessuno.

Via di accesso scelta: (a) OPeNDAP con sottoinsieme di un solo pixel, perche' ogni granulo
pesa centinaia di MB (~2,4 TB in tutto per 3 845 granuli, stima da ``granule_size`` di
CMR) e per un pixel bastano pochi kB. Richiesta DAP4 con la sessione autenticata di
earthaccess: ``<url>.dap.nc4?dap4.ce=/<gruppo>/<variabile>[riga][colonna];...``. Insieme
all'umidita' e al flag si chiedono ``EASE_row_index``/``EASE_column_index`` e
``latitude``/``longitude`` del pixel e si controlla che coincidano con quelli calcolati:
se la griglia non e' quella prevista il client si ferma. AppEEARS (``SPL3SMP_E.006``,
layer ``Soil_Moisture_Retrieval_Data_AM_soil_moisture`` ecc., verificato nell'elenco
pubblico dei prodotti) e' l'alternativa (c), non implementata. ``--method download``
(ultima risorsa) scarica il granulo intero, lo legge e lo cancella.

Griglia EASE-Grid 2.0 globale 9 km (EPSG:6933, WGS84, proiezione cilindrica equivalente
con parallelo standard 30 gradi): 3856 colonne x 1624 righe, pixel quadrato di
9008.055210146 m (36032.220840584 / 4), angolo in alto a sinistra a
(-3856/2 * 9008.055 m, +812 * 9008.055 m) = (-17367530.445, 7314540.79) m. NOTA: la
Tabella 5 della guida v006 riporta "9,024.31 m" come dimensione del pixel e chiama
"centro" del pixel in alto a sinistra quelle stesse coordinate, che invece corrispondono
all'ANGOLO (3856/2 * 9008.055 = 17367530.4); qui si usa il valore standard NSIDC e il
controllo sugli indici letti dal file protegge da errori.

Uso::

    python -m fieldwise.data.smap --lat 45.2 --lon 10.0 [--start 2015-03-31 --end 2025-12-31]
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

SHORT_NAME = "SPL3SMP_E"
VERSION = "006"
DOI = "10.5067/M20OXIZHY3RJ"
SOURCE = "smap"
FIRST_DAY = dt.date(2015, 3, 31)
FILL_SM = -9999.0
FILL_QUAL = 65534
GOOD_FLAGS = (0, 8)
PROCESSED_NAME = "smap_daily.csv"
UNITS = "m3/m3 (cm3/cm3)"

# griglia EASE-Grid 2.0 globale 9 km
N_ROWS, N_COLS = 1624, 3856
PIXEL_M = 36032.220840584 / 4.0                # 9008.055210146 m
X0 = -N_COLS / 2.0 * PIXEL_M                   # bordo ovest
Y0 = N_ROWS / 2.0 * PIXEL_M                    # bordo nord
_A = 6378137.0                                 # WGS84
_F = 1.0 / 298.257223563
_E2 = _F * (2.0 - _F)
_E = math.sqrt(_E2)
_LAT_TS = math.radians(30.0)
_TOL = 1e-6                                    # in unita' di pixel

GROUPS = {
    "am": {"group": "Soil_Moisture_Retrieval_Data_AM", "sm": "soil_moisture",
           "qual": "retrieval_qual_flag", "row": "EASE_row_index",
           "col": "EASE_column_index", "lat": "latitude", "lon": "longitude"},
    "pm": {"group": "Soil_Moisture_Retrieval_Data_PM", "sm": "soil_moisture_pm",
           "qual": "retrieval_qual_flag_pm", "row": "EASE_row_index_pm",
           "col": "EASE_column_index_pm", "lat": "latitude_pm", "lon": "longitude_pm"},
}
RAW_COLUMNS = ["date", "sm_am", "qual_am", "sm_pm", "qual_pm"]


# ----------------------------------------------------------------------------------
# geometria EASE-Grid 2.0 (cilindrica equivalente, ellissoide WGS84)
# ----------------------------------------------------------------------------------

def _q(phi: float) -> float:
    s = math.sin(phi)
    return (1.0 - _E2) * (s / (1.0 - _E2 * s * s)
                          - (1.0 / (2.0 * _E)) * math.log((1.0 - _E * s) / (1.0 + _E * s)))


_K0 = math.cos(_LAT_TS) / math.sqrt(1.0 - _E2 * math.sin(_LAT_TS) ** 2)
_QP = _q(math.pi / 2.0)


def forward(lat: float, lon: float) -> tuple[float, float]:
    """(x, y) in metri EPSG:6933 di un punto lat/lon (gradi)."""
    x = _A * _K0 * math.radians(lon)
    y = _A * _q(math.radians(lat)) / (2.0 * _K0)
    return x, y


def inverse(x: float, y: float) -> tuple[float, float]:
    """(lat, lon) in gradi da (x, y) EPSG:6933."""
    lon = math.degrees(x / (_A * _K0))
    qt = 2.0 * _K0 * y / _A
    phi = math.asin(max(-1.0, min(1.0, qt / _QP)))     # latitudine autalica, poi Newton
    for _ in range(50):
        s = math.sin(phi)
        dq = (1.0 - _E2) / (1.0 - _E2 * s * s) ** 2 * 2.0 * math.cos(phi)
        new = phi - (_q(phi) - qt) / dq
        if abs(new - phi) < 1e-14:
            phi = new
            break
        phi = new
    return math.degrees(phi), lon


def pixel_index(lat: float, lon: float) -> tuple[int, int, float, float]:
    """(riga, colonna, lat_centro, lon_centro) del pixel EASE-2 9 km che contiene il punto.

    Righe dall'alto (0 = nord), colonne da ovest, come negli array del prodotto.
    Un punto esattamente su un bordo va al pixel a sud/est (convenzione floor).
    """
    if not (-180.0 <= lon <= 180.0):
        raise ValueError(f"longitudine fuori intervallo: {lon}")
    x, y = forward(lat, lon)
    col = int(math.floor((x - X0) / PIXEL_M + _TOL))
    row = int(math.floor((Y0 - y) / PIXEL_M + _TOL))
    if not (0 <= row < N_ROWS and 0 <= col < N_COLS):
        raise ValueError(f"punto fuori dalla griglia EASE-2 globale a 9 km: lat={lat}, lon={lon}")
    clat, clon = inverse(X0 + (col + 0.5) * PIXEL_M, Y0 - (row + 0.5) * PIXEL_M)
    return row, col, round(clat, 6), round(clon, 6)


def constraint(row: int, col: int) -> str:
    """Vincolo DAP4 per un solo pixel: AM e PM, valore, flag, indici e coordinate."""
    parts = []
    for k in ("am", "pm"):
        g = GROUPS[k]
        for field in ("sm", "qual", "row", "col", "lat", "lon"):
            parts.append(f"/{g['group']}/{g[field]}[{row}][{col}]")
    return ";".join(parts)


# ----------------------------------------------------------------------------------
# estrazione
# ----------------------------------------------------------------------------------

def _scalar(h5, group: str, name: str, row: int, col: int):
    """Valore di un campo 2D: dal sottoinsieme (un elemento) o dall'array intero."""
    if group not in h5 or name not in h5[group]:
        return None
    arr = np.asarray(h5[group][name][...])
    if arr.size == 1:
        return arr.reshape(-1)[0]
    if arr.shape != (N_ROWS, N_COLS):
        raise ValueError(f"forma inattesa di {group}/{name}: {arr.shape}")
    return arr[row, col]


def clean_sm(v) -> float:
    """Umidita' m3/m3, NaN se riempimento (-9999) o non finita."""
    if v is None:
        return float("nan")
    x = float(v)
    if not math.isfinite(x) or x <= -9998.0:
        return float("nan")
    return x


def clean_qual(v) -> float:
    """Flag intero, NaN se riempimento (65534) o assente."""
    if v is None:
        return float("nan")
    q = int(v)
    return float("nan") if q == FILL_QUAL else float(q)


def extract_point(h5, row: int, col: int, clat: float, clon: float) -> dict:
    """Valori AM/PM del pixel da un file h5py (sottoinsieme OPeNDAP o granulo intero).

    Controlla indici EASE e coordinate del pixel quando presenti nel file (valori di
    riempimento ignorati: fuori dai pixel con retrieval lat/lon possono mancare).
    """
    out: dict = {}
    for k in ("am", "pm"):
        g = GROUPS[k]
        grp = g["group"]
        r = _scalar(h5, grp, g["row"], row, col)
        c = _scalar(h5, grp, g["col"], row, col)
        if r is not None and int(r) != FILL_QUAL and int(r) != row:
            raise ValueError(f"indice di riga letto {int(r)} != atteso {row} ({k.upper()})")
        if c is not None and int(c) != FILL_QUAL and int(c) != col:
            raise ValueError(f"indice di colonna letto {int(c)} != atteso {col} ({k.upper()})")
        la = _scalar(h5, grp, g["lat"], row, col)
        lo = _scalar(h5, grp, g["lon"], row, col)
        if la is not None and lo is not None:
            la, lo = float(la), float(lo)
            if la > -9998 and lo > -9998 and (abs(la - clat) > 0.1 or abs(lo - clon) > 0.1):
                raise ValueError(f"centro pixel letto ({la}, {lo}) lontano da quello atteso "
                                 f"({clat}, {clon}) ({k.upper()})")
        out[f"sm_{k}"] = clean_sm(_scalar(h5, grp, g["sm"], row, col))
        out[f"qual_{k}"] = clean_qual(_scalar(h5, grp, g["qual"], row, col))
    return out


def _row_from_subset(granule, row, col, clat, clon) -> dict:
    url = earthdata.opendap_url(granule)
    content = earthdata.with_retry(
        lambda: earthdata.fetch_subset(url, constraint(row, col)),
        what=f"OPeNDAP {granule['meta'].get('concept-id')}",
        no_retry=(earthdata.EarthdataAuthError,))
    with earthdata.open_h5_bytes(content) as h5:
        vals = extract_point(h5, row, col, clat, clon)
    return {"date": earthdata.granule_date(granule), **vals}


def _row_from_download(granule, row, col, clat, clon) -> dict:
    import h5py

    def reader(path: Path) -> dict:
        with h5py.File(path, "r") as h5:
            return extract_point(h5, row, col, clat, clon)

    vals = earthdata.with_retry(lambda: earthdata.download_and_read(granule, reader),
                                what="download granulo SMAP",
                                no_retry=(earthdata.EarthdataAuthError,))
    return {"date": earthdata.granule_date(granule), **vals}


def good_mean(sm_am, qual_am, sm_pm, qual_pm) -> float:
    """Media dei passaggi con flag in {0, 8} e umidita' valida; NaN se nessuno."""
    vals = []
    for sm, q in ((sm_am, qual_am), (sm_pm, qual_pm)):
        if pd.notna(sm) and pd.notna(q) and int(q) in GOOD_FLAGS:
            vals.append(float(sm))
    return float(np.mean(vals)) if vals else float("nan")


# ----------------------------------------------------------------------------------
# API pubblica
# ----------------------------------------------------------------------------------

def _raw_dir(lat: float, lon: float) -> Path:
    return cache.raw_dir("smap", lat, lon)


def processed_path(lat: float, lon: float, create: bool = True) -> Path:
    return cache.processed_dir(lat, lon, create=create) / PROCESSED_NAME


def build_processed(lat: float, lon: float) -> Path:
    """Unisce i CSV grezzi annuali in ``smap_daily.csv``
    (date, sm_am, qual_am, sm_pm, qual_pm, sm_good_mean)."""
    raw = _raw_dir(lat, lon)
    parts = []
    for p in sorted(raw.glob("smap_*.csv")):
        if cache.is_cached(p):
            parts.append(pd.read_csv(p, parse_dates=["date"]))
    if not parts:
        raise cache.CacheMiss(f"nessun dato SMAP grezzo in {raw} - per scaricarlo: "
                              f"python -m fieldwise.data.smap --lat {lat} --lon {lon}")
    df = pd.concat(parts, ignore_index=True).drop_duplicates("date", keep="last")
    df = df.sort_values("date").reset_index(drop=True)
    df["sm_good_mean"] = [good_mean(*r) for r in
                          df[["sm_am", "qual_am", "sm_pm", "qual_pm"]].itertuples(index=False)]
    for c in ("qual_am", "qual_pm"):
        df[c] = df[c].astype("Int64")
    out = processed_path(lat, lon)
    df[["date", "sm_am", "qual_am", "sm_pm", "qual_pm", "sm_good_mean"]].to_csv(
        out, index=False, date_format="%Y-%m-%d")
    return out


def fetch(lat: float, lon: float, start: dt.date | str | None = None,
          end: dt.date | str | None = None, force: bool = False,
          method: str = "opendap", workers: int = earthdata.MAX_WORKERS) -> Path:
    """Scarica (a riprese) SMAP SPL3SMP_E v006 per il pixel del punto e scrive ``smap_daily.csv``.

    Ritorna il percorso di ``smap_daily.csv``. Chiama ``cache.ensure_online()`` e
    ``earthdata.login()`` prima di qualsiasi rete.
    """
    cache.ensure_online("SMAP SPL3SMP_E v006")
    earthdata.login()
    if method not in ("opendap", "download"):
        raise ValueError("method deve essere 'opendap' o 'download'")
    start = max(_as_date(start, FIRST_DAY), FIRST_DAY)
    end = _as_date(end, dt.date(config.END_YEAR, 12, 31))
    row, col, clat, clon = pixel_index(lat, lon)
    worker = _row_from_subset if method == "opendap" else _row_from_download
    params = {
        "lat": lat, "lon": lon, "ease_row": row, "ease_col": col,
        "pixel_center_lat": clat, "pixel_center_lon": clon,
        "grid": "EASE-Grid 2.0 Global 9 km (EPSG:6933), 1624 x 3856",
        "pixel_size_m": PIXEL_M,
        "variables": {k: [GROUPS[k]["group"], GROUPS[k]["sm"], GROUPS[k]["qual"]] for k in GROUPS},
        "units": UNITS, "fill_value_sm": FILL_SM, "fill_value_qual": FILL_QUAL,
        "good_flags": list(GOOD_FLAGS), "access": method, "doi": DOI,
        "fill_policy": "valori di riempimento salvati come vuoto (NaN)",
    }
    earthdata.fetch_years(
        raw=_raw_dir(lat, lon), prefix="smap", source=SOURCE, short_name=SHORT_NAME,
        version=VERSION, url=f"https://doi.org/{DOI}", params=params, start=start, end=end,
        extract=lambda g: worker(g, row, col, clat, clon), force=force, workers=workers,
        notes="umidita' superficiale SMAP L3 enhanced 9 km, passaggi AM e PM")
    return build_processed(lat, lon)


def load(lat: float, lon: float) -> pd.DataFrame:
    """Legge ``smap_daily.csv`` dalla cache (mai la rete). CacheMiss se manca."""
    p = processed_path(lat, lon, create=False)
    if not p.exists():
        raise cache.CacheMiss(f"dato non in cache: {p} - per scaricarlo: "
                              f"python -m fieldwise.data.smap --lat {lat} --lon {lon}")
    return pd.read_csv(p, parse_dates=["date"])


def _as_date(v, default: dt.date) -> dt.date:
    if v is None:
        return default
    if isinstance(v, dt.datetime):
        return v.date()
    if isinstance(v, dt.date):
        return v
    return dt.date.fromisoformat(str(v))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scarica SMAP SPL3SMP_E v006 per un punto.")
    ap.add_argument("--lat", type=float, default=config.PILOT_LAT)
    ap.add_argument("--lon", type=float, default=config.PILOT_LON)
    ap.add_argument("--start", default=None, help="AAAA-MM-GG (default 2015-03-31)")
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
    print(f"{out}: {len(df)} giorni, {df['sm_good_mean'].notna().sum()} con umidita' di qualita' raccomandata")
    return 0


if __name__ == "__main__":
    sys.exit(main())
