"""Metodo Delta Change su serie storica NASA POWER per proiezioni climatiche CMIP6.

Applica delta mensili (da params/cmip6.yaml) alla serie storica giornaliera
validata (power_daily.csv) per generare una serie futura rappresentativa
dell'orizzonte temporale richiesto. Nessuna richiesta di rete.

Delta Change mensile (lineare nel tempo da anno_base a anno_base+20):
  tmax_fut[d] = tmax_stor[d] + delta_t_c[mese] * h/20
  tmin_fut[d] = tmin_stor[d] + delta_t_c[mese] * h/20
  tmean_fut[d] = tmean_stor[d] + delta_t_c[mese] * h/20
  rain_fut[d]  = max(0, rain_stor[d] * alpha_rain[mese]^(h/20))   [esponente per coerenza fisica]
  srad_fut[d]  = srad_stor[d] * alpha_srad[mese]^(h/20)
  rh_fut[d]    = clip(rh_stor[d] + delta_rh[mese] * h/20, 5, 100)
  wind invariato

ET0 viene ricalcolata da et0.et0_from_power dopo il delta.

Vincoli fisici:
  tmin_fut <= tmax_fut  (se delta fosse disomogeneo per errore, usa max(tmin_fut, tmax_fut-0.1))
  rain >= 0
  rh in [5, 100]
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .. import params as _params
from .. import et0 as _et0

__all__ = [
    "SSP_CODES",
    "HORIZONS",
    "apply_delta_change",
    "climate_summary",
]

SSP_CODES = ("ssp126", "ssp245", "ssp585")
HORIZONS = (5, 10, 15, 20)

# ---------------------------------------------------------------------------
# helper interni
# ---------------------------------------------------------------------------

def _get_monthly_array(p: dict, path_prefix: str) -> list[float]:
    """Restituisce la lista di 12 valori mensili per il path dato."""
    return [_params.get(p, f"{path_prefix}[{i}]") for i in range(12)]


def _build_month_index(dates: pd.Series) -> np.ndarray:
    """Vettore 0-based (0=gennaio … 11=dicembre) per ogni giorno della serie."""
    return pd.to_datetime(dates).dt.month.to_numpy() - 1  # 0-based


# ---------------------------------------------------------------------------
# funzione principale
# ---------------------------------------------------------------------------

def apply_delta_change(
    forcing: pd.DataFrame,
    ssp_code: str,
    horizon_years: int,
    lat: float,
    elev_m: float,
    p: dict | None = None,
) -> pd.DataFrame:
    """Applica il metodo Delta Change CMIP6 alla serie storica giornaliera.

    Parameters
    ----------
    forcing:
        DataFrame con colonne ``date, tmax, tmin, tmean, rain, srad, rh, wind``
        (output di weather.load_forcing / power_daily.csv).
    ssp_code:
        Uno dei valori in ``SSP_CODES`` ("ssp126", "ssp245", "ssp585").
    horizon_years:
        Orizzonte temporale in anni; uno dei valori in ``HORIZONS`` (5, 10, 15, 20).
    lat:
        Latitudine del punto in gradi decimali (N positivo).
    elev_m:
        Elevazione del punto in metri s.l.m.
    p:
        Albero parametri da ``params.load_params()``; se None viene caricato
        automaticamente.

    Returns
    -------
    pd.DataFrame
        Stesse colonne di forcing (date, tmax, tmin, tmean, rain, srad, rh, wind)
        più ``et0`` (mm/giorno, Penman-Monteith), ``rain_source``,
        ``rain_trusted``, ``temp_source``, ``temp_trusted``.
    """
    if ssp_code not in SSP_CODES:
        raise ValueError(f"ssp_code non valido: {ssp_code!r}. Usa uno di {SSP_CODES}.")
    if horizon_years not in HORIZONS:
        raise ValueError(f"horizon_years non valido: {horizon_years}. Usa uno di {HORIZONS}.")

    if p is None:
        p = _params.load_params()

    h = horizon_years
    prefix = f"cmip6.delta_{ssp_code}"

    # Recupera i delta mensili a +20 anni (liste di 12 valori, 0-based)
    delta_t_20   = np.array(_get_monthly_array(p, f"{prefix}.delta_t_c"))   # °C
    alpha_rain_20 = np.array(_get_monthly_array(p, f"{prefix}.alpha_rain"))  # moltiplicatore
    alpha_srad_20 = np.array(_get_monthly_array(p, f"{prefix}.alpha_srad"))  # moltiplicatore
    delta_rh_20   = np.array(_get_monthly_array(p, f"{prefix}.delta_rh"))    # pp %

    # Indice del mese (0-based) per ogni riga
    mi = _build_month_index(forcing["date"])  # shape (N,)

    # Fattore di scala lineare nel tempo
    scale = h / 20.0

    # --- temperatura (additiva, scalata linearmente) ---
    dt_vec = delta_t_20[mi] * scale

    tmax_fut  = forcing["tmax"].to_numpy(float)  + dt_vec
    tmin_fut  = forcing["tmin"].to_numpy(float)  + dt_vec
    tmean_fut = forcing["tmean"].to_numpy(float) + dt_vec

    # Vincolo fisico: tmin <= tmax
    too_warm = tmin_fut > tmax_fut
    tmin_fut[too_warm] = tmax_fut[too_warm] - 0.1

    # --- precipitazione (moltiplicativa con esponente per coerenza fisica) ---
    alpha_rain_vec = alpha_rain_20[mi] ** scale
    rain_fut = np.maximum(0.0, forcing["rain"].to_numpy(float) * alpha_rain_vec)

    # --- radiazione solare (moltiplicativa con esponente) ---
    alpha_srad_vec = alpha_srad_20[mi] ** scale
    srad_fut = forcing["srad"].to_numpy(float) * alpha_srad_vec

    # --- umidità relativa (additiva, scalata linearmente, clippata) ---
    drh_vec = delta_rh_20[mi] * scale
    rh_fut = np.clip(forcing["rh"].to_numpy(float) + drh_vec, 5.0, 100.0)

    # --- vento: invariato ---
    wind_fut = forcing["wind"].to_numpy(float).copy()

    # Costruisce il DataFrame futuro (stesse date, stesso numero di righe)
    df_fut = pd.DataFrame({
        "date":  forcing["date"].to_numpy(),
        "tmax":  tmax_fut,
        "tmin":  tmin_fut,
        "tmean": tmean_fut,
        "rain":  rain_fut,
        "srad":  srad_fut,
        "rh":    rh_fut,
        "wind":  wind_fut,
    })

    # Ricalcola ET0 con la serie futura
    et0_df = _et0.et0_from_power(df_fut, lat, elev_m)
    df_fut["et0"] = et0_df["et0_pm"].to_numpy()

    # Metadati di provenienza
    df_fut["rain_source"]  = "cmip6_delta"
    df_fut["rain_trusted"] = True
    df_fut["temp_source"]  = "cmip6_delta"
    df_fut["temp_trusted"] = True

    return df_fut


# ---------------------------------------------------------------------------
# statistiche climatiche per FULL ANALYSIS
# ---------------------------------------------------------------------------

def climate_summary(forcing_fut: pd.DataFrame, lat: float) -> dict:
    """Statistiche climatiche annue medie della serie futura per i grafici FULL ANALYSIS.

    Parameters
    ----------
    forcing_fut:
        DataFrame prodotto da ``apply_delta_change`` (con colonna ``et0``).
    lat:
        Latitudine del punto (non usata nei calcoli correnti, presente per
        coerenza con l'interfaccia futura).

    Returns
    -------
    dict con chiavi:
        ``tmean_ann_c``    – temperatura media annua (°C)
        ``tmax_ann_c``     – temperatura massima media annua (°C)
        ``gdd_base10_ann`` – GDD base 10°C annui medi (°C·giorno)
        ``rain_ann_mm``    – precipitazione totale annua media (mm)
        ``et0_ann_mm``     – ET0 totale annua media (mm)
        ``hot_days_ann``   – giorni annui medi con tmax > 35°C
    """
    df = forcing_fut.copy()
    df["_year"] = pd.to_datetime(df["date"]).dt.year

    # GDD base 10: max(0, tmean - 10)
    df["_gdd"] = np.maximum(0.0, df["tmean"].to_numpy(float) - 10.0)

    # Giornate calde: tmax > 35°C
    df["_hot"] = (df["tmax"].to_numpy(float) > 35.0).astype(float)

    # Statistiche per anno solare
    agg = df.groupby("_year").agg(
        tmean_ann   =("tmean",  "mean"),
        tmax_ann    =("tmax",   "mean"),
        gdd_ann     =("_gdd",   "sum"),
        rain_ann    =("rain",   "sum"),
        et0_ann     =("et0",    "sum"),
        hot_days_ann=("_hot",   "sum"),
    )

    return {
        "tmean_ann_c":    float(agg["tmean_ann"].mean()),
        "tmax_ann_c":     float(agg["tmax_ann"].mean()),
        "gdd_base10_ann": float(agg["gdd_ann"].mean()),
        "rain_ann_mm":    float(agg["rain_ann"].mean()),
        "et0_ann_mm":     float(agg["et0_ann"].mean()),
        "hot_days_ann":   float(agg["hot_days_ann"].mean()),
    }
