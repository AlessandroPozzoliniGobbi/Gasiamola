"""Pagina "Dettaglio di una annata": calendario, acqua, azoto giorno per giorno."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import fw_confronto as confronto
import fw_dati as dati
from fw_util import COLORI, ET, bella, num, pct


def _gg(iso: str | None) -> str:
    if not iso:
        return "—"
    a, m, g = str(iso)[:10].split("-")
    return f"{g}/{m}/{a}"


def _calendario(out: dict) -> pd.DataFrame:
    righe = []
    for c in out["colture"]:
        righe.append({"Periodo": f"Coltura: {c['coltura']}", "Dal": _gg(c["semina"]), "Al": _gg(c["raccolta"]),
                      "Note": f"fioritura il {_gg(c['fioritura'])}; resa {num(c['resa'], 1)} t/ha su "
                              f"{num(c['resa_potenziale'], 1)} t/ha possibili"})
    for iv in out["intervalli"]:
        if iv["tipo"] == "cover":
            nota = f"cover crop seminata il {_gg(iv['cover_semina'])}, terminata il {_gg(iv['cover_terminazione'])}"
        else:
            nota = "terreno nudo" + (" (la cover era richiesta ma non è praticabile)" if iv["cover_richiesta"] else "")
        if iv["avvertenze"]:
            nota += "; avvertenze: " + "; ".join(iv["avvertenze"])
        righe.append({"Periodo": f"Dopo {iv['dopo']}", "Dal": _gg(iv["inizio"]), "Al": _gg(iv["fine"]), "Note": nota})
    return pd.DataFrame(righe).sort_values("Dal", key=lambda s: pd.to_datetime(s, format="%d/%m/%Y")
                                           ).reset_index(drop=True)


def _grafici(lat: float, lon: float, out: dict):
    ac, az, segs = out["acqua"], out["azoto_giornaliero"], out["segmenti"]
    date = pd.date_range(dati.contesto(lat, lon).date(segs[0].start), periods=len(ac.tr))
    ok = (date >= pd.Timestamp(out["inizio"])) & (date <= pd.Timestamp(out["fine"]))
    d = date[ok]
    fig = make_subplots(rows=5, cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        subplot_titles=("Acqua nel suolo (mm)", "Traspirazione ed evaporazione (mm al giorno)",
                                        "Pioggia e irrigazione (mm al giorno)",
                                        "Azoto minerale nel suolo (kg N/ha)", "Azoto perso con l'acqua (kg N/ha al giorno)"))
    fig.add_scatter(x=d, y=(ac.w1 + ac.w2)[ok], name="acqua nel suolo", line=dict(color="#2c7fb8"), row=1, col=1)
    fig.add_scatter(x=d, y=ac.tr[ok], name="traspirazione (dalle foglie)", line=dict(color="#1b9e77"), row=2, col=1)
    fig.add_scatter(x=d, y=ac.ev[ok], name="evaporazione (dal suolo)", line=dict(color="#d95f02"), row=2, col=1)
    fig.add_bar(x=d, y=ac.rain[ok], name="pioggia", marker_color="#9ecae1", row=3, col=1)
    fig.add_bar(x=d, y=ac.irr[ok], name="irrigazione", marker_color="#08519c", row=3, col=1)
    fig.add_scatter(x=d, y=az.n_min[ok], name="azoto minerale", line=dict(color="#7570b3"), row=4, col=1)
    fig.add_bar(x=d, y=az.l[ok], name="azoto lisciviato", marker_color="#e7298a", row=5, col=1)
    for k, s in enumerate(segs):
        if s.kind != "coltura":
            continue
        t0, t1 = date[s.start - segs[0].start], date[s.end - segs[0].start]
        if t1 < d[0] or t0 > d[-1]:
            continue
        for r in range(1, 6):
            fig.add_vrect(x0=max(t0, d[0]), x1=min(t1, d[-1]), fillcolor="#1b9e77", opacity=0.07, line_width=0,
                          row=r, col=1)
        fig.add_annotation(x=t0 + (t1 - t0) / 2, y=1.0, yref="paper", text=s.crop, showarrow=False, yanchor="bottom")
    fig.update_layout(height=900, barmode="stack", margin=dict(t=60, b=10), legend=dict(orientation="h", y=-0.06))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Le fasce verdi sono i periodi in cui la coltura è in campo.")


def _azoto(out: dict) -> pd.DataFrame:
    return pd.DataFrame([{
        "Coltura": c["coltura"], "Concime (kg N/ha)": round(c["concime"], 0),
        "Fissato dalla pianta (kg N/ha)": round(c["fissazione"], 0),
        "Perso con l'acqua (kg N/ha)": round(c["lisciviazione"], 1),
        "Carenza di azoto (kg N/ha)": round(c["deficit_n"], 1),
        "Sopra il limite di legge": "sì" if c["supera_mas"] else "no"} for c in out["colture"]])


def mostra(stato: dict, risultato: dict | None):
    st.title("Una rotazione in una annata")
    if risultato is None or "conf" not in risultato:
        st.warning("Prima serve un confronto valido: controlla le priorità nella barra laterale.")
        return
    vs = confronto.voci(risultato["conf"])
    det, meta, sc = risultato["dett"], risultato["meta"], stato["scenario"]
    nomi = {f"{('Attuale' if v['ruolo'] == 'attuale' else f'Alternativa {i}')}: {bella(v['classe'])}": v["classe"]
            for i, v in enumerate(vs)}
    scelta = st.selectbox("Rotazione", list(nomi))
    classe = nomi[scelta]
    d = det[(det["scenario"] == sc) & (det["etichetta"] == classe)]
    if d.empty:
        d = det[(det["scenario"] == sc) & (det["classe"] == classe)]
    if d.empty:
        st.warning("Nessuna annata simulata per questa rotazione e questo scenario.")
        return
    anni = d.sort_values("anno_valutato")[["anno_valutato", "anno_partenza", "etichetta"]].drop_duplicates("anno_valutato")
    anno = st.selectbox("Annata (anno in cui finisce il ciclo valutato)", anni["anno_valutato"].tolist(),
                        index=len(anni) - 1)
    riga = anni[anni["anno_valutato"] == anno].iloc[0]
    out = dati.simula(stato["lat"], stato["lon"], riga["etichetta"], int(riga["anno_partenza"]), sc,
                      int(meta.get("n_avviamento", 1)))
    if out["esito"] != "ok":
        st.warning(f"Questa simulazione non è disponibile: {out['motivo']}")
        return
    ind = out["indicatori"]
    st.caption(f"Ciclo valutato dal {_gg(out['inizio'])} al {_gg(out['fine'])}, scenario «{ET['scenari'][sc]}». "
               "Meteo realmente avvenuto in quegli anni.")
    c = st.columns(5)
    c[0].metric("Resa media", pct(ind["resa_relativa_media"]), help="In % del potenziale della coltura")
    c[1].metric("Irrigazione", f"{num(ind['irrigazione_anno'], 0)} mm/anno")
    c[2].metric("Concime", f"{num(ind['concime_anno'], 0)} kg N/ha/anno")
    c[3].metric("Azoto perso", f"{num(ind['n_lisciviato_anno'], 1)} kg N/ha/anno")
    c[4].metric("Humus", f"{num(ind['humus_variazione_anno'], 2)} t/ha/anno")

    st.subheader("Calendario")
    st.dataframe(_calendario(out), hide_index=True, use_container_width=True)
    st.subheader("Giorno per giorno")
    _grafici(stato["lat"], stato["lon"], out)
    st.subheader("Azoto per coltura")
    st.dataframe(_azoto(out), hide_index=True, use_container_width=True)
    st.caption("Il bilancio dell'azoto non è stato confrontato con misure: leggilo come un ordine di grandezza.")
