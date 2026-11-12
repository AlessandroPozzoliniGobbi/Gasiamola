"""Client della pioggia ARPA Lombardia (open data di Regione Lombardia, Socrata/SODA).

Serve solo come verifica a terra delle piogge satellitari/di rianalisi.

Fonti (nessun login):
* anagrafica "Stazioni Idro Nivo Meteorologiche" (nf78-nj6b): sensori con
  tipologia "Precipitazione", coordinate, quota, datastart/datastop;
* misure dei pluviometri, un dataset per periodo ("Precipitazioni fino al 2010",
  "... dal 2011 al 2020", "... dal 2021"): gli identificativi si trovano con
  l'API del catalogo, non sono scritti nel codice.

Le misure sono a passo di 10 minuti e gli archivi hanno milioni di righe: la
somma e il conteggio per giorno si fanno LATO SERVER (SoQL), una richiesta per
dataset-anno. I valori non validi (stato diverso da 'VA' o valore negativo, p.es.
la sentinella -999) non entrano ne' nella somma ne' in n_obs: sono mancanti.

CONVENZIONE ORARIA (dichiarata da ARPA nella descrizione dei dataset: "l'orario del
dato e' 'ora solare' e si riferisce alle osservazioni ottenute fino all'orario
indicato"). Quindi:
* i tempi sono ora solare (UTC+1 fisso, senza ora legale);
* una misura con timestamp T e' la pioggia caduta nell'intervallo (T-10', T];
* il "giorno" D e' l'intervallo solare (D 00:00, D+1 00:00]: la misura delle
  00:00 appartiene al giorno precedente; il giorno completo ha 144 misure
  (00:10 ... 24:00). Conferma: gli archivi si chiudono alle 00:00 del primo
  gennaio del periodo successivo e il successivo inizia alle 00:10.
Il giorno solare UTC+1 e' sfasato di 1 ora (2 con l'ora legale) rispetto al
giorno civile italiano e di 1 ora rispetto al giorno UTC.

Elaborato: cache.processed_dir(lat, lon) / "arpa_rain_daily.csv" con colonne
date, rain_mm, n_obs, n_expected, complete, sensor_id, station
(rain_mm = NaN se nessuna misura valida; complete = n_obs >= 90% di n_expected).

TEMPERATURA (fetch_temperature / load_temperature): stessa stazione e stessa
meccanica della pioggia, sensori di tipologia "Temperatura" (aria) e dataset
"Temperatura fino al 2010 / dal 2011 al 2020 / dal 2021" trovati dal catalogo.
Lato server si calcolano per giorno massimo, minimo, somma e conteggio dei valori
validi; tmean = somma / conteggio (media aritmetica delle misure a 10 minuti o
orarie, non (tmax+tmin)/2). Sono validi i valori con stato 'VA' e -50 < T < 60 °C
(esclude la sentinella -999 e i valori fisicamente impossibili, p.es. un sensore
bloccato a 145.3 °C ma con stato 'VA'). Elaborato: arpa_temp_daily.csv con
date, tmax, tmin, tmean, n_obs, n_expected, complete, sensor_id, station.

DEFINIZIONE DEL GIORNO PER IL CONFRONTO CON NASA POWER: tmax/tmin ARPA sono il
massimo/minimo delle misure nel giorno SOLARE UTC+1 (D 00:00, D+1 00:00], come
per la pioggia (la misura delle 00:00 va al giorno precedente). Il giorno di
POWER (time_standard LST, ora solare locale vera del meridiano) e' sfasato di
lon/15 h rispetto a UTC: a lon 10.0 E sono +40 min, cioe' 20 min dopo il giorno
ARPA (UTC+1). Lo sfasamento e' piccolo rispetto alla variazione termica
giornaliera, ma non nullo: tmax/tmin giornalieri ARPA e POWER non sono
definiti sulla stessa finestra al minuto. Inoltre POWER e' una cella di
rianalisi (media su ~50x50 km, quota della cella diversa da quella del campo)
mentre ARPA e' una misura puntuale.

CLI:  python -m fieldwise.data.arpa --lat 45.2 --lon 10.0 [--variable rain|temperature]
      [--start-year --end-year --force]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple

import numpy as np
import pandas as pd
import requests

from . import cache

SOURCE = "arpa"
BASE_URL = "https://www.dati.lombardia.it"
CATALOG_URL = f"{BASE_URL}/api/catalog/v1"
STATIONS_DATASET = "nf78-nj6b"  # "Stazioni Idro Nivo Meteorologiche"
STATIONS_PRODUCT = "Stazioni Idro Nivo Meteorologiche"
PRECIP_TYPE = "Precipitazione"
TEMP_TYPE = "Temperatura"
DATASET_NAME_RE = re.compile(r"^Precipitazioni (fino al|dal)\b", re.I)
TEMP_DATASET_NAME_RE = re.compile(r"^Temperatura (fino al|dal)\b", re.I)
T_VALID_RANGE = (-50.0, 60.0)  # °C, estremi esclusi: filtro di plausibilita' per l'aria

RADIUS_KM = 25.0
EARTH_RADIUS_KM = 6371.0088
MIN_COVERAGE_GAIN = 0.01  # il secondario serve se aggiunge almeno l'1% del periodo
COMPLETE_FRACTION = 0.90
OUT_NAME = "arpa_rain_daily.csv"
COLUMNS = ["date", "rain_mm", "n_obs", "n_expected", "complete", "sensor_id", "station"]
TEMP_OUT_NAME = "arpa_temp_daily.csv"
TEMP_COLUMNS = ["date", "tmax", "tmin", "tmean", "n_obs", "n_expected", "complete",
                "sensor_id", "station"]
# passi di campionamento plausibili (misure/giorno) per ricavare n_expected
EXPECTED_STEPS = (24, 48, 144, 288, 1440)

TIMEOUT = (30, 300)
ATTEMPTS = 3
BACKOFF = 5.0  # attesa prima di ritentare: BACKOFF * n secondi
PAUSE = 2.0    # pausa tra una richiesta riuscita e la successiva

CONVENTION = (
    "Orario ARPA = ora solare (UTC+1 fisso), riferito alle osservazioni fino all'orario "
    "indicato: la misura con timestamp T e' la pioggia in (T-10min, T]. Giorno D = "
    "intervallo solare (D 00:00, D+1 00:00]; la misura delle 00:00 va al giorno precedente."
)


# --------------------------------------------------------------------------- rete

def _get(url: str, params: dict[str, Any]) -> Any:
    last: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            time.sleep(PAUSE)
            return data
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt < ATTEMPTS:
                time.sleep(BACKOFF * attempt)
    raise RuntimeError(f"ARPA/Socrata: {ATTEMPTS} tentativi falliti per {url} ({last})") from last


# --------------------------------------------------------------------- geometria

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distanza sulla sfera (formula dell'emisenoverso), in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def _parse_day(value: Any) -> pd.Timestamp | None:
    if value in (None, "", "None"):
        return None
    return pd.Timestamp(str(value)[:10])


def _coverage_mask(days: pd.DatetimeIndex, st: dict[str, Any]) -> np.ndarray:
    a, b = _parse_day(st.get("datastart")), _parse_day(st.get("datastop"))
    m = np.ones(len(days), dtype=bool)
    if a is not None:
        m &= days >= a
    if b is not None:
        m &= days <= b
    return m


def choose_stations(stations: list[dict[str, Any]], lat: float, lon: float,
                    start_year: int = 2000, end_year: int = 2025,
                    radius_km: float = RADIUS_KM,
                    tipologia: str = PRECIP_TYPE) -> list[dict[str, Any]]:
    """Sensori della tipologia richiesta (default precipitazione) entro radius_km: primario ed eventuale secondario.

    Primario: massima copertura (da datastart/datastop, arrotondata all'1%) del
    periodo, a parita' la piu' vicina. Secondario: solo se il primario non copre
    tutto, il sensore che copre di piu' i giorni lasciati scoperti (minimo l'1% del
    periodo), a parita' il piu' vicino. Ogni elemento: dict dell'anagrafica con in
    piu' dist_km, coverage, role ('primary'/'secondary').
    """
    days = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")
    cands = []
    for st in stations:
        if str(st.get("tipologia", "")).strip().lower() != tipologia.lower():
            continue
        try:
            d = haversine_km(lat, lon, float(st["lat"]), float(st["lng"]))
        except (KeyError, TypeError, ValueError):
            continue
        if d > radius_km:
            continue
        mask = _coverage_mask(days, st)
        cands.append({**st, "dist_km": d, "coverage": float(mask.mean()), "_mask": mask})
    if not cands:
        return []
    cands.sort(key=lambda c: (-round(c["coverage"], 2), c["dist_km"]))
    primary = cands[0]
    out = [primary]
    uncovered = ~primary["_mask"]
    if uncovered.mean() > MIN_COVERAGE_GAIN:
        rest = []
        for c in cands[1:]:
            gain = float((c["_mask"] & uncovered).mean())
            if gain >= MIN_COVERAGE_GAIN:
                rest.append((-round(gain, 2), c["dist_km"], c))
        if rest:
            rest.sort(key=lambda t: (t[0], t[1]))
            out.append(rest[0][2])
    res = []
    for role, c in zip(("primary", "secondary"), out):
        c = {k: v for k, v in c.items() if k != "_mask"}
        c["role"] = role
        res.append(c)
    return res


# ------------------------------------------------------------------- dataset

def parse_dataset_years(name: str) -> tuple[int, int]:
    """'Precipitazioni dal 2011 al 2020' -> (2011, 2020); estremi aperti = 0 / 9999."""
    m = re.search(r"fino al (\d{4})", name)
    if m:
        return 0, int(m.group(1))
    m = re.search(r"dal (\d{4}) al (\d{4})", name)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"dal (\d{4})", name)
    if m:
        return int(m.group(1)), 9999
    raise ValueError(f"periodo non riconosciuto in '{name}'")


def datasets_from_catalog(catalog: dict[str, Any],
                          name_re: re.Pattern = DATASET_NAME_RE) -> list[dict[str, Any]]:
    out = []
    for r in catalog.get("results", []):
        res = r.get("resource", {})
        name = res.get("name", "")
        if not name_re.match(name):
            continue
        first, last = parse_dataset_years(name)
        out.append({"id": res["id"], "name": name, "first": first, "last": last,
                    "updated": res.get("data_updated_at") or res.get("updatedAt") or "?"})
    out.sort(key=lambda d: d["first"])
    return out


def dataset_for_year(datasets: list[dict[str, Any]], year: int) -> dict[str, Any] | None:
    for d in datasets:
        if d["first"] <= year <= d["last"]:
            return d
    return None


# --------------------------------------------------------------- aggregazione

def _select_clause() -> str:
    valid = "stato='VA' AND valore>=0"
    return (
        "date_trunc_ymd(data) as giorno, "
        "case(date_extract_hh(data)=0 AND date_extract_mm(data)=0, 1, true, 0) as mezzanotte, "
        f"sum(case({valid}, valore, true, 0)) as pioggia, "
        f"sum(case({valid}, 1, true, 0)) as n_valid, "
        "count(*) as n_tot"
    )


def _year_params(sensor_id: str, year: int) -> dict[str, str]:
    return {
        "$select": _select_clause(),
        "$where": (f"idsensore='{sensor_id}' AND data>'{year}-01-01T00:00:00' "
                   f"AND data<='{year + 1}-01-01T00:00:00'"),
        "$group": "giorno,mezzanotte",
        "$order": "giorno,mezzanotte",
        "$limit": "50000",
    }


def rows_to_daily(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Righe SoQL (giorno, mezzanotte, pioggia, n_valid, n_tot) -> giorni solari.

    La misura delle 00:00 (mezzanotte=1) e' attribuita al giorno precedente.
    Colonne: date, rain_mm (somma dei soli valori validi), n_obs (validi), n_tot.
    """
    if not rows:
        return pd.DataFrame(columns=["date", "rain_mm", "n_obs", "n_tot"])
    df = pd.DataFrame(rows)
    day = pd.to_datetime(df["giorno"].astype(str).str[:10])
    shift = pd.to_numeric(df["mezzanotte"]).astype(int)
    df["date"] = day - pd.to_timedelta(shift, unit="D")
    df["rain_mm"] = pd.to_numeric(df["pioggia"])
    df["n_obs"] = pd.to_numeric(df["n_valid"]).astype(int)
    df["n_tot"] = pd.to_numeric(df["n_tot"]).astype(int)
    out = df.groupby("date", as_index=False)[["rain_mm", "n_obs", "n_tot"]].sum()
    return out.sort_values("date").reset_index(drop=True)


def infer_expected(n_obs: pd.Series) -> int:
    """Misure attese al giorno ricavate dalla risoluzione osservata nell'anno.

    Si prende il 95-esimo percentile dei conteggi giornalieri e lo si aggancia al
    passo piu' vicino per eccesso (24 = orario, 144 = 10 minuti, ...). Senza dati: 144,
    la risoluzione massima dichiarata da ARPA.
    """
    s = pd.Series(n_obs).dropna()
    s = s[s > 0]
    if s.empty:
        return 144
    q = float(np.percentile(s, 95))
    for step in EXPECTED_STEPS:
        if q <= step:
            return step
    return EXPECTED_STEPS[-1]


def _day_grid(start_year: int, end_year: int, datastart: Any, datastop: Any) -> pd.DatetimeIndex:
    days = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")
    a, b = _parse_day(datastart), _parse_day(datastop)
    if a is not None:
        days = days[days >= a]
    if b is not None:
        days = days[days <= b]
    return days


def _add_completeness(df: pd.DataFrame, sensor_id: str, station: str) -> pd.DataFrame:
    """Aggiunge n_expected (dalla risoluzione osservata in ogni anno), complete, sensore e stazione."""
    df["n_obs"] = df["n_obs"].fillna(0).astype(int)
    year = df["date"].dt.year
    exp = {y: infer_expected(df.loc[(year == y) & (df["n_obs"] > 0), "n_obs"]) for y in year.unique()}
    df["n_expected"] = year.map(exp).astype(int)
    df["complete"] = df["n_obs"] >= COMPLETE_FRACTION * df["n_expected"]
    df["sensor_id"] = str(sensor_id)
    df["station"] = station
    return df


def build_daily(rows_by_year: dict[int, list[dict[str, Any]]], sensor_id: str, station: str,
                start_year: int, end_year: int, datastart: Any = None,
                datastop: Any = None) -> pd.DataFrame:
    """Elaborato giornaliero di un sensore sull'intero periodo (giorni senza righe = mancanti)."""
    frames = []
    for year, rows in rows_by_year.items():
        d = rows_to_daily(rows)
        if d.empty:
            continue
        d["year"] = year
        frames.append(d)
    daily = (pd.concat(frames).groupby("date", as_index=False)[["rain_mm", "n_obs", "n_tot"]].sum()
             if frames else pd.DataFrame(columns=["date", "rain_mm", "n_obs", "n_tot"]))
    days = _day_grid(start_year, end_year, datastart, datastop)
    df = pd.DataFrame({"date": days}).merge(daily, on="date", how="left")
    df["n_obs"] = df["n_obs"].fillna(0).astype(int)
    df.loc[df["n_obs"] == 0, "rain_mm"] = np.nan  # nessuna misura valida: pioggia ignota
    return _add_completeness(df, sensor_id, station)[COLUMNS]


# ------------------------------------------------------------------ temperatura

def _temp_valid() -> str:
    lo, hi = T_VALID_RANGE
    return f"stato='VA' AND valore>{lo:g} AND valore<{hi:g}"


def _temp_select_clause() -> str:
    valid = _temp_valid()
    return (
        "date_trunc_ymd(data) as giorno, "
        "case(date_extract_hh(data)=0 AND date_extract_mm(data)=0, 1, true, 0) as mezzanotte, "
        f"max(case({valid}, valore)) as tmax, "
        f"min(case({valid}, valore)) as tmin, "
        f"sum(case({valid}, valore, true, 0)) as somma, "
        f"sum(case({valid}, 1, true, 0)) as n_valid, "
        "count(*) as n_tot"
    )


def _temp_year_params(sensor_id: str, year: int) -> dict[str, str]:
    p = _year_params(sensor_id, year)
    p["$select"] = _temp_select_clause()
    return p


def temp_rows_to_daily(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Righe SoQL (giorno, mezzanotte, tmax, tmin, somma, n_valid, n_tot) -> giorni solari.

    La misura delle 00:00 (mezzanotte=1) e' attribuita al giorno precedente; massimo e
    minimo si compongono con max/min, somma e conteggi con la somma.
    Colonne: date, tmax, tmin, tmean (somma/n_obs), n_obs (validi), n_tot.
    """
    cols = ["date", "tmax", "tmin", "tmean", "n_obs", "n_tot"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows).reindex(columns=["giorno", "mezzanotte", "tmax", "tmin", "somma",
                                             "n_valid", "n_tot"])
    day = pd.to_datetime(df["giorno"].astype(str).str[:10])
    df["date"] = day - pd.to_timedelta(pd.to_numeric(df["mezzanotte"]).astype(int), unit="D")
    for c in ("tmax", "tmin", "somma", "n_valid", "n_tot"):
        df[c] = pd.to_numeric(df[c])
    g = df.groupby("date")
    out = pd.DataFrame({"tmax": g["tmax"].max(), "tmin": g["tmin"].min(), "somma": g["somma"].sum(),
                        "n_obs": g["n_valid"].sum().astype(int),
                        "n_tot": g["n_tot"].sum().astype(int)}).reset_index()
    out["tmean"] = np.where(out["n_obs"] > 0, out["somma"] / out["n_obs"].where(out["n_obs"] > 0), np.nan)
    return out[cols].sort_values("date").reset_index(drop=True)


def build_daily_temp(rows_by_year: dict[int, list[dict[str, Any]]], sensor_id: str, station: str,
                     start_year: int, end_year: int, datastart: Any = None,
                     datastop: Any = None) -> pd.DataFrame:
    """Elaborato giornaliero di temperatura: giorni senza misure valide = NaN, mai 0."""
    frames = [d for d in (temp_rows_to_daily(r) for r in rows_by_year.values()) if not d.empty]
    cols = ["date", "tmax", "tmin", "tmean", "n_obs"]
    if frames:
        all_ = pd.concat(frames)
        # il file di un anno contiene la misura delle 00:00 del 1 gennaio successivo,
        # attribuita al 31 dicembre: nessun giorno compare in due anni
        daily = all_.groupby("date", as_index=False).agg(
            tmax=("tmax", "max"), tmin=("tmin", "min"), tmean=("tmean", "mean"), n_obs=("n_obs", "sum"))
    else:
        daily = pd.DataFrame(columns=cols)
    days = _day_grid(start_year, end_year, datastart, datastop)
    df = pd.DataFrame({"date": days}).merge(daily[cols], on="date", how="left")
    df["n_obs"] = df["n_obs"].fillna(0).astype(int)
    return _add_completeness(df, sensor_id, station)[TEMP_COLUMNS]


# ------------------------------------------------------------ specifiche per variabile

class _Spec(NamedTuple):
    key: str | None          # chiave in arpa_stations.json (None = livello principale, la pioggia)
    label: str
    tipologia: str
    catalog_q: str
    catalog_file: str
    stations_file: str
    name_re: re.Pattern
    raw_prefix: str
    params_fn: Callable[[str, int], dict[str, str]]
    builder: Callable[..., pd.DataFrame]
    out_name: str
    row_desc: str


RAIN = _Spec(None, "pioggia", PRECIP_TYPE, "Precipitazioni", "catalogo_precipitazioni.json",
             "anagrafica_precipitazione.json", DATASET_NAME_RE, "pioggia", _year_params, build_daily,
             OUT_NAME, "(giorno, mezzanotte, pioggia, n_valid, n_tot)")
TEMP = _Spec("temperature", "temperatura", TEMP_TYPE, "Temperatura", "catalogo_temperatura.json",
             "anagrafica_temperatura.json", TEMP_DATASET_NAME_RE, "temperatura", _temp_year_params,
             build_daily_temp, TEMP_OUT_NAME,
             "(giorno, mezzanotte, tmax, tmin, somma, n_valid, n_tot)")


# ----------------------------------------------------------------------- cache

def _raw_dir(lat: float, lon: float) -> Path:
    return cache.raw_dir(SOURCE, lat, lon)


def _write_json(path: Path, payload: Any, *, product: str, version: str, url: str,
                params: dict[str, Any], notes: str | None) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    cache.write_meta(path, source=SOURCE, product=product, version=version, url=url,
                     params=params, notes=notes)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _stations_payload(lat: float, lon: float, force: bool, spec: _Spec = RAIN) -> list[dict[str, Any]]:
    path = _raw_dir(lat, lon) / spec.stations_file
    if cache.is_cached(path) and not force:
        return _read_json(path)
    cache.ensure_online(f"anagrafica {STATIONS_DATASET}")
    url = f"{BASE_URL}/resource/{STATIONS_DATASET}.json"
    params = {"$where": f"tipologia='{spec.tipologia}'", "$limit": "50000"}
    rows = _get(url, params)
    version = f"{STATIONS_DATASET}; scaricata il {pd.Timestamp.now(tz='UTC'):%Y-%m-%d} (righe: {len(rows)})"
    _write_json(path, rows, product=STATIONS_PRODUCT, version=version, url=url, params=params,
                notes=f"Anagrafica dei sensori di {spec.label} (datastart/datastop = periodo di attivita').")
    return rows


def _catalog_payload(lat: float, lon: float, force: bool, spec: _Spec = RAIN) -> dict[str, Any]:
    path = _raw_dir(lat, lon) / spec.catalog_file
    if cache.is_cached(path) and not force:
        return _read_json(path)
    cache.ensure_online("catalogo Socrata")
    params = {"q": spec.catalog_q, "only": "datasets", "limit": "50"}
    payload = _get(CATALOG_URL, params)
    _write_json(path, payload, product=f"Catalogo dati.lombardia.it ({spec.catalog_q})",
                version=f"catalogo del {pd.Timestamp.now(tz='UTC'):%Y-%m-%d}", url=CATALOG_URL,
                params=params, notes="Serve a trovare gli identificativi dei dataset delle misure.")
    return payload


def _year_path(lat: float, lon: float, dataset_id: str, sensor_id: str, year: int,
               spec: _Spec = RAIN) -> Path:
    return _raw_dir(lat, lon) / f"{spec.raw_prefix}_{dataset_id}_sensore{sensor_id}_{year}.json"


def _station_info(st: dict[str, Any]) -> dict[str, Any]:
    return {"sensor_id": str(st["idsensore"]), "station": st.get("nomestazione"),
            "station_id": st.get("idstazione"), "lat": float(st["lat"]), "lon": float(st["lng"]),
            "quota_m": st.get("quota"), "dist_km": round(float(st["dist_km"]), 3),
            "role": st.get("role"), "datastart": st.get("datastart"), "datastop": st.get("datastop")}


def _fetch_year(lat: float, lon: float, ds: dict[str, Any], st: dict[str, Any], year: int,
                force: bool, spec: _Spec = RAIN) -> Path:
    sid = str(st["idsensore"])
    path = _year_path(lat, lon, ds["id"], sid, year, spec)
    if cache.is_cached(path) and not force:
        return path
    cache.ensure_online(f"{ds['id']} sensore {sid} anno {year}")
    url = f"{BASE_URL}/resource/{ds['id']}.json"
    params = spec.params_fn(sid, year)
    rows = _get(url, params)
    info = _station_info(st)
    extra = (f" Valori validi: stato 'VA' e {T_VALID_RANGE[0]:g} < T < {T_VALID_RANGE[1]:g} °C."
             if spec is TEMP else "")
    _write_json(
        path, rows, product=ds["name"], version=f"{ds['id']}; ultimo aggiornamento {ds['updated']}",
        url=url, params={**params, **info, "year": year},
        notes=(f"Sensore {sid} ({info['station']}, quota {info['quota_m']} m, "
               f"{info['dist_km']} km dal punto). Righe = aggregato giornaliero SoQL "
               f"{spec.row_desc}.{extra} {CONVENTION}"))
    return path


def _update_stations_json(lat: float, lon: float, spec: _Spec, block: dict[str, Any]) -> None:
    """Scrive arpa_stations.json conservando le informazioni dell'altra variabile."""
    path = cache.processed_dir(lat, lon) / "arpa_stations.json"
    cur: dict[str, Any] = {}
    if path.exists():
        try:
            cur = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            cur = {}
    if spec.key is None:
        cur.update(block)
    else:
        cur[spec.key] = block
    path.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")


def _out_name(spec: _Spec, sensor_id: str | None) -> str:
    """Nome dell'elaborato; con sensore esplicito: arpa_temp_daily_<sensor_id>.csv."""
    if sensor_id is None:
        return spec.out_name
    stem, ext = spec.out_name.rsplit(".", 1)
    return f"{stem}_{sensor_id}.{ext}"


def _build_and_write(lat: float, lon: float, stations: list[dict[str, Any]],
                     datasets: list[dict[str, Any]], start_year: int, end_year: int,
                     spec: _Spec = RAIN, sensor_id: str | None = None) -> Path:
    frames = []
    for st in stations:
        sid = str(st["idsensore"])
        rows_by_year: dict[int, list[dict[str, Any]]] = {}
        for year in range(start_year, end_year + 1):
            ds = dataset_for_year(datasets, year)
            if ds is None:
                continue
            p = _year_path(lat, lon, ds["id"], sid, year, spec)
            if cache.is_cached(p):
                rows_by_year[year] = _read_json(p)
        if not rows_by_year:
            continue
        frames.append(spec.builder(rows_by_year, sid, st.get("nomestazione", ""), start_year, end_year,
                                   st.get("datastart"), st.get("datastop")))
    if not frames:
        raise cache.CacheMiss(f"nessun dato di {spec.label} ARPA in cache - per scaricarlo: "
                              f"python -m fieldwise.data.arpa --lat {lat} --lon {lon}"
                              + (" --variable temperature" if spec is TEMP else ""))
    df = pd.concat(frames, ignore_index=True)
    out = cache.processed_dir(lat, lon) / _out_name(spec, sensor_id)
    df.to_csv(out, index=False, date_format="%Y-%m-%d")
    block = {"stations": [_station_info(s) for s in stations], "convention": CONVENTION,
             "datasets": datasets, "start_year": start_year, "end_year": end_year}
    if sensor_id is None:
        _update_stations_json(lat, lon, spec, block)
    else:  # sensore esplicito: arpa_stations.json (scelta automatica) non si tocca
        (cache.processed_dir(lat, lon) / f"arpa_temp_station_{sensor_id}.json").write_text(
            json.dumps(block, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def _explicit_station(stations_raw: list[dict[str, Any]], lat: float, lon: float,
                      sensor_id: str, start_year: int, end_year: int) -> list[dict[str, Any]]:
    for st in stations_raw:
        if str(st.get("idsensore")) == str(sensor_id):
            days = pd.date_range(f"{start_year}-01-01", f"{end_year}-12-31", freq="D")
            return [{**st, "dist_km": haversine_km(lat, lon, float(st["lat"]), float(st["lng"])),
                     "coverage": float(_coverage_mask(days, st).mean()), "role": "explicit"}]
    return []


def _fetch_variable(lat: float, lon: float, start_year: int, end_year: int, force: bool,
                    spec: _Spec, sensor_id: str | None = None) -> Path:
    cache.ensure_online("ARPA Lombardia (dati.lombardia.it)")
    stations_raw = _stations_payload(lat, lon, force, spec)
    if sensor_id is not None:
        sensor_id = str(sensor_id)
        stations = _explicit_station(stations_raw, lat, lon, sensor_id, start_year, end_year)
        if not stations:
            raise RuntimeError(f"sensore di {spec.label} {sensor_id} non trovato nell'anagrafica")
    else:
        stations = choose_stations(stations_raw, lat, lon, start_year, end_year, tipologia=spec.tipologia)
    if not stations:
        raise RuntimeError(f"nessun sensore di {spec.label} entro {RADIUS_KM:.0f} km da ({lat}, {lon})")
    datasets = datasets_from_catalog(_catalog_payload(lat, lon, force, spec), spec.name_re)
    if not datasets:
        raise RuntimeError(f"catalogo Socrata: nessun dataset di {spec.label} trovato")
    for st in stations:
        for year in range(start_year, end_year + 1):
            ds = dataset_for_year(datasets, year)
            if ds is None:
                continue
            first = _parse_day(st.get("datastart"))
            last = _parse_day(st.get("datastop"))
            if (first is not None and year < first.year) or (last is not None and year > last.year):
                continue  # il sensore non era attivo: nessuna richiesta
            _fetch_year(lat, lon, ds, st, year, force, spec)
    return _build_and_write(lat, lon, stations, datasets, start_year, end_year, spec, sensor_id)


def _load_variable(lat: float, lon: float, spec: _Spec, sensor_id: str | None = None) -> pd.DataFrame:
    sensor_id = None if sensor_id is None else str(sensor_id)
    csv = cache.processed_dir(lat, lon) / _out_name(spec, sensor_id)
    if not csv.exists():
        raise cache.CacheMiss(
            f"dato non in cache: {csv} - per scaricarlo: "
            f"python -m fieldwise.data.arpa --lat {lat} --lon {lon}"
            + (" --variable temperature" if spec is TEMP else "")
            + (f" --sensor-id {sensor_id}" if sensor_id else ""))
    return pd.read_csv(csv, parse_dates=["date"], dtype={"sensor_id": str, "station": str})


# ------------------------------------------------------------------- interfaccia

def fetch(lat: float, lon: float, start_year: int = 2000, end_year: int = 2025,
          force: bool = False) -> Path:
    """Scarica (se serve) anagrafica, catalogo e un aggregato giornaliero per anno;
    scrive l'elaborato arpa_rain_daily.csv e ne restituisce il percorso."""
    return _fetch_variable(lat, lon, start_year, end_year, force, RAIN)


def load(lat: float, lon: float) -> pd.DataFrame:
    """Elaborato giornaliero dalla cache (mai dalla rete); CacheMiss se manca."""
    return _load_variable(lat, lon, RAIN)


def fetch_temperature(lat: float, lon: float, start_year: int = 2000, end_year: int = 2025,
                      force: bool = False, sensor_id: str | None = None) -> Path:
    """Come fetch() per la temperatura dell'aria; scrive arpa_temp_daily.csv.

    Con sensor_id esplicito (qualunque sensore "Temperatura" dell'anagrafica, anche oltre
    25 km) scarica quel sensore e scrive arpa_temp_daily_<sensor_id>.csv e
    arpa_temp_station_<sensor_id>.json; arpa_temp_daily.csv e arpa_stations.json della
    scelta automatica non cambiano. I grezzi hanno gia' il sensore nel nome.

    Giorno = giorno solare UTC+1, (D 00:00, D+1 00:00]; vedi il docstring del modulo per
    la differenza con il giorno LST di NASA POWER (+20 min a lon 10 E).
    """
    return _fetch_variable(lat, lon, start_year, end_year, force, TEMP, sensor_id)


def load_temperature(lat: float, lon: float, sensor_id: str | None = None) -> pd.DataFrame:
    """Elaborato giornaliero di temperatura dalla cache (mai dalla rete); CacheMiss se manca.
    Con sensor_id legge arpa_temp_daily_<sensor_id>.csv."""
    return _load_variable(lat, lon, TEMP, sensor_id)


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per sensore e anno: pioggia totale (mm, solo giorni con misure) e % di giorni completi."""
    g = df.assign(year=df["date"].dt.year).groupby(["sensor_id", "year"])
    return pd.DataFrame({
        "rain_mm": g["rain_mm"].sum(min_count=1),
        "pct_complete": g["complete"].mean() * 100,
        "days": g["date"].count(),
    }).reset_index()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Pioggia e temperatura giornaliere ARPA Lombardia (open data)")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--variable", choices=("rain", "temperature"), default="rain")
    ap.add_argument("--start-year", type=int, default=2000)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sensor-id", default=None,
                    help="solo con --variable temperature: sensore esplicito invece della scelta automatica")
    a = ap.parse_args(argv)
    if a.sensor_id and a.variable != "temperature":
        ap.error("--sensor-id vale solo con --variable temperature")
    if a.variable == "temperature" and a.sensor_id:
        out = fetch_temperature(a.lat, a.lon, a.start_year, a.end_year, force=a.force,
                                sensor_id=a.sensor_id)
        print(f"processed: {out}")
        return
    if a.variable == "temperature":
        out = fetch_temperature(a.lat, a.lon, a.start_year, a.end_year, force=a.force)
        key = "temperature"
    else:
        out = fetch(a.lat, a.lon, a.start_year, a.end_year, force=a.force)
        key = None
    print(f"processed: {out}")
    info = json.loads((out.parent / "arpa_stations.json").read_text(encoding="utf-8"))
    for s in (info[key] if key else info)["stations"]:
        print(f"{s['role']}: sensore {s['sensor_id']} {s['station']} quota {s['quota_m']} m, "
              f"{s['dist_km']:.1f} km")


if __name__ == "__main__":
    main()
