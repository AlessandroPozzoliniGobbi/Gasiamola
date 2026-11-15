"""Geographic preparation adapter for FIELDWISE, without modifying engine code.

Site-conditioned experimental estimates (not field-measured or validated forecasts).
Coordinates rounded to 0.001 degrees to match the existing engine cache key.

Safety rules:
* a point whose cache folder is the pilot folder never triggers a local preparation, so the
  pilot ensemble can never be overwritten by a location-conditioned run;
* a cached local result is used only if its record matches the current parameter files,
  engine version, engine source code and every cached file it was derived from; otherwise
  ``local_record_status`` says why it is out of date (it is never silently used);
* the number of running and remembered preparation jobs is bounded.

The API has no authentication: bind it to 127.0.0.1 and do not expose it publicly.
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

MODEL_ADAPTER_VERSION = 2
# Every file a local report is derived from (the detail file feeds the historical windows).
FINGERPRINTED_FILES = ("power_daily.csv", "power_site.json", "soilgrids_agg.csv",
                       "ensemble_sintesi.csv", "ensemble_dettaglio.csv", "ensemble_meta.json")
MAX_ACTIVE_JOBS = 4          # queued or running preparations at the same time
MAX_REMEMBERED_JOBS = 200    # finished jobs kept for status polling
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fieldwise-local")
_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}
_ACTIVE_POINTS: dict[str, str] = {}


class PreparationError(RuntimeError):
    pass


class PreparationBusy(PreparationError):
    """Too many preparations are already running."""


def engine_code_hash() -> str:
    """SHA-256 of the engine source code (``src/fieldwise/**/*.py``), line endings normalised."""
    root = Path(__file__).resolve().parent / "src" / "fieldwise"
    h = hashlib.sha256()
    for f in sorted(root.rglob("*.py")):
        # The optional nine-year optimizer does not participate in historical
        # ensemble preparation. Its UI/output changes must not invalidate the
        # expensive NASA POWER / SoilGrids caches produced by the main engine.
        if f.name == "beam_optimizer.py":
            continue
        h.update(f.relative_to(root).as_posix().encode())
        h.update(f.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


ENGINE_CODE_HASH = engine_code_hash()


def normalized_point(point: tuple[float, float]) -> tuple[float, float]:
    """Return (longitude, latitude) at the same precision as cache.point_key."""
    return (round(point[0], 3), round(point[1], 3))


def _point_dir(point: tuple[float, float]) -> Path:
    lon, lat = normalized_point(point)
    return config.DATA_DIR / "processed" / cache.point_key(lat, lon)


def is_pilot_cell(point: tuple[float, float]) -> bool:
    """True if ``point`` ([lon, lat]) maps to the pilot's cache folder (same 0.001 degree key)."""
    return cache.point_key(point[1], point[0]) == cache.point_key(config.PILOT_LAT, config.PILOT_LON)


def _fingerprint(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _matches(path: Path, saved: str | None) -> bool:
    """True if ``path`` has fingerprint ``saved``, ignoring only LF/CRLF line endings
    (a cache prepared on Windows must stay valid on macOS/Linux and vice versa)."""
    if not saved or not path.is_file():
        return False
    raw = path.read_bytes()
    lf = raw.replace(b"\r\n", b"\n")
    return saved in {hashlib.sha256(x).hexdigest() for x in (raw, lf, lf.replace(b"\n", b"\r\n"))}


def _params_hash(p: dict) -> str:
    return hashlib.sha256(json.dumps(p, sort_keys=True, default=str, ensure_ascii=True).encode()).hexdigest()


_STALE_MESSAGES = {
    "parameters_changed": "the project parameter files changed after these local simulations were computed",
    "engine_changed": "the engine code changed after these local simulations were computed",
    "adapter_changed": "they were prepared by an older version of the local-analysis adapter",
    "files_changed": "a cached input or result file no longer matches the one used for the simulations",
    "corrupt": "the local cache record is unreadable or refers to another point",
}


def local_record_status(point: tuple[float, float]) -> tuple[dict | None, str | None, str]:
    """``(record, reason, message)`` for the local cache of ``point``.

    ``reason`` is None when the record can be used, ``"missing"`` when there is no local
    preparation, otherwise one of ``_STALE_MESSAGES``: the record exists but is out of date
    and must not be used."""
    directory = _point_dir(point)
    file = directory / "fieldwise_local.json"
    if not file.exists():
        return None, "missing", "No local preparation exists for this point."
    try:
        rec = json.loads(file.read_text(encoding="utf-8"))
        if rec.get("point") != list(normalized_point(point)):
            return None, "corrupt", _STALE_MESSAGES["corrupt"]
        saved = rec.get("paramsFiles") or {}
        current = {f.name for f in config.PARAMS_DIR.glob("*.yaml")}
        changed = sorted(n for n in set(saved) | current if not _matches(config.PARAMS_DIR / n, saved.get(n)))
        if changed:
            return None, "parameters_changed", f"{_STALE_MESSAGES['parameters_changed']} ({', '.join(changed)})"
        if rec.get("engineVersion") != __version__ or (
                "engineCodeHash" in rec and rec["engineCodeHash"] != ENGINE_CODE_HASH):
            return None, "engine_changed", _STALE_MESSAGES["engine_changed"]
        if rec.get("adapterVersion") != MODEL_ADAPTER_VERSION or "engineCodeHash" not in rec:
            return None, "adapter_changed", _STALE_MESSAGES["adapter_changed"]
        files = rec.get("files") or {}
        for name in FINGERPRINTED_FILES:
            if not _matches(directory / name, files.get(name)):
                return None, "files_changed", f"{_STALE_MESSAGES['files_changed']} ({name})"
        return rec, None, "Local analysis data are current."
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None, "corrupt", _STALE_MESSAGES["corrupt"]


def _ready_record(point: tuple[float, float]) -> dict | None:
    return local_record_status(point)[0]


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
        if is_pilot_cell(point):
            # Never write a location-conditioned ensemble into the pilot folder.
            raise PreparationError("This point maps to the pilot cache folder; local preparation is not allowed there.")
        _set_job(job_id, stage="Retrieving NASA POWER historical climate data...")
        power.fetch(lat, lon)
        _set_job(job_id, stage="Retrieving SoilGrids soil profile (WCS or cached coverage)...")
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
            "engineVersion": __version__, "engineCodeHash": ENGINE_CODE_HASH, "point": list(point),
            "calculatedAt": datetime.now(timezone.utc).isoformat(),
            "parametersHash": _params_hash(p),
            "files": {name: _fingerprint(directory / name) for name in FINGERPRINTED_FILES},
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


def _prune_jobs() -> None:
    """Forget the oldest finished jobs beyond ``MAX_REMEMBERED_JOBS`` (caller holds the lock)."""
    finished = [k for k, v in _JOBS.items() if v.get("status") not in {"queued", "running"}]
    for k in finished[:max(0, len(_JOBS) - MAX_REMEMBERED_JOBS)]:
        _JOBS.pop(k, None)


def start_preparation(point: tuple[float, float]) -> dict:
    point = normalized_point(point)
    if is_pilot_cell(point):
        raise PreparationError("This point maps to the Cremona pilot cache cell; use the pilot data instead of a local preparation.")
    rec, reason, detail = local_record_status(point)
    if rec is not None:
        return {"status": "ready", "stage": "Local analysis data are cached.", "modelPoint": point}
    if config.offline():
        if reason == "missing":
            raise PreparationError("The selected field has no cached local climate and soil results, and the backend is "
                                   "offline (FIELDWISE_OFFLINE=1), so they cannot be downloaded.")
        raise PreparationError(f"The cached local results for this field are out of date: {detail}. They were not used, "
                               "and the backend is offline (FIELDWISE_OFFLINE=1), so they cannot be regenerated.")
    key = cache.point_key(point[1], point[0])
    with _LOCK:
        previous = _ACTIVE_POINTS.get(key)
        if previous and _JOBS.get(previous, {}).get("status") in {"queued", "running"}:
            return {"jobId": previous, **_JOBS[previous]}
        if len(_ACTIVE_POINTS) >= MAX_ACTIVE_JOBS:
            raise PreparationBusy(f"{MAX_ACTIVE_JOBS} local preparations are already running. Retry in a few minutes.")
        job_id = uuid.uuid4().hex
        stage = "Queued for preparation..." if reason == "missing" else f"Cached local results are out of date ({detail}); preparing again..."
        _JOBS[job_id] = {"status": "running", "stage": stage, "modelPoint": point}
        _ACTIVE_POINTS[key] = job_id
        _prune_jobs()
    _POOL.submit(_work, job_id, point)
    return {"jobId": job_id, **_JOBS[job_id]}


def job_status(job_id: str) -> dict | None:
    with _LOCK:
        entry = _JOBS.get(job_id)
        return dict(entry) if entry else None
