"""Local location-conditioning: tests run without external network access."""
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi.testclient import TestClient

from api import app
from fieldwise import config, params, rotation, ensemble
from local_analysis import build_local_parameters, normalized_point

CLIENT = TestClient(app)
BASE = {"point": [10.013, 45.203], "rotation": "mais > soia > frumento",
        "scenario": "tetto_irriguo", "priorities": {"resa": 5, "rischio": 5, "acqua": 5,
                                                "concime": 5, "suolo": 5, "profitto": 5}}


def test_local_profile_from_existing_soilgrids_aggregates():
    csv = config.DATA_DIR / "processed" / "lat45.200_lon10.000" / "soilgrids_agg.csv"
    assert csv.exists(), "Repository pilot sample needed for adapter test"
    with patch("fieldwise.data.soilgrids.load_aggregated", return_value=pd.read_csv(csv)), \
         patch("fieldwise.data.soilgrids.pixel_info", return_value={"shift_m": 0, "via": "wcs"}):
        p, details = build_local_parameters(45.2, 10.0)
    assert not params.validate_params(p)
    assert details["soilDataMethod"] == "wcs"
    assert details["curveNumber"] == 72
    assert p["soil"]["strati_soilgrids"]["s0_30"]["sostanza_organica"]["valore"] > 0
    assert "Location-conditioned" in p["soil"]["_meta"]["descrizione"]
    context = rotation.build_context(p=p, lat=45.2, lon=10.0)
    assert 0 < context.soil.wp1 < context.soil.fc1 < context.soil.sat1


def test_point_cache_precision_matches_engine():
    assert normalized_point((10.01349, 45.20349)) == (10.013, 45.203)
    assert normalized_point((10.01351, 45.20351)) == (10.014, 45.204)


def test_local_preparation_is_explicit_when_offline():
    with patch("api.start_preparation", side_effect=__import__("local_analysis").PreparationError("Offline cache not ready")):
        r = CLIENT.post("/api/v1/prepare", json={"point": BASE["point"]})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "PREPARATION_UNAVAILABLE"


def test_local_preparation_starts_and_status_polls():
    with patch("api.start_preparation", return_value={"jobId": "abc", "status": "running", "stage": "Retrieving data"}), \
         patch("api.job_status", return_value={"status": "ready", "stage": "Done"}):
        initial = CLIENT.post("/api/v1/prepare", json={"point": BASE["point"]})
        assert initial.status_code == 200
        assert initial.json()["jobId"] == "abc"
        done = CLIENT.get("/api/v1/prepare/abc")
        assert done.json()["status"] == "ready"
    assert CLIENT.post("/api/v1/prepare",json={"point":[12.5,45.2]}).status_code==422


def test_local_report_uses_prepared_ensemble_not_pilot_point():
    _, summary = ensemble.load_ensemble(lat=45.2,lon=10.0)
    rec = {"parametersHash": summary.attrs["meta"]["hash_parametri"],
           "details": {"soilDataMethod": "wcs", "curveNumber": 72}}
    with patch("api.local_record_status", return_value=(rec, None, "current")), \
         patch("api.ensemble.load_ensemble", return_value=(None, summary)), \
         patch("api._cache_is_current", return_value=True):
        r = CLIENT.post("/api/v1/analyze", json=BASE)
    assert r.status_code == 200, r.text
    output = r.json()
    assert output["engine"]["sourceMode"] == "local_estimate"
    assert output["engine"]["modelPoint"] == [10.013, 45.203]
    assert output["results"]["current"] is not None
    assert "not filtered by regional rules" in output["results"]["notes"][1]
    assert "least favourable" in output["results"]["notes"][1]
    assert output["engine"]["limitations"]["appliesToThisAnalysisData"] is False
