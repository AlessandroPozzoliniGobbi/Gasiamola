"""Simulazione climatica futura con proiezioni CMIP6 (metodo Delta Change).

Espone:
  * ``get_future_simulation_payload``: un singolo (SSP, orizzonte) → payload piatto.
  * ``run_all_ssps_horizons``: pre-calcola tutti i 3 SSP x 4 orizzonti e salva
    i tre file di output in ``data/processed/<punto>/``.
  * ``load_future_payload``: legge ``future_dashboard_summary.json`` dalla cache
    (solleva ``CacheMiss`` se mancante).

Dipendenze interne richieste: ``cmip6.py`` in ``fieldwise.data.cmip6`` deve
esistere prima che questo modulo venga importato.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import config as _config
from . import economics as _eco
from . import ensemble as en
from . import params as _params
from . import ranking
from . import weather as _weather
from . import rotation as rt
from .data import cache as _cache
from .data import cmip6 as _cmip6

# ---------------------------------------------------------------------------
# Costanti pubbliche
# ---------------------------------------------------------------------------

SSP_LABELS: dict[str, str] = {
    "ssp126": "Sostenibile (SSP1-2.6)",
    "ssp245": "Tendenziale (SSP2-4.5)",
    "ssp585": "Estremo (SSP5-8.5)",
}

SSP_DESCRIPTIONS: dict[str, str] = {
    "ssp126": (
        "Transizione ecologica rapida e taglio delle emissioni, "
        "riscaldamento contenuto sotto +2°C."
    ),
    "ssp245": (
        "Politiche attuali lungo il trend storico recente, "
        "estati progressivamente più calde e asciutte."
    ),
    "ssp585": (
        "Alte emissioni da fonti fossili, massima frequenza di "
        "ondate di calore e siccità severa."
    ),
}

HORIZONS: tuple[int, ...] = (5, 10, 15, 20)
SSP_CODES: tuple[str, ...] = ("ssp126", "ssp245", "ssp585")

# File prodotti da run_all_ssps_horizons
FILE_SUMMARY = "future_dashboard_summary.json"
FILE_RANKING = "future_rotations_ranking.csv"
FILE_TIMESERIES = "future_full_analysis_timeseries.csv"

# Subset di rotazioni rappresentative per il pre-calcolo
# (include successioni tradizionali, monocolture e rotazioni con cover crop conformi)
_ROTAZIONI_PRECOMPUTE = [
    "mais > soia > frumento",
    "mais > mais > soia",
    "mais > mais > mais",
    "soia > frumento > mais",
    "frumento > mais > soia",
    "soia > soia > mais",
    "frumento > soia > mais",
    "mais > frumento > soia",
    "mais > soia > mais",
    "soia > mais > frumento",
    "frumento > frumento > mais",
    "frumento+cover > soia+cover > mais",
    "frumento > soia+cover > mais",
    "frumento+cover > mais+cover > soia",
    "frumento+cover > soia > mais",
    "frumento > mais+cover > soia",
    "mais > soia+cover > frumento",
    "mais > soia+cover > mais",
    "mais+cover > mais+cover > mais+cover",
    "frumento+cover > mais+cover > mais",
    "frumento > mais+cover > mais",
    "mais+cover > mais+cover > mais",
]


# ---------------------------------------------------------------------------
# Helper interni
# ---------------------------------------------------------------------------

def _elev_m(lat: float, lon: float) -> float:
    """Legge l'elevazione da power_site.json; ritorna 100.0 come fallback."""
    site = _cache.processed_dir(lat, lon, create=False) / "power_site.json"
    if site.exists():
        try:
            return float(json.loads(site.read_text(encoding="utf-8"))["elevation_m"])
        except Exception:
            pass
    return 100.0  # fallback


def _resa_t_ha(sin_row: pd.Series, rotation_label: str) -> float:
    """Resa in t/ha: media annua su ciclo 3 anni dalle colonne resa_t_ha_<coltura>."""
    try:
        rot = rt.Rotation.from_label(rotation_label)
        crops = rot.crops
        total = 0.0
        n_found = 0
        for crop in crops:
            col = f"resa_t_ha_{crop}"
            if col in sin_row.index and not pd.isna(sin_row[col]):
                total += float(sin_row[col])
                n_found += 1
        if n_found > 0:
            # La sintesi ha la resa mediana per coltura; dividiamo sul ciclo (3 anni)
            return total / 3.0
    except Exception:
        pass
    # Fallback: resa_rel_mediana * 10 t/ha
    if "resa_rel_mediana" in sin_row.index:
        return float(sin_row["resa_rel_mediana"]) * 10.0
    return float("nan")


def _get_sin_row(sin: pd.DataFrame, classe: str, scenario: str) -> pd.Series | None:
    """Prima riga della sintesi che corrisponde alla classe e allo scenario dati."""
    mask = (sin["classe"] == classe) & (sin["scenario"] == scenario)
    rows = sin[mask]
    if rows.empty:
        return None
    return rows.iloc[0]


def _margine_p10(p: dict, sin_row: pd.Series) -> float:
    """Margine caso-peggiore (p10 della resa relativa) scalando il margine mediano."""
    med = float(sin_row.get("resa_rel_mediana", 1.0)) or 1.0
    p10 = float(sin_row.get("resa_rel_p10", med))
    margine = float(sin_row.get("margine_lordo_eur_ha", 0.0))
    # costi fissi (concime + irrigazione) non dipendono dalla resa
    irr = float(sin_row.get("irrigazione_mm", 0.0))
    conc = float(sin_row.get("concime_kg_n", 0.0))
    costo_irr = _eco.costo_irrigazione_anno(p, irr)
    costo_conc = _eco.costo_concime_anno(p, conc)
    costi = costo_irr + costo_conc
    # margine = ricavo - costi  →  ricavo = margine + costi
    ricavo = margine + costi
    # scala il ricavo proporzionalmente alla resa
    ricavo_p10 = ricavo * (p10 / med) if med > 0 else 0.0
    return ricavo_p10 - costi


def _build_ctx_future(
    p: dict, lat: float, lon: float,
    forcing_fut: pd.DataFrame
) -> rt.RotationContext:
    """Costruisce un RotationContext usando il forcing futuro al posto di quello storico."""
    return rt.build_context(p=p, forcing=forcing_fut, lat=lat, lon=lon)


def _climate_summary_hist(forcing: pd.DataFrame) -> dict:
    """Statistiche climatiche dalla serie storica (stessa interfaccia di cmip6.climate_summary)."""
    return _cmip6.climate_summary(forcing, lat=0.0)


# ---------------------------------------------------------------------------
# Funzione principale
# ---------------------------------------------------------------------------

def get_future_simulation_payload(
    lat: float = _config.PILOT_LAT,
    lon: float = _config.PILOT_LON,
    horizon_years: int = 10,
    ssp_code: str = "ssp245",
    current_rotation: str = "mais > soia > frumento",
    irrigation_regime: str = "tetto_irriguo",
    weights: dict | None = None,
    solo_conformi: bool = False,
) -> dict:
    """Calcola il payload piatto per una combinazione (lat, lon, SSP, orizzonte).

    Parameters
    ----------
    lat, lon:
        Coordinate del punto (default: punto pilota Cremona).
    horizon_years:
        Orizzonte temporale (5, 10, 15 o 20). Default: 10.
    ssp_code:
        Codice SSP ("ssp126", "ssp245" o "ssp585"). Default: "ssp245".
    current_rotation:
        Etichetta della rotazione attuale (es. "mais > soia > frumento").
    irrigation_regime:
        Scenario irriguo ("solo_pioggia", "tetto_irriguo" o "irrigazione_libera").
    weights:
        Pesi per il ranking. Se None, usa tutte le 6 priorità con peso 1.0 (standard del motore).
    solo_conformi:
        Se True, filtra solo le rotazioni conformi ai disciplinari (es. SRA01 / BCAA 7). Default: False.

    Returns
    -------
    dict  –  payload piatto con chiavi documentate nel modulo.

    Raises
    ------
    CacheMiss
        Se il forcing storico non è in cache (safe per pytest.skip).
    """
    if ssp_code not in SSP_CODES:
        raise ValueError(f"ssp_code non valido: {ssp_code!r}")
    if horizon_years not in HORIZONS:
        raise ValueError(f"horizon_years non valido: {horizon_years}")

    if weights is None:
        weights = {k: 1.0 for k in ranking.PRIORITA}

    # 1. Parametri
    p = _params.load_params()

    # 2. Forcing storico (CacheMiss se manca → caller decide)
    forcing_hist = _weather.load_forcing(lat, lon)
    elev = _elev_m(lat, lon)

    # 3. Forcing futuro via Delta Change
    forcing_fut = _cmip6.apply_delta_change(
        forcing_hist, ssp_code, horizon_years, lat, elev, p
    )

    # 4. Contesti
    ctx_hist = rt.build_context(p=p, forcing=forcing_hist, lat=lat, lon=lon)
    ctx_fut = _build_ctx_future(p, lat, lon, forcing_fut)

    # 5. Ensemble futuro
    det_fut, sin_fut = en.run_ensemble(
        ctx=ctx_fut,
        rotazioni=None,          # tutte le 216
        scenari=(irrigation_regime,),
        rotazione_attuale=current_rotation,
    )

    # 6. Baseline storica
    det_base, sin_base = en.run_ensemble(
        ctx=ctx_hist,
        rotazioni=None,
        scenari=(irrigation_regime,),
        rotazione_attuale=current_rotation,
    )

    # 7. Ranking futuro con metriche standard del motore
    sc_fut = ranking.score(sin_fut, weights, irrigation_regime, solo_conformi=solo_conformi)
    conf_fut = ranking.confronta(sin_fut, weights, irrigation_regime, solo_conformi=solo_conformi)

    # Classe della rotazione attuale
    att_classe = en.classe_rotazione_attuale(current_rotation, p)

    # Riga baseline (rotazione attuale)
    row_base = _get_sin_row(sin_base, att_classe, irrigation_regime)
    # Riga futuro (rotazione attuale)
    row_fut = _get_sin_row(sin_fut, att_classe, irrigation_regime)

    def _float(row, col, default=float("nan")):
        if row is None:
            return default
        v = row.get(col, default) if hasattr(row, "get") else (
            row[col] if col in row.index else default)
        return float(v) if v == v else default  # NaN passthrough

    # --- Statistiche climatiche ---
    clim_hist = _climate_summary_hist(forcing_hist)
    clim_fut = _cmip6.climate_summary(forcing_fut, lat=lat)

    # --- Baseline ---
    base_resa_rel = _float(row_base, "resa_rel_mediana", 0.0)
    base_resa_t = _resa_t_ha(row_base, att_classe) if row_base is not None else float("nan")
    base_margine = _float(row_base, "margine_lordo_eur_ha", 0.0)
    base_irr = _float(row_base, "irrigazione_mm", 0.0)
    base_conc = _float(row_base, "concime_kg_n", 0.0)
    base_costo_irr = _eco.costo_irrigazione_anno(p, base_irr)
    base_costo_conc = _eco.costo_concime_anno(p, base_conc)
    base_costo = base_costo_irr + base_costo_conc
    base_humus = _float(row_base, "humus_t_ha", 0.0)
    base_nlisc = _float(row_base, "n_lisciviato_kg_n", 0.0)

    # --- Futuro (rotazione attuale) ---
    fut_resa_rel = _float(row_fut, "resa_rel_mediana", 0.0)
    fut_resa_p10 = _float(row_fut, "resa_rel_p10", fut_resa_rel)
    fut_resa_t = _resa_t_ha(row_fut, att_classe) if row_fut is not None else float("nan")
    fut_margine = _float(row_fut, "margine_lordo_eur_ha", 0.0)
    fut_margine_p10 = _margine_p10(p, row_fut) if row_fut is not None else float("nan")
    fut_irr = _float(row_fut, "irrigazione_mm", 0.0)
    fut_conc = _float(row_fut, "concime_kg_n", 0.0)
    fut_costo_irr = _eco.costo_irrigazione_anno(p, fut_irr)
    fut_costo_conc = _eco.costo_concime_anno(p, fut_conc)
    fut_costo = fut_costo_irr + fut_costo_conc
    fut_humus = _float(row_fut, "humus_t_ha", 0.0)
    fut_nlisc = _float(row_fut, "n_lisciviato_kg_n", 0.0)

    # --- Best rotation ---
    best_classe: str = ""
    best_resa_rel = float("nan")
    best_resa_t = float("nan")
    best_margine = float("nan")
    best_irr = float("nan")
    best_conc = float("nan")
    best_costo_irr = float("nan")
    best_costo_conc = float("nan")
    best_costo = float("nan")
    best_pos = -1
    best_non_dom = False
    best_conformita = "non_valutabile"
    best_rischi: list[str] = []

    if conf_fut.get("alternative"):
        alt = conf_fut["alternative"][0]
        best_classe = str(alt.get("classe", ""))
        best_pos = int(alt.get("posizione", -1))
        best_non_dom = bool(alt.get("non_dominata", False))
        best_rischi = list(alt.get("rischi", []))
        row_best = _get_sin_row(sin_fut, best_classe, irrigation_regime)
        if row_best is not None:
            best_conformita = str(row_best.get("conformita", "non_valutabile"))
            best_resa_rel = _float(row_best, "resa_rel_mediana", 0.0)
            best_resa_t = _resa_t_ha(row_best, best_classe)
            best_margine = _float(row_best, "margine_lordo_eur_ha", 0.0)
            best_irr = _float(row_best, "irrigazione_mm", 0.0)
            best_conc = _float(row_best, "concime_kg_n", 0.0)
            best_costo_irr = _eco.costo_irrigazione_anno(p, best_irr)
            best_costo_conc = _eco.costo_concime_anno(p, best_conc)
            best_costo = best_costo_irr + best_costo_conc
    elif not sc_fut.empty:
        # Fallback: prima riga del ranking
        first = sc_fut.iloc[0]
        best_classe = str(first.get("classe", ""))
        best_pos = int(first.get("posizione", 1))
        best_non_dom = bool(first.get("non_dominata", False)) if "non_dominata" in first.index else False
        row_best = _get_sin_row(sin_fut, best_classe, irrigation_regime)
        if row_best is not None:
            best_resa_rel = _float(row_best, "resa_rel_mediana", 0.0)
            best_resa_t = _resa_t_ha(row_best, best_classe)
            best_margine = _float(row_best, "margine_lordo_eur_ha", 0.0)
            best_irr = _float(row_best, "irrigazione_mm", 0.0)
            best_conc = _float(row_best, "concime_kg_n", 0.0)
            best_costo_irr = _eco.costo_irrigazione_anno(p, best_irr)
            best_costo_conc = _eco.costo_concime_anno(p, best_conc)
            best_costo = best_costo_irr + best_costo_conc

    now_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    return {
        # Metadati
        "lat": float(lat),
        "lon": float(lon),
        "horizon_years": int(horizon_years),
        "ssp_code": str(ssp_code),
        "ssp_label": SSP_LABELS.get(ssp_code, ssp_code),
        "ssp_description": SSP_DESCRIPTIONS.get(ssp_code, ""),
        "current_rotation": str(current_rotation),
        "irrigation_regime": str(irrigation_regime),
        "calcolato_il": now_utc,

        # Baseline storica
        "baseline_resa_rel_pct": round(base_resa_rel * 100, 2),
        "baseline_resa_t_ha": round(base_resa_t, 2) if math.isfinite(base_resa_t) else None,
        "baseline_margine_eur_ha": round(base_margine, 1),
        "baseline_costo_eur_ha": round(base_costo, 1),
        "baseline_costo_irrigazione_eur_ha": round(base_costo_irr, 1),
        "baseline_costo_concime_eur_ha": round(base_costo_conc, 1),
        "baseline_irrigazione_mm": round(base_irr, 1),
        "baseline_concime_kg_n_ha": round(base_conc, 1),
        "baseline_humus_t_ha": round(base_humus, 3),
        "baseline_n_lisciviato_kg_n_ha": round(base_nlisc, 2),
        "baseline_et0_ann_mm": round(clim_hist["et0_ann_mm"], 1),
        "baseline_tmean_ann_c": round(clim_hist["tmean_ann_c"], 2),
        "baseline_gdd_base10_ann": round(clim_hist["gdd_base10_ann"], 0),

        # Futuro – rotazione attuale
        "future_resa_rel_pct": round(fut_resa_rel * 100, 2),
        "future_resa_rel_p10_pct": round(fut_resa_p10 * 100, 2),
        "future_resa_t_ha": round(fut_resa_t, 2) if math.isfinite(fut_resa_t) else None,
        "future_margine_eur_ha": round(fut_margine, 1),
        "future_margine_p10_eur_ha": round(fut_margine_p10, 1) if math.isfinite(fut_margine_p10) else None,
        "future_costo_eur_ha": round(fut_costo, 1),
        "future_costo_irrigazione_eur_ha": round(fut_costo_irr, 1),
        "future_costo_concime_eur_ha": round(fut_costo_conc, 1),
        "future_irrigazione_mm": round(fut_irr, 1),
        "future_concime_kg_n_ha": round(fut_conc, 1),
        "future_humus_t_ha": round(fut_humus, 3),
        "future_n_lisciviato_kg_n_ha": round(fut_nlisc, 2),
        "future_et0_ann_mm": round(clim_fut["et0_ann_mm"], 1),
        "future_tmean_ann_c": round(clim_fut["tmean_ann_c"], 2),
        "future_gdd_base10_ann": round(clim_fut["gdd_base10_ann"], 0),
        "future_hot_days_ann": round(clim_fut["hot_days_ann"], 1),

        # Delta vs baseline
        "delta_resa_rel_pct": round((fut_resa_rel - base_resa_rel) * 100, 2),
        "delta_costo_eur_ha": round(fut_costo - base_costo, 1),
        "delta_margine_eur_ha": round(fut_margine - base_margine, 1),

        # Miglior rotazione possibile
        "best_rotation": best_classe,
        "best_resa_rel_pct": round(best_resa_rel * 100, 2) if math.isfinite(best_resa_rel) else None,
        "best_resa_t_ha": round(best_resa_t, 2) if math.isfinite(best_resa_t) else None,
        "best_margine_eur_ha": round(best_margine, 1) if math.isfinite(best_margine) else None,
        "best_costo_eur_ha": round(best_costo, 1) if math.isfinite(best_costo) else None,
        "best_costo_irrigazione_eur_ha": round(best_costo_irr, 1) if math.isfinite(best_costo_irr) else None,
        "best_costo_concime_eur_ha": round(best_costo_conc, 1) if math.isfinite(best_costo_conc) else None,
        "best_irrigazione_mm": round(best_irr, 1) if math.isfinite(best_irr) else None,
        "best_concime_kg_n_ha": round(best_conc, 1) if math.isfinite(best_conc) else None,
        "delta_guadagno_eur_ha": round(best_margine - fut_margine, 1) if math.isfinite(best_margine) else None,
        "delta_resa_best_pct": round((best_resa_rel - fut_resa_rel) * 100, 2) if math.isfinite(best_resa_rel) else None,
        "delta_costo_best_eur_ha": round(best_costo - fut_costo, 1) if (math.isfinite(best_costo) and math.isfinite(fut_costo)) else None,
        "best_posizione": best_pos,
        "best_non_dominata": best_non_dom,
        "best_conformita": best_conformita,
        "best_rischi": best_rischi,
    }


# ---------------------------------------------------------------------------
# Pre-calcolo: tutti gli SSP x orizzonti
# ---------------------------------------------------------------------------

def run_all_ssps_horizons(
    lat: float = _config.PILOT_LAT,
    lon: float = _config.PILOT_LON,
    current_rotation: str = "mais > soia > frumento",
    irrigation_regime: str = "tetto_irriguo",
    weights: dict | None = None,
    solo_conformi: bool = False,
) -> dict:
    """Pre-calcola tutti i 3 SSP × 4 orizzonti (12 combinazioni).

    Salva tre file in ``data/processed/<punto>/``:

    * ``future_dashboard_summary.json``  – {ssp_horizon → payload}
    * ``future_rotations_ranking.csv``   – classifica per ssp/orizzonte
    * ``future_full_analysis_timeseries.csv`` – serie temporali per grafici

    Returns
    -------
    dict  –  {(ssp_code, horizon_years): payload}
    """
    if weights is None:
        weights = {k: 1.0 for k in ranking.PRIORITA}

    p = _params.load_params()

    # Forcing storico (CacheMiss propagato)
    forcing_hist = _weather.load_forcing(lat, lon)
    elev = _elev_m(lat, lon)

    # Contesto storico (baseline)
    ctx_hist = rt.build_context(p=p, forcing=forcing_hist, lat=lat, lon=lon)
    att_classe = en.classe_rotazione_attuale(current_rotation, p)

    # Subset di rotazioni per il pre-calcolo (più rapido)
    rotazioni_subset = []
    for label in _ROTAZIONI_PRECOMPUTE:
        try:
            rotazioni_subset.append(rt.Rotation.from_label(label))
        except Exception:
            pass

    # Assicura che la rotazione attuale sia inclusa
    try:
        rot_att = rt.Rotation.from_label(current_rotation)
        labels_subset = {r.label for r in rotazioni_subset}
        if rot_att.label not in labels_subset:
            rotazioni_subset.append(rot_att)
    except Exception:
        pass

    # Baseline storica (una sola volta)
    _, sin_base = en.run_ensemble(
        ctx=ctx_hist,
        rotazioni=rotazioni_subset,
        scenari=(irrigation_regime,),
        rotazione_attuale=current_rotation,
    )

    results: dict[tuple, dict] = {}
    summary: dict[str, dict] = {}
    ranking_rows: list[dict] = []
    timeseries_rows: list[dict] = []

    # Statistiche climatiche baseline
    clim_hist = _cmip6.climate_summary(forcing_hist, lat=lat)

    # Rotazione best in ssp245 10 anni per serie temporali extra
    best_245_10: str = ""

    for ssp in SSP_CODES:
        for h in HORIZONS:
            forcing_fut = _cmip6.apply_delta_change(
                forcing_hist, ssp, h, lat, elev, p
            )
            ctx_fut = _build_ctx_future(p, lat, lon, forcing_fut)
            clim_fut = _cmip6.climate_summary(forcing_fut, lat=lat)

            _, sin_fut = en.run_ensemble(
                ctx=ctx_fut,
                rotazioni=rotazioni_subset,
                scenari=(irrigation_regime,),
                rotazione_attuale=current_rotation,
            )

            # Payload completo per questa combinazione
            payload = _payload_from_precomputed(
                p, lat, lon, h, ssp, current_rotation, irrigation_regime,
                weights, sin_fut, sin_base, clim_hist, clim_fut, att_classe,
                solo_conformi=solo_conformi,
            )
            results[(ssp, h)] = payload
            key = f"{ssp}_{h}a"
            summary[key] = payload

            # Ranking CSV
            try:
                sc = ranking.score(sin_fut, weights, irrigation_regime, solo_conformi=solo_conformi)
                pf = ranking.pareto_front(sin_fut, irrigation_regime, solo_conformi=solo_conformi)
                nd_map = dict(zip(pf["classe"], pf["non_dominata"])) if "classe" in pf.columns else {}
                for _, row in sc.iterrows():
                    ranking_rows.append({
                        "ssp_code": ssp,
                        "horizon_years": h,
                        "classe": row["classe"],
                        "posizione": int(row["posizione"]),
                        "punteggio": round(float(row["punteggio"]), 4),
                        "resa_rel_mediana": round(float(row.get("resa_rel_mediana", float("nan"))), 4),
                        "resa_rel_p10": round(float(row.get("resa_rel_p10", float("nan"))), 4),
                        "margine_lordo_eur_ha": round(float(row.get("margine_lordo_eur_ha", float("nan"))), 1),
                        "irrigazione_mm": round(float(row.get("irrigazione_mm", float("nan"))), 1),
                        "concime_kg_n_ha": round(float(row.get("concime_kg_n", float("nan"))), 1),
                        "n_lisciviato_kg_n_ha": round(float(row.get("n_lisciviato_kg_n", float("nan"))), 2),
                        "humus_t_ha": round(float(row.get("humus_t_ha", float("nan"))), 3),
                        "non_dominata": bool(nd_map.get(row["classe"], False)),
                    })
            except Exception:
                pass

            # Timeseries per rotazione attuale
            row_fut_att = _get_sin_row(sin_fut, att_classe, irrigation_regime)
            if row_fut_att is not None:
                timeseries_rows.append(_timeseries_row(
                    ssp, h, att_classe, clim_fut, row_fut_att, att_classe, p,
                ))

            # Timeseries per miglior rotazione trovata per questa combinazione
            best_curr = payload.get("best_rotation", "")
            if best_curr and best_curr != att_classe:
                row_fut_best = _get_sin_row(sin_fut, best_curr, irrigation_regime)
                if row_fut_best is not None:
                    timeseries_rows.append(_timeseries_row(
                        ssp, h, best_curr, clim_fut, row_fut_best, att_classe, p,
                    ))

    # Aggiunge baseline storica (orizzonte 0) per rotazione attuale
    row_base_att = _get_sin_row(sin_base, att_classe, irrigation_regime)
    if row_base_att is not None:
        for ssp in SSP_CODES:
            timeseries_rows.append(_timeseries_row(
                ssp, 0, att_classe, clim_hist, row_base_att, att_classe, p,
            ))

    # Aggiunge baseline per tutte le best rotations comparse
    all_best_rotations = {
        payload["best_rotation"]
        for payload in summary.values()
        if payload.get("best_rotation") and payload.get("best_rotation") != att_classe
    }
    for b_rot in all_best_rotations:
        row_b = _get_sin_row(sin_base, b_rot, irrigation_regime)
        if row_b is not None:
            for ssp in SSP_CODES:
                timeseries_rows.append(_timeseries_row(
                    ssp, 0, b_rot, clim_hist, row_b, att_classe, p,
                ))

    # Deduplica le righe della timeseries
    seen_ts = set()
    dedup_timeseries = []
    for r in timeseries_rows:
        k = (r["ssp_code"], r["horizon_years"], r["rotation"])
        if k not in seen_ts:
            seen_ts.add(k)
            dedup_timeseries.append(r)
    timeseries_rows = dedup_timeseries

    # Salva i 3 file
    out_dir = _cache.processed_dir(lat, lon)

    # 1. Summary JSON
    (out_dir / FILE_SUMMARY).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, default=_json_default),
        encoding="utf-8",
    )

    # 2. Ranking CSV
    if ranking_rows:
        df_rank = pd.DataFrame(ranking_rows)
        df_rank.to_csv(out_dir / FILE_RANKING, index=False)

    # 3. Timeseries CSV
    if timeseries_rows:
        df_ts = pd.DataFrame(timeseries_rows)
        df_ts.to_csv(out_dir / FILE_TIMESERIES, index=False)

    return results


def _json_default(obj: Any) -> Any:
    """Serializza tipi non-standard per json.dumps."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if hasattr(obj, "item"):
        return obj.item()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _timeseries_row(
    ssp: str,
    h: int,
    rotation: str,
    clim: dict,
    sin_row: pd.Series,
    att_classe: str,
    p: dict,
) -> dict:
    """Costruisce una riga della timeseries CSV per i grafici FULL ANALYSIS."""
    def fv(col, default=float("nan")):
        v = sin_row.get(col, default) if hasattr(sin_row, "get") else (
            sin_row[col] if col in sin_row.index else default)
        try:
            val = float(v)
            return default if math.isnan(val) else val
        except Exception:
            return default

    resa_rel = fv("resa_rel_mediana", 0.0)
    irr = fv("irrigazione_mm", 0.0)
    conc = fv("concime_kg_n", 0.0)
    costo_irr = _eco.costo_irrigazione_anno(p, irr)
    costo_conc = _eco.costo_concime_anno(p, conc)
    costo_tot = costo_irr + costo_conc
    margine = fv("margine_lordo_eur_ha", 0.0)
    rain = clim.get("rain_ann_mm", 0.0)
    runoff = fv("ruscellamento_mm", 0.0)
    dp = fv("percolazione_mm", 0.0)
    eta_est = max(0.0, rain + irr - runoff - dp)
    f_acqua = fv("f_acqua", 1.0)
    deficit_stress = max(0.0, 1.0 - f_acqua)

    return {
        "ssp_code": ssp,
        "horizon_years": int(h),
        "rotation": rotation,
        "is_current": bool(rotation == att_classe),
        "tmean_ann_c": round(clim["tmean_ann_c"], 2),
        "tmax_ann_c": round(clim.get("tmax_ann_c", clim["tmean_ann_c"] + 5.0), 2),
        "gdd_base10_ann": round(clim["gdd_base10_ann"], 0),
        "hot_days_ann": round(clim.get("hot_days_ann", 0.0), 1),
        "et0_ann_mm": round(clim["et0_ann_mm"], 1),
        "eta_ann_mm": round(eta_est, 1),
        "rain_ann_mm": round(rain, 1),
        "irrigazione_mm": round(irr, 1),
        "f_acqua": round(f_acqua, 3),
        "deficit_stress_ks": round(deficit_stress, 3),
        "concime_kg_n_ha": round(conc, 1),
        "n_lisciviato_kg_n_ha": round(fv("n_lisciviato_kg_n", 0.0), 2),
        "deficit_n_kg_n_ha": round(fv("deficit_n_kg_n", 0.0), 2),
        "humus_t_ha": round(fv("humus_t_ha", 0.0), 3),
        "costo_irrigazione_eur_ha": round(costo_irr, 1),
        "costo_concime_eur_ha": round(costo_conc, 1),
        "costo_eur_ha": round(costo_tot, 1),
        "margine_eur_ha": round(margine, 1),
        "ricavo_eur_ha": round(margine + costo_tot, 1),
        "resa_rel_pct": round(resa_rel * 100, 2),
        "resa_t_ha": round(resa_rel * 10.0, 2),
    }


def _payload_from_precomputed(
    p: dict,
    lat: float,
    lon: float,
    horizon_years: int,
    ssp_code: str,
    current_rotation: str,
    irrigation_regime: str,
    weights: dict,
    sin_fut: pd.DataFrame,
    sin_base: pd.DataFrame,
    clim_hist: dict,
    clim_fut: dict,
    att_classe: str,
    solo_conformi: bool = False,
) -> dict:
    """Costruisce il payload da sintesi già calcolate (evita ricalcoli nel pre-computo)."""
    def _float(row, col, default=float("nan")):
        if row is None:
            return default
        v = row.get(col, default) if hasattr(row, "get") else (
            row[col] if col in row.index else default)
        try:
            f = float(v)
            return default if math.isnan(f) else f
        except Exception:
            return default

    row_fut = _get_sin_row(sin_fut, att_classe, irrigation_regime)
    row_base = _get_sin_row(sin_base, att_classe, irrigation_regime)

    base_resa_rel = _float(row_base, "resa_rel_mediana", 0.0)
    base_resa_t = _resa_t_ha(row_base, att_classe) if row_base is not None else float("nan")
    base_margine = _float(row_base, "margine_lordo_eur_ha", 0.0)
    base_irr = _float(row_base, "irrigazione_mm", 0.0)
    base_conc = _float(row_base, "concime_kg_n", 0.0)
    base_costo_irr = _eco.costo_irrigazione_anno(p, base_irr)
    base_costo_conc = _eco.costo_concime_anno(p, base_conc)
    base_costo = base_costo_irr + base_costo_conc
    base_humus = _float(row_base, "humus_t_ha", 0.0)
    base_nlisc = _float(row_base, "n_lisciviato_kg_n", 0.0)

    fut_resa_rel = _float(row_fut, "resa_rel_mediana", 0.0)
    fut_resa_p10 = _float(row_fut, "resa_rel_p10", fut_resa_rel)
    fut_resa_t = _resa_t_ha(row_fut, att_classe) if row_fut is not None else float("nan")
    fut_margine = _float(row_fut, "margine_lordo_eur_ha", 0.0)
    fut_margine_p10 = _margine_p10(p, row_fut) if row_fut is not None else float("nan")
    fut_irr = _float(row_fut, "irrigazione_mm", 0.0)
    fut_conc = _float(row_fut, "concime_kg_n", 0.0)
    fut_costo_irr = _eco.costo_irrigazione_anno(p, fut_irr)
    fut_costo_conc = _eco.costo_concime_anno(p, fut_conc)
    fut_costo = fut_costo_irr + fut_costo_conc
    fut_humus = _float(row_fut, "humus_t_ha", 0.0)
    fut_nlisc = _float(row_fut, "n_lisciviato_kg_n", 0.0)

    # Best rotation
    best_classe = ""
    best_resa_rel = float("nan")
    best_resa_t = float("nan")
    best_margine = float("nan")
    best_irr = float("nan")
    best_conc = float("nan")
    best_costo_irr = float("nan")
    best_costo_conc = float("nan")
    best_costo = float("nan")
    best_pos = -1
    best_non_dom = False
    best_conformita = "non_valutabile"
    best_rischi: list[str] = []

    try:
        conf = ranking.confronta(sin_fut, weights, irrigation_regime, solo_conformi=solo_conformi)
        if conf.get("alternative"):
            alt = conf["alternative"][0]
            best_classe = str(alt.get("classe", ""))
            best_pos = int(alt.get("posizione", -1))
            best_non_dom = bool(alt.get("non_dominata", False))
            best_rischi = list(alt.get("rischi", []))
            row_best = _get_sin_row(sin_fut, best_classe, irrigation_regime)
            if row_best is not None:
                best_conformita = str(row_best.get("conformita", "non_valutabile"))
                best_resa_rel = _float(row_best, "resa_rel_mediana", 0.0)
                best_resa_t = _resa_t_ha(row_best, best_classe)
                best_margine = _float(row_best, "margine_lordo_eur_ha", 0.0)
                best_irr = _float(row_best, "irrigazione_mm", 0.0)
                best_conc = _float(row_best, "concime_kg_n", 0.0)
                best_costo_irr = _eco.costo_irrigazione_anno(p, best_irr)
                best_costo_conc = _eco.costo_concime_anno(p, best_conc)
                best_costo = best_costo_irr + best_costo_conc
    except Exception:
        pass

    now_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def _r(v, nd=2):
        if v is None or (isinstance(v, float) and not math.isfinite(v)):
            return None
        return round(float(v), nd)

    return {
        "lat": float(lat),
        "lon": float(lon),
        "horizon_years": int(horizon_years),
        "ssp_code": str(ssp_code),
        "ssp_label": SSP_LABELS.get(ssp_code, ssp_code),
        "ssp_description": SSP_DESCRIPTIONS.get(ssp_code, ""),
        "current_rotation": str(current_rotation),
        "irrigation_regime": str(irrigation_regime),
        "calcolato_il": now_utc,
        # Baseline
        "baseline_resa_rel_pct": _r(base_resa_rel * 100, 2),
        "baseline_resa_t_ha": _r(base_resa_t, 2),
        "baseline_margine_eur_ha": _r(base_margine, 1),
        "baseline_costo_eur_ha": _r(base_costo, 1),
        "baseline_costo_irrigazione_eur_ha": _r(base_costo_irr, 1),
        "baseline_costo_concime_eur_ha": _r(base_costo_conc, 1),
        "baseline_irrigazione_mm": _r(base_irr, 1),
        "baseline_concime_kg_n_ha": _r(base_conc, 1),
        "baseline_humus_t_ha": _r(base_humus, 3),
        "baseline_n_lisciviato_kg_n_ha": _r(base_nlisc, 2),
        "baseline_et0_ann_mm": _r(clim_hist["et0_ann_mm"], 1),
        "baseline_tmean_ann_c": _r(clim_hist["tmean_ann_c"], 2),
        "baseline_gdd_base10_ann": _r(clim_hist["gdd_base10_ann"], 0),
        # Futuro
        "future_resa_rel_pct": _r(fut_resa_rel * 100, 2),
        "future_resa_rel_p10_pct": _r(fut_resa_p10 * 100, 2),
        "future_resa_t_ha": _r(fut_resa_t, 2),
        "future_margine_eur_ha": _r(fut_margine, 1),
        "future_margine_p10_eur_ha": _r(fut_margine_p10, 1),
        "future_costo_eur_ha": _r(fut_costo, 1),
        "future_costo_irrigazione_eur_ha": _r(fut_costo_irr, 1),
        "future_costo_concime_eur_ha": _r(fut_costo_conc, 1),
        "future_irrigazione_mm": _r(fut_irr, 1),
        "future_concime_kg_n_ha": _r(fut_conc, 1),
        "future_humus_t_ha": _r(fut_humus, 3),
        "future_n_lisciviato_kg_n_ha": _r(fut_nlisc, 2),
        "future_et0_ann_mm": _r(clim_fut["et0_ann_mm"], 1),
        "future_tmean_ann_c": _r(clim_fut["tmean_ann_c"], 2),
        "future_gdd_base10_ann": _r(clim_fut["gdd_base10_ann"], 0),
        "future_hot_days_ann": _r(clim_fut["hot_days_ann"], 1),
        # Delta
        "delta_resa_rel_pct": _r((fut_resa_rel - base_resa_rel) * 100, 2),
        "delta_costo_eur_ha": _r(fut_costo - base_costo, 1),
        "delta_margine_eur_ha": _r(fut_margine - base_margine, 1),
        # Best rotation
        "best_rotation": best_classe,
        "best_resa_rel_pct": _r(best_resa_rel * 100, 2),
        "best_resa_t_ha": _r(best_resa_t, 2),
        "best_margine_eur_ha": _r(best_margine, 1),
        "best_costo_eur_ha": _r(best_costo, 1),
        "best_costo_irrigazione_eur_ha": _r(best_costo_irr, 1),
        "best_costo_concime_eur_ha": _r(best_costo_conc, 1),
        "best_irrigazione_mm": _r(best_irr, 1),
        "best_concime_kg_n_ha": _r(best_conc, 1),
        "delta_guadagno_eur_ha": _r(best_margine - fut_margine, 1) if math.isfinite(best_margine) else None,
        "delta_resa_best_pct": _r((best_resa_rel - fut_resa_rel) * 100, 2) if math.isfinite(best_resa_rel) else None,
        "delta_costo_best_eur_ha": _r(best_costo - fut_costo, 1) if (math.isfinite(best_costo) and math.isfinite(fut_costo)) else None,
        "best_posizione": best_pos,
        "best_non_dominata": best_non_dom,
        "best_conformita": best_conformita,
        "best_rischi": best_rischi,
    }


# ---------------------------------------------------------------------------
# Lettura dalla cache (offline-safe)
# ---------------------------------------------------------------------------

def load_future_payload(
    lat: float = _config.PILOT_LAT,
    lon: float = _config.PILOT_LON,
) -> dict:
    """Legge ``future_dashboard_summary.json`` dalla cache.

    Raises
    ------
    CacheMiss
        Se il file non esiste nel processed_dir del punto.
    """
    path = _cache.processed_dir(lat, lon, create=False) / FILE_SUMMARY
    if not path.exists():
        raise _cache.CacheMiss(
            f"future_dashboard_summary.json non trovato per ({lat}, {lon}). "
            f"Eseguire run_all_ssps_horizons() per generarlo."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_future_ranking(
    lat: float = _config.PILOT_LAT,
    lon: float = _config.PILOT_LON,
) -> pd.DataFrame:
    """Legge ``future_rotations_ranking.csv`` dalla cache.

    Raises
    ------
    CacheMiss
        Se il file non esiste nel processed_dir del punto.
    """
    path = _cache.processed_dir(lat, lon, create=False) / FILE_RANKING
    if not path.exists():
        raise _cache.CacheMiss(
            f"future_rotations_ranking.csv non trovato per ({lat}, {lon}). "
            f"Eseguire run_all_ssps_horizons() per generarlo."
        )
    return pd.read_csv(path)


def load_future_timeseries(
    lat: float = _config.PILOT_LAT,
    lon: float = _config.PILOT_LON,
) -> pd.DataFrame:
    """Legge ``future_full_analysis_timeseries.csv`` dalla cache.

    Raises
    ------
    CacheMiss
        Se il file non esiste nel processed_dir del punto.
    """
    path = _cache.processed_dir(lat, lon, create=False) / FILE_TIMESERIES
    if not path.exists():
        raise _cache.CacheMiss(
            f"future_full_analysis_timeseries.csv non trovato per ({lat}, {lon}). "
            f"Eseguire run_all_ssps_horizons() per generarlo."
        )
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# __all__
# ---------------------------------------------------------------------------

__all__ = [
    "get_future_simulation_payload",
    "run_all_ssps_horizons",
    "load_future_payload",
    "load_future_ranking",
    "load_future_timeseries",
    "SSP_LABELS",
    "SSP_DESCRIPTIONS",
    "HORIZONS",
    "SSP_CODES",
    "FILE_SUMMARY",
    "FILE_RANKING",
    "FILE_TIMESERIES",
]
