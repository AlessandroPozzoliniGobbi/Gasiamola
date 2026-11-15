"""Regression tests for the frontend-link review (reports/revisione_collegamento_frontend.md).

No network: every test that could start a local preparation forces offline mode or mocks it.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import api
import local_analysis
from api import app
from fieldwise import config, ensemble, params, ranking

CLIENT = TestClient(app)
ZERO = {k: 0 for k in ranking.PRIORITA}
BASE = {"point": [10.0, 45.2], "rotation": "mais > soia > frumento", "scenario": "tetto_irriguo",
        "priorities": {k: 5 for k in ranking.PRIORITA}}
PILOT_DIR = config.DATA_DIR / "processed" / "lat45.200_lon10.000"
EXTRA_POINTS = [[10.495, 45.168], [10.509, 45.191], [9.505, 45.204], [10.086, 45.217], [10.073, 45.393]]


def analyze(**changes):
    response = CLIENT.post("/api/v1/analyze", json={**BASE, **changes})
    assert response.status_code == 200, response.text
    return response.json()


# --- n. 1 / 7: recommendation, roles, position --------------------------------------------
def test_noncompliant_current_is_never_recommended_even_if_it_scores_first():
    out = analyze(rotation="mais > mais > mais", priorities={**ZERO, "profitto": 10})
    rec = out["results"]["recommendation"]
    # Previous test expected a high-scoring but illegal current rotation to be
    # recommended. The current rules are strict: compliance wins over score.
    assert rec["status"] == "current_not_compliant"
    assert rec["currentPosition"] == 1 and rec["recommendedAlternativeIndex"] == 0
    assert "compliant" in rec["message"]
    current = out["results"]["current"]
    assert current["position"] == 1 and current["role"] == "attuale"
    for alt in out["results"]["alternatives"]:
        assert alt["score"] < current["score"]
        assert alt["role"] in ranking_roles() and alt["roleLabel"]
        assert isinstance(alt["nonDominated"], bool) and alt["position"] > 1


def ranking_roles():
    return {"migliore_punteggio_non_dominata", "migliore_punteggio", "migliore_rischio", "per_punteggio"}


def test_priorities_that_do_not_discriminate_give_no_recommendation():
    out = analyze(scenario="solo_pioggia", priorities={**ZERO, "acqua": 5})
    rec = out["results"]["recommendation"]
    assert rec["status"] == "priorities_do_not_discriminate"
    assert rec["recommendedAlternativeIndex"] is None and rec["priorityWarning"]
    notes = " ".join(out["results"]["notes"])
    assert ranking.AVVISO_NON_DISCRIMINA not in notes          # translated, not Italian
    assert "cannot be told apart" in notes


def test_recommended_alternative_always_scores_above_current():
    out = analyze()
    rec = out["results"]["recommendation"]
    assert rec["status"] == "alternative_ranks_higher" and rec["recommendedAlternativeIndex"] == 0
    assert out["results"]["alternatives"][0]["score"] > out["results"]["current"]["score"]
    assert out["results"]["alternatives"][0]["role"] == "migliore_punteggio_non_dominata"
    assert out["results"]["alternatives"][1]["role"] == "migliore_rischio"


# --- n. 3 / 4 / 13: English statements faithful to the engine -------------------------------
def _cases():
    _, summary = ensemble.load_ensemble()
    weights = [{k: 1 for k in ranking.PRIORITA}, {**ZERO, "profitto": 10}]
    for regime, conformi in (("lombardia_impegno_quinquennale", True), (None, False)):
        for scenario in ("solo_pioggia", "tetto_irriguo", "irrigazione_libera"):
            for w in weights:
                for cls in sorted(summary["classe"].unique()):
                    s = summary.copy()
                    s["attuale"] = s["classe"] == cls
                    conf = ranking.confronta(s, w, scenario, n_alternative=2, solo_conformi=conformi, regime=regime)
                    if conf["attuale"] is not None:
                        yield conf, regime, ranking.score(s, w, scenario, solo_conformi=conformi, regime=regime).attrs.get("avviso")


def test_english_statements_match_every_engine_sentence_and_number():
    checked = 0
    for conf, regime, warning in _cases():
        current = conf["attuale"]
        for entry in (current, *conf["alternative"]):
            evidence, risks = api.english_statements(entry, current, regime)
            for italian, english in ((entry["evidenze"], evidence), (entry["rischi"], risks)):
                assert len(italian) == len(english), (italian, english)
                for it, (_, en) in zip(italian, english):
                    assert ranking.numeri_in_frase(it) == ranking.numeri_in_frase(en), (it, en)
                checked += 1
        rec = api._recommendation(conf, warning)
        if rec["recommendedAlternativeIndex"] is not None:
            assert conf["alternative"][0]["punteggio"] > current["punteggio"]
            assert not warning
    assert checked > 1000


def test_current_rotation_receives_its_engine_risks():
    out = analyze(rotation="mais > mais > mais")
    risks = out["results"]["current"]["risks"]
    assert len(risks) == len(out["results"]["current"]["sourceNotesItalian"]["risks"]) >= 2
    assert any("Not compliant" in r for r in risks)
    assert any("worst year" in r for r in risks)


def test_alternative_risks_include_nitrogen_limit_and_no_invented_absence():
    out = analyze(rotation="mais > soia > frumento")
    alt = out["results"]["alternatives"][0]
    assert any("legal nitrogen limit" in r for r in alt["risks"])
    assert not any("No decline" in r for r in alt["risks"])
    assert len(alt["risks"]) == len(alt["sourceNotesItalian"]["risks"])
    assert len(alt["riskTopics"]) == len(alt["risks"]) and len(alt["evidenceTopics"]) == len(alt["evidence"])


# --- n. 2: margin -----------------------------------------------------------------------------
def test_margin_is_described_with_all_engine_costs():
    out = analyze()
    text = json.dumps(out)
    assert "partial" not in text.lower()
    eco = out["engine"]["economics"]
    p = params.load_params()
    assert eco["otherCropCostsEurHa"]["mais"] == params.get(p, "economia.altri_costi_eur_ha.mais")
    assert "other crop costs" in eco["marginDefinition"] and "seed" in eco["marginDefinition"]
    c = out["results"]["current"]
    m = c["marginComponents"]
    assert c["metrics"]["grossMarginEurHa"] == pytest.approx(
        m["revenueEurHa"] - m["fertilizerCostEurHa"] - m["irrigationCostEurHa"] - m["otherCropCostsEurHa"])


# --- n. 5: historical axis and period ----------------------------------------------------------
def test_historical_axis_uses_evaluated_year_and_period_comes_from_meta():
    out = analyze()
    meta = json.loads((PILOT_DIR / "ensemble_meta.json").read_text())
    years = [p["evaluatedYear"] for s in out["results"]["historicalWindows"]["series"] for p in s["points"]]
    assert min(years) == meta["anni_valutati"][0] and max(years) == meta["anni_valutati"][1]
    assert out["engine"]["weatherYears"] == meta["annate_partenza"]
    assert out["engine"]["evaluatedCycleStartYears"] == meta["anni_valutati"]
    assert f"{meta['annate_partenza'][0]}–{meta['annate_partenza'][1]}" in out["engine"]["dataPeriod"]


# --- n. 6: limitations read from the engine reports ----------------------------------------------
def test_limitations_are_read_from_the_engine_reports():
    out = analyze(scenario="tetto_irriguo")
    lim = out["engine"]["limitations"]
    sens = json.loads((PILOT_DIR / "sensitivity_summary.json").read_text())
    val = json.loads((PILOT_DIR / "validation_summary.json").read_text())
    assert lim["appliesToThisAnalysisData"] is True
    assert lim["rankingStability"]["firstStaysFirstShare"] == sens["montecarlo"]["tetto_irriguo"]["prima_resta"]
    wheat = next(y for y in lim["validation"]["yields"] if y["crop"] == "frumento")
    assert wheat["ci95"][1] < 0 and wheat["verdict"] == "negative"
    eco = val["ecostress"]["scenari"]["tetto_irriguo"]["stagione"]
    assert lim["validation"]["evapotranspiration"]["biasMmDay"] == eco["scarto_sim_meno_obs"] > 0
    assert len(lim["validation"]["notValidated"]) == len(val["non_validato"])
    text = " ".join(lim["statements"])
    assert f"{sens['montecarlo']['tetto_irriguo']['prima_resta'] * 100:.1f}%" in text
    assert "humus" in text and "ECOSTRESS" in text


def test_limitations_for_a_local_point_say_they_refer_to_the_pilot():
    lim = api.limitations("solo_pioggia", applies_to_pilot_data=False)
    assert lim["appliesToThisAnalysisData"] is False
    assert "pilot point" in lim["statements"][0] and "not to this field" in lim["statements"][0]
    assert CLIENT.get("/api/v1/limitations", params={"scenario": "solo_pioggia"}).json()["statements"]


# --- n. 8: pilot cache protected --------------------------------------------------------------
def test_point_in_pilot_cell_never_starts_a_local_preparation():
    near = [10.0004, 45.2003]                     # about 50 m from the pilot, same cache folder
    assert local_analysis.is_pilot_cell(near) and not local_analysis.is_pilot_cell([10.0006, 45.2])
    with patch("api.start_preparation", side_effect=AssertionError("must not prepare")):
        r = CLIENT.post("/api/v1/prepare", json={"point": near})
    assert r.status_code == 200 and r.json()["modelPoint"] == [10.0, 45.2]
    with pytest.raises(local_analysis.PreparationError):
        local_analysis.start_preparation(tuple(near))
    out = analyze(point=near)
    assert out["engine"]["sourceMode"] == "pilot_point" and out["engine"]["modelPoint"] == [10.0, 45.2]


def test_preparation_worker_refuses_to_write_into_the_pilot_folder():
    local_analysis._JOBS["guard"] = {"status": "running"}
    with patch("local_analysis.power.fetch") as fetch, patch("local_analysis.ensemble.save_ensemble") as save:
        local_analysis._work("guard", (10.0004, 45.2003))
    assert local_analysis._JOBS["guard"]["status"] == "failed"
    fetch.assert_not_called()
    save.assert_not_called()


# --- n. 9: one area definition ------------------------------------------------------------------
def test_area_definition_is_shared_and_matches_the_engine_pilot():
    area = json.loads(api.AREA_FILE.read_text())
    assert tuple(area["pilotPoint"]) == (config.PILOT_LON, config.PILOT_LAT)
    health = CLIENT.get("/api/v1/health").json()
    assert health["maxDistanceKm"] == area["maxDistanceKm"] and list(health["pilotPoint"]) == area["pilotPoint"]


# --- n. 10: explicit pilot reference -----------------------------------------------------------
def test_pilot_reference_is_explicit_and_labelled():
    far = [10.3, 45.3]
    r = CLIENT.post("/api/v1/analyze", json={**BASE, "point": far})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "LOCAL_DATA_NOT_READY"
    out = analyze(point=far, use_pilot_reference=True)
    assert out["engine"]["sourceMode"] == "pilot_reference"
    assert "NOT of your field" in out["engine"]["methodologyNote"]


# --- n. 11: rotation order ---------------------------------------------------------------------
def test_current_rotation_keeps_the_order_entered():
    out = analyze(rotation="soia > frumento > mais")
    current = out["results"]["current"]
    assert current["label"] == "soia > frumento > mais"
    assert current["cyclicClass"] == ensemble.classe_rotazione_attuale("soia > frumento > mais")
    assert "same sequence" in out["results"]["rotationOrderNote"]
    assert analyze(rotation=current["cyclicClass"])["results"]["rotationOrderNote"] is None


# --- n. 12: local-mode compliance --------------------------------------------------------------
def test_local_mode_compliance_risk_and_note_agree():
    _, summary = ensemble.load_ensemble()
    s = summary.copy()
    s["attuale"] = s["classe"] == "mais > mais > mais"
    conf = ranking.confronta(s, {k: 1 for k in ranking.PRIORITA}, "tetto_irriguo", regime=None)
    _, risks = api.english_statements(conf["attuale"], conf["attuale"], None)
    text = " ".join(t for _, t in risks)
    assert "Lombardy" not in text and "least favourable" in text


# --- n. 14 / 16: notes and input validation ----------------------------------------------------
def test_unknown_engine_notes_are_marked_known_ones_translated():
    assert api._translate_notes([ranking.AVVISO_NON_DISCRIMINA])[0].startswith("With these priorities")
    assert api._translate_notes(["nota nuova"])[0] == "Engine note (original Italian): nota nuova"


@pytest.mark.parametrize("body", [
    '{"point":[NaN,45.2],"rotation":"mais > mais > mais","scenario":"tetto_irriguo","priorities":{"resa":1}}',
    '{"point":[10.0,Infinity],"rotation":"mais > mais > mais","scenario":"tetto_irriguo","priorities":{"resa":1}}',
    '{"point":[10.0,45.2],"rotation":"mais > mais > mais","scenario":"tetto_irriguo","priorities":{"resa":NaN}}',
    '{"point":[10.0,45.2],"rotation":"mais > mais > mais","scenario":"tetto_irriguo","priorities":{"resa":true}}',
])
def test_non_finite_or_boolean_inputs_give_422_not_500(body):
    r = CLIENT.post("/api/v1/analyze", content=body, headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    json.loads(r.text)                                   # valid JSON body
    r = CLIENT.post("/api/v1/prepare", content='{"point":[NaN,45.2]}', headers={"Content-Type": "application/json"})
    assert r.status_code == 422


# --- n. 19 / 20: local cache fingerprints and job limits ---------------------------------------
def _fake_local_cache(tmp_path: Path, point):
    for name in local_analysis.FINGERPRINTED_FILES:
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    rec = {"adapterVersion": local_analysis.MODEL_ADAPTER_VERSION, "engineVersion": local_analysis.__version__,
           "engineCodeHash": local_analysis.ENGINE_CODE_HASH, "point": list(point),
           "files": {n: local_analysis._fingerprint(tmp_path / n) for n in local_analysis.FINGERPRINTED_FILES},
           "paramsFiles": {f.name: local_analysis._fingerprint(f) for f in config.PARAMS_DIR.glob("*.yaml")},
           "parametersHash": "x", "details": {}}
    (tmp_path / "fieldwise_local.json").write_text(json.dumps(rec), encoding="utf-8")
    return rec


def test_local_record_covers_detail_file_and_engine_code(tmp_path):
    point = (10.3, 45.3)
    rec = _fake_local_cache(tmp_path, point)
    with patch("local_analysis._point_dir", return_value=tmp_path):
        assert local_analysis.local_record_status(point)[1] is None
        (tmp_path / "ensemble_dettaglio.csv").write_text("changed\n", encoding="utf-8")
        assert local_analysis.local_record_status(point)[1] == "files_changed"
        _fake_local_cache(tmp_path, point)
        (tmp_path / "fieldwise_local.json").write_text(json.dumps({**rec, "engineCodeHash": "0" * 64}), encoding="utf-8")
        assert local_analysis.local_record_status(point)[1] == "engine_changed"


def test_too_many_preparations_give_429():
    with patch("local_analysis.MAX_ACTIVE_JOBS", 0), patch("local_analysis.config.offline", return_value=False), \
         patch("local_analysis.local_record_status", return_value=(None, "missing", "")), \
         patch("local_analysis._POOL.submit", side_effect=AssertionError("must not start")):
        r = CLIENT.post("/api/v1/prepare", json={"point": [10.3, 45.3]})
    assert r.status_code == 429 and r.json()["detail"]["code"] == "PREPARATION_BUSY"


# --- extra points: computed before the last economia.yaml change -------------------------------
@pytest.mark.parametrize("point", EXTRA_POINTS)
def test_outdated_extra_points_give_a_clear_error_not_old_numbers(point):
    key = config.DATA_DIR / "processed" / f"lat{point[1]:.3f}_lon{point[0]:.3f}"
    if not (key / "fieldwise_local.json").exists():
        pytest.skip("extra point cache not present")
    r = CLIENT.post("/api/v1/analyze", json={**BASE, "point": point})
    assert r.status_code == 409
    detail = r.json()["detail"]
    assert detail["code"] == "LOCAL_DATA_STALE" and "economia.yaml" in detail["message"]
    with patch("local_analysis.config.offline", return_value=True):      # never regenerate in tests
        r = CLIENT.post("/api/v1/prepare", json={"point": point})
    assert r.status_code == 409 and "out of date" in r.json()["detail"]["message"]
