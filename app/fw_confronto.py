"""Pagina "Confronto": rotazione attuale contro le alternative (tutta la logica e' in fieldwise.ranking)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import fw_dati as dati
from fieldwise import ranking
from fw_util import (AVVISO_FRUMENTO, AVVISO_HUMUS, AVVISO_PUNTEGGIO, COLORI, ET, PREFISSO_RESA_T_HA, RESA,
                     bella, differenza, nome_regime, num, pct, rese_t_ha, rese_t_ha_testo, segno,
                     stato_conformita, valore)

RUOLI = {
    "attuale": "Rotazione attuale",
    "migliore_punteggio_non_dominata": "Alternativa: la migliore per le tue priorità",
    "migliore_punteggio": "Alternativa: la migliore per le tue priorità",
    "migliore_rischio": "Alternativa: la più sicura nell'annata peggiore",
    "per_punteggio": "Altra alternativa",
}
INDICATORI_TABELLA = ("resa_rel_mediana", "resa_rel_min", "resa_rel_p10", "irrigazione_mm", "concime_kg_n",
                      "n_lisciviato_kg_n", "humus_t_ha", "giorni_caldo", "quota_oltre_limite_n")


def calcola(stato: dict):
    """Esegue il confronto. Restituisce un dizionario con ensemble, confronto e avvisi, oppure ``errore``."""
    dett, sint, meta = dati.ensemble(stato["lat"], stato["lon"], stato["attuale"])
    pesi, sc = stato["pesi"], stato["scenario"]
    kw = dict(solo_conformi=stato["solo_conformi"], regime=stato["regime"])
    try:
        punteggi = ranking.score(sint, pesi, sc, **kw)
        conf = ranking.confronta(sint, pesi, sc, n_alternative=2, **kw)
    except ValueError as e:
        return {"errore": str(e), "dett": dett, "sint": sint, "meta": meta}
    return {"dett": dett, "sint": sint, "meta": meta, "punteggi": punteggi, "conf": conf,
            "avviso": punteggi.attrs.get("avviso")}


def voci(conf: dict) -> list[dict]:
    return ([conf["attuale"]] if conf["attuale"] else []) + conf["alternative"]


def _etichetta_voce(v: dict, i: int) -> str:
    return "Attuale" if v["ruolo"] == "attuale" else f"Alternativa {i}"


def _scheda(v: dict, stato: dict, n_conf: int):
    val = v["valori"]
    with st.container(border=True):
        st.markdown(f"**{RUOLI.get(v['ruolo'], v['ruolo'])}**")
        st.markdown(f"### {bella(v['classe'])}")
        riga = [f"posizione {v['posizione']} su {n_conf}",
                f"disciplinare ({nome_regime(stato['regime'])}): **{stato_conformita(val, stato['regime'])}**"]
        if v["non_dominata"]:
            riga.append("nessun'altra rotazione la batte su tutti gli indicatori")
        st.caption(" · ".join(riga))
        rese = rese_t_ha_testo(val)
        if rese:
            st.caption(f"Resa mediana: {pct(val['resa_rel_mediana'])} del potenziale ({rese}).")
        if "frumento" in v["classe"]:
            st.warning(AVVISO_FRUMENTO)
        if v["evidenze"]:
            st.markdown("**A favore**")
            for f in v["evidenze"]:
                st.markdown(f"- {f}")
        if v["rischi"]:
            st.markdown("**Rischi e svantaggi**" if v["ruolo"] != "attuale" else "**Punti deboli**")
            for f in v["rischi"]:
                st.markdown(f"- {f}")


def _tabella(vs: list[dict]) -> pd.DataFrame:
    att = vs[0]["valori"] if vs and vs[0]["ruolo"] == "attuale" else None
    righe = []
    for col in INDICATORI_TABELLA:
        r = {"Indicatore": ET["indicatori"].get(col, col)}
        for i, v in enumerate(vs):
            nome = _etichetta_voce(v, i)
            x = v["valori"].get(col)
            r[nome] = valore(col, x)
            if att is not None and v["ruolo"] != "attuale":
                r[f"{nome}: differenza"] = differenza(col, x, att[col])
        righe.append(r)
        if col == "resa_rel_mediana":      # accanto alla resa relativa, la resa in t/ha per coltura
            for coltura in dict.fromkeys(c for v in vs for c in rese_t_ha(v["valori"])):
                r = {"Indicatore": f"Resa mediana del {coltura} (t/ha)"}
                for i, v in enumerate(vs):
                    x = v["valori"].get(f"{PREFISSO_RESA_T_HA}{coltura}")
                    r[_etichetta_voce(v, i)] = "—" if x is None or x != x else num(x, 1)
                    if att is not None and v["ruolo"] != "attuale":
                        a = att.get(f"{PREFISSO_RESA_T_HA}{coltura}")
                        ok = x is not None and x == x and a is not None and a == a
                        r[f"{_etichetta_voce(v, i)}: differenza"] = segno(x - a, 1) if ok else "—"
                righe.append(r)
    return pd.DataFrame(righe).set_index("Indicatore")


def _fattori(vs: list[dict]):
    fig = go.Figure()
    nomi = ("f_acqua", "f_caldo", "f_rotazione")
    asse = [ET["fattori"][k.removeprefix("f_")] for k in nomi]
    asse = [a.removeprefix("l'").removeprefix("il ").capitalize() for a in asse]
    for i, v in enumerate(vs):
        y = [100 * v["valori"][k] for k in nomi]
        fig.add_bar(x=asse, y=y, name=f"{_etichetta_voce(v, i)}: {bella(v['classe'])}",
                    marker_color=COLORI[i % len(COLORI)], text=[f"{t:.0f}%" for t in y], textposition="outside")
    fig.update_layout(barmode="group", height=360, margin=dict(t=30, b=10),
                      yaxis_title="resa mantenuta (100% = nessuna perdita)", yaxis_range=[0, 112],
                      legend=dict(orientation="h", y=-0.25))
    st.plotly_chart(fig, width="stretch")
    for i, v in enumerate(vs):
        lim = v["valori"].get("fattore_limitante")
        if lim in ET["fattori"]:
            st.markdown(f"- **{_etichetta_voce(v, i)}** ({bella(v['classe'])}): perde più resa per {ET['fattori'][lim]}.")


def _compromesso(r: dict, stato: dict, vs: list[dict]):
    inds = list(ranking.VERSI)
    c1, c2 = st.columns(2)
    x = c1.selectbox("Asse orizzontale", inds, index=inds.index("irrigazione_mm"), key="asse_x",
                     format_func=lambda c: ET["indicatori"].get(c, c))
    y = c2.selectbox("Asse verticale", inds, index=inds.index("resa_rel_mediana"), key="asse_y",
                     format_func=lambda c: ET["indicatori"].get(c, c))
    if x == y:
        st.info("Scegli due indicatori diversi.")
        return
    pf = ranking.pareto_front(r["sint"], stato["scenario"], indicatori=[x, y],
                              solo_conformi=stato["solo_conformi"], regime=stato["regime"])
    classi = {v["classe"]: (_etichetta_voce(v, i), COLORI[i % len(COLORI)]) for i, v in enumerate(vs)}
    fattore = {c: (100 if c in RESA else 1) for c in (x, y)}
    fig = go.Figure()
    for non_dom, nome, col, sz in ((False, "dominate (c'è di meglio)", "#b5b5b5", 8),
                                   (True, "non dominate", "#2c7fb8", 12)):
        d = pf[(pf["non_dominata"] == non_dom) & ~pf["classe"].isin(classi)]
        fig.add_scatter(x=d[x] * fattore[x], y=d[y] * fattore[y], mode="markers", name=nome,
                        text=[bella(c) for c in d["classe"]], hovertemplate="%{text}<extra></extra>",
                        marker=dict(color=col, size=sz, line=dict(width=1, color="white")))
    for c, (nome, col) in classi.items():
        d = pf[pf["classe"] == c]
        if d.empty:
            continue
        fig.add_scatter(x=d[x] * fattore[x], y=d[y] * fattore[y], mode="markers+text", name=nome,
                        text=[nome], textposition="top center", hovertemplate=bella(c) + "<extra></extra>",
                        marker=dict(color=col, size=16, symbol="star" if nome == "Attuale" else "diamond",
                                    line=dict(width=1, color="white")))

    def titolo(c):
        verso = "più alto è meglio" if ranking.VERSI[c] > 0 else "più basso è meglio"
        return f"{ET['indicatori'].get(c, c)} ({verso})"

    fig.update_layout(height=460, margin=dict(t=20, b=10), xaxis_title=titolo(x), yaxis_title=titolo(y),
                      legend=dict(orientation="h", y=-0.22))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"Rotazioni confrontate: {len(pf)}; non dominate (nessun'altra è migliore o pari su tutti e due "
               f"gli indicatori e meglio su almeno uno): {int(pf['non_dominata'].sum())}. "
               f"Un punto non dominato non è per forza la scelta giusta: dipende da cosa conta di più per te.")


def _distribuzione(r: dict, stato: dict, vs: list[dict]):
    det = r["dett"]
    det = det[det["scenario"] == stato["scenario"]]
    fig = go.Figure()
    for i, v in enumerate(vs):
        d = det[det["classe"] == v["classe"]]
        fig.add_box(y=100 * d["resa_rel_media"], name=_etichetta_voce(v, i), boxpoints="all", jitter=0.4,
                    pointpos=0, marker_color=COLORI[i % len(COLORI)], boxmean=True,
                    text=[f"annata {a}" for a in d["anno_valutato"]], hovertemplate="%{y:.0f}% %{text}<extra></extra>")
    fig.update_layout(height=420, margin=dict(t=20, b=10), showlegend=False,
                      yaxis_title="resa media della rotazione (% del potenziale)")
    st.plotly_chart(fig, width="stretch")
    a0, a1 = r["meta"].get("anni_valutati", [None, None])
    st.caption(f"Ogni punto è una simulazione con il meteo realmente avvenuto nelle annate dal {a0} al {a1}: "
               "mostra quanto può variare la resa da un'annata all'altra. "
               "È la stima del rischio. **Non sono previsioni del tempo**: nessuno sa che annata verrà.")
    st.markdown("Resa nel 10% delle annate peggiori (10° percentile): " + " · ".join(
        f"**{_etichetta_voce(v, i)}** {pct(v['valori']['resa_rel_p10'])}" for i, v in enumerate(vs)))


def mostra(stato: dict):
    r = calcola(stato)
    if "errore" in r:
        st.warning(f"Non posso fare il confronto: {r['errore']}. "
                   "Metti almeno una priorità sopra zero e controlla il filtro sul disciplinare.")
        return
    conf = r["conf"]
    vs = voci(conf)
    st.title("Confronto delle rotazioni")
    st.caption("Come cambiano acqua, concime, suolo e raccolto passando dalla rotazione che fai oggi ad altre. "
               "Uno strumento di confronto, non una prescrizione agronomica.")
    st.caption("I pesi delle priorità servono solo a ordinare la classifica: non cambiano le simulazioni.")
    if r["avviso"]:
        st.warning(f"Attenzione: {r['avviso']}. L'ordine mostrato non significa nulla: "
                   "cambia le priorità o lo scenario d'acqua.")
    note = [n for n in conf["note"] if n != ranking.AVVISO_NON_DISCRIMINA]
    for n in note:
        st.info(n[0].upper() + n[1:])
    if conf["attuale"] is None:
        st.warning("La rotazione attuale non è nel confronto: mostro solo le alternative.")
    if len(conf["alternative"]) < 2:
        st.warning("Con questi filtri ci sono meno di due alternative da confrontare.")
    st.caption(f"Confronto fatto su {conf['n_confrontate']} rotazioni, scenario «{ET['scenari'][stato['scenario']]}»"
               + ("; solo rotazioni conformi al disciplinare" if stato["solo_conformi"] else "") + ".")

    cols = st.columns(len(vs))
    for c, v in zip(cols, vs):
        with c:
            _scheda(v, stato, conf["n_confrontate"])

    st.subheader("Gli indicatori a confronto")
    st.dataframe(_tabella(vs), width="stretch")
    st.caption("Valori mediani su tutte le annate storiche. La resa è in % del potenziale della coltura; "
               "sotto, la stessa resa in tonnellate per ettaro per ogni coltura.")
    st.caption("Humus: " + AVVISO_HUMUS)

    st.subheader("Perché una rotazione perde resa")
    st.markdown("La resa è il potenziale della coltura moltiplicato per tre fattori: acqua, caldo e successione "
                "colturale (cosa è stato coltivato prima). Un fattore sotto il 100% è una perdita.")
    _fattori(vs)

    st.subheader("Il compromesso tra due indicatori")
    _compromesso(r, stato, vs)

    st.subheader("Quanto cambia da un'annata all'altra")
    _distribuzione(r, stato, vs)

    with st.expander("Classifica completa"):
        p = r["punteggi"].copy()
        t = pd.DataFrame({"Posizione": p["posizione"], "Rotazione": [bella(c) for c in p["classe"]],
                          "Punteggio": p["punteggio"].round(2),
                          "Disciplinare": [stato_conformita(row, stato["regime"]) for row in p.to_dict("records")],
                          "Irrigazione (mm)": p["irrigazione_mm"].round(0),
                          "Resa mediana": [pct(x) for x in p["resa_rel_mediana"]]})
        st.dataframe(t, hide_index=True, width="stretch")
        st.caption(AVVISO_PUNTEGGIO)
    return r
