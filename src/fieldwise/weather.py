"""Tabella meteo giornaliera per il motore (forzante), letta SOLO dalla cache.

Traduce in codice le decisioni 1 e 2 di ``data/CHECKS.md`` (sezione Decisioni):

* D1 pioggia: di default NASA POWER (PRECTOTCORR) su tutti i giorni, ma gli anni dopo
  ``POWER_RAIN_LAST_RELIABLE_YEAR`` sono marcati come non affidabili (``rain_trusted``
  False) e non entrano nell'ensemble delle annate (``available_years``). Nessuna
  correzione di scala.
* D2 temperature: NASA POWER (T2M_MAX, T2M_MIN, T2M) per fenologia, ET0 e caldo;
  ET0 Penman-Monteith FAO-56 (``fieldwise.et0.et0_from_power``) alla quota della cella
  POWER (``power_site.json``), salvo ``elev_m`` esplicito.

Fonti selezionabili per l'analisi di sensibilita':

``rain_source``
  ``"default"``      POWER, anni > 2022 non affidabili (D1).
  ``"power"``        POWER puro, tutti gli anni affidabili (ipotesi "POWER e' giusto").
  ``"power_arpa"``   POWER fino al 2022, pluviometro ARPA (``arpa_rain_daily.csv``) dal
                     2023; i giorni ARPA incompleti prendono il valore POWER dello stesso
                     giorno (``rain_source = "power_gapfill"``). Solo per il punto pilota
                     o dove esiste un pluviometro in cache.
  ``"imerg"``        GPM IMERG Final (``imerg_daily.csv``) dove c'e'; fuori copertura POWER
                     con ``rain_trusted`` False (vedi D6). CacheMiss se IMERG non e' in cache.

``temp_source``
  ``"default"`` / ``"power"``  POWER (D2).
  ``"arpa_<idsensore>"``       stazione ARPA in cache (``arpa_temp_daily_<id>.csv``, es.
                               ``arpa_9031`` Casalbuttano, ``arpa_6823`` Gambara); giorni
                               senza dato valido -> POWER (``temp_source = "power_gapfill"``).
                               Umidita', vento e radiazione restano POWER.

Regola comune per le fonti alternative: un anno e' affidabile se almeno
``MIN_PRIMARY_FRACTION`` dei suoi giorni viene dalla fonte scelta (stessa soglia del 90%
usata da ARPA per il giorno completo); il riempimento con POWER e' dichiarato per giorno.

Nessun parametro agronomico qui dentro.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .data import cache
from .et0 import et0_from_power

# Ultimo anno in cui la pioggia POWER e' considerata affidabile.
# data/CHECKS.md, Decisioni, D1: rapporto POWER/pluviometri 1.02 (Persico Dosimo, 2000-2022);
# 2024 e 2025 sopra +38% e +72% sulla media di cinque pluviometri ARPA; 2023 escluso per prudenza.
POWER_RAIN_LAST_RELIABLE_YEAR = 2022

# Frazione minima di giorni dalla fonte scelta perche' un anno sia affidabile (D1, D2).
MIN_PRIMARY_FRACTION = 0.90

# Giorno ARPA di temperatura valido: almeno 20 misure (D2; il campo n_expected del client
# e' inaffidabile negli anni con passo di misura misto).
ARPA_MIN_OBS = 20

ENGINE_COLUMNS = ["date", "tmax", "tmin", "tmean", "rain", "srad", "rh", "wind", "et0"]
PROVENANCE_COLUMNS = ["rain_source", "rain_trusted", "temp_source", "temp_trusted"]

RAIN_SOURCES = ("default", "power", "power_arpa", "imerg")


def _point_dir(lat: float, lon: float):
    return cache.processed_dir(lat, lon, create=False)   # solo letture


def _read_csv(path, hint: str) -> pd.DataFrame:
    if not path.exists():
        raise cache.CacheMiss(f"dato non in cache: {path} - {hint}")
    return pd.read_csv(path, parse_dates=["date"])


def _load_power(lat: float, lon: float) -> tuple[pd.DataFrame, float]:
    d = _point_dir(lat, lon)
    hint = f"python -m fieldwise.data.power --lat {lat} --lon {lon}"
    df = _read_csv(d / "power_daily.csv", hint)
    site = d / "power_site.json"
    if not site.exists():
        raise cache.CacheMiss(f"dato non in cache: {site} - {hint}")
    elev = float(json.loads(site.read_text(encoding="utf-8"))["elevation_m"])
    return df.sort_values("date").reset_index(drop=True), elev


def _year_trust(dates: pd.Series, primary: pd.Series) -> pd.Series:
    """True per i giorni degli anni con almeno MIN_PRIMARY_FRACTION di giorni da fonte primaria."""
    frac = primary.groupby(dates.dt.year).transform("mean")
    return frac >= MIN_PRIMARY_FRACTION


def _apply_rain(df: pd.DataFrame, lat: float, lon: float, source: str) -> None:
    year = df["date"].dt.year
    if source == "default":
        df["rain_source"] = "power"
        df["rain_trusted"] = year <= POWER_RAIN_LAST_RELIABLE_YEAR
    elif source == "power":
        df["rain_source"] = "power"
        df["rain_trusted"] = True
    elif source == "power_arpa":
        a = _read_csv(_point_dir(lat, lon) / "arpa_rain_daily.csv",
                      f"python -m fieldwise.data.arpa --lat {lat} --lon {lon}")
        a = a.set_index("date")
        ok = a["complete"].astype(bool) & a["rain_mm"].notna()
        g = df["date"].map(a["rain_mm"].where(ok))
        late = year > POWER_RAIN_LAST_RELIABLE_YEAR
        use = late & g.notna()
        df.loc[use, "rain"] = g[use]
        df["rain_source"] = np.where(use, "arpa", np.where(late, "power_gapfill", "power"))
        primary = ~late | use
        df["rain_trusted"] = _year_trust(df["date"], primary)
    elif source == "imerg":
        im = _read_csv(_point_dir(lat, lon) / "imerg_daily.csv",
                       f"python -m fieldwise.data.imerg --lat {lat} --lon {lon} (credenziali Earthdata)")
        g = df["date"].map(im.set_index("date")["rain_mm"])
        use = g.notna()
        df.loc[use, "rain"] = g[use]
        df["rain_source"] = np.where(use, "imerg", "power")
        # un anno vale solo se interamente IMERG (nessun riempimento da POWER nell'ensemble)
        df["rain_trusted"] = use.groupby(year).transform("all")
    else:
        raise ValueError(f"rain_source sconosciuta: {source!r}; ammesse {RAIN_SOURCES} ")


def _apply_temp(df: pd.DataFrame, lat: float, lon: float, source: str) -> None:
    if source in ("default", "power"):
        df["temp_source"] = "power"
        df["temp_trusted"] = True
        return
    if not source.startswith("arpa_"):
        raise ValueError(f"temp_source sconosciuta: {source!r}; ammesse 'default', 'power', 'arpa_<id>'")
    sid = source.split("_", 1)[1]
    st = _read_csv(_point_dir(lat, lon) / f"arpa_temp_daily_{sid}.csv",
                   f"python -m fieldwise.data.arpa --lat {lat} --lon {lon} --variable temperature "
                   f"--sensor-id {sid}").set_index("date")
    valid = (st["n_obs"] >= ARPA_MIN_OBS) & st[["tmax", "tmin", "tmean"]].notna().all(axis=1)
    st = st[valid]
    use = df["date"].isin(st.index)
    for c in ("tmax", "tmin", "tmean"):
        df.loc[use, c] = df.loc[use, "date"].map(st[c]).to_numpy()
    df["temp_source"] = np.where(use, source, "power_gapfill")
    df["temp_trusted"] = _year_trust(df["date"], use)


def load_forcing(lat: float, lon: float, rain_source: str = "default",
                 temp_source: str = "default", elev_m: float | None = None) -> pd.DataFrame:
    """Tabella giornaliera pronta per il motore, solo dalla cache (CacheMiss se manca).

    Colonne: ``date, tmax, tmin, tmean, rain, srad, rh, wind, et0`` (degC, mm/g,
    MJ m-2 g-1, %, m/s a 2 m, mm/g) piu' ``rain_source, rain_trusted, temp_source,
    temp_trusted``. ``et0`` = Penman-Monteith FAO-56 con le temperature scelte e
    umidita'/vento/radiazione POWER, alla quota della cella POWER se ``elev_m`` e' None (D2).
    """
    df, elev_power = _load_power(lat, lon)
    _apply_rain(df, lat, lon, rain_source)
    _apply_temp(df, lat, lon, temp_source)
    elev = elev_power if elev_m is None else float(elev_m)
    et0 = et0_from_power(df, lat, elev)
    df["et0"] = et0["et0_pm"].to_numpy()
    df.attrs.update(lat=lat, lon=lon, elev_m=elev, rain_option=rain_source,
                    temp_option=temp_source)
    return df[ENGINE_COLUMNS + PROVENANCE_COLUMNS]


def available_years(forcing: pd.DataFrame) -> list[int]:
    """Anni utilizzabili come annate di partenza dell'ensemble (D1).

    Un anno vale se e' completo (tutti i giorni presenti), non ha NaN nelle colonne del
    motore e ha pioggia e temperature affidabili in ogni giorno. Il motore decide come
    concatenare gli anni (es. una rotazione pluriennale richiede anni consecutivi validi).
    """
    d = forcing.copy()
    d["date"] = pd.to_datetime(d["date"])
    y = d["date"].dt.year
    ok = d[ENGINE_COLUMNS[1:]].notna().all(axis=1) & d["rain_trusted"].astype(bool) \
        & d["temp_trusted"].astype(bool)
    out = []
    for year, g in ok.groupby(y):
        ndays = 366 if pd.Timestamp(year=int(year), month=12, day=31).dayofyear == 366 else 365
        if len(g) == ndays and bool(g.all()):
            out.append(int(year))
    return out
