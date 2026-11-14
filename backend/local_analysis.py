"""Geographic preparation adapter for FIELDWISE, without modifying engine code.

Site-conditioned experimental estimates (not field-measured or validated forecasts).
Coordinates rounded to 0.001 degrees to match the existing engine cache key.
"""
from __future__ import annotations

import hashlib
import json
import math
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fieldwise import __version__, config, ensemble, params, soil
from fieldwise.data import cache, power, soilgrids

MODEL_ADAPTER_VERSION = 1
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fieldwise-local")
_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}
_ACTIVE_POINTS: dict[str, str] = {}


class PreparationError(RuntimeError):
    pass


def normalized_point(point: tuple[float, float]) -> tuple[float, float]:
    """Return (longitude, latitude) at the same precision as cache.point_key."""
    return (round(point[0], 3), round(point[1], 3))


def _point_dir(point: tuple[float, float]) -> Path:
    lon, lat = normalized_point(point)
    return config.DATA_DIR / "processed" / cache.point_key(lat, lon)


def _fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _params_hash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, default=str, ensure_ascii=True).encode()).hexdigest()


def _ready_record(point: tuple[float, float]) -> dict | None:
    directory = _point_dir(point)
    file = directory / "fieldwise_local.json"
    if not file.exists():
        return None
    try:
        rec = json.loads(file.read_text(encoding="utf-8"))
        if (rec.get("adapterVersion") != MODEL_ADAPTER_VERSION or
            rec.get("engineVersion") != __version__ or
            rec.get("point") != list(normalized_point(point))):
            return None
        for name in ("power_daily.csv", "soilgrids_agg.csv", "ensemble_sintesi.csv", "ensemble_meta.json"):
            p = directory / name
            if not p.is_file() or _fingerprint(p) != rec["files"][name]:
                return None
        for file_name, hash_value in rec["paramsFiles"].items():
            p = config.PARAMS_DIR / file_name
            if not p.is_file() or _fingerprint(p) != hash_value:
                return None
        return rec
    except (OSError, ValueError, KeyError, TypeError):
        return None


def ready_record(point: tuple[float, float]) -> dict | None:
    return _ready_record(point)


def _validated_horizons(lat: float, lon: float):
    table = soilgrids.load_aggregated(lat, lon)
    horizons = soil.horizons_from_aggregated(table)
    if [(int(h["top_cm"]), int(h["bottom_cm"])) for h in horizons] != [(0,30),(30,100),(100,200)]:
        raise PreparationError("SoilGrids does not contain a complete soil profile to 200 cm.")
    for h in horizons:
        for key in ("sand", "clay", "silt", "om", "bdod", "cfvo"):
            v = float(h[key])
            if not math.isfinite(v):
                raise PreparationError(f"SoilGrids has no valid {key} for {h['layer']}.")
        if (min(h["sand"], h["clay"], h["silt"]) < 0 or
            abs(h["sand"] + h["clay"] + h["silt"] - 100) > 12 or
            h["om"] <= 0 or h["bdod"] <= 0 or not 0 <= h["cfvo"] < 100):
            raise PreparationError("SoilGrids returned implausible soil properties; cannot simulate safely.")
    return horizons


def build_local_parameters(lat: float, lon: float) -> tuple[dict, dict]:
    """Adapt location-specific SoilGrids values using the engine's existing soil functions.

    Climate, soil texture, soil organic matter, bulk density, water characteristics and
    AquaCrop soil runoff group are local estimates. Other field management assumptions
    remain at project defaults; the output must disclose that limitation.
    """
    raw = params.load_params()
    horizons = _validated_horizons(lat, lon)
    props = soil.profile_properties(horizons, z_max_cm=200, apply_density=False, apply_gravel=False)
    if any(h["fuori_validita"] for h in props):
        raise PreparationError("The local soil is outside the supported Saxton–Rawls calibration range.")
    top, deep = soil.engine_layers(props, (0, 30, 150))
    surface_ksat_day = top["ksat"] * 24
    # AquaCrop v7.3 Reference Manual, Chapter 3, Table 3.7a; Ia/S = 0.05.
    if surface_ksat_day > 864:
        group, cn = "A", 46
    elif surface_ksat_day > 346:
        group, cn = "B", 61
    elif surface_ksat_day > 35:
        group, cn = "C", 72
    else:
        group, cn = "D", 77

    changes: dict[str, object] = {
        "soil.ruscellamento.aquacrop.cn": cn,
        "soil.ruscellamento.gruppo_idrologico": group,
        "soil.profilo.acqua_disponibile_totale": round(top["aw_mm"] + deep["aw_mm"], 3),
    }
    for source, name in zip((top, deep), ("strato_superficiale", "strato_profondo")):
        for key in ("fc", "wp", "sat", "ksat"):
            changes[f"soil.profilo.{name}.{key}"] = round(float(source[key]), 8)
        changes[f"soil.profilo.{name}.acqua_disponibile"] = round(float(source["aw_mm"]), 3)
    for horizon, derived, name in zip(horizons, props, ("s0_30", "s30_100", "s100_200")):
        prefix = f"soil.strati_soilgrids.{name}"
        for field, src in (("sabbia", "sand"), ("argilla", "clay"),
                           ("sostanza_organica", "om"), ("densita_apparente", "bdod"),
                           ("frammenti_grossolani", "cfvo")):
            changes[f"{prefix}.{field}"] = round(float(horizon[src]), 6)
        for field, src in (("fc", "fc"), ("wp", "wp"), ("sat", "sat"),
                           ("ksat", "ksat"), ("acqua_disponibile", "aw_mm")):
            changes[f"{prefix}.{field}"] = round(float(derived[src]), 8)
        # Carbon from SoilGrids is estimated OM / 1.724, in g/kg.
        if name == "s0_30":
            changes[f"{prefix}.carbonio_organico"] = round(float(horizon["om"]) / 1.724 * 10, 5)
            changes[f"{prefix}.limo"] = round(float(horizon["silt"]), 6)
            changes[f"{prefix}.classe_tessiturale"] = soil.usda_texture_class(
                float(horizon["sand"]), float(horizon["clay"]), float(horizon["silt"]))
    p = params.override(raw, changes)
    # The original YAML metadata document the pilot location. Replace provenance
    # on locally overridden entries rather than retaining misleading pilot citations.
    p["soil"]["_meta"] = {
        "descrizione": "Location-conditioned experimental soil profile",
        "coordinate": {"lat": lat, "lon": lon},
        "dati": "SoilGrids 250 m; local meteorology from NASA POWER; agricultural assumptions from shared project YAML",
        "limiti": "No on-site soil sampling or groundwater measurements; estimates require independent validation.",
    }
    for path in changes:
        entry = p
        for segment in path.split("."):
            entry = entry[segment]
        entry["fonte"] = ("SoilGrids 2.0, local pixel; Saxton–Rawls (2006) for derived water properties; "
                          "AquaCrop v7.3 Table 3.7a for runoff group and CN")
        entry["verificato"] = False
        entry["nota"] = "Locally derived estimate; overrides project pilot value, not independently validated."
        entry.pop("intervallo", None)  # pilot-specific uncertainty intervals do not apply here
    pixel = soilgrids.pixel_info(lat, lon)
    return p, {
        "aquaCropRunoffGroup": group, "curveNumber": cn,
        "soilPixelShiftMeters": pixel.get("shift_m", 0),
        "soilDataMethod": pixel.get("via", "unknown"),
        "surfaceTexture": changes["soil.strati_soilgrids.s0_30.classe_tessiturale"],
        "surfaceAvailableWaterMm": round(top["aw_mm"], 1),
        "profileAvailableWaterMm": round(top["aw_mm"] + deep["aw_mm"], 1),
    }


def _set_job(job_id: str, **kwargs):
    with _LOCK:
        _JOBS[job_id].update(kwargs)


def _work(job_id: str, point: tuple[float, float]):
    lon, lat = point
    try:
        directory = _point_dir(point)
        _set_job(job_id, stage="Retrieving NASA POWER historical climate data...")
        power.fetch(lat, lon)
        _set_job(job_id, stage="Retrieving SoilGrids soil profile (REST or WCS fallback)...")
        soilgrids.fetch(lat, lon)
        _set_job(job_id, stage="Deriving local hydraulic properties...")
        p, details = build_local_parameters(lat, lon)
        # Check forcing before running many model simulations.
        from fieldwise import rotation
        rotation.build_context(p=p, lat=lat, lon=lon)
        _set_job(job_id, stage="Comparing crop rotations across historical weather years...")
        detail, summary = ensemble.run_ensemble(p=p, lat=lat, lon=lon)
        if summary.empty or not summary["n_simulazioni"].sum():
            raise PreparationError("The local ensemble did not produce any valid crop-rotation results.")
        ensemble.save_ensemble(detail, summary, lat=lat, lon=lon)
        rec = {
            "adapterVersion": MODEL_ADAPTER_VERSION,
            "engineVersion": __version__, "point": list(point),
            "calculatedAt": datetime.now(timezone.utc).isoformat(),
            "parametersHash": _params_hash(p),
            "files": {name: _fingerprint(directory / name) for name in (
                "power_daily.csv", "soilgrids_agg.csv", "ensemble_sintesi.csv", "ensemble_meta.json")},
            "paramsFiles": {f.name: _fingerprint(f) for f in config.PARAMS_DIR.glob("*.yaml")},
            "details": details,
        }
        tmp = directory / "fieldwise_local.json.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(directory / "fieldwise_local.json")
        _set_job(job_id, status="ready", stage="Local analysis data are ready.")
    except Exception as exc:
        # Do not fall back to pilot data. Present a readable error, leave raw cache for retry.
        _set_job(job_id, status="failed", stage="Local data preparation failed.",
                 error=f"{type(exc).__name__}: {exc}"[:500])
    finally:
        with _LOCK:
            _ACTIVE_POINTS.pop(cache.point_key(lat, lon), None)


def start_preparation(point: tuple[float, float]) -> dict:
    point = normalized_point(point)
    rec = ready_record(point)
    if rec is not None:
        return {"status": "ready", "stage": "Local analysis data are cached.", "modelPoint": point}
    if config.offline():
        raise PreparationError("The selected field has no cached local climate and soil results. Set FIELDWISE_OFFLINE=0 on the backend to enable data download, then restart the server.")
    key = cache.point_key(point[1], point[0])
    with _LOCK:
        previous = _ACTIVE_POINTS.get(key)
        if previous and _JOBS.get(previous, {}).get("status") in {"queued", "running"}:
            return {"jobId": previous, **_JOBS[previous]}
        job_id = uuid.uuid4().hex
        _JOBS[job_id] = {"status": "running", "stage": "Queued for preparation...", "modelPoint": point}
        _ACTIVE_POINTS[key] = job_id
    _POOL.submit(_work, job_id, point)
    return {"jobId": job_id, **_JOBS[job_id]}


def job_status(job_id: str) -> dict | None:
    with _LOCK:
        entry = _JOBS.get(job_id)
        return dict(entry) if entry else None
