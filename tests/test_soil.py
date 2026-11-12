"""Test di fieldwise.soil (Saxton e Rawls 2006) e coerenza con params/soil.yaml.

Valori di riferimento: foglio USDA "Soil Water Characteristics-Equations.xls" (K. Saxton,
rev. 2007), USDA Ag Data Commons doi:10.15482/USDA.ADC/1529226, foglio "Equations":
righe 40-51 = esempi per le 12 classi tessiturali con OM 2,5 %, senza densita'/scheletro
(gli esempi della tabella per classi dell'articolo, che li stampa arrotondati: theta al
punto percentuale, Ksat a 0,1 mm/h); righe 18-28 = medie per classe dei campioni A
dell'NRCS; riga 30 = esempio con fattore di densita' 1,2.

Tolleranza: il foglio riporta theta in % con 4+ decimali e Ksat con 4 decimali, quindi si
confronta con 1e-4 m3/m3 su theta e 0,1 % relativo su Ksat. Contro i valori arrotondati
stampati nell'articolo la tolleranza consentita sarebbe 0,005 m3/m3 e 0,05 mm/h.
"""
from __future__ import annotations

import math

import numpy as np
import pytest
import yaml

from fieldwise import config, soil

# classe, S, C, OM, wp %, fc %, sat %, Ksat mm/h  (foglio USDA, righe 40-51, OM 2,5 %)
TABLE_OM25 = [
    ("sand", 0.88, 0.05, 2.5, 5.022058, 10.282792, 46.172241, 108.147828),
    ("loamy sand", 0.80, 0.05, 2.5, 5.09593, 12.024455, 46.022569, 96.67463),
    ("sandy loam", 0.65, 0.10, 2.5, 8.07703, 17.916761, 44.989465, 50.304555),
    ("loam", 0.40, 0.20, 2.5, 13.70236, 27.961016, 45.947824, 15.475656),
    ("silt loam", 0.20, 0.15, 2.5, 10.98631, 30.518295, 47.872493, 16.120217),
    ("silt", 0.10, 0.05, 2.5, 5.74231, 30.454126, 47.903064, 21.993884),
    ("sandy clay loam", 0.60, 0.25, 2.5, 16.57345, 26.704505, 43.413075, 11.258895),
    ("clay loam", 0.30, 0.35, 2.5, 21.79921, 35.789791, 47.724069, 4.323838),
    ("silty clay loam", 0.10, 0.35, 2.5, 21.51877, 38.18351, 51.121996, 5.683962),
    ("silty clay", 0.10, 0.45, 2.5, 26.77759, 40.913035, 52.348037, 3.671623),
    ("sandy clay", 0.50, 0.40, 2.5, 24.8641, 36.11151, 44.37899, 1.391659),
    ("clay", 0.25, 0.50, 2.5, 29.79175, 42.063063, 49.843463, 1.144958),
]

# medie per classe dei campioni NRCS (righe 18-28): S, C, OM, wp, fc, sat (frazioni), Ksat
TABLE_CLASS_MEANS = [
    (0.846273, 0.043015, 2.08, 0.041824, 0.100212, 0.453311, 107.833912),
    (0.802438, 0.051656, 2.327939, 0.050066, 0.117969, 0.455432, 94.662044),
    (0.634455, 0.102993, 2.519965, 0.08273, 0.184432, 0.450503, 48.009751),
    (0.412374, 0.185478, 3.055654, 0.132644, 0.277329, 0.473566, 19.978354),
    (0.15039, 0.180107, 3.045249, 0.128629, 0.331377, 0.504826, 15.549469),
    (0.0494, 0.100525, 1.893814, 0.080848, 0.32353, 0.462659, 10.642092),
    (0.532231, 0.262179, 2.29071, 0.170869, 0.282575, 0.437899, 9.244172),
    (0.291177, 0.315769, 3.509799, 0.203217, 0.351965, 0.496751, 7.735977),
    (0.088847, 0.321913, 4.056728, 0.204295, 0.382743, 0.546432, 11.39988),
    (0.076554, 0.465157, 3.592151, 0.275626, 0.412373, 0.542607, 5.286654),
    (0.127364, 0.545557, 2.88, 0.318629, 0.434552, 0.531142, 2.103228),
]

TOL_THETA = 1e-4
TOL_KSAT_REL = 1e-3


@pytest.mark.parametrize("name,S,C,OM,wp,fc,sat,ks", TABLE_OM25, ids=[r[0] for r in TABLE_OM25])
def test_texture_class_examples_om25(name, S, C, OM, wp, fc, sat, ks):
    r = soil.saxton_rawls(S, C, OM)
    assert r["wp"] == pytest.approx(wp / 100, abs=TOL_THETA)
    assert r["fc"] == pytest.approx(fc / 100, abs=TOL_THETA)
    assert r["sat"] == pytest.approx(sat / 100, abs=TOL_THETA)
    assert r["ksat"] == pytest.approx(ks, rel=TOL_KSAT_REL)
    # anche la classe tessiturale dell'esempio deve tornare
    assert soil.usda_texture_class(S * 100, C * 100) == name


@pytest.mark.parametrize("row", TABLE_CLASS_MEANS)
def test_nrcs_class_means(row):
    S, C, OM, wp, fc, sat, ks = row
    r = soil.saxton_rawls(S, C, OM)
    assert (r["wp"], r["fc"], r["sat"]) == pytest.approx((wp, fc, sat), abs=TOL_THETA)
    assert r["ksat"] == pytest.approx(ks, rel=TOL_KSAT_REL)


def test_vectorised_matches_scalar():
    S = np.array([r[1] for r in TABLE_OM25])
    C = np.array([r[2] for r in TABLE_OM25])
    r = soil.saxton_rawls(S, C, 2.5)
    np.testing.assert_allclose(r["fc"], [x[5] / 100 for x in TABLE_OM25], atol=TOL_THETA)


def test_density_adjustment_usda_example():
    # foglio USDA riga 30: S = C = 0,05, OM = 1 %, DF = 1,2
    r = soil.saxton_rawls(0.05, 0.05, 1.0, df=1.2)
    assert r["rho_n"] == pytest.approx(1.5563, abs=5e-4)
    assert r["rho_df"] == pytest.approx(1.8676, abs=5e-4)
    assert r["wp"] == pytest.approx(0.048309, abs=TOL_THETA)
    assert r["fc"] == pytest.approx(0.275007, abs=TOL_THETA)
    assert r["sat"] == pytest.approx(0.295242, abs=TOL_THETA)
    assert r["ksat"] == pytest.approx(0.094557, rel=5e-3)


def test_gravel_reduces_bulk_water_only():
    r0 = soil.saxton_rawls(0.4, 0.2, 2.5)
    r = soil.saxton_rawls(0.4, 0.2, 2.5, gravel_vol=0.2)
    assert r["fc_bulk"] == pytest.approx(0.8 * r0["fc"])
    assert r["fc"] == pytest.approx(r0["fc"])
    assert r["ksat"] == pytest.approx(r0["ksat"])


# ------------------------------------------------------------ controlli fisici

GRID = [(s, c, om) for s in (0.05, 0.2, 0.4, 0.6, 0.85) for c in (0.05, 0.15, 0.3, 0.45, 0.6)
        if s + c < 1.0 for om in (0.5, 2.5, 5.0, 8.0)]


def test_corner_without_silt_is_rejected():
    # Al bordo del campo di validita' (argilla 60 %, sabbia 40 %, limo 0, OM 5 %) le
    # regressioni danno fc >= sat: la funzione rifiuta invece di restituire numeri non fisici.
    with pytest.raises(ValueError):
        soil.saxton_rawls(0.4, 0.6, 5.0)


@pytest.mark.parametrize("S,C,OM", GRID)
def test_physical_order(S, C, OM):
    r = soil.saxton_rawls(S, C, OM)
    assert 0 < r["wp"] < r["fc"] < r["sat"] < 1
    assert r["ksat"] > 0


def test_wp_increases_with_clay():
    for S in (0.1, 0.3, 0.5):
        for OM in (1.0, 2.5, 5.0):
            clays = np.linspace(0.05, 0.6 - 0.0, 12)
            clays = clays[S + clays <= 1]
            wp = soil.saxton_rawls(S, clays, OM)["wp"]
            assert np.all(np.diff(wp) > 0)


def test_ksat_decreases_with_clay():
    for S in (0.2, 0.4):
        ks = soil.saxton_rawls(S, np.linspace(0.05, 0.5, 10), 2.5)["ksat"]
        assert np.all(np.diff(ks) < 0)


def test_om_effect_where_expected():
    # dfc/dOM ~ 0,011 + 0,006 S - 0,027 C (eq. 2) > 0 per suoli non argillosi: fc e acqua
    # disponibile crescono con la sostanza organica; la saturazione cresce sempre.
    oms = np.linspace(0.5, 8.0, 16)
    for S, C in ((0.4, 0.2), (0.33, 0.26), (0.65, 0.1), (0.2, 0.15)):
        r = soil.saxton_rawls(S, C, oms)
        assert np.all(np.diff(r["fc"]) > 0)
        assert np.all(np.diff(r["fc"] - r["wp"]) > 0)
        assert np.all(np.diff(r["sat"]) > 0)


def test_out_of_range_warns():
    with pytest.warns(UserWarning):
        r = soil.saxton_rawls(0.1, 0.65, 2.0)
    assert r["fuori_validita"] is True
    with pytest.warns(UserWarning):
        soil.saxton_rawls(0.3, 0.3, 12.0)


def test_texture_classes():
    assert soil.usda_texture_class(32.8, 25.6, 41.7) == "loam"
    assert soil.usda_texture_class(56, 10, 34) == "sandy loam"   # Luignano (FerSoil 2009)
    assert soil.usda_texture_class(10, 10, 80) == "silt"
    assert soil.usda_texture_class(15, 30, 55) == "silty clay loam"


def test_hydrologic_group():
    assert soil.hydrologic_soil_group(2.0, 2.0, 150) == "C"
    assert soil.hydrologic_soil_group(2.0, 2.0, 85) == "C"
    assert soil.hydrologic_soil_group(2.0, 2.0, 40) == "C/D"
    assert soil.hydrologic_soil_group(50, 50, 200) == "A"
    assert soil.hydrologic_soil_group(5, 5, 200, impermeable_cm=30) == "D"


def test_aquacrop_tau():
    # eq. 3.7b: Ksat 100 mm/giorno -> 0,0866 * 100^0,35
    assert soil.aquacrop_tau(100 / 24) == pytest.approx(0.0866 * 100 ** 0.35)
    assert soil.aquacrop_tau(1e6) == 1.0


# ------------------------------------------------------------ coerenza con params/soil.yaml

def _yaml():
    with (config.PARAMS_DIR / "soil.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _v(node):
    return node["valore"]


def _horizons_from_yaml(y):
    hz = []
    for key in ("s0_30", "s30_100", "s100_200"):
        s = y["strati_soilgrids"][key]
        top, bot = _v(s["profondita"])
        hz.append({"top_cm": top, "bottom_cm": bot, "sand": _v(s["sabbia"]), "clay": _v(s["argilla"]),
                   "om": _v(s["sostanza_organica"]), "bdod": _v(s["densita_apparente"]),
                   "cfvo": _v(s["frammenti_grossolani"])})
    return hz


def test_yaml_inputs_match_soilgrids_cache():
    sg = pytest.importorskip("fieldwise.data.soilgrids")
    try:
        cached = soil.horizons_from_aggregated(sg.load_aggregated(45.2, 10.0))
    except Exception as exc:  # cache assente
        pytest.skip(f"cache SoilGrids non disponibile: {exc}")
    for h, c in zip(_horizons_from_yaml(_yaml()), cached):
        for k in ("sand", "clay", "om", "bdod", "cfvo"):
            assert h[k] == pytest.approx(c[k], abs=0.006), k


def test_yaml_results_match_recomputation():
    y = _yaml()
    hz = _horizons_from_yaml(y)
    props = soil.profile_properties(hz)
    cum = 0.0
    for key, p in zip(("s0_30", "s30_100", "s100_200"), props):
        s = y["strati_soilgrids"][key]
        for k in ("fc", "wp", "sat"):
            assert _v(s[k]) == pytest.approx(p[k], abs=5e-4), (key, k)
        assert _v(s["ksat"]) == pytest.approx(p["ksat"], rel=5e-3), key
        assert _v(s["acqua_disponibile"]) == pytest.approx(p["aw_mm"], abs=0.5), key
        cum += p["aw_mm"]
    assert y["strati_soilgrids"]["s0_30"]["classe_tessiturale"]["valore"] == props[0]["texture"]

    z = _v(y["profilo"]["profondita_profilo"])
    thick = _v(y["profilo"]["spessore_strati"])
    assert sum(thick) == pytest.approx(z)
    bounds = [0, thick[0] * 100, z * 100]
    eng = soil.engine_layers(soil.profile_properties(hz, z_max_cm=z * 100), bounds)
    for name, L in zip(("strato_superficiale", "strato_profondo"), eng):
        s = y["profilo"][name]
        for k in ("fc", "wp", "sat"):
            assert _v(s[k]) == pytest.approx(L[k], abs=5e-4), (name, k)
        assert _v(s["ksat"]) == pytest.approx(L["ksat"], rel=5e-3), name
        assert _v(s["acqua_disponibile"]) == pytest.approx(L["aw_mm"], abs=0.5), name
    assert _v(y["profilo"]["acqua_disponibile_totale"]) == pytest.approx(sum(L["aw_mm"] for L in eng), abs=0.5)

    tau = y["drenaggio"]["tau_alternativa"]
    assert _v(tau["strato_superficiale"]) == pytest.approx(soil.aquacrop_tau(eng[0]["ksat"]), abs=2e-3)
    assert _v(tau["strato_profondo"]) == pytest.approx(soil.aquacrop_tau(eng[1]["ksat"]), abs=2e-3)

    k = min(p["ksat"] for p in props[:2]) / 3.6
    assert y["ruscellamento"]["gruppo_idrologico"]["valore"] == soil.hydrologic_soil_group(k, k, 130)


def test_yaml_om_alternative_effect():
    # la nota della sostanza organica riporta fc e wp ricalcolati con la sostanza organica ERSAF
    y = _yaml()
    s = y["strati_soilgrids"]["s0_30"]
    om_alt = s["sostanza_organica"]["intervallo"][0]
    assert om_alt == pytest.approx(13.5 / 10 * 1.724, abs=1e-3)
    r = soil.saxton_rawls(_v(s["sabbia"]) / 100, _v(s["argilla"]) / 100, om_alt)
    assert s["fc"]["intervallo"][0] == pytest.approx(r["fc"], abs=5e-4)
    assert s["wp"]["intervallo"][0] == pytest.approx(r["wp"], abs=5e-4)
    assert not math.isnan(r["ksat"])
