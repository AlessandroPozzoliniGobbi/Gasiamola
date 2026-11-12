"""Client ISTAT (SDMX): rese provinciali di mais da granella, soia e frumento tenero.

Sorgente
    Servizio SDMX di ISTAT, https://esploradati.istat.it/SDMXWS/rest/
    Dataflow  IT1:101_1015_DF_DCSP_COLTIVAZIONI_2  v1.0
    "Superfici e produzione - dati in complesso - prov" (Agricoltura > Coltivazioni).
    Dimensioni: FREQ, REF_AREA (CL_ITTER107), DATA_TYPE (CL_TIPO_DATO5),
    TYPE_OF_CROP (CL_AGRI_MADRE), DESTINATION_WINEGRAPES (sempre ALL qui).

Codici usati (letti dalle codelist del dataflow, vedi structure_COLTIVAZIONI_2.xml in cache)
    REF_AREA      ITC4A = Cremona (provincia)
    TYPE_OF_CROP  MAIZE = mais (EN: grain maize, figlio di CEREAG "cereali per granella"),
                  SOYA = soia, COMMEAT = frumento tenero (EN: common wheat)
    DATA_TYPE     ART = superficie totale (ettari)
                  HP_Q_EXT = produzione raccolta (quintali)
                  TP_QUIN_EXT = produzione totale (quintali)
    Per queste tre colture il dataflow NON fornisce una resa: DATA_TYPE YIELDS_PROD e
    AVEYIELD_PERC esistono nella codelist ma non hanno osservazioni per Cremona.

Resa (t/ha)
    Calcolata qui: resa = produzione raccolta (HP_Q_EXT) x 0,1 / superficie totale (ART),
    con 1 quintale = 0,1 t. E' la resa alla raccolta su superficie totale seminata/investita
    (ART), non sulla superficie "in produzione". I metadati SDMX NON dichiarano a quale
    umidita' sia riferita la produzione (peso del prodotto cosi' com'e' alla raccolta):
    non e' quindi confrontabile alla lettera con una resa a umidita' standard. Le rese ISTAT
    sono stime esperte a livello provinciale (spesso numeri tondi in q/ha).

Copertura
    Il dataflow provinciale parte dal 2006. Prima non c'e' nulla di provinciale nel catalogo
    SDMX di ISTAT; il vecchio archivio agri.istat.it e' dismesso (reindirizza ad avvisi.istat.it,
    con errore TLS). Nessun dato precedente al 2006 e' stato inventato o preso da altre fonti.

Limite di frequenza
    ISTAT blocca l'IP per 1-2 giorni oltre 5 richieste/min. RateLimiter impone >= 15 s tra due
    richieste, tentativi compresi, anche tra processi diversi (istante salvato su file).
    Ogni risposta e' salvata in cache prima di essere elaborata e non viene mai richiesta due volte.

CLI:  python -m fieldwise.data.istat [--province Cremona] [--force]
"""
from __future__ import annotations

import argparse
import io
import time
from pathlib import Path

import pandas as pd
import requests

from . import cache

BASE_URL = "https://esploradati.istat.it/SDMXWS/rest/"
SOURCE = "istat"
AGENCY = "IT1"
DATAFLOW_ID = "101_1015_DF_DCSP_COLTIVAZIONI_2"
DATAFLOW_NAME = "Superfici e produzione - dati in complesso - prov"
DATAFLOW_VERSION = "1.0"
MIN_INTERVAL_S = 15.0
USER_AGENT = "fieldwise-research-client/0.1"
CSV_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0;charset=utf-8"

# provincia -> codice ITTER107 (NUTS3)
PROVINCE_CODES = {"Cremona": "ITC4A"}
# codice TYPE_OF_CROP -> nome della coltura nel progetto
CROPS = {"MAIZE": "mais", "SOYA": "soia", "COMMEAT": "frumento"}
AREA_TYPE = "ART"          # superficie totale, ettari
PROD_TYPE = "HP_Q_EXT"     # produzione raccolta, quintali
PROD_TOTAL_TYPE = "TP_QUIN_EXT"  # produzione totale, quintali
QUINTAL_T = 0.1            # 1 q = 0,1 t

COLUMNS = ["year", "crop", "area_ha", "production_t", "yield_t_ha", "dataflow", "note"]


class IstatError(RuntimeError):
    """Errore del servizio ISTAT (HTTP o contenuto inatteso)."""


class RateLimiter:
    """Garantisce almeno `min_interval` secondi tra due richieste, anche tra processi.

    L'ultimo istante di richiesta e' salvato su file (orologio di sistema), cosi' un
    nuovo processo avviato subito dopo un altro aspetta comunque.
    """

    def __init__(self, min_interval: float = MIN_INTERVAL_S, clock=time.time,
                 sleep=time.sleep, state_file: Path | None = None):
        self.min_interval = float(min_interval)
        self.clock = clock
        self.sleep = sleep
        self.state_file = Path(state_file) if state_file else None
        self._last: float | None = None

    def _read_last(self) -> float | None:
        if self._last is not None:
            return self._last
        if self.state_file and self.state_file.exists():
            try:
                return float(self.state_file.read_text().strip())
            except ValueError:
                return None
        return None

    def wait(self) -> float:
        """Blocca finche' sono passati min_interval secondi; registra l'istante. Ritorna l'attesa."""
        waited = 0.0
        last = self._read_last()
        if last is not None:
            remaining = self.min_interval - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
                waited = remaining
        self._last = self.clock()
        if self.state_file:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(repr(self._last))
        return waited


_LIMITER: RateLimiter | None = None


def limiter() -> RateLimiter:
    global _LIMITER
    state = cache.raw_dir(SOURCE, key="_ratelimit") / "last_request.txt"
    if _LIMITER is None or _LIMITER.state_file != state:
        _LIMITER = RateLimiter(MIN_INTERVAL_S, state_file=state)
    return _LIMITER


def http_get(url: str, accept: str = "application/xml", *, retries: int = 2,
             lim: RateLimiter | None = None, session=None) -> bytes:
    """GET con limitatore: ogni tentativo (anche i ritentativi) attende >= 15 s dal precedente.

    HTTP 403/429 = possibile blocco IP: ci si ferma subito, senza ritentare.
    """
    lim = lim or limiter()
    get = (session or requests).get
    last_err = ""
    for _ in range(retries + 1):
        lim.wait()
        try:
            r = get(url, headers={"Accept": accept, "User-Agent": USER_AGENT}, timeout=120)
        except requests.RequestException as exc:  # rete assente, timeout
            last_err = f"{type(exc).__name__}: {exc}"
            continue
        if r.status_code == 200:
            return r.content
        if r.status_code in (403, 429):
            raise IstatError(f"HTTP {r.status_code} da ISTAT (possibile blocco per frequenza): {url}")
        last_err = f"HTTP {r.status_code}"
        if r.status_code < 500:
            break
    raise IstatError(f"richiesta ISTAT fallita ({last_err}): {url}")


def _territory(province: str) -> str:
    try:
        return PROVINCE_CODES[province]
    except KeyError:
        raise ValueError(f"provincia non configurata: {province!r} (disponibili: {sorted(PROVINCE_CODES)})")


def data_url(province: str = "Cremona") -> str:
    """URL della richiesta filtrata: annuale, un solo territorio, tutti i tipi di dato e colture."""
    return f"{BASE_URL}data/{AGENCY},{DATAFLOW_ID},{DATAFLOW_VERSION}/A.{_territory(province)}..."


def raw_path(province: str = "Cremona") -> Path:
    return cache.raw_dir(SOURCE, key=province.lower()) / f"data_{_territory(province)}.csv"


def fetch(province: str = "Cremona", force: bool = False, *, session=None,
          lim: RateLimiter | None = None) -> Path:
    """Scarica (1 sola richiesta) le serie annuali della provincia nella cache grezza.

    Se il file e' gia' in cache con i metadati non rifa' la richiesta (salvo force=True).
    Ritorna il percorso del CSV SDMX grezzo.
    """
    path = raw_path(province)
    if cache.is_cached(path) and not force:
        return path
    cache.ensure_online(f"ISTAT {DATAFLOW_ID}")
    url = data_url(province)
    content = http_get(url, CSV_ACCEPT, session=session, lim=lim)
    if not content.lstrip().startswith(b"DATAFLOW,"):
        raise IstatError(f"risposta ISTAT inattesa (non CSV SDMX): {content[:120]!r}")
    path.write_bytes(content)  # grezzo in cache prima di qualsiasi elaborazione
    cache.write_meta(
        path, source=SOURCE, product=f"{DATAFLOW_NAME} ({DATAFLOW_ID})",
        version=DATAFLOW_VERSION, url=url,
        params={"agency": AGENCY, "dataflow": DATAFLOW_ID, "key": f"A.{_territory(province)}...",
                "format": "SDMX-CSV 1.0"},
        notes="Tutte le colture e i tipi di dato per il territorio; filtrato a valle.",
    )
    return path


def parse_sdmx_csv(text: str) -> pd.DataFrame:
    """Da CSV SDMX grezzo a tabella (year, crop, area_ha, production_t, yield_t_ha, dataflow, note)."""
    raw = pd.read_csv(io.StringIO(text), dtype=str)
    needed = {"DATAFLOW", "DATA_TYPE", "TYPE_OF_CROP", "TIME_PERIOD", "OBS_VALUE"}
    if not needed <= set(raw.columns):
        raise IstatError(f"colonne SDMX mancanti: {sorted(needed - set(raw.columns))}")
    raw = raw[raw["TYPE_OF_CROP"].isin(CROPS)].copy()
    raw["OBS_VALUE"] = pd.to_numeric(raw["OBS_VALUE"], errors="coerce")
    raw["year"] = pd.to_numeric(raw["TIME_PERIOD"], errors="coerce")
    raw = raw.dropna(subset=["year"])
    raw["year"] = raw["year"].astype(int)
    wide = raw.pivot_table(index=["TYPE_OF_CROP", "year"], columns="DATA_TYPE",
                           values="OBS_VALUE", aggfunc="first")
    flow = raw["DATAFLOW"].iloc[0] if len(raw) else f"IT1:{DATAFLOW_ID}({DATAFLOW_VERSION})"
    flow = flow.replace("IT1:", "")
    rows = []
    for (code, year), r in wide.iterrows():
        area = r.get(AREA_TYPE)
        harvested = r.get(PROD_TYPE)
        total = r.get(PROD_TOTAL_TYPE)
        notes = []
        prod_q = harvested
        if pd.isna(prod_q) and not pd.isna(total):
            prod_q = total
            notes.append("produzione raccolta assente: usata la produzione totale")
        if not pd.isna(harvested) and not pd.isna(total) and harvested != total:
            notes.append(f"produzione raccolta ({harvested:g} q) diversa dalla totale ({total:g} q)")
        area = float(area) if not pd.isna(area) else float("nan")
        prod_t = float(prod_q) * QUINTAL_T if not pd.isna(prod_q) else float("nan")
        yld = prod_t / area if area and not pd.isna(area) and not pd.isna(prod_t) else float("nan")
        notes.insert(0, "resa calcolata = produzione raccolta (q) x 0,1 / superficie totale (ha); "
                        "ISTAT non fornisce la resa; umidita' di riferimento non specificata")
        rows.append({"year": int(year), "crop": CROPS[code], "area_ha": area, "production_t": prod_t,
                     "yield_t_ha": yld, "dataflow": flow, "note": "; ".join(notes)})
    out = pd.DataFrame(rows, columns=COLUMNS)
    return out.sort_values(["crop", "year"]).reset_index(drop=True)


def load(province: str = "Cremona") -> pd.DataFrame:
    """Legge SOLO dalla cache (mai rete), scrive istat_yields.csv e restituisce la tabella."""
    path = cache.require(raw_path(province), hint="python -m fieldwise.data.istat")
    df = parse_sdmx_csv(path.read_text(encoding="utf-8"))
    out = cache.processed_dir(key=province.lower()) / "istat_yields.csv"
    df.to_csv(out, index=False)
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scarica e elabora le rese ISTAT provinciali.")
    ap.add_argument("--province", default="Cremona")
    ap.add_argument("--force", action="store_true", help="rifa' la richiesta anche se in cache")
    args = ap.parse_args(argv)
    p = fetch(args.province, force=args.force)
    df = load(args.province)
    print(f"grezzo: {p}")
    for crop, g in df.groupby("crop"):
        y = g["yield_t_ha"].dropna()
        print(f"{crop}: {g.year.min()}-{g.year.max()} ({len(g)} anni) resa t/ha "
              f"min {y.min():.2f} mediana {y.median():.2f} max {y.max():.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
