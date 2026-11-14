"""Smoke test for direct PDF download and text wrapping."""
from fastapi.testclient import TestClient
from api import app


def test_direct_pdf_download_without_external_print_window():
    markdown = """# FIELDWISE | Field Report

## 1. Notes

""" + "The analysis is based on historical windows. " * 25 + """

| Parameter | Value |
| --- | --- |
| Source | Location-conditioned estimate |
| Long note | """ + "Detailed model assumption and provenance. " * 25 + """ |

## Final disclaimer

This is not a field measurement.
"""
    report = {"id": "test-pdf-1", "field": {"name": "Example field"}, "inputs": {"advancedEconomics": False}, "results": {"current": {"metrics": {}}, "alternatives": [], "notes": []}}
    response = TestClient(app).post('/api/v1/reports/pdf', json={"markdown": markdown, "report": report, "demo": False})
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.content[:5] == b'%PDF-'
    assert len(response.content) > 2000


def test_empty_markdown_is_rejected():
    response = TestClient(app).post('/api/v1/reports/pdf', json={"markdown": "Hi", "report": {}})
    assert response.status_code == 422
