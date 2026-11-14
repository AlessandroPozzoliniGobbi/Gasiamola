"""PDF export: Unicode font on macOS (n. 21) and historical axis by evaluated cycle (n. 5)."""
from pathlib import Path

import pytest

import report_export
from report_export import render_pdf


def _series(key):
    return [{"role": "current", "rotation": "mais > mais > mais",
             "points": [{key: 2003 + i, "memberCount": 3, "relativeYield": 0.8 + i / 100,
                         "irrigationMm": 100, "humusChangeTonsHa": -0.2, "grossMarginEurHa": 500} for i in range(5)]}]


@pytest.mark.parametrize("key", ["evaluatedYear", "startYear"])       # new reports and legacy saved reports
def test_historical_figures_render_for_new_and_legacy_axis(key):
    md = "# Report\n\n## Historical\n\n<!-- FIELDWISE_HISTORICAL_CHARTS -->\n\n## End\n\nNot a forecast → Δ ≥ −1."
    report = {"inputs": {"advancedEconomics": True}, "results": {"historicalWindows": {"series": _series(key)}}}
    assert render_pdf(md, report).startswith(b"%PDF-")
    assert report_export._point_year({key: 2003}) == 2003


def test_unicode_font_is_used_when_the_system_provides_one():
    mac = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    if not mac.is_file() and not Path("C:/Windows/Fonts/arial.ttf").is_file() and \
            not Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf").is_file():
        pytest.skip("no known Unicode TTF on this system")
    assert report_export._fonts() == ("FW-Regular", "FW-Bold")
