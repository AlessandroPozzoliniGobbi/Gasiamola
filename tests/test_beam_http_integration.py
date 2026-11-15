"""HTTP contract, strict compliance, price overrides, and coherent nine-year path."""
import time
from unittest.mock import patch

from fastapi.testclient import TestClient
from api import app

client = TestClient(app)
BASE = {"point": [10.0, 45.2], "objectives": ["resa", "guadagno", "costo"],
        "regime_normativo": "lombardia_impegno_quinquennale"}


def test_validates_input_and_rejects_outside_area():
    assert client.post('/api/v1/beam-search', json={**BASE, "objectives": ["resa"]}).status_code == 422
    assert client.post('/api/v1/beam-search', json={**BASE, "point": [11.8, 45.2]}).status_code == 422
    assert client.post('/api/v1/beam-search', json={**BASE, "beam_width": 10000}).status_code == 422
    assert client.post('/api/v1/beam-search', json={**BASE, "other_crop_costs_eur_ha": {"unknown": 1}}).status_code == 422
    assert client.get('/api/v1/beam-search/does-not-exist').status_code == 404


def _completed(params):
    started = client.post('/api/v1/beam-search', json={**BASE, **params})
    assert started.status_code == 200, started.text
    d = started.json()
    assert d["status"] == "running"
    deadline = time.monotonic() + 65
    while time.monotonic() < deadline:
        r = client.get('/api/v1/beam-search/' + d['jobId'])
        assert r.status_code == 200
        state = r.json()
        if state['status'] == 'ready':
            return state['result']
        assert state['status'] == 'running', state
        time.sleep(.15)
    raise AssertionError("timed out waiting for pilot optimizer")


def test_9y_compliant_and_costs_override():
    normal = _completed({"beam_width": 4})
    assert len(normal['trienni']) == 3
    assert len(normal['eredita_suolo']) == 2
    assert all(row['stato_conformita'] == 'conforme' for row in normal['trienni'])
    assert normal['solo_conformi'] is True
    adjusted = _completed({"beam_width": 4, "other_crop_costs_eur_ha": {'mais': 8500}})
    assert len(adjusted['trienni']) == 3
    assert adjusted['trienni'][0]['costo_totale_eur_ha'] != normal['trienni'][0]['costo_totale_eur_ha']
    assert adjusted['trienni'][0]['stato_conformita'] == 'conforme'


def test_field_rejects_unprepared_without_fallback():
    # May be stale or missing, but must NOT secretly substitute pilot weather.
    r = client.post('/api/v1/beam-search', json={**BASE, 'point': [10.15,45.2]})
    assert r.status_code == 409
    assert r.json()['detail']['code'] in {'LOCAL_DATA_NOT_READY', 'LOCAL_DATA_STALE'}


def test_prepared_field_starts_optimizer_with_local_source_mode():
    """A valid non-pilot field must return its sourceMode, not HTTP 500."""
    field_point = [9.433, 45.314]
    with patch('api.local_record_status', return_value=({'parametersHash': 'valid'}, None, 'Local analysis data are current.')) as local_check, \
         patch('beam_jobs.start', return_value={'jobId': 'local-test-job', 'status': 'running', 'stage': 'Starting optimizer...'}) as start_job:
        response = client.post('/api/v1/beam-search', json={**BASE, 'point': field_point})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['sourceMode'] == 'local_estimate'
    assert payload['modelPoint'] == field_point
    assert payload['jobId'] == 'local-test-job'
    local_check.assert_called_once()
    assert start_job.call_args.args[0]['model_point'] == tuple(field_point)
