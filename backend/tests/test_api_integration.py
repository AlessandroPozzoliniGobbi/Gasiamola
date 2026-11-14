"""Tests for the HTTP layer; no engine mutation or network needed."""
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)
BASE = {"point": [10.0,45.2], "rotation":"mais > soia > frumento", "scenario":"tetto_irriguo",
        "priorities":{"resa":5,"rischio":5,"acqua":5,"concime":5,"suolo":5,"profitto":5}}

def test_health():
    r=client.get('/api/v1/health'); assert r.status_code==200; assert r.json()['pilotReady']

def test_real_report_has_compliant_alternatives_and_profit():
    r=client.post('/api/v1/analyze',json=BASE)
    assert r.status_code==200, r.text
    out=r.json()
    assert out['results']['current']['metrics']['relativeYieldMedian'] is not None
    assert out['results']['alternatives'][0]['metrics']['grossMarginEurHa'] is not None
    assert out['engine']['sourceMode']=='pilot_point'
    assert out['results']['comparedRotations']>=2

def test_location_guard():
    d={**BASE,'point':[9.9,45.3]}
    assert client.post('/api/v1/analyze',json=d).status_code==409
    d['use_pilot_reference']=True
    r=client.post('/api/v1/analyze',json=d)
    assert r.status_code==200, r.text
    assert r.json()['engine']['sourceMode']=='pilot_reference'

def test_reject_outside_100km_and_invalid_weights():
    assert client.post('/api/v1/analyze',json={**BASE,'point':[11.8,45.2],'use_pilot_reference':True}).status_code==422
    assert client.post('/api/v1/analyze',json={**BASE,'priorities':{'resa':0}}).status_code==422
