"""Accesso ai dati per l'app: cache di Streamlit, controllo della cache locale, fonti.

Nessuna logica di dominio: tutto il calcolo sta in ``fieldwise.*``. Qui ci sono solo funzioni di
presentazione (percorsi, messaggi, lettura dei metadati) e le cache di Streamlit.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# la demo funziona OFFLINE: l'app non tenta mai la rete (i client sollevano OfflineError)
os.environ["FIELDWISE_OFFLINE"] = "1"

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from fieldwise import config, params as _params  # noqa: E402
from fieldwise import ensemble as _ens  # noqa: E402
from fieldwise import rotation as rt  # noqa: E402
from fieldwise import weather as _weather  # noqa: E402
from fieldwise.data import cache as _cache  # noqa: E402

PILOTA = (config.PILOT_LAT, config.PILOT_LON)
FILE_SENSIBILITA = "sensitivity_summary.json"
FONTI = (   # (cartella raw, nome, a cosa serve) - le date vengono dai metadati in cache
    ("power", "NASA POWER", "temperature, radiazione, umidità, vento e pioggia giornalieri; da qui si calcola l'ET0"),
    ("imerg", "GPM IMERG", "pioggia da satellite, usata per confrontare la pioggia di POWER"),
    ("smap", "SMAP", "umidità dello strato superficiale del suolo, usata per controllare il modello"),
    ("modis", "MODIS", "indice di verde della vegetazione (NDVI), usato per controllare gli anni di siccità"),
    ("soilgrids", "SoilGrids", "caratteristiche del suolo del campo (sabbia, argilla, sostanza organica)"),
    ("istat", "ISTAT", "rese provinciali di mais, soia e frumento, usate per controllare il modello"),
    ("arpa", "ARPA Lombardia", "pluviometri e temperature a terra, usati per controllare i dati satellitari"),
)


def chiave(lat: float, lon: float) -> str:
    return _cache.point_key(lat, lon)


def _processato(lat, lon) -> Path:
    """Cartella degli elaborati del punto SENZA crearla (``processed_dir`` la creerebbe)."""
    return config.PROCESSED_DIR / chiave(lat, lon)


def dati_mancanti(lat: float, lon: float) -> list[dict]:
    """Dati in cache che servono al motore e mancano per il punto. Lista vuota = punto utilizzabile."""
    d = _processato(lat, lon)
    k = chiave(lat, lon)
    mancanti = []
    cmd_power = f"python -m fieldwise.data.power --lat {lat} --lon {lon}"
    for f in ("power_daily.csv", "power_site.json"):
        if not (d / f).exists():
            mancanti.append({"cosa": "meteo giornaliero NASA POWER", "file": f"data/processed/{k}/{f}",
                             "comando": cmd_power})
    raw_suolo = config.RAW_DIR / "soilgrids" / k
    if not (d / "soilgrids_agg.csv").exists() and not (raw_suolo.is_dir() and any(raw_suolo.iterdir())):
        mancanti.append({"cosa": "suolo SoilGrids", "file": f"data/raw/soilgrids/{k}/",
                         "comando": f"python -m fieldwise.data.soilgrids --lat {lat} --lon {lon}"})
    return mancanti


def ensemble_in_cache(lat: float, lon: float) -> bool:
    d = _processato(lat, lon)
    return all((d / f).exists() for f in (_ens.FILE_DETTAGLIO, _ens.FILE_SINTESI, _ens.FILE_META))


@st.cache_resource(show_spinner="Preparo i dati del campo...")
def contesto(lat: float, lon: float):
    """Contesto del motore (meteo, suolo, parametri) per il punto: si costruisce una volta sola."""
    return rt.build_context(lat=lat, lon=lon)


@st.cache_data(show_spinner=False)
def colture_principali() -> list[str]:
    return rt.main_crops(_params.load_params())


def classe_attuale(etichetta: str) -> str:
    """Classe ciclica (etichetta canonica) a cui appartiene la rotazione attuale.

    Una ripetizione di una classe triennale ('mais') vale come la classe ('mais > mais > mais'), come in
    ``run_ensemble``. Serve solo a sapere se la sintesi in cache e' gia' marcata su questa rotazione."""
    r = _ens.parse_rotazione(etichetta)
    if r.n < 3 and 3 % r.n == 0:
        r = rt.Rotation(r.crops * (3 // r.n), r.cover * (3 // r.n))
    return r.canonical().label


@st.cache_data(show_spinner="Calcolo il confronto per la tua rotazione (circa 7 secondi)...")
def ensemble(lat: float, lon: float, attuale: str):
    """``(dettaglio, sintesi, meta)`` per il punto e la rotazione attuale.

    Usa la cache dell'ensemble se e' marcata sulla stessa rotazione attuale; altrimenti rifa' il
    calcolo (solo in memoria: la cache su disco non viene toccata)."""
    n_avv = 1
    if ensemble_in_cache(lat, lon):
        dett, sint = _ens.load_ensemble(lat, lon)
        meta = dict(sint.attrs["meta"])
        if meta.get("rotazione_attuale") == classe_attuale(attuale):
            return dett, sint, meta
        n_avv = int(meta.get("n_avviamento", 1))
    dett, sint = _ens.run_ensemble(contesto(lat, lon), lat=lat, lon=lon, rotazione_attuale=attuale,
                                   n_avviamento=n_avv)
    return dett, sint, dict(sint.attrs["meta"])


@st.cache_resource(show_spinner="Simulo la rotazione...")
def simula(lat: float, lon: float, etichetta: str, anno: int, scenario: str, n_avviamento: int):
    """Simulazione dettagliata di una rotazione in un'annata (con le serie giornaliere)."""
    return rt.simulate(contesto(lat, lon), rt.Rotation.from_label(etichetta), int(anno), scenario,
                       n_avviamento=n_avviamento, dettaglio=True)


@st.cache_data(show_spinner=False)
def meteo_giornaliero(lat: float, lon: float) -> pd.DataFrame:
    """Meteo del motore (solo dalla cache) con le colonne date, rain, et0, rain_trusted."""
    f = _weather.load_forcing(lat, lon)
    return f[["date", "rain", "et0", "tmax", "rain_trusted"]].copy()


@st.cache_data(show_spinner=False)
def validazione() -> dict | None:
    return _leggi_json(_processato(*PILOTA) / "validation_summary.json")


@st.cache_data(show_spinner=False)
def sensibilita() -> dict | None:
    """Riepilogo dell'analisi di sensibilita' se esiste (puo' non esserci)."""
    return _leggi_json(_processato(*PILOTA) / FILE_SENSIBILITA)


def _leggi_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


@st.cache_data(show_spinner=False)
def tabella_csv(nome: str) -> pd.DataFrame | None:
    p = _processato(*PILOTA) / nome
    try:
        return pd.read_csv(p) if p.exists() else None
    except (OSError, ValueError):
        return None


@st.cache_data(show_spinner=False)
def fonti_scaricate(lat: float, lon: float) -> list[dict]:
    """Per ogni fonte: data del primo e dell'ultimo download letta dai metadati in cache (se ci sono)."""
    out = []
    for cartella, nome, uso in FONTI:
        base = config.RAW_DIR / cartella
        dirs = [base / "cremona"] if cartella == "istat" else [base / chiave(lat, lon)]
        date, prodotti = [], set()
        for d in dirs:
            for m in (d.glob("*.meta.json") if d.is_dir() else []):
                try:
                    j = json.loads(m.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if j.get("downloaded_at_utc"):
                    date.append(str(j["downloaded_at_utc"])[:10])
                if j.get("product"):
                    prodotti.add(str(j["product"]))
        out.append({"nome": nome, "uso": uso, "prodotto": "; ".join(sorted(prodotti)[:3]),
                    "dal": min(date) if date else None, "al": max(date) if date else None})
    return out


def testo_data(iso: str | None) -> str:
    if not iso:
        return "non disponibile"
    a, m, g = iso.split("-")
    return f"{g}/{m}/{a}"


CacheMiss = _cache.CacheMiss
