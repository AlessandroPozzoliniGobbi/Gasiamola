"""Contract tests: current economy is fixed-assumption; unsupported overrides fail clearly."""
import pytest
from fastapi.testclient import TestClient
from api import app
from fieldwise import economics, params

CLIENT = TestClient(app)
BASE = {"point": [10.0, 45.2], "rotation": "mais > soia > frumento",
        "scenario": "tetto_irriguo", "priorities": {"resa": 5, "rischio": 5,
        "acqua": 5, "concime": 5, "suolo": 5, "profitto": 0}}


def test_standard_report_without_profit_priority_is_valid():
    response = CLIENT.post('/api/v1/analyze', json=BASE)
    assert response.status_code == 200, response.text
    assert response.json()["results"]["current"] is not None


def test_unknown_economic_overrides_are_not_silently_ignored():
    response = CLIENT.post('/api/v1/analyze', json={**BASE,
        "economic_parameters": {"seedCostEurHa": 150}})
    assert response.status_code == 422
    assert "economic_parameters" in response.text


def test_existing_economics_formula_uses_fixed_assumptions():
    p = params.load_params()
    out = {"durata_anni": 3,
           "colture": [{"coltura": "mais", "resa": 10},
                       {"coltura": "soia", "resa": 3},
                       {"coltura": "frumento", "resa": 5}],
           "indicatori": {"concime_anno": 100, "irrigazione_anno": 50}}
    actual = economics.margine_anno(p, out)
    expected = ((10 * economics.prezzo_coltura(p, "mais") +
                 3 * economics.prezzo_coltura(p, "soia") +
                 5 * economics.prezzo_coltura(p, "frumento")) / 3 -
                 economics.costo_concime_anno(p, 100) -
                 economics.costo_irrigazione_anno(p, 50) -
                 sum(economics.altri_costi_coltura(p, c) for c in ("mais", "soia", "frumento")) / 3)
    assert actual == pytest.approx(expected)
