"""Ordinamento e confronto delle rotazioni secondo le priorita' dell'agricoltore.

I pesi dell'agricoltore entrano SOLO qui: il motore (`rotation.py`) e l'ensemble (`ensemble.py`)
non li conoscono. Tutto parte dalla ``sintesi`` di `ensemble.run_ensemble` (una riga per classe
ciclica e scenario).

* ``score``: punteggio relativo all'insieme confrontato, serve solo a ordinare.
* ``pareto_front``: rotazioni non dominate (nessuna e' migliore o pari su tutto e strettamente
  migliore su un indicatore).
* ``confronta``: rotazione attuale e alternative, con differenze, evidenze e rischi in italiano.
"""
from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Priorita' -> indicatori della sintesi, con verso (+1 = piu' alto e' meglio, -1 = piu' basso).
# E' una scelta di PRESENTAZIONE (come raggruppare gli indicatori in cinque domande che
# l'agricoltore capisce), non un parametro fisico del modello: non ha fonte e non entra nel motore.
# Una priorita' con piu' indicatori e' la media dei loro punteggi parziali con PESI UGUALI
# (dichiarato: 'suolo' = meta' variazione di humus, meta' azoto lisciviato).
# -----------------------------------------------------------------------------
PRIORITA = {
    "resa": (("resa_rel_mediana", +1),),
    "rischio": (("resa_rel_min", +1),),
    "acqua": (("irrigazione_mm", -1),),
    "concime": (("concime_kg_n", -1),),
    "suolo": (("humus_t_ha", +1), ("n_lisciviato_kg_n", -1)),
}
VERSI = {col: v for ind in PRIORITA.values() for col, v in ind}   # colonna -> verso
NESSUNO = "nessuno"              # valore di ``equivalente_a`` per le classi non equivalenti ad altre
AVVISO_NON_DISCRIMINA = "con queste priorita' e questo scenario le rotazioni non si distinguono"
PUNTEGGIO_NEUTRO = 0.5            # indicatore costante su tutte le rotazioni: non discrimina
TOL_PARETO = 1e-6                 # frazione della scala di un indicatore (il maggiore tra intervallo
                                  # max-min e valore assoluto massimo): differenze minori = parita'
REGIME_PREDEFINITO = "lombardia_impegno_quinquennale"   # disciplinare del punto pilota (Cremona)
STATI_CONFORMI = ("conforme",)
SOGLIA_EVIDENZA = 0.05            # variazione relativa minima per citare un indicatore (5%)
SOGLIA_FATTORE = 0.97             # sopra questa media un fattore di resa non "limita" davvero
SOGLIA_HUMUS = 0.05               # variazione minima dell'humus citata (t/ha all'anno)
# Etichette leggibili in italiano per l'interfaccia (indicatori, priorita', scenari, regimi, stati):
# nelle frasi e nelle tabelle per l'agricoltore non compaiono mai gli identificativi tecnici.
ETICHETTE = {
    "indicatori": {
        "resa_rel_mediana": "resa mediana (rispetto al potenziale)",
        "resa_rel_min": "resa media della rotazione nell'annata peggiore",
        "resa_rel_p10": "resa media della rotazione nelle annate sfavorevoli (10\u00b0 percentile)",
        "irrigazione_mm": "irrigazione (mm all'anno)", "concime_kg_n": "concime azotato (kg N/ha all'anno)",
        "n_lisciviato_kg_n": "azoto lisciviato (kg N/ha all'anno)",
        "humus_t_ha": "variazione di humus (t/ha all'anno)",
        "giorni_caldo": "giorni di stress da caldo all'anno", "ruscellamento_mm": "ruscellamento (mm all'anno)",
        "percolazione_mm": "percolazione (mm all'anno)", "deficit_n_kg_n": "carenza di azoto (kg N/ha all'anno)",
        "quota_oltre_limite_n": "annate con azoto sopra il limite normativo",
        "cover_realizzata_quota": "casi in cui la cover e' praticabile"},
    "priorita": {"resa": "resa", "rischio": "rischio (annata peggiore)", "acqua": "risparmio di acqua",
                 "concime": "risparmio di concime", "suolo": "salute del suolo"},
    "scenari": {"solo_pioggia": "solo pioggia", "tetto_irriguo": "irrigazione limitata",
                "irrigazione_libera": "irrigazione libera"},
    "regimi": {"lombardia_impegno_quinquennale": "Lombardia, impegno quinquennale",
               "lombardia_impegno_triennale_SRA01_2026": "Lombardia, impegno triennale (SRA01)",
               "emilia_romagna_impegno_quinquennale": "Emilia-Romagna, impegno quinquennale",
               "emilia_romagna_adesione_singola_coltura": "Emilia-Romagna, adesione per singola coltura"},
    "stati": {"conforme": "conforme", "conforme_solo_in_deroga": "conforme solo in deroga",
              "non_conforme": "non conforme", "non_valutabile": "non valutabile"},
    "fattori": {"acqua": "l'acqua", "caldo": "il caldo", "rotazione": "la successione colturale"},
}
_NOMI = {"resa_rel_mediana": "resa mediana", "resa_rel_min": "resa media della rotazione nell'annata peggiore",
         "irrigazione_mm": "irrigazione", "concime_kg_n": "concime azotato",
         "n_lisciviato_kg_n": "azoto lisciviato", "humus_t_ha": "bilancio dell'humus"}
_UNITA = {"irrigazione_mm": "mm", "concime_kg_n": "kg N/ha", "n_lisciviato_kg_n": "kg N/ha",
          "humus_t_ha": "t/ha all'anno"}
_PRIORITA_FATTORE = ETICHETTE["fattori"]


# =============================================================================
# Selezione dell'insieme confrontato
# =============================================================================
def _senza_equivalente(df: pd.DataFrame) -> pd.Series:
    if "equivalente_a" not in df.columns:
        return pd.Series(True, index=df.index)
    return df["equivalente_a"].isna() | df["equivalente_a"].isin(["", NESSUNO])


def _attuale(df: pd.DataFrame) -> pd.Series:
    if "attuale" not in df.columns:
        return pd.Series(False, index=df.index)
    return df["attuale"].astype(bool)


def _scenario(sintesi: pd.DataFrame, scenario: str) -> pd.DataFrame:
    df = sintesi[sintesi["scenario"] == scenario]
    if df.empty:
        raise ValueError(f"scenario {scenario!r} assente dalla sintesi "
                         f"(presenti: {sorted(sintesi['scenario'].unique())})")
    return df


def _colonna_conformita(df: pd.DataFrame, regime) -> str:
    col = "conformita" if regime is None else f"conformita_{regime}"
    if col not in df.columns:
        raise ValueError(f"regime {regime!r} sconosciuto: colonna {col!r} assente")
    return col


def insieme(sintesi: pd.DataFrame, scenario: str, solo_conformi: bool = False,
            regime: str | None = REGIME_PREDEFINITO, ammetti_deroga: bool = False,
            mantieni_attuale: bool = True, includi_equivalenti: bool = False) -> pd.DataFrame:
    """Righe dello scenario che formano l'insieme confrontato: escluse le classi senza
    simulazioni riuscite; con ``solo_conformi`` restano quelle ``conforme`` (anche
    ``conforme_solo_in_deroga`` se ``ammetti_deroga``) per il ``regime`` (``None`` = la piu'
    sfavorevole tra i regimi). La rotazione attuale resta comunque, per poterla confrontare. Le
    classi con ``equivalente_a`` valorizzato (cover mai praticate: risultati identici a quelli della
    classe indicata) sono escluse, salvo ``includi_equivalenti``: cosi' non ci sono pari merito
    arbitrari."""
    df = _scenario(sintesi, scenario)
    if "n_simulazioni" in df.columns:
        df = df[df["n_simulazioni"] > 0]
    if not includi_equivalenti:
        df = df[_senza_equivalente(df) | _attuale(df)]
    if solo_conformi:
        ok = STATI_CONFORMI + (("conforme_solo_in_deroga",) if ammetti_deroga else ())
        tieni = df[_colonna_conformita(df, regime)].isin(ok)
        if mantieni_attuale and "attuale" in df.columns:
            tieni = tieni | df["attuale"].astype(bool)
        df = df[tieni]
    return df.copy()


# =============================================================================
# Punteggio
# =============================================================================
def _normalizza(x: np.ndarray, verso: int) -> np.ndarray:
    """0..1 con 1 = migliore; costante -> ``PUNTEGGIO_NEUTRO``."""
    lo, hi = float(np.min(x)), float(np.max(x))
    if hi - lo <= 0.0:
        return np.full(len(x), PUNTEGGIO_NEUTRO)
    z = (x - lo) / (hi - lo)
    return z if verso > 0 else 1.0 - z


def _verifica_pesi(pesi: dict) -> dict:
    ignoti = set(pesi) - set(PRIORITA)
    if ignoti:
        raise ValueError(f"priorita' sconosciute: {sorted(ignoti)} (ammesse {list(PRIORITA)})")
    w = {k: float(pesi.get(k, 0.0)) for k in PRIORITA}
    if any((not math.isfinite(v)) or v < 0 for v in w.values()):
        raise ValueError("i pesi devono essere numeri finiti non negativi")
    if sum(w.values()) <= 0:
        raise ValueError("tutti i pesi sono nulli: indicare almeno una priorita' con peso > 0")
    return w


def score(sintesi: pd.DataFrame, pesi: dict, scenario: str, solo_conformi: bool = False,
          regime: str | None = REGIME_PREDEFINITO, ammetti_deroga: bool = False,
          includi_equivalenti: bool = False) -> pd.DataFrame:
    """Sintesi dello ``scenario`` ordinata per punteggio decrescente.

    Ogni indicatore (vedi ``PRIORITA``) e' normalizzato tra 0 e 1 con minimo e massimo
    sull'insieme delle rotazioni confrontate, nel verso giusto (1 = migliore); un indicatore
    costante su tutto l'insieme vale 0.5 per tutti. Il punteggio parziale di una priorita' e' la
    media dei suoi indicatori; ``punteggio`` = somma(peso x parziale) / somma(pesi). ``pesi``:
    {priorita': peso >= 0} (mancanti = 0; tutti nulli e' un errore).

    ATTENZIONE: il punteggio e' RELATIVO all'insieme confrontato (cambia se si aggiungono o
    tolgono rotazioni, o con ``solo_conformi``) e serve solo a ordinare: non e' una misura
    assoluta ne' confrontabile tra scenari. Colonne aggiunte: ``punt_<priorita'>``,
    ``punteggio``, ``posizione`` (1 = primo). Se tutti gli indicatori con peso positivo sono costanti
    (es. solo 'acqua' in 'solo_pioggia'), l'ordine e' alfabetico e non significa nulla: lo dice
    ``risultato.attrs['avviso']`` (assente altrimenti). Le classi equivalenti a un'altra (``equivalente_a``)
    sono escluse salvo ``includi_equivalenti=True``."""
    w = _verifica_pesi(pesi)
    df = insieme(sintesi, scenario, solo_conformi, regime, ammetti_deroga,
                 includi_equivalenti=includi_equivalenti)
    if df.empty:
        raise ValueError("nessuna rotazione da confrontare con questi filtri")
    for pr, inds in PRIORITA.items():
        parz = [_normalizza(df[c].to_numpy(float), v) for c, v in inds]
        df[f"punt_{pr}"] = np.mean(parz, axis=0)
    # se nessun indicatore pesato discrimina, l'ordine sarebbe solo alfabetico: lo si dichiara
    discriminano = [c for pr, inds in PRIORITA.items() if w[pr] > 0 for c, _ in inds
                    if np.ptp(df[c].to_numpy(float)) > 0]
    df["punteggio"] = sum(w[pr] * df[f"punt_{pr}"] for pr in PRIORITA) / sum(w.values())
    df = df.sort_values(["punteggio", "classe"], ascending=[False, True], kind="mergesort")
    df["posizione"] = np.arange(1, len(df) + 1)
    df = df.reset_index(drop=True)
    if not discriminano:
        df.attrs["avviso"] = AVVISO_NON_DISCRIMINA
    return df


# =============================================================================
# Fronte di Pareto
# =============================================================================
def pareto_front(sintesi: pd.DataFrame, scenario: str, indicatori=None,
                 tol: float = TOL_PARETO, includi_equivalenti: bool = False,
                 solo_conformi: bool = False, regime: str | None = REGIME_PREDEFINITO,
                 ammetti_deroga: bool = False) -> pd.DataFrame:
    """Righe dello ``scenario`` con la colonna booleana ``non_dominata``.

    Una rotazione A domina B se su tutti gli ``indicatori`` A e' almeno pari a B e su almeno uno e'
    strettamente migliore (nel verso di ``PRIORITA``). Due valori sono 'pari' se differiscono per
    meno di ``tol`` volte la scala (max tra intervallo e valore assoluto massimo) di quell'indicatore (default
    ``TOL_PARETO``): cosi' il rumore numerico non crea dominanze. ``indicatori``: colonne tra
    quelle di ``PRIORITA`` (default: tutte, cioe' sei). Le classi con ``equivalente_a`` valorizzato
    sono escluse salvo ``includi_equivalenti`` (restano pari a un'altra: sarebbero entrambe non
    dominate). ``solo_conformi``, ``regime`` e ``ammetti_deroga`` selezionano l'insieme come in
    ``score`` (via ``insieme``; l'attuale resta anche se non conforme)."""
    inds = list(VERSI) if indicatori is None else list(indicatori)
    ignoti = [c for c in inds if c not in VERSI]
    if ignoti:
        raise ValueError(f"indicatori senza verso dichiarato: {ignoti}")
    if not inds:
        raise ValueError("nessun indicatore")
    df = insieme(sintesi, scenario, solo_conformi, regime, ammetti_deroga,
                 includi_equivalenti=includi_equivalenti)
    return _marca_non_dominate(df, inds, tol)


def _marca_non_dominate(df: pd.DataFrame, inds: list, tol: float) -> pd.DataFrame:
    m = np.column_stack([df[c].to_numpy(float) * VERSI[c] for c in inds])     # piu' alto = meglio
    n = len(m)
    soglia = (tol * np.maximum(m.max(axis=0) - m.min(axis=0), np.abs(m).max(axis=0))
              if n else np.zeros(len(inds)))
    non_dom = np.ones(n, dtype=bool)
    for i in range(n):
        diff = m - m[i]       # righe j rispetto a i: positivo = j migliore di i
        domina = np.all(diff >= -soglia, axis=1) & np.any(diff > soglia, axis=1)
        domina[i] = False
        non_dom[i] = not domina.any()
    df["non_dominata"] = non_dom
    return df


# =============================================================================
# Confronto con la rotazione attuale
# =============================================================================
def _num(x, nd=2) -> str:
    return f"{x:.{nd}f}".replace("-", "−")


def _pct(x) -> str:
    return f"{x:+.0f}%".replace("-", "−")


def _differenze(riga: pd.Series, att: pd.Series | None) -> dict:
    """{indicatore: {'valore', 'attuale', 'assoluta', 'percentuale'}} rispetto all'attuale."""
    out = {}
    for c in VERSI:
        d = {"valore": float(riga[c])}
        if att is not None:
            a = float(att[c])
            d.update(attuale=a, assoluta=float(riga[c]) - a,
                     percentuale=(100.0 * (float(riga[c]) - a) / abs(a)) if abs(a) > 1e-12 else None)
        out[c] = d
    return out


def _evidenze_e_peggioramenti(riga, att, dif):
    """Frasi sui miglioramenti (evidenze) e sui peggioramenti (rischi) rispetto all'attuale; solo
    numeri presenti nella sintesi o differenze calcolate da essi."""
    ev, peg = [], []
    if att is None:
        ev.append(f"resa mediana {_num(riga['resa_rel_mediana'])} (rispetto al potenziale), "
                  f"irrigazione mediana {_num(riga['irrigazione_mm'], 0)} mm")
        fl = riga["fattore_limitante"]
        ev.append(f"il fattore che limita la resa e' {_PRIORITA_FATTORE[fl]}"
                  if fl in _PRIORITA_FATTORE and riga[f"f_{fl}"] < SOGLIA_FATTORE else "")
        return [e for e in ev if e], peg

    def aggiungi(col, migliora, frase):
        (ev if migliora else peg).append(frase)

    for col in ("irrigazione_mm", "concime_kg_n", "n_lisciviato_kg_n"):
        d = dif[col]
        nome, un = _NOMI[col], _UNITA[col]
        if d["percentuale"] is None:
            if abs(d["assoluta"]) > 1e-9:
                aggiungi(col, d["assoluta"] < 0,
                         f"{nome}: {_num(d['valore'], 0)} {un} invece di 0 {un}")
        elif abs(d["percentuale"]) >= 100 * SOGLIA_EVIDENZA:
            aggiungi(col, d["assoluta"] < 0,
                     f"{_pct(d['percentuale'])} di {nome} ({_num(d['attuale'], 0)} → {_num(d['valore'], 0)} {un})")
    for col in ("resa_rel_mediana", "resa_rel_min"):
        d, nome = dif[col], _NOMI[col]
        if d["percentuale"] is not None and abs(d["percentuale"]) >= 100 * SOGLIA_EVIDENZA:
            frase = f"{nome} {_num(d['attuale'])} → {_num(d['valore'])} ({_pct(d['percentuale'])})"
            if d["assoluta"] > 0:
                ev.append(frase)
            elif col != "resa_rel_min":      # il peggioramento della resa nell'annata peggiore sta in _rischi
                peg.append(frase)
    d = dif["humus_t_ha"]
    if abs(d["assoluta"]) >= SOGLIA_HUMUS:
        aggiungi("humus_t_ha", d["assoluta"] > 0,
                 f"humus: {_num(d['valore'])} t/ha all'anno invece di {_num(d['attuale'])}")
    fl = riga["fattore_limitante"]
    if fl in _PRIORITA_FATTORE and riga[f"f_{fl}"] < SOGLIA_FATTORE:
        if fl == att["fattore_limitante"]:
            ev.append(f"il fattore che limita la resa e' {_PRIORITA_FATTORE[fl]}, come nella rotazione attuale")
        else:
            ev.append(f"il fattore che limita la resa e' {_PRIORITA_FATTORE[fl]} "
                      f"(nell'attuale: {_PRIORITA_FATTORE.get(att['fattore_limitante'], att['fattore_limitante'])})")
    return ev, peg


def _stato(riga, regime) -> str:
    col = "conformita" if regime is None else f"conformita_{regime}"
    return riga[col] if col in riga.index else riga["conformita"]


_GRAVITA = {"conforme": 0, "conforme_solo_in_deroga": 1, "non_conforme": 2, "non_valutabile": 3}


def _evidenze_extra(riga, att, regime) -> list:
    """Miglioramenti rispetto all'attuale che non sono differenze numeriche degli indicatori principali."""
    ev = []
    if att is None:
        return ev
    if riga["quota_oltre_limite_n"] < att["quota_oltre_limite_n"]:
        ev.append(f"il limite normativo di azoto e' superato in meno annate: "
                  f"{riga['quota_oltre_limite_n'] * 100:.0f}% invece di {att['quota_oltre_limite_n'] * 100:.0f}%")
    s_alt, s_att = _stato(riga, regime), _stato(att, regime)
    if s_alt == "conforme" and s_att in ("non_conforme", "conforme_solo_in_deroga"):
        ev.append(f"conforme al disciplinare di produzione integrata, mentre l'attuale e' "
                  f"{ETICHETTE['stati'][s_att]}")
    return ev


def _rischi(riga, att, peggioramenti, regime) -> list:
    """Rischi della rotazione. Un miglioramento rispetto all'attuale non e' mai un rischio: se la resa
    dell'annata peggiore o la quota di annate oltre il limite di azoto migliorano, stanno nelle evidenze."""
    r = []
    if att is None:
        r.append(f"nell'annata peggiore la resa media della rotazione scende a {_num(riga['resa_rel_min'])}")
    elif riga["resa_rel_min"] < att["resa_rel_min"]:
        r.append(f"nell'annata peggiore la resa media della rotazione scende a {_num(riga['resa_rel_min'])} "
                 f"(attuale: {_num(att['resa_rel_min'])})")
    q_n = riga["quota_oltre_limite_n"]
    if q_n > 0 and (att is None or q_n >= att["quota_oltre_limite_n"]):
        extra = "" if att is None else f" (attuale: {att['quota_oltre_limite_n'] * 100:.0f}%)"
        r.append(f"in {q_n * 100:.0f}% delle annate almeno una coltura supera il limite normativo di azoto{extra}")
    stato = _stato(riga, regime)
    reg = "" if regime is None else f" ({ETICHETTE['regimi'].get(regime, regime)})"
    if stato == "non_conforme":
        r.append("non conforme al disciplinare di produzione integrata" + reg)
    elif stato == "conforme_solo_in_deroga":
        r.append("conforme al disciplinare solo in deroga" + reg)
    elif stato == "non_valutabile":
        r.append("conformita' al disciplinare non valutabile per questa successione")
    q = riga["cover_realizzata_quota"] if "cover_realizzata_quota" in riga.index else float("nan")
    if q == q and q < 1.0:        # q = NaN se nessuna cover e' richiesta
        r.append(f"la cover e' praticabile nel {q * 100:.0f}% dei casi: negli altri l'intervallo resta a suolo nudo")
    r += [f"rispetto all'attuale: {p}" for p in peggioramenti]
    return r


def _dict_riga(riga: pd.Series) -> dict:
    return {k: (v.item() if hasattr(v, "item") else v) for k, v in riga.items()}


def confronta(sintesi: pd.DataFrame, pesi: dict, scenario: str, n_alternative: int = 2,
              solo_conformi: bool = False, regime: str | None = REGIME_PREDEFINITO,
              ammetti_deroga: bool = False, includi_equivalenti: bool = False) -> dict:
    """Rotazione attuale (se marcata nella sintesi) e alternative.

    La prima alternativa e' la migliore per punteggio tra le non dominate e diverse dall'attuale
    (se nessuna e' non dominata, la migliore per punteggio, con una nota); la seconda e' la
    migliore sulla priorita' 'rischio' tra le altre (se e' la stessa della prima, la seconda per
    punteggio); le eventuali successive (``n_alternative`` > 2) seguono il punteggio. Il punteggio e'
    relativo all'insieme confrontato (vedi ``score``). Con ``solo_conformi`` le alternative sono
    solo rotazioni conformi per ``regime``; l'attuale resta anche se non conforme.

    Restituisce {'scenario', 'attuale', 'alternative', 'n_non_dominate', 'n_confrontate', 'note'};
    ogni voce ha 'ruolo', 'classe', 'punteggio', 'posizione', 'non_dominata', 'valori' (riga della
    sintesi), 'differenze' (per indicatore: valore, attuale, assoluta, percentuale), 'evidenze' e
    'rischi' (liste di frasi)."""
    if n_alternative < 1:
        raise ValueError("n_alternative deve essere >= 1")
    sc = score(sintesi, pesi, scenario, solo_conformi, regime, ammetti_deroga, includi_equivalenti)
    avviso = sc.attrs.get("avviso")
    sc = _marca_non_dominate(sc, list(VERSI), TOL_PARETO)
    is_att = sc["attuale"].astype(bool) if "attuale" in sc.columns else pd.Series(False, index=sc.index)
    att = sc[is_att].iloc[0] if is_att.any() else None
    cand = sc[~is_att]
    if att is not None and "equivalente_a" in cand.columns:     # mai proporre l'attuale con un altro nome
        cand = cand[(cand["classe"] != att.get("equivalente_a")) & (cand["equivalente_a"] != att["classe"])]
    note = []
    scelte = []                    # (ruolo, riga)
    if len(cand):
        nd = cand[cand["non_dominata"]]
        if len(nd):
            prima = nd.iloc[0]
            ruolo1 = "migliore_punteggio_non_dominata"
        else:
            prima = cand.iloc[0]
            ruolo1 = "migliore_punteggio"
            note.append("nessuna alternativa e' non dominata: scelta la migliore per punteggio")
        scelte.append((ruolo1, prima))
        resto = cand[cand["classe"] != prima["classe"]]
        if n_alternative >= 2 and len(resto):
            rischio = resto.sort_values(["resa_rel_min", "punteggio"], ascending=[False, False], kind="mergesort")
            scelte.append(("migliore_rischio", rischio.iloc[0]))
        extra = resto[~resto["classe"].isin([r["classe"] for _, r in scelte])]
        for _, r in extra.head(max(0, n_alternative - len(scelte))).iterrows():
            scelte.append(("per_punteggio", r))
    else:
        note.append("nessuna alternativa nell'insieme confrontato")
    if avviso:
        note.append(avviso)
    if att is None:
        grezza = _scenario(sintesi, scenario)
        senza_sim = grezza[(grezza["n_simulazioni"] == 0) & _attuale(grezza)] if "attuale" in grezza.columns else grezza.iloc[0:0]
        if len(senza_sim):
            note.append("la rotazione attuale non ha simulazioni riuscite in questo scenario: confronto assoluto")
        else:
            note.append("rotazione attuale non marcata nella sintesi: confronto assoluto")
    for n in (sintesi.attrs.get("meta") or {}).get("note", []):
        note.append(n)

    def voce(ruolo, riga):
        dif = _differenze(riga, att)
        ev, peg = _evidenze_e_peggioramenti(riga, att, dif)
        ev = ev + _evidenze_extra(riga, att, regime)
        return {"ruolo": ruolo, "classe": riga["classe"], "punteggio": float(riga["punteggio"]),
                "posizione": int(riga["posizione"]), "non_dominata": bool(riga["non_dominata"]),
                "valori": _dict_riga(riga), "differenze": dif, "evidenze": ev,
                "rischi": _rischi(riga, att, peg, regime)}

    out_att = None
    if att is not None:
        out_att = {"ruolo": "attuale", "classe": att["classe"], "punteggio": float(att["punteggio"]),
                   "posizione": int(att["posizione"]), "non_dominata": bool(att["non_dominata"]),
                   "valori": _dict_riga(att), "differenze": _differenze(att, None), "evidenze": [],
                   "rischi": _rischi(att, None, [], regime)}
    return {"scenario": scenario, "attuale": out_att,
            "alternative": [voce(r, x) for r, x in scelte],
            "n_non_dominate": int(sc["non_dominata"].sum()), "n_confrontate": int(len(sc)),
            "note": note}


def numeri_in_frase(frase: str) -> list:
    """Numeri (senza segno) citati in una frase: serve ai test per verificare che vengano dalla sintesi."""
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", frase.replace("−", "-"))]


__all__ = ["PRIORITA", "VERSI", "score", "pareto_front", "confronta", "insieme", "numeri_in_frase",
           "REGIME_PREDEFINITO", "TOL_PARETO", "PUNTEGGIO_NEUTRO"]
