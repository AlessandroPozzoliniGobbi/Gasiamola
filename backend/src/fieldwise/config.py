"""Percorsi e costanti condivise da tutto il progetto.

Nessun parametro agronomico vive qui: quelli stanno in params/*.yaml.
"""
from __future__ import annotations

import os
from pathlib import Path

# radice del repository: .../src/fieldwise/config.py -> due livelli sopra src/
ROOT = Path(os.environ.get("FIELDWISE_ROOT", Path(__file__).resolve().parents[2]))

PARAMS_DIR = ROOT / "params"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = ROOT / "reports"
FIGURE_DIR = REPORTS_DIR / "figure"

# campo dimostrativo (provincia di Cremona); modificabile dall'utente
PILOT_LAT = 45.2
PILOT_LON = 10.0
PILOT_PROVINCE = "Cremona"

# periodo di riferimento dei dati
START_YEAR = 2000
END_YEAR = 2025


def offline() -> bool:
    """True se la rete e' vietata (demo): i client devono usare solo la cache."""
    return os.environ.get("FIELDWISE_OFFLINE", "0") not in ("0", "", "false", "False")
