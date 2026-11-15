"""HTTP adapter for the FIELDWISE engine.

Run from the repository root: python -m uvicorn api:app --host 127.0.0.1 --port 8000
No scientific model code, params or cached ensemble files are modified here.
The API has no authentication: keep it bound to 127.0.0.1 (see local_analysis.py).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from fieldwise import __version__, config, economics, ensemble, params, ranking
from fieldwise.data.cache import CacheMiss, point_key
from local_analysis import (ENGINE_CODE_HASH, PreparationBusy, PreparationError, is_pilot_cell,
                            job_status, local_record_status, normalized_point, start_preparation)

app = FastAPI(title="FIELDWISE integration API", version="1.1.0")
_ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
_ALLOWED_ORIGINS += [s.strip().rstrip("/") for s in os.getenv("FIELDWISE_FRONTEND_ORIGINS", "").split(",") if s.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_ALLOWED_ORIGINS, allow_credentials=False,
                   allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

PILOT = (config.PILOT_LON, config.PILOT_LAT)
PRIORITIES = tuple(ranking.PRIORITA.keys())
PILOT_REGIME = "lombardia_impegno_quinquennale"

# One definition of the analysis area, shared with the frontend map (read, never written here).
AREA_FILE = Path(__file__).resolve().parent / "frontend" / "src" / "lib" / "demoArea.json"
_AREA = json.loads(AREA_FILE.read_text(encoding="utf-8"))
MAX_DISTANCE_KM = float(_AREA["maxDistanceKm"])
if tuple(float(x) for x in _AREA["pilotPoint"]) != PILOT:
    raise RuntimeError(f"{AREA_FILE} pilotPoint {_AREA['pilotPoint']} differs from the engine pilot {PILOT}.")

FiniteCoordinate = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PriorityWeight = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=0, le=10)]


def _json_safe(value):
    """Validation errors echo the input; NaN/Infinity are not valid JSON, so stringify them."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    errors = [{k: _json_safe(v) for k, v in err.items() if k != "ctx"} | (
        {"ctx": {k: str(v) for k, v in err["ctx"].items()}} if "ctx" in err else {}) for err in exc.errors()]
    return JSONResponse(status_code=422, content=jsonable_encoder({"detail": errors}))


class AnalyzeRequest(BaseModel):
    # Unknown fields (e.g. economic overrides) are rejected, not silently ignored.
    model_config = ConfigDict(extra="forbid")
    # GeoJSON order, [longitude, latitude]
    point: tuple[FiniteCoordinate, FiniteCoordinate]
    rotation: str = Field(min_length=4, max_length=160)
    scenario: Literal["solo_pioggia", "tetto_irriguo", "irrigazione_libera"]
    priorities: dict[str, PriorityWeight]
    use_pilot_reference: bool = Field(default=False, strict=True)
    include_future: bool = Field(default=False, strict=True)
    future_horizon: Literal[5, 10, 15, 20] = Field(default=10)
    future_ssp: Literal["ssp126", "ssp245", "ssp585"] = Field(default="ssp245")

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
        if not value or any(k not in PRIORITIES for k in value):
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


# =============================================================================
# English statements: same rules, thresholds and numbers as ranking.confronta
# (_evidenze_e_peggioramenti, _evidenze_extra, _rischi). tests/test_api_statements.py checks
# that every engine sentence has exactly one English counterpart citing the same numbers.
# =============================================================================
NAMES_EN = {"resa_rel_mediana": "median relative yield",
            "resa_rel_min": "mean relative yield of the rotation in the worst year",
            "irrigazione_mm": "irrigation", "concime_kg_n": "nitrogen fertilizer",
            "n_lisciviato_kg_n": "nitrogen leaching", "humus_t_ha": "humus balance",
            "margine_lordo_eur_ha": "margin"}
UNITS_EN = {"irrigazione_mm": "mm/year", "concime_kg_n": "kg N/ha/year", "n_lisciviato_kg_n": "kg N/ha/year",
            "humus_t_ha": "t/ha/year", "margine_lordo_eur_ha": "EUR/ha/year"}
FACTORS_EN = {"acqua": "water", "caldo": "heat", "rotazione": "the crop sequence (rotation effect)"}
STATES_EN = {"conforme": "compliant", "conforme_solo_in_deroga": "compliant only under derogation",
             "non_conforme": "not compliant", "non_valutabile": "not assessable"}
REGIMES_EN = {"lombardia_impegno_quinquennale": "Lombardy, five-year commitment",
              "lombardia_impegno_triennale_SRA01_2026": "Lombardy, three-year commitment (SRA01)",
              "emilia_romagna_impegno_quinquennale": "Emilia-Romagna, five-year commitment",
              "emilia_romagna_adesione_singola_coltura": "Emilia-Romagna, single-crop membership"}
ROLES_EN = {"attuale": "Current rotation (baseline)",
            "migliore_punteggio_non_dominata": "Best-scoring non-dominated alternative",
            "migliore_punteggio": "Best-scoring alternative (no alternative is non-dominated)",
            "migliore_rischio": "Best worst-year yield among the other alternatives",
            "per_punteggio": "Next alternative by score"}
NOTES_EN = {
    "nessuna alternativa e' non dominata: scelta la migliore per punteggio":
        "No alternative is non-dominated: the first alternative is simply the best by score.",
    "nessuna alternativa nell'insieme confrontato": "No alternative rotation is available in the compared set.",
    ranking.AVVISO_NON_DISCRIMINA:
        "With these priorities and this scenario the rotations cannot be told apart: every weighted indicator "
        "is identical across rotations, so the order shown is alphabetical and carries no meaning.",
    "la rotazione attuale non ha simulazioni riuscite in questo scenario: confronto assoluto":
        "The current rotation has no successful simulations in this scenario: values are shown without a baseline.",
    "rotazione attuale non marcata nella sintesi: confronto assoluto":
        "The current rotation is not marked in the summary: values are shown without a baseline.",
}


def _num(x, nd=2) -> str:
    return f"{x:.{nd}f}".replace("-", "−")


def _pct(x) -> str:
    return f"{x:+.0f}%".replace("-", "−")


def _state(values: dict, regime: str | None) -> str:
    col = "conformita" if regime is None else f"conformita_{regime}"
    return values.get(col, values.get("conformita"))


def _regime_text(regime: str | None) -> str:
    if regime is None:
        return " (least favourable of the regional rule sets in the engine)"
    return f" ({REGIMES_EN.get(regime, regime)})"


def english_statements(entry: dict, current: dict | None, regime: str | None):
    """``(evidence, risks)`` as lists of ``(topic, sentence)`` for one ``confronta`` entry."""
    v = entry["valori"]
    att = None if current is None or entry is current else current["valori"]
    dif = entry["differenze"]
    ev, worse = [], []
    if att is not None:
        def add(topic, improves, text):
            (ev if improves else worse).append((topic, text))
        for col in ("irrigazione_mm", "concime_kg_n", "n_lisciviato_kg_n"):
            d, name, unit = dif[col], NAMES_EN[col], UNITS_EN[col]
            if d.get("percentuale") is None:
                if abs(d["assoluta"]) > 1e-9:
                    add(col, d["assoluta"] < 0, f"{name.capitalize()}: {_num(d['valore'], 0)} {unit} instead of 0 {unit}")
            elif abs(d["percentuale"]) >= 100 * ranking.SOGLIA_EVIDENZA:
                add(col, d["assoluta"] < 0, f"{_pct(d['percentuale'])} {name} ({_num(d['attuale'], 0)} → {_num(d['valore'], 0)} {unit})")
        for col in ("resa_rel_mediana", "resa_rel_min"):
            d = dif[col]
            if d.get("percentuale") is not None and abs(d["percentuale"]) >= 100 * ranking.SOGLIA_EVIDENZA:
                text = f"{NAMES_EN[col].capitalize()} {_num(d['attuale'])} → {_num(d['valore'])} ({_pct(d['percentuale'])})"
                if d["assoluta"] > 0:
                    ev.append((col, text))
                elif col != "resa_rel_min":   # a worse worst year is reported among the risks
                    worse.append((col, text))
        d = dif["margine_lordo_eur_ha"]
        if d.get("percentuale") is not None and abs(d["percentuale"]) >= 100 * ranking.SOGLIA_EVIDENZA:
            add("margine_lordo_eur_ha", d["assoluta"] > 0,
                f"Margin {_num(d['attuale'], 0)} → {_num(d['valore'], 0)} EUR/ha/year ({_pct(d['percentuale'])})")
        d = dif["humus_t_ha"]
        if abs(d["assoluta"]) >= ranking.SOGLIA_HUMUS:
            add("humus_t_ha", d["assoluta"] > 0,
                f"Humus: {_num(d['valore'])} t/ha/year instead of {_num(d['attuale'])}")
        fl = v.get("fattore_limitante")
        if fl in FACTORS_EN and v.get(f"f_{fl}", 1.0) < ranking.SOGLIA_FATTORE:
            if fl == att.get("fattore_limitante"):
                ev.append(("fattore_limitante", f"Yield is limited mainly by {FACTORS_EN[fl]}, as in the current rotation"))
            else:
                other = att.get("fattore_limitante")
                ev.append(("fattore_limitante", f"Yield is limited mainly by {FACTORS_EN[fl]} "
                                                f"(current rotation: {FACTORS_EN.get(other, str(other))})"))
        if v["quota_oltre_limite_n"] < att["quota_oltre_limite_n"]:
            ev.append(("quota_oltre_limite_n", "The legal nitrogen limit is exceeded in fewer years: "
                       f"{v['quota_oltre_limite_n'] * 100:.0f}% instead of {att['quota_oltre_limite_n'] * 100:.0f}%"))
        s_alt, s_att = _state(v, regime), _state(att, regime)
        if s_alt == "conforme" and s_att in ("non_conforme", "conforme_solo_in_deroga"):
            ev.append(("conformita", "Compliant with the integrated-production rotation rules, whereas the current "
                                     f"rotation is {STATES_EN[s_att]}"))
    risks = []
    if att is None:
        risks.append(("resa_rel_min", f"In the worst year the mean relative yield of the rotation falls to {_num(v['resa_rel_min'])}"))
    elif v["resa_rel_min"] < att["resa_rel_min"]:
        risks.append(("resa_rel_min", f"In the worst year the mean relative yield of the rotation falls to {_num(v['resa_rel_min'])} "
                                      f"(current rotation: {_num(att['resa_rel_min'])})"))
    q_n = v["quota_oltre_limite_n"]
    if q_n > 0 and (att is None or q_n >= att["quota_oltre_limite_n"]):
        extra = "" if att is None else f" (current rotation: {att['quota_oltre_limite_n'] * 100:.0f}%)"
        risks.append(("quota_oltre_limite_n", f"In {q_n * 100:.0f}% of the years at least one crop exceeds the legal nitrogen limit{extra}"))
    state = _state(v, regime)
    if state == "non_conforme":
        risks.append(("conformita", "Not compliant with the integrated-production rotation rules" + _regime_text(regime)))
    elif state == "conforme_solo_in_deroga":
        risks.append(("conformita", "Compliant with the integrated-production rotation rules only under derogation" + _regime_text(regime)))
    elif state == "non_valutabile":
        risks.append(("conformita", "Compliance with the integrated-production rotation rules cannot be assessed for this sequence"))
    q = v.get("cover_realizzata_quota", float("nan"))
    q = float("nan") if q is None else float(q)
    if q == q and q < 1.0:
        risks.append(("cover_realizzata_quota", f"The rye cover crop is feasible in {q * 100:.0f}% of cases; "
                                                "in the others the interval stays bare soil"))
    risks += [(topic, f"Compared with the current rotation: {text[0].lower() + text[1:]}") for topic, text in worse]
    return ev, risks


def _outcome(entry, current, regime, label=None):
    if entry is None:
        return None
    v = entry["valori"]
    evidence, risks = english_statements(entry, current, regime)
    return {
        "label": label or entry["classe"],
        "cyclicClass": entry["classe"],
        "role": entry.get("ruolo"),
        "roleLabel": ROLES_EN.get(entry.get("ruolo"), entry.get("ruolo")),
        "score": number(entry["punteggio"]),
        "position": entry.get("posizione"),
        "nonDominated": entry.get("non_dominata"),
        "metrics": {
            "relativeYieldMedian": _metric(v, "resa_rel_mediana"),
            "relativeYieldWorst": _metric(v, "resa_rel_min"),
            "relativeYieldP10": _metric(v, "resa_rel_p10"),
            "irrigationMm": _metric(v, "irrigazione_mm"),
            "fertilizerKgN": _metric(v, "concime_kg_n"),
            "nitrogenLeachingKgN": _metric(v, "n_lisciviato_kg_n"),
            "humusChangeTonsHa": _metric(v, "humus_t_ha"),
            "grossMarginEurHa": _metric(v, "margine_lordo_eur_ha"),
        },
        "marginComponents": {
            "revenueEurHa": _metric(v, economics.COL_RICAVO),
            "fertilizerCostEurHa": _metric(v, economics.COL_CONCIME),
            "irrigationCostEurHa": _metric(v, economics.COL_IRRIGAZIONE),
            "otherCropCostsEurHa": _metric(v, economics.COL_ALTRI),
        },
        "evidence": [t for _, t in evidence],
        "evidenceTopics": [k for k, _ in evidence],
        "risks": [t for _, t in risks],
        "riskTopics": [k for k, _ in risks],
        "sourceNotesItalian": {"evidence": entry.get("evidenze", []), "risks": entry.get("rischi", [])},
    }


def _recommendation(conf: dict, warning: str | None) -> dict:
    """Never presents as recommended an alternative that does not score above the current rotation."""
    current, alternatives = conf.get("attuale"), conf.get("alternative", [])
    n = conf.get("n_confrontate")
    first = alternatives[0] if alternatives else None
    if warning:
        status = "priorities_do_not_discriminate"
        message = ("The selected priorities do not distinguish between the rotations in this scenario (all scores "
                   "are equal). No rotation is recommended; the alternatives are shown for comparison only.")
    elif first is None:
        status, message = "no_alternative", "The engine returned no alternative rotation to compare."
    elif current is None or first["punteggio"] > current["punteggio"]:
        status = "alternative_ranks_higher"
        message = (f"Alternative 1 scores higher than your current rotation (rank {first['posizione']} of {n}"
                   + ("" if current is None else f"; current rotation rank {current['posizione']}") + ").")
    elif current["posizione"] == 1 and first["punteggio"] < current["punteggio"]:
        status = "current_is_best"
        message = (f"Your current rotation already ranks first of {n} for the selected priorities. "
                   "The alternatives are shown for comparison only.")
    else:
        status = "no_alternative_ranks_higher"
        message = (f"No alternative scores higher than your current rotation (rank {current['posizione']} of {n}"
                   + (", tied with Alternative 1" if first["punteggio"] == current["punteggio"] else "")
                   + "). The alternatives are shown for comparison only.")
    return {"status": status, "message": message,
            "recommendedAlternativeIndex": 0 if status == "alternative_ranks_higher" else None,
            "currentPosition": None if current is None else current["posizione"],
            "currentScore": None if current is None else number(current["punteggio"]),
            "comparedRotations": n, "nonDominatedCount": conf.get("n_non_dominate"),
            "priorityWarning": NOTES_EN[ranking.AVVISO_NON_DISCRIMINA] if warning else None}


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


def _historical_windows(detail, scenario: str, current, alternatives):
    """Historical rotation cycles indexed by the first year of the EVALUATED cycle (``anno_valutato``).

    Each simulation starts in ``anno_partenza`` with spin-up cycles; only the following cycle,
    starting in ``anno_valutato``, is evaluated. For each evaluated start year and cyclic class the
    successful simulations (cyclic shifts) are summarised with the median. Consecutive cycles
    overlap: points are not independent observations or annual forecasts.
    """
    if detail is None or detail.empty:
        return None
    indicators = {
        "relativeYield": "resa_rel_media",
        "irrigationMm": "irrigazione_mm",
        "nitrogenLeachingKgN": "n_lisciviato_kg_n",
        "humusChangeTonsHa": "humus_t_ha",
        "grossMarginEurHa": "margine_lordo_eur_ha",
    }
    series = []
    for role, item in [("current", current), ("alternative1", alternatives[0] if len(alternatives) > 0 else None),
                       ("alternative2", alternatives[1] if len(alternatives) > 1 else None)]:
        if item is None:
            continue
        cls = str(item["classe"])
        rows = detail.loc[(detail["classe"] == cls) & (detail["scenario"] == scenario)]
        if rows.empty:
            continue
        points = []
        for year, block in rows.groupby("anno_valutato", sort=True):
            point = {"evaluatedYear": int(year), "simulationStartYears": [int(block["anno_partenza"].min()),
                                                                          int(block["anno_partenza"].max())],
                     "memberCount": int(len(block))}
            for name, column in indicators.items():
                point[name] = number(block[column].median()) if column in block.columns else None
            points.append(point)
        if points:
            series.append({"role": role, "rotation": cls, "points": points})
    if not series:
        return None
    return {
        "axis": "evaluatedYear",
        "method": "Median across simulated cyclic shifts for each evaluated rotation cycle, indexed by the first "
                  "year of the evaluated cycle (spin-up years excluded); consecutive cycles overlap and are not "
                  "observed annual yields.",
        "series": series,
    }


def _data_period(meta: dict) -> dict:
    weather = meta.get("annate_partenza")
    evaluated = meta.get("anni_valutati")
    spin = meta.get("n_avviamento")
    ok = isinstance(weather, list) and len(weather) == 2 and isinstance(evaluated, list) and len(evaluated) == 2
    text = (f"Historical weather {weather[0]}–{weather[1]}; evaluated rotation cycles start {evaluated[0]}–{evaluated[1]}"
            + (f" (after {spin} spin-up cycle{'s' if spin != 1 else ''})" if isinstance(spin, int) else "")
            if ok else "Historical ensemble (period not recorded in the cache metadata)")
    return {"text": text, "weatherYears": weather if ok else None,
            "evaluatedCycleStartYears": evaluated if ok else None, "spinUpCycles": spin}


# =============================================================================
# Economics: description built from params/economia.yaml through the engine
# =============================================================================
CROPS_EN = {"mais": "maize", "soia": "soybean", "frumento": "winter wheat"}


def _economics_assumptions() -> dict:
    p = params.load_params()
    crops = list(p["economia"]["prezzi_eur_t"].keys())
    prices = {c: economics.prezzo_coltura(p, c) for c in crops}
    other = economics.costi_predefiniti(p, crops)
    n_price = float(params.get(p, "economia.azoto_eur_kg_n"))
    water = float(params.get(p, "economia.irrigazione_eur_mm"))
    fmt = lambda d: ", ".join(f"{CROPS_EN.get(c, c)} {d[c]:,.0f}" for c in crops)
    definition = (
        "Margin (EUR/ha/year) = grain revenue at static prices (" + fmt(prices) + " EUR/t) − nitrogen fertilizer "
        f"({n_price:g} EUR/kg N × simulated N) − irrigation ({water:g} EUR/mm × simulated water) − other crop costs per "
        "cultivated hectare (seed, crop protection, field operations, sowing, harvest, drying and transport: "
        + fmt(other) + " EUR/ha), averaged per year over the evaluated cycle. Land rent, depreciation and CAP "
        "payments are not included (equal for all rotations, they cancel out in the difference from today). "
        "Default values from params/economia.yaml, not farm-specific; not a profit forecast.")
    return {"source": "params/economia.yaml", "marginDefinition": definition,
            "cropPricesEurT": prices, "nitrogenEurKgN": n_price, "irrigationEurMm": water,
            "otherCropCostsEurHa": other}


# =============================================================================
# Limitations read from the engine reports (pilot point)
# =============================================================================
NOT_VALIDATED_EN = {"azoto (concime, assorbimento, mineralizzazione)": "nitrogen (fertilizer, uptake, mineralization)",
                    "humus": "humus", "lisciviazione dei nitrati": "nitrate leaching",
                    "percolazione e ruscellamento": "percolation and runoff"}
SCENARIOS_EN = {"solo_pioggia": "rainfed only", "tetto_irriguo": "limited irrigation",
                "irrigazione_libera": "unrestricted irrigation"}


def _pilot_dir() -> Path:
    return config.DATA_DIR / "processed" / point_key(PILOT[1], PILOT[0])


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _verdict(ci) -> str:
    lo, hi = ci
    if hi < 0:
        return "negative"
    if lo <= 0:
        return "not significant (the 95% interval includes zero)"
    return "positive"


def limitations(scenario: str, applies_to_pilot_data: bool) -> dict:
    """Sensitivity and validation caveats with their numbers, read from the engine reports.

    ``sensitivity_summary.json`` and ``validation_summary.json`` exist only for the pilot point."""
    directory = _pilot_dir()
    statements: list[str] = []
    out = {"referencePoint": list(PILOT), "appliesToThisAnalysisData": applies_to_pilot_data,
           "rankingStability": None, "validation": None, "statements": statements}
    if not applies_to_pilot_data:
        statements.append(f"The sensitivity and validation results below refer to the Cremona pilot point "
                          f"({PILOT[1]} N, {PILOT[0]} E), not to this field's local data.")
    sens = _read_json(directory / "sensitivity_summary.json")
    mc = ((sens or {}).get("montecarlo") or {}).get(scenario)
    if mc:
        base = ((sens.get("base") or {}).get(scenario) or {})
        weights = (sens.get("indicatore_principale") or {}).get("pesi")
        equal = isinstance(weights, dict) and len(set(weights.values())) == 1
        out["rankingStability"] = {"scenario": scenario, "samples": mc.get("n_validi"),
                                   "firstStaysFirstShare": mc.get("prima_resta"),
                                   "top3StayTop3Share": mc.get("top3_restano"),
                                   "referenceCurrentRotation": base.get("attuale"),
                                   "currentInBottomQuarterShare": mc.get("attuale_ultimo_quarto"),
                                   "weights": weights, "generatedAt": sens.get("generato_il"),
                                   "source": "sensitivity_summary.json"}
        statements.append(
            f"Ranking stability ({SCENARIOS_EN.get(scenario, scenario)}, "
            f"{'equal priority weights' if equal else 'reference priority weights'}): with joint parameter uncertainty "
            f"the top-ranked rotation stays first in only {mc['prima_resta'] * 100:.1f}% of {mc['n_validi']} samples"
            + (f", while the reference current rotation ({base['attuale']}) stays in the bottom quarter in "
               f"{mc['attuale_ultimo_quarto'] * 100:.1f}%" if base.get("attuale") and mc.get("attuale_ultimo_quarto") is not None else "")
            + ". The judgement on a poor current rotation is more robust than the fine choice between the leading alternatives.")
        ens_hash = (_read_json(directory / "ensemble_meta.json") or {}).get("hash_parametri")
        sens_hash = re.search(r"hash dei parametri ([0-9a-f]{64})", str(sens.get("versione", "")))
        if ens_hash and sens_hash and sens_hash.group(1) != ens_hash:
            statements.append(f"The sensitivity analysis ({sens.get('generato_il')}) was run on an earlier parameter "
                              "set than the current ensemble cache and has not been repeated since.")
    else:
        statements.append("No ranking-stability (sensitivity) summary is available for this scenario.")
    val = _read_json(directory / "validation_summary.json")
    if val:
        validation = {"source": "validation_summary.json", "yields": [], "evapotranspiration": None,
                      "notValidated": [NOT_VALIDATED_EN.get(x, x) for x in val.get("non_validato", [])]}
        istat = val.get("istat") or {}
        for crop in ("mais", "soia", "frumento"):
            rows = [c for c in istat.get("confronti", []) if c.get("coltura") == crop and c.get("detrend")]
            pick = (next((c for c in rows if c["scenario"] == scenario and c["simulazione"] == "media_rotazioni"), None)
                    or next((c for c in rows if c["scenario"] == scenario), None)
                    or next((c for c in rows if c["simulazione"] == "media_rotazioni"), None)
                    or (rows[0] if rows else None))
            if not pick:
                continue
            d = pick["detrend"]
            item = {"crop": crop, "scenario": pick["scenario"], "simulation": pick["simulazione"],
                    "years": pick.get("anni"), "pearson": d["pearson"], "ci95": d["pearson_ic95"], "n": d["n"],
                    "verdict": _verdict(d["pearson_ic95"])}
            validation["yields"].append(item)
            statements.append(
                f"{CROPS_EN[crop].capitalize()} yield vs ISTAT provincial yields ({item['years'][0]}–{item['years'][1]}, "
                f"detrended, {SCENARIOS_EN.get(item['scenario'], item['scenario'])}): Pearson r = {_num(d['pearson'])} "
                f"(95% CI {_num(d['pearson_ic95'][0])} to {_num(d['pearson_ic95'][1])}, n = {d['n']}): {item['verdict']}.")
        eco = val.get("ecostress") or {}
        season = (((eco.get("scenari") or {}).get(scenario) or {}).get("stagione"))
        if season:
            validation["evapotranspiration"] = {"years": eco.get("anni"), "scenario": scenario,
                                                "observedMmDay": season["media_obs"], "modelMmDay": season["media_sim"],
                                                "biasMmDay": season["scarto_sim_meno_obs"], "passes": season["n_passaggi"]}
            statements.append(
                f"Evapotranspiration vs ECOSTRESS ({eco['anni'][0]}–{eco['anni'][1]}, growing season, "
                f"{SCENARIOS_EN.get(scenario, scenario)}): model {season['media_sim']:.2f} mm/day vs observed "
                f"{season['media_obs']:.2f} mm/day, an overestimate of {season['scarto_sim_meno_obs']:+.2f} mm/day.")
        if validation["notValidated"]:
            statements.append("Not validated against observations: " + "; ".join(validation["notValidated"]) + ".")
        out["validation"] = validation
    else:
        statements.append("No validation summary is available.")
    return out


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "engineVersion": __version__,
            "pilotReady": (_pilot_dir() / "ensemble_sintesi.csv").is_file(),
            "pilotPoint": PILOT, "maxDistanceKm": MAX_DISTANCE_KM, "priorities": PRIORITIES}


@app.get("/api/v1/limitations")
def get_limitations(scenario: Literal["solo_pioggia", "tetto_irriguo", "irrigazione_libera"] = "tetto_irriguo"):
    return limitations(scenario, applies_to_pilot_data=True)


class PrepareRequest(BaseModel):
    point: tuple[FiniteCoordinate, FiniteCoordinate]

    @field_validator("point")
    @classmethod
    def check_point(cls, value):
        return AnalyzeRequest.check_point(value)


def _outside_area(point) -> bool:
    return distance_km(point, PILOT) > MAX_DISTANCE_KM


@app.post("/api/v1/prepare")
def prepare(request: PrepareRequest):
    if _outside_area(request.point):
        raise HTTPException(status_code=422, detail={"code": "OUTSIDE_DEMO_AREA", "message": f"The field reference point is more than {MAX_DISTANCE_KM:g} km from the Cremona pilot."})
    if is_pilot_cell(request.point):
        # Same cache folder as the pilot: the pilot data are used, never a local preparation.
        return {"status": "ready", "stage": "Pilot point is already cached.", "modelPoint": PILOT}
    try:
        return start_preparation(request.point)
    except PreparationBusy as exc:
        raise HTTPException(status_code=429, detail={"code": "PREPARATION_BUSY", "message": str(exc)}) from exc
    except PreparationError as exc:
        raise HTTPException(status_code=409, detail={"code": "PREPARATION_UNAVAILABLE", "message": str(exc)}) from exc


@app.get("/api/v1/prepare/{job_id}")
def preparation_status(job_id: str):
    status = job_status(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail={"code": "PREPARATION_NOT_FOUND", "message": "Preparation job not found. The server might have restarted; please try again."})
    return status


def _translate_notes(notes) -> list[str]:
    return [NOTES_EN.get(n, f"Engine note (original Italian): {n}") for n in notes]


@app.post("/api/v1/analyze")
def analyze(request: AnalyzeRequest):
    point = request.point
    if _outside_area(point):
        raise HTTPException(status_code=422, detail={"code": "OUTSIDE_DEMO_AREA", "message": f"The field reference point is more than {MAX_DISTANCE_KM:g} km from the Cremona pilot location."})
    in_pilot_cell = is_pilot_cell(point)
    exact_pilot = distance_km(point, PILOT) < 0.001
    local_rec = None
    if not in_pilot_cell and not request.use_pilot_reference:
        model_point = normalized_point(point)
        local_rec, reason, detail = local_record_status(model_point)
        if local_rec is None and reason == "missing":
            raise HTTPException(status_code=409, detail={
                "code": "LOCAL_DATA_NOT_READY", "message": "Local climate and soil preparation has not finished. Retry through the Analyze page to prepare this location; no pilot data were substituted."})
        if local_rec is None:
            raise HTTPException(status_code=409, detail={
                "code": "LOCAL_DATA_STALE", "message": f"The cached local simulations for this field are out of date: {detail}. "
                "They were not used and no pilot data were substituted. Prepare this field again with an online backend, "
                "or explicitly choose the Cremona pilot reference data."})
    else:
        model_point = PILOT
    regime = None if local_rec else PILOT_REGIME
    try:
        detail_table, summary = ensemble.load_ensemble(lat=model_point[1], lon=model_point[0])
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
        weights = {key: request.priorities.get(key, 0) for key in PRIORITIES}
        common = dict(solo_conformi=not bool(local_rec), regime=regime, ammetti_deroga=False)
        warning = ranking.score(summary, weights, request.scenario, **common).attrs.get("avviso")
        conf = ranking.confronta(summary, weights, request.scenario, n_alternative=2, **common)
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
    elif request.use_pilot_reference and not in_pilot_cell:
        reference = "pilot_reference"
        note = (f"Cremona pilot soil and climate ({PILOT[1]} N, {PILOT[0]} E), chosen explicitly. These are the data "
                "of the pilot point, NOT of your field: the comparison is NOT location-specific.")
    else:
        reference = "pilot_point"
        note = ("Pilot-point historical comparison with cached Cremona soil and weather data." if exact_pilot else
                "The field reference point falls in the pilot cache cell (same 0.001° cell as the pilot): "
                "pilot-point historical data are used.")
    alternatives = conf.get("alternative", [])
    same_cycle = request.rotation.strip() != canonical
    compliance_note = (
        "Alternatives are not filtered by regional rules at this location. Compliance shown in the risks is the least "
        "favourable status across the regional rule sets in the engine "
        f"({', '.join(REGIMES_EN.get(c[len('conformita_'):], c) for c in summary.columns if c.startswith('conformita_'))}); "
        "verify the rules that apply to this field." if local_rec else
        "Alternatives are filtered for compliance with the Lombardy five-year integrated-production rotation rules; "
        "the current rotation remains visible and its own compliance is reported among its risks.")
    data_period = _data_period(meta)
    pilot_data = not bool(local_rec)
    future_payload = None
    if request.include_future:
        try:
            from fieldwise import future as fw_future
            try:
                precalc = fw_future.load_future_payload(lat=model_point[1], lon=model_point[0])
                key = f"{request.future_ssp}_{request.future_horizon}a"
                future_payload = precalc.get(key)
            except Exception:
                future_payload = fw_future.get_future_simulation_payload(
                    lat=model_point[1],
                    lon=model_point[0],
                    horizon_years=request.future_horizon,
                    ssp_code=request.future_ssp,
                    current_rotation=request.rotation.strip(),
                    irrigation_regime=request.scenario,
                    weights=weights,
                )
        except Exception:
            try:
                from fieldwise import future as fw_future
                precalc = fw_future.load_future_payload(lat=PILOT[1], lon=PILOT[0])
                key = f"{request.future_ssp}_{request.future_horizon}a"
                future_payload = precalc.get(key)
            except Exception:
                future_payload = None
    return {
        "schemaVersion": 1,
        "engine": {"version": __version__, "codeHash": ENGINE_CODE_HASH,
                   "dataPeriod": data_period["text"], "weatherYears": data_period["weatherYears"],
                   "evaluatedCycleStartYears": data_period["evaluatedCycleStartYears"],
                   "spinUpCycles": data_period["spinUpCycles"],
                   "methodologyNote": note + " Historical weather years" + (", with CMIP6 future climate projections." if request.include_future else ", not a future forecast. See the limitations for ranking stability and validation results."),
                   "sourceMode": reference, "modelPoint": model_point, "requestedPoint": point,
                   "ensembleCalculatedAt": meta.get("calcolato_il"),
                   "cacheCodeVersionRecorded": bool(local_rec),
                   "localData": local_rec["details"] if local_rec else None,
                   "economics": _economics_assumptions(),
                   "future": {
                       "enabled": True,
                       "horizonYears": request.future_horizon,
                       "sspCode": request.future_ssp,
                       "methodology": "IPCC AR6 CMIP6 Delta Change consensus projections (Po Valley ensemble)",
                   } if request.include_future else None,
                   "limitations": limitations(request.scenario, applies_to_pilot_data=pilot_data)},
        "results": {"scenario": request.scenario,
                    "current": _outcome(current, current, regime, label=request.rotation.strip()),
                    "alternatives": [_outcome(x, current, regime) for x in alternatives],
                    "comparedRotations": conf.get("n_confrontate"),
                    "recommendation": _recommendation(conf, warning),
                    "rotationOrderNote": (f"Entered as {request.rotation.strip()}; compared as the cyclic rotation "
                                          f"{canonical} (same sequence, different starting year).") if same_cycle else None,
                    "historicalWindows": _historical_windows(detail_table, request.scenario, current, alternatives),
                    "future": future_payload,
                    "notes": [note, compliance_note,
                              "Ranking scores are relative to the compared set and to the chosen priorities.",
                              *([] if local_rec else [
                                  "The pilot ensemble cache records parameter-file hashes but not the engine code version: "
                                  f"engine code changes made after {meta.get('calcolato_il')} are not detected automatically."]),
                              *_translate_notes(conf.get("note", []))]},
    }


@app.get("/api/v1/future/summary")
def get_future_summary(lat: float = PILOT[1], lon: float = PILOT[0]):
    try:
        from fieldwise import future as fw_future
        return fw_future.load_future_payload(lat=lat, lon=lon)
    except Exception as exc:
        raise HTTPException(status_code=404, detail={"code": "FUTURE_DATA_MISSING", "message": str(exc)})


class PdfReportRequest(BaseModel):
    """Export the same Markdown already composed by the browser report."""
    markdown: str = Field(min_length=20, max_length=1_000_000)
    report: dict = Field(default_factory=dict)
    demo: bool = False


@app.post("/api/v1/reports/pdf")
def export_report_pdf(request: PdfReportRequest):
    try:
        from report_export import render_pdf
        pdf = render_pdf(request.markdown, request.report, request.demo)
    except ImportError as exc:
        raise HTTPException(status_code=503, detail={"code": "PDF_DEPENDENCY_MISSING", "message": "Install reportlab in the backend environment to enable PDF export."}) from exc
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=422, detail={"code": "PDF_EXPORT_FAILED", "message": str(exc)}) from exc
    report_id = str(request.report.get("id", "report"))
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in report_id)[:64]
    filename = f"FIELDWISE_{safe_id or 'report'}.pdf"
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
