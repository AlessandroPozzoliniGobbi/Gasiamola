"""Client NASA POWER (daily, point, community AG).

fetch() scarica (una volta sola, poi usa la cache), salva il JSON grezzo con i
metadati di provenienza e scrive gli elaborati; load()/load_site() leggono solo
dalla cache. I valori sentinella diventano NaN: nessuna interpolazione e nessun
riempimento dei buchi, e' compito del controllo qualita'.

CLI:  python -m fieldwise.data.power --lat 45.2 --lon 10.0 [--start --end --force]
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

SOURCE = "power"
PRODUCT = "POWER daily point AG"
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
COMMUNITY = "AG"

# parametro POWER -> colonna dell'elaborato
PARAMETERS = {
    "T2M_MAX": "tmax",
    "T2M_MIN": "tmin",
    "T2M": "tmean",
    "PRECTOTCORR": "rain",
    "ALLSKY_SFC_SW_DWN": "srad",
    "RH2M": "rh",
    "WS2M": "wind",
}
COLUMNS = ["date", *PARAMETERS.values()]
DEFAULT_FILL = -999.0

TIMEOUT = (30, 300)  # (connessione, lettura) in secondi
ATTEMPTS = 3
BACKOFF = 5.0  # attesa prima del tentativo n: BACKOFF * n secondi


def _raw_path(lat: float, lon: float, start: str, end: str) -> Path:
    return cache.raw_dir(SOURCE, lat, lon) / f"power_daily_{start}_{end}.json"


def _request(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": COMMUNITY,
        "latitude": lat,
        "longitude": lon,
        "start": start,
        "end": end,
        "format": "JSON",
    }
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = requests.get(URL, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < ATTEMPTS:
                time.sleep(BACKOFF * attempt)
    raise RuntimeError(f"NASA POWER: {ATTEMPTS} tentativi falliti ({last})") from last


def _describe(payload: dict[str, Any]) -> tuple[str, str]:
    """(version, notes) ricavati dalla risposta, per il controllo qualita'."""
    header = payload.get("header", {}) or {}
    api = header.get("api", {}) or {}
    sources = header.get("sources") or []
    version = f"{api.get('name', 'POWER API')} {api.get('version', '?')}; sources: {', '.join(sources) or '?'}"
    notes = [
        f"header.title: {header.get('title')}",
        f"header.api: {json.dumps(api, ensure_ascii=False)}",
        f"header.sources: {json.dumps(sources, ensure_ascii=False)}",
        f"header.fill_value: {header.get('fill_value')}",
        f"header.time_standard: {header.get('time_standard')}",
        f"header.start/end: {header.get('start')}/{header.get('end')}",
        f"geometry: {json.dumps(payload.get('geometry'), ensure_ascii=False)}",
        f"parameters: {json.dumps(payload.get('parameters'), ensure_ascii=False)}",
        f"messages: {json.dumps(payload.get('messages'), ensure_ascii=False)}",
    ]
    extra = {k: v for k, v in header.items()
             if k not in ("title", "api", "sources", "fill_value", "time_standard", "start", "end")}
    if extra:
        notes.append(f"header (altri campi): {json.dumps(extra, ensure_ascii=False)}")
    notes.append(
        "Le sorgenti dichiarate dall'header sono quelle elencate in header.sources "
        "(es. MERRA2 per meteo/pioggia, SYN1DEG = CERES SYN1deg per la radiazione, "
        "POWER = prodotti derivati/quasi in tempo reale). Il passaggio a prodotti "
        "quasi in tempo reale negli ultimi mesi non e' segnalato giorno per giorno: "
        "verificare nel controllo qualita'."
    )
    return version, "\n".join(notes)


def _to_frame(payload: dict[str, Any]) -> pd.DataFrame:
    fill = float(payload.get("header", {}).get("fill_value", DEFAULT_FILL))
    par = payload["properties"]["parameter"]
    df = pd.DataFrame({col: pd.Series(par[name]) for name, col in PARAMETERS.items()})
    df = df.astype(float).replace(fill, np.nan)
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    df.index.name = "date"
    return df.sort_index().reset_index()[COLUMNS]


def _site(payload: dict[str, Any], lat: float, lon: float) -> dict[str, Any]:
    coords = (payload.get("geometry") or {}).get("coordinates") or [None, None, None]
    header = payload.get("header", {}) or {}
    return {
        "lat_requested": lat,
        "lon_requested": lon,
        "lon_returned": coords[0],
        "lat_returned": coords[1],
        "elevation_m": coords[2] if len(coords) > 2 else None,
        "units": {PARAMETERS[k]: v.get("units") for k, v in (payload.get("parameters") or {}).items()
                  if k in PARAMETERS},
        "fill_value": header.get("fill_value", DEFAULT_FILL),
        "time_standard": header.get("time_standard"),
        "community": COMMUNITY,
    }


def _write_processed(payload: dict[str, Any], lat: float, lon: float) -> None:
    out = cache.processed_dir(lat, lon)
    _to_frame(payload).to_csv(out / "power_daily.csv", index=False, date_format="%Y-%m-%d")
    (out / "power_site.json").write_text(
        json.dumps(_site(payload, lat, lon), indent=2, ensure_ascii=False), encoding="utf-8")


def fetch(lat: float, lon: float, start: str = "20000101", end: str = "20251231",
          force: bool = False) -> Path:
    """Scarica (se serve) i dati POWER del punto e scrive grezzo, meta ed elaborati."""
    path = _raw_path(lat, lon, start, end)
    if cache.is_cached(path) and not force:
        payload = json.loads(path.read_text(encoding="utf-8"))
        _write_processed(payload, lat, lon)
        return path
    cache.ensure_online(f"NASA POWER {URL}")
    payload = _request(lat, lon, start, end)
    path.write_text(json.dumps(payload), encoding="utf-8")
    version, notes = _describe(payload)
    cache.write_meta(
        path, source=SOURCE, product=PRODUCT, version=version, url=URL,
        params={"parameters": list(PARAMETERS), "community": COMMUNITY, "latitude": lat,
                "longitude": lon, "start": start, "end": end, "format": "JSON"},
        notes=notes)
    _write_processed(payload, lat, lon)
    return path


def _latest_raw(lat: float, lon: float) -> Path:
    d = cache.raw_dir(SOURCE, lat, lon, create=False)
    cands = sorted(p for p in d.glob("power_daily_*.json") if cache.is_cached(p))
    if not cands:
        raise cache.CacheMiss(
            f"dati POWER non in cache per {cache.point_key(lat, lon)} - "
            f"per scaricarli: python -m fieldwise.data.power --lat {lat} --lon {lon}")
    return cands[-1]


def load(lat: float, lon: float) -> pd.DataFrame:
    """DataFrame giornaliero dalla cache (mai dalla rete); CacheMiss se manca."""
    csv = cache.processed_dir(lat, lon, create=False) / "power_daily.csv"
    if not csv.exists():
        _latest_raw(lat, lon)  # CacheMiss se manca anche il grezzo
        raise cache.CacheMiss(f"elaborato mancante: {csv} - rieseguire fetch()")
    return pd.read_csv(csv, parse_dates=["date"])


def load_site(lat: float, lon: float) -> dict[str, Any]:
    f = cache.processed_dir(lat, lon, create=False) / "power_site.json"
    if not f.exists():
        raise cache.CacheMiss(f"dato non in cache: {f}")
    return json.loads(f.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Scarica NASA POWER daily point (AG)")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", default="20000101")
    ap.add_argument("--end", default="20251231")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    p = fetch(a.lat, a.lon, a.start, a.end, force=a.force)
    print(f"raw: {p}")
    print(f"processed: {cache.processed_dir(a.lat, a.lon) / 'power_daily.csv'}")


if __name__ == "__main__":
    main()
