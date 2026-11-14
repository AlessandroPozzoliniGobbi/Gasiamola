"""Margine su concime e acqua di una rotazione (ranking 'profitto').

Margine = ricavo della granella - costo del concime azotato - costo dell'irrigazione, in EUR/ha
all'anno, sul ciclo valutato di ``rotation.simulate``. Sono i soli costi che il modello simula:
seme, difesa, meccanizzazione e costi fissi non entrano (scelta dichiarata). Il valore assoluto non
e' un margine lordo aziendale e non va confrontato con un bilancio: serve a ordinare le rotazioni.

Prezzi e costi unitari stanno in ``params/economia.yaml`` (prezzi statici, con fonte o assunzione).

    margine/anno = (sum_i resa_i * prezzo_i) / anni
                   - concime_kg_n/anno * prezzo_N - irrigazione_mm/anno * costo_mm
"""
from __future__ import annotations

from . import params as _params


def prezzo_coltura(p: dict, coltura: str) -> float:
    """Prezzo della granella in EUR/t (``economia.prezzi_eur_t.<coltura>``)."""
    return float(_params.get(p, f"economia.prezzi_eur_t.{coltura}"))


def ricavo_anno(p: dict, colture: list[dict], anni: float) -> float:
    """Ricavo medio annuo (EUR/ha): somma resa (t/ha) x prezzo sulle colture del ciclo / anni del ciclo."""
    if anni <= 0:
        raise ValueError(f"durata del ciclo non valida: {anni}")
    return sum(float(c["resa"]) * prezzo_coltura(p, c["coltura"]) for c in colture) / anni


def costo_concime_anno(p: dict, concime_kg_n_anno: float) -> float:
    """Costo annuo del concime azotato (EUR/ha)."""
    return float(concime_kg_n_anno) * float(_params.get(p, "economia.azoto_eur_kg_n"))


def costo_irrigazione_anno(p: dict, irrigazione_mm_anno: float) -> float:
    """Costo annuo dell'irrigazione (EUR/ha)."""
    return float(irrigazione_mm_anno) * float(_params.get(p, "economia.irrigazione_eur_mm"))


def margine_anno(p: dict, out: dict) -> float:
    """Margine su concime e acqua (EUR/ha all'anno) dall'uscita di ``rotation.simulate``.

    Usa ``out['colture']`` (resa per coltura del ciclo valutato), ``out['durata_anni']`` e gli
    indicatori ``concime_anno`` e ``irrigazione_anno``. Ogni coltura compare una volta per ciclo:
    una coltura ripetuta nella rotazione conta una volta per ogni segmento.
    """
    ind = out["indicatori"]
    return (ricavo_anno(p, out["colture"], out["durata_anni"])
            - costo_concime_anno(p, ind["concime_anno"])
            - costo_irrigazione_anno(p, ind["irrigazione_anno"]))


__all__ = ["prezzo_coltura", "ricavo_anno", "costo_concime_anno", "costo_irrigazione_anno", "margine_anno"]
