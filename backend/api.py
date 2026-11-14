"""HTTP adapter for the FIELDWISE engine.

Run from backend/: python -m uvicorn api:app --host 127.0.0.1 --port 8000
No scientific model code, params or cached ensemble files are modified here.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from fieldwise import __version__, config, ensemble, ranking
from fieldwise.data.cache import CacheMiss
from local_analysis import PreparationError, normalized_point, ready_record, start_preparation, job_status

app = FastAPI(title="FIELDWISE integration API", version="1.0.0")
_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ALLOWED_ORIGINS += [s.strip().rstrip("/") for s in os.getenv("FIELDWISE_FRONTEND_ORIGINS", "").split(",") if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

PILOT = (config.PILOT_LON, config.PILOT_LAT)
PRIORITIES = tuple(ranking.PRIORITA.keys())


class AnalyzeRequest(BaseModel):
    # GeoJSON order, [longitude, latitude]
    point: tuple[float, float]
    rotation: str = Field(min_length=4, max_length=160)
    scenario: Literal["solo_pioggia", "tetto_irriguo", "irrigazione_libera"]
    priorities: dict[str, float]
    use_pilot_reference: bool = False

    @field_validator("point")
    @classmethod
    def check_point(cls, value: tuple[float, float]) -> tuple[float, float]:
        lon, lat = value
        if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("Invalid geographic coordinates")
        return value

    @field_validator("priorities")
    @classmethod
    def check_priorities(cls, value: dict[str, float]) -> dict[str, float]:
        if not value or any(k not in PRIORITIES or not isinstance(v, (int, float)) or
                            not math.isfinite(v) or v < 0 or v > 10 for k, v in value.items()):
            raise ValueError("Priorities must be named engine priorities between 0 and 10")
        if sum(value.values()) <= 0:
            raise ValueError("Set at least one priority above zero")
        return value

    @field_validator("rotation")
    @classmethod
    def check_rotation(cls, value: str) -> str:
        steps = [x.strip() for x in value.split(" > ")]
        if len(steps) != 3 or any(x not in {"mais", "soia", "frumento", "mais+cover", "soia+cover", "frumento+cover"} for x in steps):
            raise ValueError("Rotation must contain exactly three supported crops, optionally +cover")
        return value


def distance_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(h)))


def number(value):
    try:
        x = float(value)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _metric(row, column):
    return number(row.get(column))


def _english_evidence(entry, current):
    """Faithful English comparisons built from numeric engine outputs.

    Original Italian engine prose is not guessed/translated; the source values drive
    the English summaries, while the raw model strings remain available in the API.
    """
    if current is None:
        return ["Baseline rotation used for comparison."], []
    if entry is current:
        return ["Current rotation — baseline for all comparisons."], []
    labels = {
        "resa_rel_mediana": ("median relative yield", True, "%"),
        "resa_rel_min": ("worst-year relative yield", True, "%"),
        "irrigazione_mm": ("irrigation", False, "mm/year"),
        "concime_kg_n": ("nitrogen fertilizer", False, "kg N/ha/year"),
        "n_lisciviato_kg_n": ("nitrogen leaching", False, "kg N/ha/year"),
        "humus_t_ha": ("annual humus change", True, "t/ha/year"),
        "margine_lordo_eur_ha": ("partial gross margin", True, "EUR/ha/year"),
    }
    better, worse = [], []
    a, b = entry["valori"], current["valori"]
    for key, (label, higher, unit) in labels.items():
        now, before = number(a.get(key)), number(b.get(key))
        if now is None or before is None or abs(now - before) < 1e-7:
            continue
        delta = now - before
        format_value = (lambda v: f"{v*100:.1f}%") if unit == "%" else (lambda v: f"{v:+.2f} {unit}" if key == "humus_t_ha" else f"{v:.1f} {unit}")
        sentence = f"{label.capitalize()}: {format_value(before)} to {format_value(now)}."
        (better if (delta > 0) == higher else worse).append((abs(delta / (abs(before) + 0.01)), sentence))
    better.sort(reverse=True)
    worse.sort(reverse=True)
    evidence = [s for _, s in better[:4]]
    risks = [s for _, s in worse[:3]]
    state = str(a.get("conformita_lombardia_impegno_quinquennale", ""))
    if state == "non_conforme":
        risks.insert(0, "Not compliant with the Lombardy five-year integrated-production rotation rules.")
    elif state == "conforme_solo_in_deroga":
        risks.insert(0, "Compliant only under an exception to the Lombardy five-year rotation rules.")
    if not evidence:
        evidence = ["The selected criteria do not show a clear numerical advantage over the baseline."]
    if not risks:
        risks = ["No decline in the displayed indicators; model uncertainty still applies."]
    return evidence, risks


def _outcome(entry, current):
    if entry is None:
        return None
    v = entry["valori"]
    evidence, risks = _english_evidence(entry, current)
    return {
        "label": entry["classe"],
        "score": number(entry["punteggio"]),
        "metrics": {
            "relativeYieldMedian": _metric(v,"resa_rel_mediana"),
            "relativeYieldWorst": _metric(v,"resa_rel_min"),
            "relativeYieldP10": _metric(v,"resa_rel_p10"),
            "irrigationMm": _metric(v,"irrigazione_mm"),
            "fertilizerKgN": _metric(v,"concime_kg_n"),
            "nitrogenLeachingKgN": _metric(v,"n_lisciviato_kg_n"),
            "humusChangeTonsHa": _metric(v,"humus_t_ha"),
            "grossMarginEurHa": _metric(v,"margine_lordo_eur_ha"),
        },
        "evidence": evidence,
        "risks": risks,
        "sourceNotesItalian": {"evidence": entry.get("evidenze", []), "risks": entry.get("rischi", [])},
    }


def _cache_is_current(meta: dict) -> bool:
    """Check parameter fingerprints, ignoring only Windows/Unix line endings.

    The engine saves the SHA-256 of the raw YAML files. A cache created on
    Windows therefore has CRLF hashes, whereas the bundled pilot ensemble
    may have LF hashes. Both are valid if the file content is unchanged.
    """
    hashes = meta.get("hash_file_parametri") or {}
    if not hashes:
        return False
    for name, original in hashes.items():
        path = config.PARAMS_DIR / name
        if not path.is_file():
            return False
        raw = path.read_bytes()
        lf = raw.replace(b"\r\n", b"\n")
        crlf = lf.replace(b"\n", b"\r\n")
        if original not in {hashlib.sha256(data).hexdigest() for data in (raw, lf, crlf)}:
            return False
    return True


@app.get("/api/v1/health")
def health():
    pointdir = config.DATA_DIR / "processed" / f"lat{PILOT[1]:.3f}_lon{PILOT[0]:.3f}"
    return {"status": "ok", "engineVersion": __version__, "pilotReady": (pointdir / "ensemble_sintesi.csv").is_file(),
            "pilotPoint": PILOT, "maxDistanceKm": 100, "priorities": PRIORITIES}


class PrepareRequest(BaseModel):
    point: tuple[float, float]

    @field_validator("point")
    @classmethod
    def check_point(cls, value):
        return AnalyzeRequest.check_point(value)


@app.post("/api/v1/prepare")
def prepare(request: PrepareRequest):
    if distance_km(request.point, PILOT) > 100:
        raise HTTPException(status_code=422, detail={"code": "OUTSIDE_DEMO_AREA", "message": "The field reference point is more than 100 km from the Cremona pilot."})
    if distance_km(request.point, PILOT) < 0.001:
        return {"status": "ready", "stage": "Pilot point is already cached.", "modelPoint": PILOT}
    try:
        return start_preparation(request.point)
    except PreparationError as exc:
        raise HTTPException(status_code=409, detail={"code": "PREPARATION_UNAVAILABLE", "message": str(exc)}) from exc


@app.get("/api/v1/prepare/{job_id}")
def preparation_status(job_id: str):
    status = job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"code": "PREPARATION_NOT_FOUND", "message": "Preparation job not found. The server might have restarted; please try again."})
    return status


@app.post("/api/v1/analyze")
def analyze(request: AnalyzeRequest):
    point = request.point
    if distance_km(point, PILOT) > 100:
        raise HTTPException(status_code=422, detail={"code": "OUTSIDE_DEMO_AREA", "message": "The field reference point is more than 100 km from the Cremona pilot location."})
    exact_pilot = distance_km(point, PILOT) < 0.001
    local_rec = None
    if not exact_pilot and not request.use_pilot_reference:
        model_point = normalized_point(point)
        local_rec = ready_record(model_point)
        if local_rec is None:
            raise HTTPException(status_code=409, detail={
                "code": "LOCAL_DATA_NOT_READY", "message": "Local climate and soil preparation has not finished. Retry through the Analyze page to prepare this location; no pilot data were substituted."})
    else:
        model_point = PILOT
    try:
        _, summary = ensemble.load_ensemble(lat=model_point[1], lon=model_point[0])
        meta = summary.attrs.get("meta", {})
        if not _cache_is_current(meta):
            raise HTTPException(status_code=409, detail={"code": "STALE_ENSEMBLE", "message": "Cached simulations no longer match the current parameter files. Regenerate and validate the ensemble before using them."})
        if local_rec and meta.get("hash_parametri") != local_rec["parametersHash"]:
            raise HTTPException(status_code=409, detail={"code": "LOCAL_DATA_STALE", "message": "The local soil parameters have changed; prepare this field again."})
        canonical = ensemble.classe_rotazione_attuale(request.rotation)
        if not bool((summary["classe"] == canonical).any()):
            raise HTTPException(status_code=422, detail={"code": "ROTATION_NOT_CACHED", "message": "This crop rotation has no saved pilot ensemble result."})
        summary = summary.copy()
        summary["attuale"] = summary["classe"] == canonical
        conf = ranking.confronta(summary, {key: request.priorities.get(key, 0) for key in PRIORITIES},
                                 request.scenario, n_alternative=2, solo_conformi=not bool(local_rec),
                                 regime="lombardia_impegno_quinquennale" if not local_rec else None,
                                 ammetti_deroga=False)
    except CacheMiss:
        raise HTTPException(status_code=503, detail={"code": "ENSEMBLE_NOT_AVAILABLE", "message": "The reference ensemble cache is missing."}) from None
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"code": "ENGINE_INPUT_ERROR", "message": str(e)}) from e
    current = conf.get("attuale")
    if current is None:
        raise HTTPException(status_code=422, detail={"code": "NO_BASELINE", "message": "The engine did not locate the requested rotation in the cached comparison."})
    if local_rec:
        reference = "local_estimate"
        note = ("Location-conditioned experimental analysis using NASA POWER historical weather "
                "and SoilGrids 250 m soil predictions at the representative point. "
                "Other crop-management, groundwater and regional assumptions are not field-measured. "
                "This is NOT a validated field-scale forecast.")
    else:
        reference = "pilot_reference" if not exact_pilot else "pilot_point"
        note = ("Cremona pilot soil and climate (45.2 N, 10.0 E). This exploratory comparison "
                "is NOT location-specific to the selected field." if not exact_pilot else
                "Pilot-point historical comparison with cached Cremona soil and weather data.")
    return {
        "schemaVersion": 1,
        "engine": {"version": __version__, "dataPeriod": (f"{meta['anni_valutati'][0]}–{meta['anni_valutati'][-1]} (historical years)" if isinstance(meta.get("anni_valutati"), list) and meta["anni_valutati"] else "Historical ensemble"),
                   "methodologyNote": note + " Historical weather years, not a future forecast. The model has material validation limitations, especially for wheat yield, nitrogen, humus and groundwater effects.",
                   "sourceMode": reference, "modelPoint": model_point, "requestedPoint": point,
                   "ensembleCalculatedAt": meta.get("calcolato_il"),
                   "localData": local_rec["details"] if local_rec else None},
        "results": {"scenario": request.scenario, "current": _outcome(current, current),
                    "alternatives": [_outcome(x, current) for x in conf.get("alternative", [])],
                    "comparedRotations": conf.get("n_confrontate"),
                    "notes": [note, ("No region-specific compliance filter was applied: local rotation regulations must be verified." if local_rec else
                              "Alternatives are filtered for compliance with the Lombardy five-year rotation rules; the existing rotation remains visible regardless of compliance."),
                              "Ranking scores are relative and can change substantially with uncertain parameters or chosen priorities.",
                              "Wheat-yield validation was negative; do not interpret the wheat-related rankings as reliable risk forecasts.",
                              "Economic margin includes crop revenue less mineral nitrogen fertilizer and irrigation only; it excludes seed, crop protection, machinery and fixed costs."] + list(conf.get("note", []) or conf.get("notes", []))},
    }
