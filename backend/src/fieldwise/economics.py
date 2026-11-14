"""Margine economico di una rotazione (ranking 'profitto').

Margine = ricavo della granella - concime azotato - irrigazione - altri costi colturali, in EUR/ha
all'anno, sul ciclo valutato di ``rotation.simulate``. Concime e irrigazione vengono dalle quantita'
simulate; gli altri costi (seme, difesa, lavorazioni, raccolta, essiccazione, trasporti) sono un costo
per ettaro coltivato di ciascuna coltura, con valori di partenza in ``params/economia.yaml`` che
l'agricoltore puo' sostituire con i propri (``ricalcola_margine``). Affitto, ammortamenti e contributi
PAC non entrano: sono uguali per tutte le rotazioni e si annullano nella differenza rispetto a oggi.

    margine/anno = sum_i (resa_i * prezzo_i - altri_costi_i) / anni
                   - concime_kg_n/anno * prezzo_N - irrigazione_mm/anno * costo_mm
"""
from __future__ import annotations

import collections

import pandas as pd

from . import params as _params

COL_MARGINE = "margine_lordo_eur_ha"
COL_RICAVO = "ricavo_eur_ha"
COL_CONCIME = "costo_concime_eur_ha"
COL_IRRIGAZIONE = "costo_irrigazione_eur_ha"
COL_ALTRI = "costo_altri_eur_ha"
PREFISSO_COLTURE_ANNO = "colture_anno_"     # + coltura: ettari coltivati con quella coltura per ettaro e per anno
COLONNE = (COL_RICAVO, COL_CONCIME, COL_IRRIGAZIONE, COL_ALTRI, COL_MARGINE)


def prezzo_coltura(p: dict, coltura: str) -> float:
    """Prezzo della granella in EUR/t (``economia.prezzi_eur_t.<coltura>``)."""
    return float(_params.get(p, f"economia.prezzi_eur_t.{coltura}"))


def altri_costi_coltura(p: dict, coltura: str) -> float:
    """Costi colturali non simulati in EUR/ha coltivato (``economia.altri_costi_eur_ha.<coltura>``)."""
    return float(_params.get(p, f"economia.altri_costi_eur_ha.{coltura}"))


def ricavo_anno(p: dict, colture: list[dict], anni: float) -> float:
    """Ricavo medio annuo (EUR/ha): somma resa (t/ha) x prezzo sulle colture del ciclo / anni del ciclo."""
    if anni <= 0:
        raise ValueError(f"durata del ciclo non valida: {anni}")
    return sum(float(c["resa"]) * prezzo_coltura(p, c["coltura"]) for c in colture) / anni


def colture_per_anno(colture: list[dict], anni: float) -> dict:
    """{coltura: volte che e' coltivata nel ciclo / anni del ciclo}."""
    if anni <= 0:
        raise ValueError(f"durata del ciclo non valida: {anni}")
    n = collections.Counter(c["coltura"] for c in colture)
    return {c: k / anni for c, k in n.items()}


def costo_concime_anno(p: dict, concime_kg_n_anno: float) -> float:
    """Costo annuo del concime azotato (EUR/ha)."""
    return float(concime_kg_n_anno) * float(_params.get(p, "economia.azoto_eur_kg_n"))


def costo_irrigazione_anno(p: dict, irrigazione_mm_anno: float) -> float:
    """Costo annuo dell'irrigazione (EUR/ha)."""
    return float(irrigazione_mm_anno) * float(_params.get(p, "economia.irrigazione_eur_mm"))


def componenti(p: dict, out: dict, colture_principali=()) -> dict:
    """Ricavo, costi e margine (EUR/ha all'anno) dall'uscita di ``rotation.simulate``, piu' le colonne
    ``colture_anno_<coltura>`` (0 se la coltura non c'e') che servono a ricalcolare gli altri costi.

    Ogni coltura compare una volta per ciclo: una coltura ripetuta conta una volta per ogni segmento."""
    ind, anni = out["indicatori"], out["durata_anni"]
    per_anno = colture_per_anno(out["colture"], anni)
    r = {COL_RICAVO: ricavo_anno(p, out["colture"], anni),
         COL_CONCIME: costo_concime_anno(p, ind["concime_anno"]),
         COL_IRRIGAZIONE: costo_irrigazione_anno(p, ind["irrigazione_anno"]),
         COL_ALTRI: sum(k * altri_costi_coltura(p, c) for c, k in per_anno.items())}
    r[COL_MARGINE] = r[COL_RICAVO] - r[COL_CONCIME] - r[COL_IRRIGAZIONE] - r[COL_ALTRI]
    for c in dict.fromkeys([*colture_principali, *per_anno]):
        r[f"{PREFISSO_COLTURE_ANNO}{c}"] = per_anno.get(c, 0.0)
    return r


def margine_anno(p: dict, out: dict) -> float:
    """Margine (EUR/ha all'anno) dall'uscita di ``rotation.simulate``."""
    return componenti(p, out)[COL_MARGINE]


def costi_predefiniti(p: dict, colture) -> dict:
    """{coltura: altri costi di partenza in EUR/ha} dai parametri."""
    return {c: altri_costi_coltura(p, c) for c in colture}


def ricalcola_margine(sintesi: pd.DataFrame, altri_costi: dict) -> pd.DataFrame:
    """Copia della sintesi con ``costo_altri_eur_ha`` e ``margine_lordo_eur_ha`` ricalcolati con gli altri
    costi indicati ({coltura: EUR/ha coltivato}). Ricavo, concime e irrigazione restano quelli simulati
    (medie sulle annate): il margine e' lineare nei costi, quindi la media resta esatta."""
    s = sintesi.copy()
    altri = pd.Series(0.0, index=s.index)
    for c, costo in altri_costi.items():
        col = f"{PREFISSO_COLTURE_ANNO}{c}"
        if col not in s.columns:
            raise KeyError(f"colonna mancante nella sintesi: {col} (rigenerare l'ensemble)")
        altri = altri + s[col].fillna(0.0) * float(costo)
    s[COL_ALTRI] = altri
    s[COL_MARGINE] = s[COL_RICAVO] - s[COL_CONCIME] - s[COL_IRRIGAZIONE] - s[COL_ALTRI]
    return s


__all__ = ["COL_MARGINE", "COL_RICAVO", "COL_CONCIME", "COL_IRRIGAZIONE", "COL_ALTRI", "PREFISSO_COLTURE_ANNO",
           "COLONNE", "prezzo_coltura", "altri_costi_coltura", "ricavo_anno", "colture_per_anno",
           "costo_concime_anno", "costo_irrigazione_anno", "componenti", "margine_anno", "costi_predefiniti",
           "ricalcola_margine"]
