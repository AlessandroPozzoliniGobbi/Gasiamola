"""Piccole funzioni di presentazione condivise dalle pagine (nessuna logica di dominio)."""
from __future__ import annotations

from fieldwise import ranking

ET = ranking.ETICHETTE
COLORI = ("#444444", "#1b9e77", "#d95f02", "#7570b3", "#e7298a")   # attuale, poi le alternative
RESA = ("resa_rel_mediana", "resa_rel_min", "resa_rel_p10")        # indicatori in frazione (1 = potenziale)


AVVISO_PUNTEGGIO = "Il punteggio è relativo alle rotazioni confrontate: serve solo a ordinarle."
AVVISO_FRUMENTO = ("Per il frumento il modello non rappresenta le perdite degli anni umidi (malattie, piante "
                   "coricate, ristagni), quindi la sua resa è ottimistica: non leggerla come un indicatore di rischio.")
AVVISO_HUMUS = ("Gli effluenti zootecnici (letame, liquame) non sono modellati: in un'azienda con stalla "
                "la variazione di humus può essere migliore.")
PREFISSO_RESA_T_HA = "resa_t_ha_"       # colonne della sintesi: resa mediana in t/ha di una coltura


def rese_t_ha(valori: dict) -> dict:
    """{coltura: resa mediana in t/ha} dalle colonne ``resa_t_ha_<coltura>`` di una riga della sintesi
    (solo le colture presenti nella rotazione)."""
    out = {}
    for k, x in valori.items():
        if k.startswith(PREFISSO_RESA_T_HA) and x is not None and x == x:
            out[k.removeprefix(PREFISSO_RESA_T_HA)] = float(x)
    return out


def rese_t_ha_testo(valori: dict) -> str:
    """'mais 14,4 t/ha · soia 3,5 t/ha' (stringa vuota se la sintesi non ha le rese per coltura)."""
    return " · ".join(f"{c} {num(x, 1)} t/ha" for c, x in rese_t_ha(valori).items())


def bella(etichetta: str) -> str:
    """'mais > soia+cover' -> 'mais → soia + cover crop'."""
    return etichetta.replace("+cover", " + cover crop").replace(" > ", " → ")


def num(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace("-", "−").replace(".", ",")


def pct(x: float, nd: int = 0) -> str:
    return f"{100 * x:.{nd}f}%".replace("-", "−").replace(".", ",")


def segno(x: float, nd: int = 1) -> str:
    return f"{x:+.{nd}f}".replace("-", "−").replace(".", ",")


def valore(col: str, x: float) -> str:
    """Valore di un indicatore della sintesi nelle sue unita' (la resa e' in % del potenziale)."""
    if x is None or x != x:
        return "n.d."
    if col in RESA or col.startswith("quota_"):
        return pct(x)
    if col == "humus_t_ha":
        return num(x, 2)
    return num(x, 0 if col in ("irrigazione_mm", "concime_kg_n") else 1)


def differenza(col: str, x: float, att: float) -> str:
    """Differenza rispetto all'attuale: punti percentuali per le rese, unita' dell'indicatore altrimenti."""
    d = x - att
    if col in RESA or col.startswith("quota_"):
        return segno(100 * d, 1) + " punti"
    if col == "humus_t_ha":
        return segno(d, 2)
    return segno(d, 0 if col in ("irrigazione_mm", "concime_kg_n") else 1)


def stato_conformita(valori: dict, regime: str | None) -> str:
    col = "conformita" if regime is None else f"conformita_{regime}"
    return ET["stati"].get(valori.get(col, "non_valutabile"), "non valutabile")


def nome_regime(regime: str | None) -> str:
    return "il più severo tra i disciplinari" if regime is None else ET["regimi"].get(regime, regime)
