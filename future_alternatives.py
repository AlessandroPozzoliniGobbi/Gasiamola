"""Scenario-conditioned future rotation alternatives for the FIELDWISE HTTP adapter.

This adapter lives outside src/fieldwise deliberately: adding a future report
feature must NOT invalidate existing location-conditioned agronomic ensemble
caches or require repeating slow SoilGrids retrieval.
"""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from fieldwise import config, ensemble, future, params, ranking, rotation, weather
from fieldwise.data import cache, cmip6


def _parameters_for_model_point(lat: float, lon: float) -> dict:
    """Use the exact local soil overrides when simulating an already-prepared field.

    Only the Cremona pilot can use the global pilot parameters. The local
    adapter rebuilds the same parameters entirely from cached SoilGrids data;
    it does not fetch any new data over the network.
    """
    if cache.point_key(lat, lon) == cache.point_key(config.PILOT_LAT, config.PILOT_LON):
        return params.load_params()
    from local_analysis import build_local_parameters
    return build_local_parameters(lat, lon)[0]


def _representative_rotations() -> list[rotation.Rotation]:
    """The documented precomputation subset, not the complete 216-option search."""
    rotations: dict[str, rotation.Rotation] = {}
    for label in future._ROTAZIONI_PRECOMPUTE:
        obj = rotation.Rotation.from_label(label)
        rotations[obj.canonical().label] = obj
    return list(rotations.values())


@lru_cache(maxsize=12)
def _future_subset_ensemble(
    lat: float, lon: float, ssp_code: str, horizon_years: int,
    irrigation_regime: str, model_revision: str,
) -> tuple[pd.DataFrame, dict]:
    """Simulate the actual selected water regime at the actual model point.

    model_revision is the historical ensemble metadata fingerprint supplied by
    the caller. A refreshed field cache cannot silently reuse old projections.
    """
    p = _parameters_for_model_point(lat, lon)
    historical_weather = weather.load_forcing(lat, lon)
    future_weather = cmip6.apply_delta_change(
        historical_weather, ssp_code, horizon_years, lat, future._elev_m(lat, lon), p
    )
    future_context = future._build_ctx_future(p, lat, lon, future_weather)
    _, future_summary = ensemble.run_ensemble(
        ctx=future_context,
        rotazioni=_representative_rotations(),
        scenari=(irrigation_regime,),
        rotazione_attuale="mais > soia > frumento",
    )
    return future_summary, cmip6.climate_summary(future_weather, lat=lat)


def get_future_comparison_payload(
    *, lat: float, lon: float, horizon_years: int, ssp_code: str,
    current_rotation: str, irrigation_regime: str, weights: dict,
    historical_summary: pd.DataFrame, model_revision: str = "",
) -> dict:
    """Compute *real* future options for one requested SSP, location and water regime.

    Previous pilot archives cover capped irrigation only and a fixed current
    rotation. Using them for other configurations would misstate the results.
    This computation runs only representative classes (same documented subset
    as the archived ranking), never fabricates future values from historical
    ensemble metrics, and does not write to the archive on disk.
    """
    if ssp_code not in future.SSP_CODES or horizon_years not in future.HORIZONS:
        raise ValueError("Unsupported future climate scenario or horizon")
    p = _parameters_for_model_point(lat, lon)
    future_summary, future_climate = _future_subset_ensemble(
        lat, lon, ssp_code, horizon_years, irrigation_regime, model_revision
    )
    actual_class = ensemble.classe_rotazione_attuale(current_rotation, p)
    if actual_class not in set(future_summary["classe"]):
        # Include a farmer's uncommon crop sequence without recalculating the
        # entire representative comparison set.
        historical_forcing = weather.load_forcing(lat, lon)
        future_weather = cmip6.apply_delta_change(
            historical_forcing, ssp_code, horizon_years, lat, future._elev_m(lat, lon), p
        )
        context = future._build_ctx_future(p, lat, lon, future_weather)
        _, current_summary = ensemble.run_ensemble(
            ctx=context,
            rotazioni=(rotation.Rotation.from_label(current_rotation),),
            scenari=(irrigation_regime,),
            rotazione_attuale=current_rotation,
        )
        future_summary = pd.concat((future_summary, current_summary), ignore_index=True)

    if actual_class not in set(historical_summary["classe"]):
        raise ValueError("The current rotation is absent from historical reference data")
    historical_weather = weather.load_forcing(lat, lon)
    historical_climate = cmip6.climate_summary(historical_weather, lat=lat)
    payload = future._payload_from_precomputed(
        p, lat, lon, horizon_years, ssp_code, current_rotation,
        irrigation_regime, weights, future_summary, historical_summary,
        historical_climate, future_climate, actual_class,
    )
    ranked = ranking.score(future_summary, weights, irrigation_regime, solo_conformi=False)
    frontier = ranking.pareto_front(future_summary, irrigation_regime, solo_conformi=False)
    non_dominated = dict(zip(frontier["classe"], frontier["non_dominata"])) if not frontier.empty else {}
    payload["candidateRotations"] = [
        {
            "classe": str(row["classe"]),
            "posizione": int(row["posizione"]),
            "resa_rel_mediana": float(row["resa_rel_mediana"]),
            "resa_rel_p10": float(row["resa_rel_p10"]),
            "margine_lordo_eur_ha": float(row["margine_lordo_eur_ha"]),
            "irrigazione_mm": float(row["irrigazione_mm"]),
            "concime_kg_n_ha": float(row["concime_kg_n"]),
            "n_lisciviato_kg_n_ha": float(row["n_lisciviato_kg_n"]),
            "humus_t_ha": float(row["humus_t_ha"]),
            "non_dominata": bool(non_dominated.get(row["classe"], False)),
        }
        for _, row in ranked.iterrows()
    ]
    payload["candidateRankingSource"] = "on_demand"
    payload["futureComparisonScope"] = (
        "Representatives from the model's precomputation rotation subset; "
        "simulated for the selected location, irrigation regime, SSP and horizon. "
        "This is not an exhaustive optimization of all crop sequences."
    )
    return payload

