"""Client NDVI MODIS (MOD13Q1, 250 m, 16 giorni) dal servizio ORNL DAAC MODIS/VIIRS subsets.

Sorgente: https://modis.ornl.gov/rst/api/v1/  (REST, nessun login).

Finestra: kmAboveBelow=1, kmLeftRight=1 -> griglia 9x9 pixel (~2 km) attorno al punto,
perche' un solo pixel da 250 m puo' non cadere in un campo coltivato. Il pixel centrale
e' (riga 4, colonna 4); i pixel sono numerati per righe dall'alto (nord) a sinistra
(ovest): pixel = row * ncols + col.

Significato dei flag (MOD13 User Guide, LP DAAC, "MOD13Q1 SDS: 250m 16 days pixel
reliability" e "250m 16 days VI Quality"):

* pixel_reliability (rank): -1 = nessun dato / fill; 0 = dato buono; 1 = dato marginale
  (utile ma da verificare con VI_Quality); 2 = coperto da neve/ghiaccio; 3 = coperto da
  nuvole. In questo modulo "good" = pixel_reliability in {0, 1} (e NDVI valido); sono
  esclusi 2, 3 e -1.
* VI_Quality (campo di bit a 16 bit, riportato grezzo): bit 0-1 qualita' MODLAND (0 buona,
  1 controllare altri QA, 2 non prodotto per nuvole, 3 non prodotto per altri motivi);
  bit 2-5 utilita' dell'indice; bit 6-7 quantita' di aerosol; bit 8 nuvole adiacenti;
  bit 9 correzione atmosferica; bit 10 nuvole miste; bit 11-13 maschera terra/acqua;
  bit 14 possibile neve/ghiaccio; bit 15 possibile ombra.

NDVI = valore intero * fattore di scala letto dalla risposta (atteso 0.0001); il valore di
riempimento (fill_value da /bands, atteso -3000) diventa NaN.

Versione/collezione: l'endpoint /products non dichiara la collezione del prodotto (solo
nome e descrizione); il meta registra cio' che il servizio dichiara, cioe' la descrizione.

Cache (contratto in fieldwise.data.cache): un file grezzo JSON per blocco di <= 10 date in
data/raw/modis/<punto>/, ognuno col suo .meta.json; i blocchi gia' in cache non si
riscaricano. Elaborati in data/processed/<punto>/: modis_ndvi_pixels.csv (formato lungo) e
modis_ndvi.csv (una riga per data di composizione).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from . import cache

BASE_URL = "https://modis.ornl.gov/rst/api/v1/"
PRODUCT = "MOD13Q1"
SOURCE = "modis"
BANDS = ("250m_16_days_NDVI", "250m_16_days_pixel_reliability", "250m_16_days_VI_Quality")
BAND_NDVI, BAND_REL, BAND_QA = BANDS
KM_ABOVE_BELOW = 1
KM_LEFT_RIGHT = 1
MAX_DATES_PER_REQUEST = 10
PAUSE_S = 0.5            # pausa tra due richieste
RETRIES = 3
BACKOFF_S = 2.0          # attesa prima del tentativo 2 = 2 s, prima del 3 = 4 s
TIMEOUT_S = 120
GOOD_RELIABILITY = (0, 1)
DEFAULT_FILL = -3000
DEFAULT_SCALE = 0.0001

PIXEL_FILE = "modis_ndvi_pixels.csv"
SERIES_FILE = "modis_ndvi.csv"
CATALOG_FILE = "catalog.json"


# --------------------------------------------------------------------------- rete

def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """GET con 3 tentativi e attesa crescente."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        if attempt:
            time.sleep(BACKOFF_S * 2 ** (attempt - 1))
        try:
            r = requests.get(url, params=params, headers={"Accept": "application/json"},
                             timeout=TIMEOUT_S)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
    raise RuntimeError(f"richiesta fallita dopo {RETRIES} tentativi: {url} {params}: {last}")


def _request_url(url: str, params: dict[str, Any]) -> str:
    return requests.Request("GET", url, params=params).prepare().url or url


def _write_json(path: Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# --------------------------------------------------------------------------- catalogo

def _fetch_catalog(lat: float, lon: float, raw: Path, force: bool) -> dict[str, Any]:
    """Prodotto, bande e elenco date (una volta, poi dalla cache)."""
    path = raw / CATALOG_FILE
    if cache.is_cached(path) and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    prods = _get_json(BASE_URL + "products")["products"]
    prod = next((p for p in prods if p.get("product") == PRODUCT), None)
    if prod is None:
        raise RuntimeError(f"prodotto {PRODUCT} assente da /products")
    time.sleep(PAUSE_S)
    bands = [b for b in _get_json(BASE_URL + f"{PRODUCT}/bands")["bands"] if b["band"] in BANDS]
    time.sleep(PAUSE_S)
    dates = _get_json(BASE_URL + f"{PRODUCT}/dates",
                      {"latitude": lat, "longitude": lon})["dates"]
    time.sleep(PAUSE_S)
    catalog = {"product": prod, "bands": bands, "dates": dates}
    _write_json(path, catalog)
    cache.write_meta(
        path, source=SOURCE, product=PRODUCT,
        version=f"not declared by service; /products description: {prod.get('description')}",
        url=BASE_URL + "products | bands | dates",
        params={"latitude": lat, "longitude": lon},
        notes="Il servizio non dichiara la collezione MODIS; si registra la descrizione di /products.",
    )
    return catalog


# --------------------------------------------------------------------------- blocchi

def _block_path(raw: Path, block: list[dict[str, str]]) -> Path:
    return raw / f"{PRODUCT}_{block[0]['modis_date']}_{block[-1]['modis_date']}.json"


def _fetch_block(lat: float, lon: float, block: list[dict[str, str]], path: Path,
                 prod: dict[str, Any]) -> None:
    responses: dict[str, Any] = {}
    urls = []
    for band in BANDS:
        params = {"latitude": lat, "longitude": lon, "band": band,
                  "startDate": block[0]["modis_date"], "endDate": block[-1]["modis_date"],
                  "kmAboveBelow": KM_ABOVE_BELOW, "kmLeftRight": KM_LEFT_RIGHT}
        responses[band] = _get_json(BASE_URL + f"{PRODUCT}/subset", params)
        urls.append(_request_url(BASE_URL + f"{PRODUCT}/subset", params))
        time.sleep(PAUSE_S)
    _write_json(path, {"product": PRODUCT, "latitude": lat, "longitude": lon,
                       "dates": block, "responses": responses})
    cache.write_meta(
        path, source=SOURCE, product=PRODUCT,
        version=f"not declared by service; /products description: {prod.get('description')}",
        url=urls[0],
        params={"latitude": lat, "longitude": lon, "bands": list(BANDS),
                "startDate": block[0]["modis_date"], "endDate": block[-1]["modis_date"],
                "kmAboveBelow": KM_ABOVE_BELOW, "kmLeftRight": KM_LEFT_RIGHT,
                "n_dates": len(block)},
        notes="Un file per blocco: le tre bande sono tre richieste, una per banda.",
    )


# --------------------------------------------------------------------------- elaborazione

def _parse_block(path: Path, fill: int, default_scale: float) -> pd.DataFrame:
    obj = json.loads(path.read_text(encoding="utf-8"))
    per_band: dict[str, pd.DataFrame] = {}
    scale = default_scale
    for band, resp in obj["responses"].items():
        nrows, ncols = int(resp["nrows"]), int(resp["ncols"])
        if band == BAND_NDVI:
            try:
                scale = float(resp["scale"])
            except (KeyError, TypeError, ValueError):
                scale = default_scale
        frames = []
        for entry in resp["subset"]:
            data = np.asarray(entry["data"], dtype="int64")
            if data.size != nrows * ncols:
                raise ValueError(f"{path.name}: {data.size} valori, attesi {nrows * ncols}")
            idx = np.arange(data.size)
            frames.append(pd.DataFrame({
                "date": entry["calendar_date"], "pixel": idx,
                "row": idx // ncols, "col": idx % ncols, band: data,
                "_nrows": nrows, "_ncols": ncols,
            }))
        per_band[band] = (pd.concat(frames, ignore_index=True) if frames
                          else pd.DataFrame(columns=["date", "pixel", "row", "col", band,
                                                     "_nrows", "_ncols"]))
    keys = ["date", "pixel", "row", "col"]
    df = per_band[BAND_NDVI]
    for band in (BAND_REL, BAND_QA):
        df = df.merge(per_band[band][keys + [band]], on=keys, how="outer")
    df["_nrows"] = df["_nrows"].ffill()
    df["_ncols"] = df["_ncols"].ffill()
    ndvi = df[BAND_NDVI].astype("float64")
    df["ndvi"] = (ndvi * scale).where((ndvi != fill) & ndvi.notna())
    df["reliability"] = df[BAND_REL]
    df["vi_quality"] = df[BAND_QA]
    return df[keys + ["ndvi", "reliability", "vi_quality", "_nrows", "_ncols"]]


def _process(blocks: list[Path], lat: float, lon: float, fill: int) -> Path:
    parts = [_parse_block(p, fill, DEFAULT_SCALE) for p in blocks]
    long = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    if long.empty:
        raise RuntimeError("nessun dato MODIS da elaborare")
    long = long.drop_duplicates(["date", "pixel"]).sort_values(["date", "pixel"])
    nrows, ncols = int(long["_nrows"].iloc[0]), int(long["_ncols"].iloc[0])
    long = long.drop(columns=["_nrows", "_ncols"]).reset_index(drop=True)
    for c in ("reliability", "vi_quality"):
        long[c] = long[c].astype("Int64")
    out = cache.processed_dir(lat, lon)
    long.to_csv(out / PIXEL_FILE, index=False, float_format="%.4f")

    crow, ccol = nrows // 2, ncols // 2
    good = long["reliability"].isin(GOOD_RELIABILITY) & long["ndvi"].notna()
    gl = long[good]
    g = gl.groupby("date")["ndvi"]
    series = pd.DataFrame({"date": sorted(long["date"].unique())}).set_index("date")
    center = long[(long["row"] == crow) & (long["col"] == ccol)].set_index("date")
    series["ndvi_center"] = center["ndvi"]
    series["reliability_center"] = center["reliability"]
    series["vi_quality_center"] = center["vi_quality"]
    series["ndvi_window_mean_good"] = g.mean()
    series["ndvi_window_median_good"] = g.median()
    series["n_good"] = g.size().reindex(series.index).fillna(0).astype(int)
    series["n_pixels"] = long.groupby("date").size().reindex(series.index).astype(int)
    series = series.reset_index()
    series.to_csv(out / SERIES_FILE, index=False, float_format="%.4f")
    return out / SERIES_FILE


# --------------------------------------------------------------------------- API pubblica

def fetch(lat: float, lon: float, start: str = "2000-01-01", end: str = "2025-12-31",
          force: bool = False) -> Path:
    """Scarica (a blocchi riprendibili) la serie MOD13Q1 e produce i CSV elaborati.

    Restituisce il percorso di modis_ndvi.csv.
    """
    cache.ensure_online("MODIS ORNL DAAC")
    raw = cache.raw_dir(SOURCE, lat, lon)
    catalog = _fetch_catalog(lat, lon, raw, force)
    prod = catalog["product"]
    fill = DEFAULT_FILL
    for b in catalog["bands"]:
        if b["band"] == BAND_NDVI:
            fill = int(b.get("fill_value", DEFAULT_FILL))
    dates = [d for d in catalog["dates"] if start <= d["calendar_date"] <= end]
    if not dates:
        raise RuntimeError(f"nessuna data MODIS tra {start} e {end}")
    blocks = [dates[i:i + MAX_DATES_PER_REQUEST]
              for i in range(0, len(dates), MAX_DATES_PER_REQUEST)]
    paths = []
    for i, block in enumerate(blocks, 1):
        path = _block_path(raw, block)
        paths.append(path)
        if cache.is_cached(path) and not force:
            continue
        _fetch_block(lat, lon, block, path, prod)
        print(f"[modis] blocco {i}/{len(blocks)} {block[0]['calendar_date']}..{block[-1]['calendar_date']}",
              flush=True)
    return _process(paths, lat, lon, fill)


def _load_csv(lat: float, lon: float, name: str) -> pd.DataFrame:
    path = cache.processed_dir(lat, lon) / name
    if not path.exists():
        raise cache.CacheMiss(
            f"dato non in cache: {path} - per scaricarlo: "
            f"python -m fieldwise.data.modis --lat {lat} --lon {lon}")
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load(lat: float, lon: float) -> pd.DataFrame:
    """Serie per data di composizione (solo cache, mai rete)."""
    return _load_csv(lat, lon, SERIES_FILE)


def load_pixels(lat: float, lon: float) -> pd.DataFrame:
    """Pixel della finestra, formato lungo (solo cache, mai rete)."""
    return _load_csv(lat, lon, PIXEL_FILE)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Scarica NDVI MODIS MOD13Q1 (ORNL DAAC)")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", default="2000-01-01")
    ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    print(fetch(a.lat, a.lon, a.start, a.end, a.force))


if __name__ == "__main__":
    main()
