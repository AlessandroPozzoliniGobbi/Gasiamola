"""FIELDWISE - confronto di rotazioni colturali (app Streamlit).

Avvio:  .venv/bin/streamlit run app/streamlit_app.py
Tutta la logica sta in ``fieldwise.*``; qui ci sono solo l'interfaccia e la presentazione.
La demo funziona offline con i dati in cache: l'app non tenta mai la rete.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st  # noqa: E402

import fw_confronto  # noqa: E402
import fw_dati as dati  # noqa: E402
import fw_dettaglio  # noqa: E402
import fw_testi  # noqa: E402
from fieldwise import ranking  # noqa: E402
from fieldwise import rotation as rt  # noqa: E402
from fw_util import ET  # noqa: E402

PAGINE = ("Confronto", "Dettaglio di una annata", "Capire i dati", "Validazione", "Limiti e fonti")
ESEMPIO_PESO = 5

st.set_page_config(page_title="FIELDWISE - confronto di rotazioni", page_icon="🌾", layout="wide")
ss = st.session_state


def _punto_iniziale():
    if "_pending" in ss:                       # clic sulla mappa del giro precedente
        ss["lat"], ss["lon"] = ss.pop("_pending")
    ss.setdefault("lat", dati.PILOTA[0])
    ss.setdefault("lon", dati.PILOTA[1])


def _torna_al_pilota():
    ss["lat"], ss["lon"] = dati.PILOTA


def mappa(lat: float, lon: float):
    """Mappa per scegliere il campo con un clic. Se non si carica (niente rete) restano i campi numerici."""
    with st.expander("Scegli il campo sulla mappa", expanded=False):
        st.caption("Se la mappa non si vede (serve la connessione), scrivi latitudine e longitudine nella barra laterale.")
        try:
            import folium
            from streamlit_folium import st_folium
            m = folium.Map(location=[lat, lon], zoom_start=9)
            folium.Marker([lat, lon], tooltip="Campo scelto").add_to(m)
            res = st_folium(m, height=320, use_container_width=True, returned_objects=["last_clicked"], key="mappa")
        except Exception:  # la mappa e' un di piu': non deve mai bloccare l'app
            st.info("La mappa non è disponibile: usa i campi di latitudine e longitudine.")
            return
        c = (res or {}).get("last_clicked")
        if c:
            nuovo = (round(c["lat"], 3), round(c["lng"], 3))
            if nuovo != ss.get("_ultimo_clic"):
                ss["_ultimo_clic"] = nuovo
                ss["_pending"] = nuovo
                st.rerun()


def barra_laterale() -> dict:
    sb = st.sidebar
    sb.title("FIELDWISE")
    sb.warning("Strumento di confronto, non una prescrizione agronomica.")
    pagina = sb.radio("Pagina", PAGINE, key="pagina")

    sb.header("Il tuo campo")
    sb.number_input("Latitudine", min_value=-90.0, max_value=90.0, step=0.001, format="%.3f", key="lat")
    sb.number_input("Longitudine", min_value=-180.0, max_value=180.0, step=0.001, format="%.3f", key="lon")
    sb.button("Torna al punto pilota (Cremona)", on_click=_torna_al_pilota)

    sb.header("Rotazione attuale")
    colture = dati.colture_principali()
    n = sb.radio("Quante colture si alternano", (1, 2, 3), horizontal=True, key="n_colture",
                 help="Con una sola coltura è la monosuccessione: la stessa coltura ogni anno.")
    voci = []
    for i in range(n):
        c1, c2 = sb.columns([3, 2])
        col = c1.selectbox(f"Coltura {i + 1}", colture, index=min(i, len(colture) - 1) if i else 0, key=f"coltura_{i}")
        cov = c2.checkbox("+ cover", key=f"cover_{i}", help=f"Cover crop dopo {col}")
        voci.append(col + (rt.COVER_TAG if cov else ""))
    attuale = rt.SEP.join(voci)

    sb.header("Acqua")
    scenario = sb.selectbox("Scenario d'acqua", rt.SCENARI, index=rt.SCENARI.index("tetto_irriguo"),
                            format_func=lambda s: ET["scenari"][s], key="scenario")

    sb.header("Le tue priorità")
    sb.caption("I pesi servono solo a ordinare la classifica. Non cambiano le simulazioni.")
    pesi = {k: sb.slider(ET["priorita"][k], 0, 10, ESEMPIO_PESO, key=f"peso_{k}") for k in ranking.PRIORITA}

    sb.header("Disciplinare")
    solo = sb.checkbox("Solo rotazioni conformi al disciplinare", key="solo_conformi")
    regimi = list(ET["regimi"])
    regime = sb.selectbox("Quale disciplinare", regimi, index=regimi.index(ranking.REGIME_PREDEFINITO),
                          format_func=lambda r: ET["regimi"][r], key="regime")
    return {"pagina": pagina, "attuale": attuale, "scenario": scenario, "pesi": pesi, "solo_conformi": solo,
            "regime": regime}


def avviso_cache(lat: float, lon: float, mancanti: list[dict]):
    st.error(f"Per il punto latitudine {lat:.3f}, longitudine {lon:.3f} i dati non sono nella cache di questo "
             "computer, e l'app non scarica nulla da sola. Mostro il punto pilota (Cremona).")
    with st.expander("Quali dati mancano e come averli", expanded=True):
        for m in mancanti:
            st.markdown(f"- **{m['cosa']}**: manca `{m['file']}`")
        st.markdown("Per scaricarli serve la connessione a internet. Esegui, una volta, dalla cartella del progetto:")
        st.code("\n".join(dict.fromkeys(m["comando"] for m in mancanti)), language="bash")
        st.markdown("Poi calcola il confronto del punto con:")
        st.code(f"python -m fieldwise.ensemble --lat {lat} --lon {lon}", language="bash")


def main():
    _punto_iniziale()
    stato = barra_laterale()
    lat, lon = round(float(ss["lat"]), 3), round(float(ss["lon"]), 3)
    mancanti = dati.dati_mancanti(lat, lon)
    if mancanti:
        avviso_cache(lat, lon, mancanti)
        lat, lon = dati.PILOTA
    stato.update(lat=lat, lon=lon)

    pagina = stato["pagina"]
    if pagina in PAGINE[:2]:
        mappa(lat, lon)
    try:
        if pagina == "Confronto":
            fw_confronto.mostra(stato)
        elif pagina == "Dettaglio di una annata":
            fw_dettaglio.mostra(stato, fw_confronto.calcola(stato))
        elif pagina == "Capire i dati":
            fw_testi.capire()
        elif pagina == "Validazione":
            fw_testi.validazione()
        else:
            try:
                sintesi = fw_confronto.calcola(stato)["sint"]
            except Exception:
                sintesi = None
            fw_testi.limiti(sintesi, stato["scenario"])
    except dati.CacheMiss as e:
        st.error(f"Manca un dato in cache: {e}. Servono la rete e i comandi di download del progetto.")
    except RuntimeError as e:      # OfflineError: l'app e' offline per scelta
        st.error(f"Questa operazione richiederebbe la rete e l'app è offline: {e}")

    st.divider()
    st.caption("FIELDWISE confronta rotazioni con dati aperti e un modello semplificato. "
               "Non è una prescrizione agronomica, non è un prodotto di nessun ente che fornisce i dati "
               "e non ha la loro approvazione.")


main()
