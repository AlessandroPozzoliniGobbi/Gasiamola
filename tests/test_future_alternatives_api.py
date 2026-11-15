"""Future alternatives are real simulated records, not extrapolated historic rankings."""
from fastapi.testclient import TestClient
import pytest
from api import app
from fieldwise import ensemble

client = TestClient(app)
BASE = {"point": [10.0, 45.2], "rotation": "mais > soia > frumento",
        "scenario": "tetto_irriguo", "include_future": True,
        "future_ssp": "ssp245", "future_horizon": 10,
        "priorities": {k: 5 for k in ("resa", "rischio", "acqua", "concime", "suolo", "profitto")}}
REGIMES = (
    "lombardia_impegno_quinquennale", "lombardia_impegno_triennale_SRA01_2026",
    "emilia_romagna_impegno_quinquennale", "emilia_romagna_adesione_singola_coltura",
)


def analyze(**kwargs):
    response = client.post("/api/v1/analyze", json={**BASE, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()["results"]["future"]


@pytest.mark.parametrize("regime", REGIMES)
def test_future_alternatives_enforce_selected_regional_rules(regime):
    payload = analyze(regulatory_regime=regime)
    choices = payload["candidateRotations"]
    assert choices, "The pilot precalculated ranking has compliant options"
    _, summary = ensemble.load_ensemble()
    compliant = set(summary.loc[summary[f"conformita_{regime}"] == "conforme", "classe"])
    assert all(x["rotation"] in compliant for x in choices)
    assert all(x["rotation"] != payload["current_rotation"] for x in choices)
    assert all(x["relativeYieldPct"] is not None and x["marginEurHa"] is not None for x in choices)
    assert all(x["precomputedRank"] >= 1 for x in choices)
    assert len({x["rotation"] for x in choices}) == len(choices)
    assert [x["precomputedRank"] for x in choices] == sorted(x["precomputedRank"] for x in choices)


def test_farmer_crop_cost_changes_future_alternative_margins_only():
    first = analyze()
    second = analyze(other_crop_costs_eur_ha={"mais": 2550.0})
    a = {x["rotation"]: x for x in first["candidateRotations"]}
    b = {x["rotation"]: x for x in second["candidateRotations"]}
    assert a.keys() == b.keys()
    assert any(a[k]["marginEurHa"] != b[k]["marginEurHa"] for k in a)
    for k in a:
        for field in ("relativeYieldPct", "yieldP10Pct", "irrigationMm", "fertilizerKgN",
                      "nitrogenLeachingKgN", "humusChangeTonsHa"):
            assert a[k][field] == b[k][field]


@pytest.mark.parametrize("scenario", ["solo_pioggia", "irrigazione_libera"])
def test_unarchived_irrigation_simulates_real_future_alternatives(scenario):
    future = analyze(scenario=scenario)
    assert future["irrigation_regime"] == scenario
    assert future["candidateRankingSource"] == "on_demand"
    assert future["referenceMatchesRequestedRotation"] is True
    assert len(future["candidateRotations"]) > 0
    assert all(c["marginDeltaVsCurrentEurHa"] is not None for c in future["candidateRotations"])


def test_unarchived_current_rotation_uses_real_requested_reference():
    future = analyze(rotation="mais > mais > mais")
    assert future["referenceMatchesRequestedRotation"] is True
    assert future["candidateRankingSource"] == "on_demand"
    assert future["current_rotation"] == "mais > mais > mais"
    assert future["candidateRotations"]
    assert all(x["marginDeltaVsCurrentEurHa"] is not None for x in future["candidateRotations"])


def test_farmer_costs_are_deducted_once_from_on_demand_reference():
    before = analyze(scenario="solo_pioggia")
    after = analyze(scenario="solo_pioggia", other_crop_costs_eur_ha={"mais": 2550.0})
    # The entered cycle has one year of maize out of three. The delta from
    # default maize cost is 600 EUR/ha, i.e. 200 EUR/ha/year.
    assert after["future_margine_eur_ha"] == pytest.approx(before["future_margine_eur_ha"] - 200, abs=.11)
    assert after["baseline_margine_eur_ha"] == pytest.approx(before["baseline_margine_eur_ha"] - 200, abs=.11)
    assert len(after["candidateRotations"]) == len(before["candidateRotations"])


def test_local_future_uses_locally_derived_soil_parameters(monkeypatch):
    import future_alternatives as fw_future
    # The helper must not silently fall back to pilot soils for a prepared field.
    sentinel = {"soil": "location specific"}
    seen = []
    def local_builder(lat, lon):
        seen.append((lat, lon))
        return sentinel, {"soilDataMethod": "wcs"}
    monkeypatch.setattr("local_analysis.build_local_parameters", local_builder)
    assert fw_future._parameters_for_model_point(45.217, 10.086) is sentinel
    assert seen == [(45.217, 10.086)]
