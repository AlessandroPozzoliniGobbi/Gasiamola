"""Cache dei dati scaricati: percorsi, metadati di provenienza, modalita' offline.

Contratto per tutti i client in fieldwise.data:

* i file grezzi vanno in      data/raw/<sorgente>/<point_key>/...
* i file elaborati vanno in   data/processed/<point_key>/<nome>.csv
* ogni file grezzo ha accanto <file>.meta.json scritto con write_meta():
  data di download (UTC), prodotto, versione, URL, parametri della richiesta,
  dimensione e sha256. Senza meta il file non e' considerato valido.
* load() non tocca mai la rete; se la cache manca solleva CacheMiss.
* fetch() chiama ensure_online() prima di qualsiasi richiesta di rete.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from .. import config


class CacheMiss(FileNotFoundError):
    """Il dato non e' in cache e non si puo' (o non si deve) scaricare."""


class OfflineError(RuntimeError):
    """E' stata tentata una richiesta di rete con FIELDWISE_OFFLINE=1."""


def point_key(lat: float, lon: float) -> str:
    """Chiave di cartella per un punto, es. 'lat45.200_lon10.000'."""
    return f"lat{lat:.3f}_lon{lon:.3f}"


def raw_dir(source: str, lat: float | None = None, lon: float | None = None,
            key: str | None = None) -> Path:
    """Cartella dei grezzi di una sorgente; key sostituisce il punto (es. 'cremona')."""
    k = key if key is not None else point_key(lat, lon)
    d = config.RAW_DIR / source / k
    d.mkdir(parents=True, exist_ok=True)
    return d


def processed_dir(lat: float | None = None, lon: float | None = None,
                  key: str | None = None) -> Path:
    k = key if key is not None else point_key(lat, lon)
    d = config.PROCESSED_DIR / k
    d.mkdir(parents=True, exist_ok=True)
    return d


def meta_path(path: Path) -> Path:
    return path.with_name(path.name + ".meta.json")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_meta(path: Path, *, source: str, product: str, version: str, url: str,
               params: dict[str, Any] | None = None, notes: str | None = None) -> Path:
    """Scrive i metadati di provenienza accanto a un file grezzo appena scaricato."""
    path = Path(path)
    meta = {
        "file": path.name,
        "source": source,
        "product": product,
        "version": version,
        "url": url,
        "params": params or {},
        "downloaded_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "notes": notes,
    }
    mp = meta_path(path)
    mp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return mp


def read_meta(path: Path) -> dict[str, Any]:
    mp = meta_path(Path(path))
    if not mp.exists():
        raise CacheMiss(f"metadati mancanti per {path}")
    return json.loads(mp.read_text(encoding="utf-8"))


def is_cached(path: Path) -> bool:
    path = Path(path)
    return path.exists() and meta_path(path).exists()


def require(path: Path, hint: str = "") -> Path:
    """Restituisce path se e' in cache con i metadati, altrimenti CacheMiss."""
    if not is_cached(path):
        msg = f"dato non in cache: {path}"
        if hint:
            msg += f" - per scaricarlo: {hint}"
        raise CacheMiss(msg)
    return Path(path)


def ensure_online(what: str = "") -> None:
    """Da chiamare prima di ogni richiesta di rete."""
    if config.offline():
        raise OfflineError(f"FIELDWISE_OFFLINE=1: rete vietata ({what})")
