"""Regression tests for multi-field PDF charts. No scientific API changes."""
from report_export import render_pdf


def _report(enabled):
    return {
        'id': 'portfolio-test',
        'portfolio': {
            'fields': [
                {'name': 'North', 'areaHectares': 3, 'advancedEconomics': enabled,
                 'current': {'irrigationMm': 120, 'fertilizerKgN': 100, 'relativeYieldMedian': 0.7,
                             'nitrogenLeachingKgN': 4, 'humusChangeTonsHa': -0.25, 'grossMarginEurHa': 1500},
                 'recommended': {'irrigationMm': 120, 'fertilizerKgN': 100, 'relativeYieldMedian': 0.7,
                                 'nitrogenLeachingKgN': 4, 'humusChangeTonsHa': -0.25, 'grossMarginEurHa': 1700}},
                {'name': 'South', 'areaHectares': 2, 'advancedEconomics': False,
                 'current': {}, 'recommended': {}},
            ]
        }
    }


def test_portfolio_zero_deltas_and_missing_fields_are_valid():
    markdown = "# Farm Portfolio\n\n## Comparison\n\n<!-- FIELDWISE_PORTFOLIO_CHARTS -->\n\n## Disclaimer\n\nModel uncertainty applies."
    result = render_pdf(markdown, _report(True))
    assert result.startswith(b'%PDF-')
    assert len(result) > 4000


def test_portfolio_without_economics_still_exports():
    markdown = "# Farm Portfolio\n\n## Comparison\n\n<!-- FIELDWISE_PORTFOLIO_CHARTS -->\n\n## Disclaimer\n\nModel uncertainty applies."
    result = render_pdf(markdown, _report(False))
    assert result.startswith(b'%PDF-')
