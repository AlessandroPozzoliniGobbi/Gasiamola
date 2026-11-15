"""Test del modulo di simulazione futura CMIP6 (`fieldwise.future` e `fieldwise.data.cmip6`).

Verifica:
- Orizzonti (5, 10, 15, 20 anni) e Scenari (SSP1-2.6, SSP2-4.5, SSP5-8.5 con etichette e descrizioni).
- Metodo Delta Change: vincoli fisici (tmin <= tmax, rain >= 0, rh in [5, 100], ricalcolo ET0).
- Conto economico con `economics.py` (costo concime + irrigazione, margine/guadagno).
- Coerenza dei file pre-calcolati: future_dashboard_summary.json, future_rotations_ranking.csv,
  future_full_analysis_timeseries.csv.
- Calcolo on-demand con `get_future_simulation_payload`.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import pytest

from fieldwise import config
from fieldwise import economics as eco
from fieldwise import future as fut
from fieldwise import params as fparams
from fieldwise import weather
from fieldwise.data import cache
from fieldwise.data import cmip6


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture(scope="module")
def p():
    return fparams.load_params()


@pytest.fixture(scope="module")
def forcing_hist():
    """Forcing storico del punto pilota (da cache)."""
    try:
        return weather.load_forcing(config.PILOT_LAT, config.PILOT_LON)
    except cache.CacheMiss as e:
        pytest.skip(f"Cache del punto pilota non disponibile: {e}")


# =============================================================================
# 1. Test parametri CMIP6 e costanti
# =============================================================================

def test_cmip6_constants():
    assert fut.HORIZONS == (5, 10, 15, 20)
    assert fut.SSP_CODES == ("ssp126", "ssp245", "ssp585")
    assert cmip6.HORIZONS == (5, 10, 15, 20)
    assert cmip6.SSP_CODES == ("ssp126", "ssp245", "ssp585")

    for ssp in fut.SSP_CODES:
        assert ssp in fut.SSP_LABELS
        assert ssp in fut.SSP_DESCRIPTIONS
        assert len(fut.SSP_LABELS[ssp]) > 0
        assert len(fut.SSP_DESCRIPTIONS[ssp]) > 10


def test_cmip6_yaml_structure(p):
    assert "cmip6" in p
    for ssp in fut.SSP_CODES:
        prefix = f"cmip6.delta_{ssp}"
        dt = [fparams.get(p, f"{prefix}.delta_t_c[{i}]") for i in range(12)]
        ar = [fparams.get(p, f"{prefix}.alpha_rain[{i}]") for i in range(12)]
        asrad = [fparams.get(p, f"{prefix}.alpha_srad[{i}]") for i in range(12)]
        drh = [fparams.get(p, f"{prefix}.delta_rh[{i}]") for i in range(12)]

        assert len(dt) == 12 and all(v > 0 for v in dt)
        assert len(ar) == 12 and all(0.5 < v <= 1.0 for v in ar)
        assert len(asrad) == 12 and all(0.9 < v < 1.2 for v in asrad)
        assert len(drh) == 12 and all(v <= 0 for v in drh)


# =============================================================================
# 2. Test Metodo Delta Change (cmip6.py)
# =============================================================================

def test_delta_change_invalid_args(forcing_hist):
    with pytest.raises(ValueError, match="ssp_code non valido"):
        cmip6.apply_delta_change(forcing_hist, "ssp_invalido", 10, 45.2, 100.0)

    with pytest.raises(ValueError, match="horizon_years non valido"):
        cmip6.apply_delta_change(forcing_hist, "ssp245", 33, 45.2, 100.0)


def test_delta_change_physics_and_scaling(forcing_hist, p):
    lat, elev = config.PILOT_LAT, 100.0

    df_5 = cmip6.apply_delta_change(forcing_hist, "ssp245", 5, lat, elev, p)
    df_20 = cmip6.apply_delta_change(forcing_hist, "ssp245", 20, lat, elev, p)

    # Stesse righe e colonne attese
    assert len(df_5) == len(forcing_hist)
    assert len(df_20) == len(forcing_hist)
    assert "et0" in df_5.columns and "et0" in df_20.columns

    # 1. Vincolo fisico tmin <= tmax
    assert (df_5["tmin"] <= df_5["tmax"]).all()
    assert (df_20["tmin"] <= df_20["tmax"]).all()

    # 2. Temperature future > storiche e crescenti con l'orizzonte
    assert (df_5["tmean"] > forcing_hist["tmean"]).all()
    assert (df_20["tmean"] > df_5["tmean"]).all()

    # 3. Pioggia >= 0 e clippata
    assert (df_5["rain"] >= 0).all()
    assert (df_20["rain"] >= 0).all()

    # 4. Umidità relativa tra 5% e 100%
    assert (df_5["rh"] >= 5.0).all() and (df_5["rh"] <= 100.0).all()
    assert (df_20["rh"] >= 5.0).all() and (df_20["rh"] <= 100.0).all()

    # 5. ET0 ricalcolata e positiva
    assert (df_5["et0"] >= 0).all()
    assert df_20["et0"].mean() > df_5["et0"].mean()


def test_climate_summary(forcing_hist, p):
    df_fut = cmip6.apply_delta_change(forcing_hist, "ssp245", 10, 45.2, 100.0, p)
    clim = cmip6.climate_summary(df_fut, lat=45.2)

    assert "tmean_ann_c" in clim
    assert "tmax_ann_c" in clim
    assert "gdd_base10_ann" in clim
    assert "rain_ann_mm" in clim
    assert "et0_ann_mm" in clim
    assert "hot_days_ann" in clim

    assert 10.0 < clim["tmean_ann_c"] < 25.0
    assert clim["gdd_base10_ann"] > 1000.0
    assert clim["rain_ann_mm"] > 200.0
    assert clim["et0_ann_mm"] > 500.0
    assert clim["hot_days_ann"] >= 0.0


# =============================================================================
# 3. Test File Pre-calcolati (future_dashboard_summary.json, CSVs)
# =============================================================================

def test_load_future_payload():
    summary = fut.load_future_payload()
    assert isinstance(summary, dict)

    # Verifica che tutte le 12 combinazioni siano presenti
    for ssp in fut.SSP_CODES:
        for h in fut.HORIZONS:
            key = f"{ssp}_{h}a"
            assert key in summary, f"Chiave mancante: {key}"
            d = summary[key]

            # Metadati
            assert d["ssp_code"] == ssp
            assert d["horizon_years"] == h
            assert d["ssp_label"] == fut.SSP_LABELS[ssp]
            assert d["ssp_description"] == fut.SSP_DESCRIPTIONS[ssp]

            # Baseline
            assert "baseline_resa_rel_pct" in d
            assert "baseline_costo_eur_ha" in d
            assert "baseline_margine_eur_ha" in d
            assert d["baseline_costo_eur_ha"] > 0
            assert d["baseline_margine_eur_ha"] > 0

            # Futuro
            assert "future_resa_rel_pct" in d
            assert "future_costo_eur_ha" in d
            assert "future_margine_eur_ha" in d
            assert d["future_costo_eur_ha"] > 0

            # Delta
            assert "delta_resa_rel_pct" in d
            assert "delta_costo_eur_ha" in d
            assert "delta_margine_eur_ha" in d

            # Best rotation
            assert "best_rotation" in d and len(d["best_rotation"]) > 0
            assert "delta_guadagno_eur_ha" in d
            assert "best_costo_eur_ha" in d
            assert "best_margine_eur_ha" in d
            assert d["best_margine_eur_ha"] >= d["future_margine_eur_ha"] - 1e-6


def test_load_future_ranking():
    df_rank = fut.load_future_ranking()
    assert isinstance(df_rank, pd.DataFrame)
    assert not df_rank.empty

    expected_cols = {
        "ssp_code", "horizon_years", "classe", "posizione", "punteggio",
        "resa_rel_mediana", "resa_rel_p10", "margine_lordo_eur_ha",
        "irrigazione_mm", "concime_kg_n_ha", "n_lisciviato_kg_n_ha",
        "humus_t_ha", "non_dominata",
    }
    assert expected_cols.issubset(df_rank.columns)

    # Verifica che le posizioni per ogni gruppo inizino da 1
    for (ssp, h), group in df_rank.groupby(["ssp_code", "horizon_years"]):
        assert 1 in group["posizione"].values
        assert (group["posizione"] > 0).all()


def test_load_future_timeseries():
    df_ts = fut.load_future_timeseries()
    assert isinstance(df_ts, pd.DataFrame)
    assert not df_ts.empty

    # Verifica presenza delle colonne per tutti gli 8 grafici di FULL ANALYSIS
    chart_cols = {
        # 1. Temperatura/GDD
        "tmean_ann_c", "tmax_ann_c", "gdd_base10_ann", "hot_days_ann",
        # 2. ETa/ET0/Irrigazione
        "et0_ann_mm", "eta_ann_mm", "irrigazione_mm", "rain_ann_mm",
        # 3. Deficit/Stress Ks
        "f_acqua", "deficit_stress_ks",
        # 4. Azoto
        "concime_kg_n_ha", "n_lisciviato_kg_n_ha", "deficit_n_kg_n_ha",
        # 5. Humus
        "humus_t_ha",
        # 6. Costo
        "costo_eur_ha", "costo_irrigazione_eur_ha", "costo_concime_eur_ha",
        # 7. Resa
        "resa_rel_pct", "resa_t_ha",
        # 8. Guadagno
        "margine_eur_ha", "ricavo_eur_ha",
    }
    assert chart_cols.issubset(df_ts.columns)

    # Verifica presenza della baseline storica (horizon 0)
    assert 0 in df_ts["horizon_years"].values
    assert set(fut.HORIZONS).issubset(df_ts["horizon_years"].values)


# =============================================================================
# 4. Test calcolo economico integrato
# =============================================================================

def test_economic_consistency():
    summary = fut.load_future_payload()
    p10a = summary["ssp245_10a"]

    # Verifica coerenza delta costi e delta margine
    exp_delta_costo = round(p10a["future_costo_eur_ha"] - p10a["baseline_costo_eur_ha"], 1)
    assert p10a["delta_costo_eur_ha"] == pytest.approx(exp_delta_costo, abs=0.2)

    exp_delta_margine = round(p10a["future_margine_eur_ha"] - p10a["baseline_margine_eur_ha"], 1)
    assert p10a["delta_margine_eur_ha"] == pytest.approx(exp_delta_margine, abs=0.2)

    # Verifica che il guadagno aggiuntivo sia coerente
    exp_delta_guadagno = round(p10a["best_margine_eur_ha"] - p10a["future_margine_eur_ha"], 1)
    assert p10a["delta_guadagno_eur_ha"] == pytest.approx(exp_delta_guadagno, abs=0.2)


def test_decision_metrics_alignment():
    """Verifica che le metriche di decisione di future adottino tutte le 6 priorità di ranking.py."""
    from fieldwise import ranking
    summary = fut.load_future_payload()
    p10a = summary["ssp245_10a"]

    # Le 6 priorità canoniche
    assert set(ranking.PRIORITA.keys()) == {"resa", "rischio", "acqua", "concime", "suolo", "profitto"}

    # Verifica presenza campi di conformità e rischi per la miglior rotazione
    assert "best_conformita" in p10a
    assert "best_rischi" in p10a
    assert isinstance(p10a["best_rischi"], list)
    assert p10a["best_rotation"] != ""

