"""Client SoilGrids 250 m v2.0 (ISRIC): proprieta' del suolo di un punto.

Sorgente predefinita: WCS ``https://maps.isric.org/mapserv?map=/map/<proprieta'>.map`` (GetCoverage 2.0.1,
un coverage per proprieta'/profondita'/statistica, riquadro di circa 0,02 gradi attorno al punto,
uscita GeoTIFF in EPSG:4326 con ricampionamento al vicino: i valori sono quelli nativi a 250 m).
REST ``https://rest.isric.org/soilgrids/v2.0/properties/query`` e' disponibile
soltanto con FIELDWISE_SOILGRIDS_PRIMARY=rest (con fallback WCS); la modalita'
`auto` tenta prima WCS poi REST. Un raster WCS completo gia' scaricato puo'
essere ricampionato su un altro punto interno alla stessa finestra, evitando
nuove chiamate di rete ma senza riusare i valori del punto originario.
La via usata e' scritta nel .meta.json (campo ``notes``) e nel JSON grezzo (campo ``via``).

Proprieta': sand, clay, silt, soc, bdod, cfvo. Profondita': 0-5, 5-15, 15-30, 30-60, 60-100,
100-200 cm. Statistiche: mean, Q0.05, Q0.5, Q0.95, uncertainty.

Unita' "mappate" e conversione (fattore ``d_factor`` della risposta REST; per il WCS la
tabella ufficiale della FAQ SoilGrids, https://www.isric.org/explore/soilgrids/faq-soilgrids):

=======  ===========  ========  =====================  ============
prop.    mappata      d_factor  convenzionale          nota
=======  ===========  ========  =====================  ============
sand     g/kg         10        % in peso              mean/10
clay     g/kg         10        % in peso
silt     g/kg         10        % in peso
soc      dg/kg        10        g/kg  (anche in %)     %: mappato/100
bdod     cg/cm3       100       g/cm3 (= kg/dm3)
cfvo     cm3/dm3      10        % in volume
=======  ===========  ========  =====================  ============

``uncertainty`` e' l'indice di incertezza fornito da SoilGrids (intero adimensionale, nel
CSV tal quale): non e' convertita con d_factor e non e' ricostruibile dai quantili.

Pixel senza dato (abitato, acqua): si prende il pixel valido piu' vicino entro ~500 m
(``MAX_SHIFT_M``); lo spostamento e' documentato nel JSON grezzo, nel meta e in ``pixel_info()``.
Nel WCS un pixel e' valido se, a tutte le profondita', sabbia+argilla+limo > 0 e bdod > 0
(il servizio riempie i pixel senza dato con 0 o con valori negativi).

Elaborati in ``cache.processed_dir(lat, lon)``:

* ``soilgrids_layers.csv``: property, depth_label, top_cm, bottom_cm, mapped_mean, mean, q05,
  q50, q95, uncertainty, unit. Oltre alle sei proprieta' c'e' ``soc_pct`` (carbonio organico in
  %, = g/kg / 10) con le stesse colonne.
* ``soilgrids_agg.csv``: property, layer, top_cm, bottom_cm, mean, q05, q95, unit; media
  pesata sullo spessore degli strati per gli orizzonti 0-30, 30-100 e 100-200 cm.
  APPROSSIMAZIONE: per q05 e q95 si usa la media pesata dei quantili degli strati, che non e'
  il quantile dell'orizzonte (i quantili non si sommano; le correlazioni verticali sono
  ignorate). Va letta come ordine di grandezza dell'incertezza, non come intervallo esatto.
  Riga derivata ``om`` (sostanza organica %) = carbonio organico % x 1,724 (fattore di
  van Bemmelen: ipotesi di 58% di carbonio nella sostanza organica); anche i quantili sono
  moltiplicati per 1,724.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

from . import cache

log = logging.getLogger(__name__)

SOURCE = "soilgrids"
PRODUCT = "SoilGrids 250m"
VERSION = "2.0"
REST_URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
WCS_URL = "https://maps.isric.org/mapserv"

PROPERTIES = ("sand", "clay", "silt", "soc", "bdod", "cfvo")
DEPTHS = ((0, 5), (5, 15), (15, 30), (30, 60), (60, 100), (100, 200))
STATS = ("mean", "Q0.05", "Q0.5", "Q0.95", "uncertainty")

# conversione: d_factor, unita' mappata, unita' convenzionale (FAQ SoilGrids)
UNITS: dict[str, dict[str, Any]] = {
    "sand": {"d_factor": 10, "mapped": "g/kg", "unit": "%"},
    "clay": {"d_factor": 10, "mapped": "g/kg", "unit": "%"},
    "silt": {"d_factor": 10, "mapped": "g/kg", "unit": "%"},
    "soc": {"d_factor": 10, "mapped": "dg/kg", "unit": "g/kg"},
    "bdod": {"d_factor": 100, "mapped": "cg/cm3", "unit": "g/cm3"},
    "cfvo": {"d_factor": 10, "mapped": "cm3/dm3", "unit": "% vol"},
}
SOC_PCT = {"d_factor": 100, "mapped": "dg/kg", "unit": "%"}  # derivata da soc
VAN_BEMMELEN = 1.724
HORIZONS = ((0, 30), (30, 100), (100, 200))

# ISRIC's beta REST service has been paused. WCS is the default; REST
# remains opt-in for later recovery/testing via FIELDWISE_SOILGRIDS_PRIMARY=rest.
# A full WCS profile needs 6 properties x 6 depths x 5 statistics = 180
# GetCoverage calls, so we also reuse valid nearby WCS windows (not values
# interpolated or copied from a different point).
# robustezza di rete
REST_TIMEOUT = (20, 90)          # (connessione, lettura) in secondi
REST_ATTEMPTS = 5
REST_WAITS = (5, 15, 30, 60)     # attese tra un tentativo e il successivo
WCS_TIMEOUT = (20, 120)
WCS_ATTEMPTS = 4
WCS_WAITS = (3, 8, 20)
WCS_WORKERS = 4
WCS_HALF_BOX_DEG = 0.01          # semi-lato del riquadro (circa 0,8-1,1 km)
MAX_SHIFT_M = 500.0
REST_SHIFT_STEP_M = 250.0

_sleep = time.sleep              # sostituibile nei test


class SoilGridsError(RuntimeError):
    """Il servizio non ha restituito dati utilizzabili."""


# --------------------------------------------------------------------------- rete

def _http_get(url: str, params: Any = None, timeout: Any = None) -> requests.Response:
    """Unico punto di accesso alla rete (sostituito nei test)."""
    resp = requests.get(url, params=params, timeout=timeout,
                        headers={"User-Agent": "fieldwise/0.2 (research prototype)"})
    resp.raise_for_status()
    return resp


def _retry(fn, attempts: int, waits: tuple[float, ...], what: str):
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except (requests.RequestException, ValueError, SoilGridsError) as exc:
            last = exc
            if i < attempts - 1:
                _sleep(waits[min(i, len(waits) - 1)])
    raise SoilGridsError(f"{what}: {attempts} tentativi falliti ({last})")


def _meters_per_deg(lat: float) -> tuple[float, float]:
    """(metri per grado di longitudine, metri per grado di latitudine) approssimati."""
    return 111_320.0 * float(np.cos(np.radians(lat))), 110_574.0


# --------------------------------------------------------------------------- REST

def _rest_query(lat: float, lon: float, prop: str) -> dict:
    params = [("lon", f"{lon:.6f}"), ("lat", f"{lat:.6f}"), ("property", prop)]
    params += [("depth", f"{t}-{b}cm") for t, b in DEPTHS]
    params += [("value", s) for s in STATS]

    def go():
        data = _http_get(REST_URL, params=params, timeout=REST_TIMEOUT).json()
        if not isinstance(data, dict) or "properties" not in data:
            raise SoilGridsError("risposta REST senza 'properties'")
        return data

    return _retry(go, REST_ATTEMPTS, REST_WAITS, f"REST {prop}")


def _rest_all_null(resp: dict) -> bool:
    for layer in resp["properties"].get("layers", []):
        for d in layer.get("depths", []):
            if any(v is not None for v in d.get("values", {}).values()):
                return False
    return True


def _shift_candidates(max_m: float = MAX_SHIFT_M, step: float = REST_SHIFT_STEP_M):
    """Spostamenti (dx_m, dy_m) ordinati per distanza, escluso lo zero."""
    n = int(max_m // step)
    cand = [(i * step, j * step) for i in range(-n, n + 1) for j in range(-n, n + 1)
            if (i, j) != (0, 0) and np.hypot(i * step, j * step) <= max_m + 1e-9]
    return sorted(cand, key=lambda c: (np.hypot(*c), c))


def _fetch_rest(lat: float, lon: float) -> dict:
    mlon, mlat = _meters_per_deg(lat)
    responses: dict[str, dict] = {}
    # la prima proprieta' decide se il pixel ha dato; se no, si sposta il punto
    point = (lat, lon, 0.0, 0.0)
    first = _rest_query(lat, lon, PROPERTIES[0])
    if _rest_all_null(first):
        for dx, dy in _shift_candidates():
            plat, plon = lat + dy / mlat, lon + dx / mlon
            r = _rest_query(plat, plon, PROPERTIES[0])
            if not _rest_all_null(r):
                first, point = r, (plat, plon, dx, dy)
                break
        else:
            raise SoilGridsError(f"nessun pixel valido entro {MAX_SHIFT_M:.0f} m")
    responses[PROPERTIES[0]] = first
    for prop in PROPERTIES[1:]:
        responses[prop] = _rest_query(point[0], point[1], prop)
    shift_m = float(np.hypot(point[2], point[3]))
    return {
        "via": "rest",
        "requested": {"lat": lat, "lon": lon},
        "queried": {"lat": point[0], "lon": point[1]},
        "shift_m": shift_m,
        "responses": responses,
    }


def _parse_rest(raw: dict) -> list[dict]:
    """Risposte REST -> righe canoniche (una per proprieta' e profondita')."""
    rows = []
    for prop, resp in raw["responses"].items():
        for layer in resp["properties"]["layers"]:
            name = layer["name"]
            um = layer.get("unit_measure", {}) or {}
            d_factor = um.get("d_factor") or UNITS[name]["d_factor"]
            for d in layer["depths"]:
                rng = d["range"]
                vals = d.get("values", {})
                rows.append({
                    "property": name,
                    "top": int(rng["top_depth"]), "bottom": int(rng["bottom_depth"]),
                    "d_factor": float(d_factor),
                    "mapped": {s: vals.get(s) for s in STATS},
                })
    return rows


# --------------------------------------------------------------------------- WCS

def _decode_tiff(content: bytes) -> dict:
    """GeoTIFF (EPSG:4326) -> array + origine (angolo alto-sinistra) e passo in gradi."""
    from PIL import Image

    im = Image.open(io.BytesIO(content))
    arr = np.array(im).astype(np.int64)
    tags = im.tag_v2
    tie, scale = tags.get(33922), tags.get(33550)
    if tie is None or scale is None:
        raise SoilGridsError("GeoTIFF senza georeferenziazione")
    return {"values": arr.tolist(), "origin_lon": float(tie[3]), "origin_lat": float(tie[4]),
            "dx": float(scale[0]), "dy": float(scale[1])}


def _wcs_one(args: tuple[str, int, int, str, float, float]) -> dict:
    prop, top, bottom, stat, lat, lon = args
    cov = f"{prop}_{top}-{bottom}cm_{stat}"
    h = WCS_HALF_BOX_DEG
    crs = "http://www.opengis.net/def/crs/EPSG/0/4326"
    params = [("map", f"/map/{prop}.map"), ("SERVICE", "WCS"), ("VERSION", "2.0.1"),
              ("REQUEST", "GetCoverage"), ("COVERAGEID", cov), ("FORMAT", "image/tiff"),
              ("SUBSETTINGCRS", crs), ("OUTPUTCRS", crs),
              ("SUBSET", f"X({lon - h:.6f},{lon + h:.6f})"),
              ("SUBSET", f"Y({lat - h:.6f},{lat + h:.6f})")]

    def go():
        resp = _http_get(WCS_URL, params=params, timeout=WCS_TIMEOUT)
        if "tiff" not in resp.headers.get("Content-Type", "").lower():
            raise SoilGridsError(f"{cov}: risposta non TIFF ({resp.text[:120]!r})")
        return _decode_tiff(resp.content)

    out = _retry(go, WCS_ATTEMPTS, WCS_WAITS, f"WCS {cov}")
    out.update({"property": prop, "top": top, "bottom": bottom, "stat": stat})
    return out


def _fetch_wcs(lat: float, lon: float) -> dict:
    jobs = [(p, t, b, s, lat, lon) for p in PROPERTIES for t, b in DEPTHS for s in STATS]
    with ThreadPoolExecutor(max_workers=WCS_WORKERS) as ex:
        coverages = list(ex.map(_wcs_one, jobs))
    return {"via": "wcs", "requested": {"lat": lat, "lon": lon},
            "half_box_deg": WCS_HALF_BOX_DEG, "coverages": coverages}


def _parse_wcs(raw: dict, lat: float, lon: float) -> tuple[list[dict], dict]:
    """Coverage WCS -> (righe canoniche, informazioni sul pixel scelto)."""
    covs = raw["coverages"]
    ref = covs[0]
    grid = (ref["origin_lon"], ref["origin_lat"], ref["dx"], ref["dy"])
    for c in covs:
        if (c["origin_lon"], c["origin_lat"], c["dx"], c["dy"]) != grid:
            raise SoilGridsError("le finestre WCS non hanno la stessa griglia")
    arrays = {(c["property"], c["top"], c["bottom"], c["stat"]): np.array(c["values"], float)
              for c in covs}
    nrows, ncols = ref_shape = np.array(ref["values"]).shape

    def mean_at(prop, top, bottom):
        return arrays[(prop, top, bottom, "mean")]

    valid = np.ones(ref_shape, bool)
    for t, b in DEPTHS:
        tex = mean_at("sand", t, b) + mean_at("clay", t, b) + mean_at("silt", t, b)
        valid &= (tex > 0) & (mean_at("bdod", t, b) > 0)
        for a in (mean_at("sand", t, b), mean_at("clay", t, b), mean_at("silt", t, b)):
            valid &= a >= 0

    o_lon, o_lat, dx, dy = grid
    col0 = int(np.floor((lon - o_lon) / dx))
    row0 = int(np.floor((o_lat - lat) / dy))
    mlon, mlat = _meters_per_deg(lat)
    cols, rows_ = np.meshgrid(np.arange(ncols), np.arange(nrows))
    clon = o_lon + (cols + 0.5) * dx
    clat = o_lat - (rows_ + 0.5) * dy
    dist = np.hypot((clon - lon) * mlon, (clat - lat) * mlat)
    in_win = 0 <= row0 < nrows and 0 <= col0 < ncols
    if in_win and valid[row0, col0]:
        row, col = row0, col0
    else:
        d = np.where(valid, dist, np.inf)
        idx = np.unravel_index(int(np.argmin(d)), d.shape)
        if not np.isfinite(d[idx]) or d[idx] > MAX_SHIFT_M:
            raise SoilGridsError(f"nessun pixel valido entro {MAX_SHIFT_M:.0f} m")
        row, col = int(idx[0]), int(idx[1])
    own_valid = bool(in_win and valid[row0, col0])
    info = {
        "pixel_row": row, "pixel_col": col,
        "pixel_center_lat": float(clat[row, col]), "pixel_center_lon": float(clon[row, col]),
        "own_pixel_valid": own_valid,
        "shift_m": 0.0 if own_valid else float(dist[row, col]),
    }
    out = []
    for prop in PROPERTIES:
        for t, b in DEPTHS:
            out.append({
                "property": prop, "top": t, "bottom": b,
                "d_factor": float(UNITS[prop]["d_factor"]),
                "mapped": {s: float(arrays[(prop, t, b, s)][row, col]) for s in STATS},
            })
    return out, info


# --------------------------------------------------------------------------- elaborazione

def _nan(v) -> float:
    return np.nan if v is None else float(v)


def _layers_frame(canon: list[dict]) -> pd.DataFrame:
    recs = []
    for r in canon:
        prop = r["property"]
        m = {s: _nan(r["mapped"].get(s)) for s in STATS}
        specs = [(prop, r["d_factor"], UNITS[prop]["unit"])]
        if prop == "soc":
            specs.append(("soc_pct", r["d_factor"] * 10, SOC_PCT["unit"]))
        for name, d, unit in specs:
            recs.append({
                "property": name, "depth_label": f"{r['top']}-{r['bottom']}cm",
                "top_cm": r["top"], "bottom_cm": r["bottom"],
                "mapped_mean": m["mean"], "mean": m["mean"] / d,
                "q05": m["Q0.05"] / d, "q50": m["Q0.5"] / d, "q95": m["Q0.95"] / d,
                "uncertainty": m["uncertainty"], "unit": unit,
            })
    df = pd.DataFrame(recs)
    order = {p: i for i, p in enumerate([*PROPERTIES, "soc_pct"])}
    df["_o"] = df["property"].map(order)
    df = df.sort_values(["_o", "top_cm"]).drop(columns="_o").reset_index(drop=True)
    return df


def aggregate(layers: pd.DataFrame) -> pd.DataFrame:
    """Media pesata sullo spessore per gli orizzonti 0-30, 30-100, 100-200 cm (+ riga om)."""
    recs = []
    for prop, g in layers.groupby("property", sort=False):
        for top, bottom in HORIZONS:
            sel = g[(g["top_cm"] >= top) & (g["bottom_cm"] <= bottom)]
            w = (sel["bottom_cm"] - sel["top_cm"]).to_numpy(float)
            if w.sum() != bottom - top:
                raise SoilGridsError(f"{prop}: strati non coprono {top}-{bottom} cm")
            recs.append({
                "property": prop, "layer": f"{top}-{bottom}cm",
                "top_cm": top, "bottom_cm": bottom,
                "mean": float(np.average(sel["mean"], weights=w)),
                "q05": float(np.average(sel["q05"], weights=w)),
                "q95": float(np.average(sel["q95"], weights=w)),
                "unit": sel["unit"].iloc[0],
            })
    agg = pd.DataFrame(recs)
    om = agg[agg["property"] == "soc_pct"].copy()
    for c in ("mean", "q05", "q95"):
        om[c] = om[c] * VAN_BEMMELEN
    om["property"], om["unit"] = "om", "%"
    return pd.concat([agg, om], ignore_index=True)


def _raw_path(lat: float, lon: float, via: str) -> Path:
    return cache.raw_dir(SOURCE, lat, lon) / f"soilgrids_{via}.json"


def _find_raw(lat: float, lon: float) -> Path:
    d = cache.raw_dir(SOURCE, lat, lon, create=False)
    for via in ("rest", "wcs"):
        p = d / f"soilgrids_{via}.json"
        if cache.is_cached(p):
            return p
    raise cache.CacheMiss(
        f"dato non in cache: {d}/soilgrids_(rest|wcs).json - per scaricarlo: "
        f"python -m fieldwise.data.soilgrids --lat {lat} --lon {lon}")


def _canonical(raw: dict, lat: float, lon: float) -> tuple[list[dict], dict]:
    if raw["via"] == "rest":
        info = {"via": "rest", "shift_m": raw.get("shift_m", 0.0),
                "queried_lat": raw["queried"]["lat"], "queried_lon": raw["queried"]["lon"]}
        return _parse_rest(raw), info
    canon, info = _parse_wcs(raw, lat, lon)
    return canon, {"via": "wcs", **info}


def _process(lat: float, lon: float, raw_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    canon, info = _canonical(raw, lat, lon)
    layers = _layers_frame(canon)
    agg = aggregate(layers)
    out = cache.processed_dir(lat, lon)
    layers.to_csv(out / "soilgrids_layers.csv", index=False)
    agg.to_csv(out / "soilgrids_agg.csv", index=False)
    return layers, agg, info


# --------------------------------------------------------------------------- API pubblica

def _cached_nearby_wcs(lat: float, lon: float) -> dict | None:
    """Reuse an existing georeferenced WCS raster window covering this point.

    The new location is sampled separately from the original rasters via
    _parse_wcs: never treat the source point's already-sampled soil values as
    measurements of the new point. The source must have a valid cache meta.
    """
    root = cache.raw_dir(SOURCE, key="__unused__", create=False).parent
    if not root.exists():
        return None
    for path in root.glob("lat*_lon*/soilgrids_wcs.json"):
        if not cache.is_cached(path):
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if raw.get("via") != "wcs" or not raw.get("coverages"):
                continue
            origin = raw.get("requested", {})
            # Fast filter before decoding a large 180-coverage JSON file.
            if (abs(float(origin["lat"]) - lat) > 2 * WCS_HALF_BOX_DEG or
                    abs(float(origin["lon"]) - lon) > 2 * WCS_HALF_BOX_DEG):
                continue
            ref = raw["coverages"][0]
            values = ref["values"]
            height, width = len(values), len(values[0])
            left, top = float(ref["origin_lon"]), float(ref["origin_lat"])
            dx, dy = float(ref["dx"]), float(ref["dy"])
            if dx <= 0 or dy <= 0 or not (left <= lon < left + width * dx and
                                          top - height * dy < lat <= top):
                continue
            # Check validity and pixel selection at the NEW location. This also
            # enforces the unchanged 500 m nodata shift limit.
            _parse_wcs(raw, lat, lon)
            source_meta = cache.read_meta(path)
            return {
                **raw,
                "requested": {"lat": lat, "lon": lon},
                "reused_from": {
                    "lat": origin["lat"], "lon": origin["lon"],
                    "downloaded_at_utc": source_meta.get("downloaded_at_utc"),
                },
            }
        except (ValueError, TypeError, KeyError, IndexError, OSError, SoilGridsError):
            # One corrupt/incompatible cached window must not block others.
            continue
    return None


def fetch(lat: float, lon: float, force: bool = False) -> Path:
    """Recupera SoilGrids (cache, WCS di default, REST opt-in) e salva gli elaborati.

    Restituisce il percorso del JSON grezzo. Con force=False e cache valida non tocca la rete.
    """
    d = cache.raw_dir(SOURCE, lat, lon)
    if not force:
        for via in ("rest", "wcs"):
            p = d / f"soilgrids_{via}.json"
            if cache.is_cached(p):
                if not (cache.processed_dir(lat, lon) / "soilgrids_agg.csv").exists():
                    _process(lat, lon, p)
                return p
    start = time.perf_counter()
    raw = None if force else _cached_nearby_wcs(lat, lon)
    if raw is None:
        cache.ensure_online("SoilGrids")
        mode = os.environ.get("FIELDWISE_SOILGRIDS_PRIMARY", "wcs").strip().lower()
        if mode not in {"wcs", "rest", "auto"}:
            raise ValueError("FIELDWISE_SOILGRIDS_PRIMARY must be wcs, rest or auto")
        errors: list[str] = []
        if mode == "rest":
            # Legacy route, opt-in while ISRIC REST is paused.
            try:
                raw = _fetch_rest(lat, lon)
            except SoilGridsError as exc:
                errors.append(str(exc))
            if raw is None:
                raw = _fetch_wcs(lat, lon)
        else:
            # No failed REST retries on the normal path.
            try:
                raw = _fetch_wcs(lat, lon)
            except SoilGridsError as exc:
                if mode != "auto":
                    raise
                errors.append(str(exc))
                raw = _fetch_rest(lat, lon)
        if errors:
            raw["upstream_error"] = errors[0]
    via = raw["via"]
    log.info("SoilGrids %s for %s in %.1f s%s", via, cache.point_key(lat, lon),
             time.perf_counter() - start,
             " (reused cached WCS coverage)" if raw.get("reused_from") else "")

    for other in ("rest", "wcs"):  # niente grezzi doppi
        if other != via:
            for f in (d / f"soilgrids_{other}.json", cache.meta_path(d / f"soilgrids_{other}.json")):
                f.unlink(missing_ok=True)
    path = d / f"soilgrids_{via}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    _, _, info = _process(lat, lon, path)
    notes = f"via={via}"
    if raw.get("reused_from"):
        notes += f"; WCS raster cached at {raw['reused_from']['lat']}, {raw['reused_from']['lon']}"
    if raw.get("upstream_error"):
        notes += f"; previous source failed: {raw['upstream_error']}"
    if info.get("shift_m", 0.0) > 0:
        notes += f"; pixel spostato di {info['shift_m']:.0f} m (pixel del punto senza dato)"
    else:
        notes += "; pixel del punto valido, nessuno spostamento"
    cache.write_meta(
        path, source=SOURCE, product=PRODUCT, version=VERSION,
        url=REST_URL if via == "rest" else WCS_URL,
        params={"lat": lat, "lon": lon, "properties": list(PROPERTIES),
                "depths_cm": [f"{t}-{b}" for t, b in DEPTHS], "values": list(STATS),
                "via": via, "pixel": info,
                "reused_from": raw.get("reused_from")},
        notes=notes)
    return path


def load(lat: float, lon: float) -> pd.DataFrame:
    """Strati (``soilgrids_layers.csv``) dalla cache; CacheMiss se manca. Mai rete."""
    raw_path = _find_raw(lat, lon)
    csv = cache.processed_dir(lat, lon, create=False) / "soilgrids_layers.csv"
    if not csv.exists():
        _process(lat, lon, raw_path)
    return pd.read_csv(csv)


def load_aggregated(lat: float, lon: float) -> pd.DataFrame:
    """Aggregato per orizzonti (``soilgrids_agg.csv``) dalla cache; CacheMiss se manca."""
    raw_path = _find_raw(lat, lon)
    csv = cache.processed_dir(lat, lon, create=False) / "soilgrids_agg.csv"
    if not csv.exists():
        _process(lat, lon, raw_path)
    return pd.read_csv(csv)


def pixel_info(lat: float, lon: float) -> dict:
    """Via usata (rest/wcs), pixel scelto ed eventuale spostamento in metri."""
    raw_path = _find_raw(lat, lon)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    return _canonical(raw, lat, lon)[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scarica SoilGrids 250 m per un punto")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    path = fetch(a.lat, a.lon, force=a.force)
    print(f"grezzo: {path}")
    print(f"pixel: {pixel_info(a.lat, a.lon)}")
    print(load_aggregated(a.lat, a.lon).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
