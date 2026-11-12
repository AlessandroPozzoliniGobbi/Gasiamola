"""Infrastruttura comune per i prodotti NASA Earthdata (GES DISC, NSIDC DAAC).

Contenuto:

* ``login()``: autenticazione NON interattiva con earthaccess. Prova prima
  ``strategy="netrc"`` (file ``~/.netrc``, o quello indicato da ``NETRC``) e poi
  ``strategy="environment"`` (variabili ``EARTHDATA_TOKEN`` oppure
  ``EARTHDATA_USERNAME`` + ``EARTHDATA_PASSWORD``; nomi verificati nel codice di
  earthaccess 0.17.0). La strategia ``interactive`` non viene mai usata. Se nessuna
  funziona solleva ``EarthdataAuthError`` con le istruzioni in italiano. Le
  credenziali non vengono mai lette, stampate o scritte da questo modulo.
* ``search_granules()``: ricerca CMR con ``earthaccess.search_data`` (funziona anche
  senza login).
* ``opendap_url()`` e ``fetch_subset()``: sottoinsieme di una sola cella via OPeNDAP
  (Hyrax "OPeNDAP in the Cloud", ``opendap.earthdata.nasa.gov``), protocollo DAP4:
  ``<url granulo>.dap.nc4?dap4.ce=/variabile[i][j]``. La risposta e' un piccolo file
  netCDF-4 (qualche kB) invece del granulo intero.
* ``download_and_read()``: ultima risorsa, scarica il granulo intero, lo legge e lo
  cancella.
* ``run_parallel()`` e ``with_retry()``: parallelismo moderato (massimo 8 richieste
  insieme) e tentativi ripetuti con attesa crescente.
* ``write_year_file()`` / ``year_status()``: salvataggio riprendibile di un CSV grezzo
  per anno con ``cache.write_meta``.

Perche' OPeNDAP (via (a) del brief) invece del download: IMERG Final giornaliero V07
sono ~9 250 granuli da ~30 MB (~270 GB), SPL3SMP_E v006 sono ~3 850 granuli da
centinaia di MB (~2,4 TB secondo il campo ``granule_size`` di CMR). Per estrarre una
cella basta un sottoinsieme; il link OPeNDAP e' pubblicato da CMR come
"USE SERVICE API" in ogni granulo di entrambe le collezioni.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io
import os
import tempfile
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd

from . import cache

MAX_WORKERS = 8          # tetto massimo di richieste insieme (vincolo del brief)
DEFAULT_TRIES = 5
DEFAULT_WAIT_S = 2.0     # attesa iniziale, raddoppia a ogni tentativo

_AUTH_HELP = """\
Credenziali NASA Earthdata non trovate o rifiutate.

Cosa fare (una sola delle due strade):

1. File ~/.netrc (consigliato). Crea il file con questa riga, sostituendo utente e password:
       machine urs.earthdata.nasa.gov login <utente> password <password>
   poi proteggilo:
       chmod 600 ~/.netrc

2. Variabili d'ambiente (nella shell che lancia il comando):
       export EARTHDATA_USERNAME=<utente>
       export EARTHDATA_PASSWORD=<password>
   oppure, in alternativa, un token generato su urs.earthdata.nasa.gov (menu "Generate Token"):
       export EARTHDATA_TOKEN=<token>

L'account si crea gratis su https://urs.earthdata.nasa.gov. Dopo la registrazione, in
"Applications > Authorized Apps" vanno autorizzate le applicazioni
"NASA GESDISC DATA ARCHIVE" (per IMERG) e quella dell'NSIDC DAAC (per SMAP, nome
dell'applicazione contenente "NSIDC"): senza autorizzazione le richieste ricevono
errore 401/403 anche con credenziali corrette.
"""


class EarthdataAuthError(RuntimeError):
    """Login Earthdata impossibile (credenziali assenti o rifiutate)."""


class EarthdataRequestError(RuntimeError):
    """Richiesta di dati fallita dopo tutti i tentativi."""


# ----------------------------------------------------------------------------------
# login
# ----------------------------------------------------------------------------------

def login() -> Any:
    """Autentica con earthaccess (netrc, poi variabili d'ambiente). Mai interattivo.

    Restituisce l'oggetto ``earthaccess.Auth``. Solleva ``EarthdataAuthError``.
    """
    import earthaccess

    errors: list[str] = []
    for strategy in ("netrc", "environment"):
        try:
            auth = earthaccess.login(strategy=strategy)
        except Exception as exc:  # LoginStrategyUnavailable, LoginAttemptFailure, rete...
            # si riporta solo il tipo dell'errore, mai il messaggio completo: potrebbe
            # contenere percorsi o nomi utente
            errors.append(f"{strategy}: {type(exc).__name__}")
            continue
        if getattr(auth, "authenticated", False):
            return auth
        errors.append(f"{strategy}: non autenticato")
    raise EarthdataAuthError(_AUTH_HELP + "\nEsito dei tentativi: " + "; ".join(errors))


# ----------------------------------------------------------------------------------
# ricerca CMR
# ----------------------------------------------------------------------------------

def search_granules(short_name: str, version: str, start: str | dt.date,
                    end: str | dt.date) -> list[Any]:
    """Granuli CMR di un prodotto nel periodo [start, end] (estremi inclusi).

    Funziona anche senza login. Ritorna la lista di ``earthaccess.DataGranule``.
    """
    import earthaccess

    return with_retry(lambda: earthaccess.search_data(
        short_name=short_name, version=version,
        temporal=(str(start), str(end))), what=f"ricerca CMR {short_name}")


def granule_date(granule: Any) -> dt.date:
    """Data (UTC) di inizio del granulo."""
    rng = granule["umm"]["TemporalExtent"]["RangeDateTime"]
    return dt.date.fromisoformat(rng["BeginningDateTime"][:10])


def opendap_url(granule: Any) -> str:
    """URL OPeNDAP (Hyrax cloud) del granulo, dai RelatedUrls pubblicati da CMR."""
    for u in granule["umm"].get("RelatedUrls", []):
        url = u.get("URL", "")
        if u.get("Type") == "USE SERVICE API" and "opendap" in url:
            return url
    raise EarthdataRequestError(
        f"nessun link OPeNDAP nel granulo {granule['meta'].get('concept-id')}")


def granule_https_url(granule: Any) -> str:
    """URL HTTPS di download del granulo intero (tipo 'GET DATA')."""
    for u in granule["umm"].get("RelatedUrls", []):
        if u.get("Type") == "GET DATA" and u.get("URL", "").startswith("https"):
            return u["URL"]
    raise EarthdataRequestError("nessun link di download nel granulo")


# ----------------------------------------------------------------------------------
# nuovi tentativi e parallelismo
# ----------------------------------------------------------------------------------

def with_retry(fn: Callable[[], Any], *, tries: int = DEFAULT_TRIES,
               wait: float = DEFAULT_WAIT_S, what: str = "richiesta",
               sleep: Callable[[float], None] = time.sleep,
               no_retry: tuple[type[BaseException], ...] = ()) -> Any:
    """Esegue ``fn`` con attesa crescente (wait, 2*wait, 4*wait...) tra i tentativi."""
    last: BaseException | None = None
    for attempt in range(tries):
        try:
            return fn()
        except no_retry:
            raise
        except Exception as exc:
            last = exc
            if attempt < tries - 1:
                sleep(wait * (2 ** attempt))
    raise EarthdataRequestError(f"{what}: fallita dopo {tries} tentativi ({last!r})") from last


def run_parallel(func: Callable[[Any], Any], items: Iterable[Any],
                 workers: int = MAX_WORKERS) -> list[tuple[Any, Any, BaseException | None]]:
    """Applica ``func`` a ogni item con al massimo ``workers`` (<= 8) thread.

    Ritorna [(item, risultato, errore)]; non solleva per gli errori dei singoli item.
    """
    workers = max(1, min(int(workers), MAX_WORKERS))
    out: list[tuple[Any, Any, BaseException | None]] = []
    items = list(items)
    if not items:
        return out
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(func, it): it for it in items}
        try:
            for fut in as_completed(futs):
                it = futs[fut]
                try:
                    out.append((it, fut.result(), None))
                except Exception as exc:
                    out.append((it, None, exc))
        except BaseException:
            for f in futs:
                f.cancel()
            raise
    return out


# ----------------------------------------------------------------------------------
# sottoinsieme OPeNDAP (DAP4) e download di ripiego
# ----------------------------------------------------------------------------------

_local = threading.local()


def _session() -> Any:
    """Sessione HTTP autenticata di earthaccess, una per thread."""
    import earthaccess

    s = getattr(_local, "session", None)
    if s is None:
        s = earthaccess.get_requests_https_session()
        _local.session = s
    return s


def dap4_url(base: str, constraint: str) -> str:
    """Compone ``<base>.dap.nc4?dap4.ce=<constraint>`` (parentesi quadre non codificate)."""
    return f"{base}.dap.nc4?dap4.ce=" + urllib.parse.quote(constraint, safe="/[]:,;=_")


def fetch_subset(base_url: str, constraint: str, *, timeout: float = 120.0) -> bytes:
    """Scarica il sottoinsieme DAP4 (file netCDF-4 in memoria). Solleva su errore HTTP."""
    resp = _session().get(dap4_url(base_url, constraint), timeout=timeout)
    if resp.status_code in (401, 403):
        raise EarthdataAuthError(
            f"HTTP {resp.status_code} da {urllib.parse.urlsplit(base_url).netloc}: "
            "credenziali non valide o applicazione non autorizzata su urs.earthdata.nasa.gov.\n"
            + _AUTH_HELP)
    resp.raise_for_status()
    content = resp.content
    if not content.startswith(b"\x89HDF"):
        raise EarthdataRequestError(
            "risposta OPeNDAP non e' un file netCDF-4/HDF5 "
            f"(primi byte: {content[:60]!r})")
    return content


@contextlib.contextmanager
def open_h5_bytes(content: bytes):
    """Apre con h5py un file netCDF-4/HDF5 tenuto in memoria."""
    import h5py

    with h5py.File(io.BytesIO(content), "r") as f:
        yield f


def download_and_read(granule: Any, reader: Callable[[Path], Any]) -> Any:
    """Ultima risorsa: scarica il granulo intero in una cartella temporanea, lo legge
    con ``reader(path)`` e lo cancella subito."""
    import earthaccess

    with tempfile.TemporaryDirectory(prefix="fieldwise_granule_") as tmp:
        files = earthaccess.download([granule], tmp)
        if not files:
            raise EarthdataRequestError("download del granulo fallito")
        return reader(Path(files[0]))


# ----------------------------------------------------------------------------------
# CSV grezzo per anno, riprendibile
# ----------------------------------------------------------------------------------

def year_path(raw: Path, prefix: str, year: int) -> Path:
    return raw / f"{prefix}_{year}.csv"


def write_year_file(raw: Path, prefix: str, year: int, df: pd.DataFrame, *, source: str,
                    product: str, version: str, url: str, params: dict[str, Any],
                    complete: bool, notes: str | None = None) -> Path:
    """Scrive il CSV grezzo dell'anno (anche parziale) e il suo .meta.json."""
    path = year_path(raw, prefix, year)
    tmp = path.with_name(path.name + ".tmp")
    df.sort_values("date").to_csv(tmp, index=False)
    os.replace(tmp, path)
    p = dict(params)
    p.update(year=year, complete=complete, n_rows=int(len(df)))
    cache.write_meta(path, source=source, product=product, version=version, url=url,
                     params=p, notes=notes)
    return path


def year_status(raw: Path, prefix: str, year: int) -> tuple[pd.DataFrame | None, bool, dict]:
    """(dati gia' in cache dell'anno, anno completo?, meta). Senza meta -> (None, False, {})."""
    path = year_path(raw, prefix, year)
    if not cache.is_cached(path):
        return None, False, {}
    meta = cache.read_meta(path)
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.date
    return df, bool(meta.get("params", {}).get("complete")), meta


# ----------------------------------------------------------------------------------
# ciclo per anno, comune a IMERG e SMAP
# ----------------------------------------------------------------------------------

def _covers(meta: dict, y0: dt.date, y1: dt.date) -> bool:
    p = meta.get("params", {})
    try:
        ws = dt.date.fromisoformat(p["window_start"])
        we = dt.date.fromisoformat(p["window_end"])
    except (KeyError, ValueError):
        return False
    return ws <= y0 and we >= y1


def fetch_years(*, raw: Path, prefix: str, source: str, short_name: str, version: str,
                url: str, params: dict[str, Any], start: dt.date, end: dt.date,
                extract: Callable[[Any], dict[str, Any]], force: bool = False,
                workers: int = MAX_WORKERS, log: Callable[[str], None] = print,
                notes: str | None = None) -> pd.DataFrame:
    """Scarica (a riprese) i dati puntuali di ``short_name`` per anno e li ritorna uniti.

    Per ogni anno: se in cache c'e' un CSV completo che copre la finestra richiesta non si
    fa nulla (nemmeno la ricerca CMR); altrimenti si cercano i granuli e si estraggono
    solo quelli con data non ancora presente. ``extract(granule)`` deve restituire un dict
    con la chiave ``date`` (datetime.date). Il CSV dell'anno viene scritto a ogni anno,
    anche se parziale (``complete=false``), cosi' una interruzione non perde il lavoro.
    """
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    for year in range(start.year, end.year + 1):
        y0 = max(start, dt.date(year, 1, 1))
        y1 = min(end, dt.date(year, 12, 31))
        old, complete, meta = (None, False, {}) if force else year_status(raw, prefix, year)
        if old is not None and complete and _covers(meta, y0, y1):
            log(f"{year}: gia' completo in cache ({len(old)} giorni)")
            frames.append(old)
            continue
        granules = search_granules(short_name, version, y0, y1)
        by_date = {granule_date(g): g for g in granules}
        have = set(old["date"]) if old is not None else set()
        todo = [g for d, g in sorted(by_date.items()) if d not in have]
        log(f"{year}: {len(granules)} granuli CMR, {len(have)} gia' in cache, {len(todo)} da estrarre")
        rows: list[dict[str, Any]] = []
        errors: list[tuple[Any, BaseException]] = []
        try:
            for g, row, err in run_parallel(extract, todo, workers):
                if err is not None:
                    errors.append((g, err))
                else:
                    rows.append(row)
        finally:
            parts = [x for x in (old, pd.DataFrame(rows)) if x is not None and len(x)]
            df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["date"])
            df = df.drop_duplicates("date", keep="last")
            if len(df):
                ok = not errors and set(by_date) <= set(df["date"])
                p = dict(params)
                p.update(window_start=y0.isoformat(), window_end=y1.isoformat(),
                         n_granules_cmr=len(granules))
                write_year_file(raw, prefix, year, df, source=source, product=short_name,
                                version=version, url=url, params=p, complete=ok, notes=notes)
        for g, err in errors:
            if isinstance(err, EarthdataAuthError):
                raise err
        if todo and not rows and errors:
            raise EarthdataRequestError(
                f"{year}: tutte le {len(errors)} estrazioni sono fallite; ultimo errore: {errors[-1][1]!r}")
        for g, err in errors:
            failures.append(f"{granule_date(g)}: {err!r}")
        frames.append(df)
    if failures:
        log(f"ATTENZIONE: {len(failures)} granuli non estratti (rilanciare per riprovare); "
            f"primo errore: {failures[0]}")
    frames = [f for f in frames if len(f)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date"])
