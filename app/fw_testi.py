"""Pagine di spiegazione: "Capire i dati", "Validazione", "Limiti e fonti".

Ogni numero viene da file in cache o dai risultati del modello (riepiloghi JSON/CSV del punto pilota);
le frasi sono scritte a mano ma non contengono numeri propri.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

import fw_dati as dati
from fieldwise import config, ranking
from fw_util import AVVISO_FRUMENTO, ET, bella, num, pct

AVVISO = ("Questo è uno strumento di confronto, non una prescrizione agronomica. "
          "Le scelte sul tuo campo vanno discusse con un tecnico.")


def _r(c: dict | None, chiave: str = "pearson") -> str:
    if not c:
        return "n.d."
    ic = c.get(f"{chiave}_ic95")
    s = f"r = {c[chiave]:+.2f}".replace(".", ",").replace("-", "−")
    if ic:
        s += f" (intervallo al 95%: da {ic[0]:+.2f} a {ic[1]:+.2f})".replace(".", ",").replace("-", "−")
    return s


# ---------------------------------------------------------------------------------------------
def capire():
    st.title("Capire i dati")
    st.caption("Spiegazioni semplici, con esempi presi dal campo dimostrativo (provincia di Cremona).")
    lat, lon = dati.PILOTA
    try:
        m = dati.meteo_giornaliero(lat, lon)
    except dati.CacheMiss:
        m = None
    m_ok = m[m["rain_trusted"].astype(bool)].copy() if m is not None else None
    if m_ok is not None:
        m_ok["anno"] = pd.to_datetime(m_ok["date"]).dt.year
        m_ok["mese"] = pd.to_datetime(m_ok["date"]).dt.month

    st.header("Evapotraspirazione di riferimento (ET0)")
    st.markdown(
        "- È l'acqua che in un giorno un prato verde e ben bagnato perde nell'aria.\n"
        "- Una parte evapora dal terreno, una parte esce dalle foglie.\n"
        "- Si misura in millimetri. 1 mm è 1 litro su ogni metro quadro.\n"
        "- Serve da metro: ogni coltura ne usa una parte, che cambia con la sua fase di crescita.\n"
        "- Non si misura in campo. Si calcola da temperatura, sole, umidità dell'aria e vento.")
    if m_ok is not None and len(m_ok):
        anni = m_ok.groupby("anno").agg(et0=("et0", "sum"), pioggia=("rain", "sum"))
        luglio = m_ok[m_ok["mese"] == 7]["et0"].mean()
        estate = m_ok[m_ok["mese"].isin([6, 7, 8])].groupby("anno").agg(et0=("et0", "sum"), pioggia=("rain", "sum"))
        st.info(f"**Esempio dal campo.** Negli anni {anni.index.min()}–{anni.index.max()} l'ET0 media è stata "
                f"{num(anni['et0'].mean(), 0)} mm all'anno. A luglio sono {num(luglio, 1)} mm al giorno. "
                f"In giugno, luglio e agosto l'ET0 è in media {num(estate['et0'].mean(), 0)} mm, "
                f"mentre di pioggia ne cadono {num(estate['pioggia'].mean(), 0)} mm. "
                "Per questo in estate le colture hanno sete e l'irrigazione fa la differenza.")

    st.header("Umidità del suolo e il satellite SMAP")
    st.markdown(
        "- L'umidità del suolo dice quanta acqua c'è nel terreno.\n"
        "- Si scrive in m³/m³: litri d'acqua ogni litro di terra (0,1 vuol dire 10 litri ogni 100 litri di terra).\n"
        "- Le radici pescano l'acqua in profondità. La parte alta del terreno si bagna e si asciuga in fretta.\n"
        "- Il satellite SMAP misura solo i primi 5 centimetri circa. Passa ogni due o tre giorni.\n"
        "- Ogni misura vale per un quadrato di circa 9 km di lato. Dentro ci sono campi, strade, boschi e case.\n"
        "- Non dice quanta acqua hanno le radici del tuo campo. Dice se l'annata e il mese sono più asciutti o più umidi del solito.")
    smap = dati.tabella_csv("smap_daily.csv")
    v = dati.validazione()
    if smap is not None and "sm_good_mean" in smap:
        s = smap["sm_good_mean"].dropna()
        extra = ""
        c = next((x for x in (v or {}).get("smap", {}).get("confronti", [])
                  if x["configurazione"] == "mais continuo" and x["scenario"] == "tetto_irriguo"
                  and x["periodo"] == "principale"), None)
        if c:
            extra = (f" Il confronto mese per mese con il modello dà {_r(c['anomalie'])}: "
                     "i mesi più asciutti del solito coincidono.")
        st.info(f"**Esempio dal campo.** Su {len(s)} giorni di misure buone, SMAP vede in media "
                f"{num(s.mean(), 2)} m³/m³, cioè {num(100 * s.mean(), 0)} litri d'acqua ogni 100 litri di terra. "
                f"Nei giorni più asciutti scende a {num(s.min(), 2)}, in quelli più bagnati sale a {num(s.max(), 2)}."
                + extra)

    st.header("NDVI: quanto è verde il campo")
    st.markdown(
        "- L'NDVI è un numero tra 0 e 1 che dice quanto è verde e rigogliosa la vegetazione vista dall'alto.\n"
        "- Terra nuda: valori bassi. Foglie verdi e fitte: valori alti.\n"
        "- Lo misura il satellite MODIS ogni 16 giorni circa, su quadrati di circa 250 metri.\n"
        "- Una coltura in sofferenza per la siccità ingiallisce e l'NDVI scende.\n"
        "- Non distingue il mais dalla soia. Quando le foglie sono molto fitte il numero non sale più.")
    nd = dati.tabella_csv("validation_ndvi_annuale.csv")
    if nd is not None and len(nd):
        nd = nd.set_index("anno")["ndvi_lug_ago"]
        casi = sorted(((v or {}).get("ndvi", {}).get("casi") or {}).keys())
        anno = int(casi[0]) if casi else int(nd.idxmin())
        st.info(f"**Esempio dal campo.** A luglio e agosto l'NDVI della zona è in media {num(nd.median(), 2)} "
                f"({nd.index.min()}–{nd.index.max()}). Nel {anno}, anno di forte siccità, è sceso a "
                f"{num(nd.loc[anno], 2)}. Il valore più basso in assoluto è del {int(nd.idxmin())} ({num(nd.min(), 2)}).")

    st.header("Dato da satellite e misura a terra")
    st.markdown(
        "- Il satellite vede tutto il territorio, ma guarda da lontano e fa una media su un'area grande.\n"
        "- Il pluviometro a terra misura bene, ma solo in quel punto.\n"
        "- Per questo i dati satellitari si controllano sempre con le misure a terra, quando ci sono.")
    q = dati.tabella_csv("qc_rain_annual.csv")
    if q is not None:
        a = q[q["reference"] == "ARPA"].set_index("year")
        vecchi, nuovi = a[a.index <= 2022], a[a.index >= 2023]
        anni_ok = dati.anni_affidabili()
        y_ok = int(vecchi.index.max())
        y_ko = int(nuovi.index.min()) if len(nuovi) else y_ok + 1
        a22 = a.loc[y_ok]
        a24 = nuovi.loc[nuovi["power_total_mm"].idxmax()] if len(nuovi) else None
        txt = (f"**Esempio reale: la pioggia.** Nel {y_ok} NASA POWER ha stimato {num(a22['power_total_mm'], 0)} mm di pioggia, "
               f"il pluviometro ARPA ne ha misurati {num(a22['ref_total_mm'], 0)} mm: vicinissimi. ")
        if a24 is not None:
            txt += (f"Nel {int(a24.name)} invece POWER dice {num(a24['power_total_mm'], 0)} mm e il pluviometro "
                    f"{num(a24['ref_total_mm'], 0)} mm. ")
        txt += (f"Dal {int(vecchi.index.min())} al {y_ok} il rapporto medio tra POWER e pluviometro è {num(vecchi['ratio'].mean(), 2)} "
                f"(1 vuol dire uguali). Dal {y_ko} al {int(nuovi.index.max()) if len(nuovi) else y_ok} sale a {num(nuovi['ratio'].mean(), 2)}: "
                "il dato satellitare segna molta più pioggia di quella che è caduta. "
                "Altri quattro pluviometri confermano lo stesso salto, quindi non è un problema di una sola stazione.")
        st.info(txt)
        st.markdown(
            f"**Per questo le annate dal {y_ko} sono escluse.** Non sapremmo dire quali siano giuste. "
            "Meglio perdere qualche anno che sporcare tutti i confronti con pioggia sbagliata. "
            f"Il modello usa solo le annate dal {anni_ok[0]} al {anni_ok[1]}.")
        giorni = a[a.index <= 2022]
        st.markdown(f"Un altro difetto: POWER segna pioggia nel {num(giorni['wet_freq_power_pct'].mean(), 0)}% dei giorni, "
                    f"il pluviometro nel {num(giorni['wet_freq_ref_pct'].mean(), 0)}%. Troppa pioggerella, "
                    "poche piogge forti. Il modello lo sa e lo dichiara tra i limiti.")
    st.caption(AVVISO)


# ---------------------------------------------------------------------------------------------
def _istat(v: dict, colt: str, scen: str, sim: str = "monosuccessione") -> dict | None:
    return next(((c["detrend"]) for c in v["istat"]["confronti"]
                 if c["coltura"] == colt and c["scenario"] == scen and c["simulazione"] == sim), None)


def validazione():
    st.title("Validazione: quanto ci si può fidare")
    v = dati.validazione()
    if not v:
        st.warning("Il riepilogo della validazione non è nella cache (validation_summary.json).")
        return
    rapp = v["metodo"]["scenario_rappresentativo"]
    st.markdown(
        "Abbiamo confrontato le simulazioni con quello che è davvero successo nelle annate passate "
        "(umidità da satellite, verde da satellite, rese provinciali). "
        "Un buon accordo non prova che il modello sia giusto. Un cattivo accordo dice dove non fidarsi. "
        f"Per le rese si usa lo scenario «{ET['scenari'][rapp]}» (scelto prima di guardare i risultati) "
        "perché in provincia mais e soia sono per lo più irrigati.")
    punto = v["punto"]
    st.caption(f"Punto pilota: latitudine {punto['lat']}, longitudine {punto['lon']}. I risultati valgono per questa zona.")

    smap = next((c for c in v["smap"]["confronti"] if c["configurazione"] == "mais continuo"
                 and c["scenario"] == rapp and c["periodo"] == "principale"), None)
    ndvi = next((c for c in v["ndvi"]["confronti"] if c["indicatore"] == "ndvi_lug_ago" and c["scenario"] == rapp), None)
    casi = ", ".join(sorted(v["ndvi"]["casi"]))
    mais, soia = _istat(v, "mais", rapp), _istat(v, "soia", rapp)
    fru = _istat(v, "frumento", "solo_pioggia")

    st.subheader("Cosa è confermato")
    st.success(
        f"**Umidità della parte alta del suolo.** Mese per mese, le variazioni rispetto al solito seguono quelle "
        f"misurate da SMAP: {_r(smap['anomalie']) if smap else 'n.d.'}.\n\n"
        f"**Anni secchi.** Il modello e il satellite (NDVI) riconoscono gli stessi anni di siccità ({casi}). "
        f"Correlazione tra stress simulato e verde: {_r(ndvi)}. Vale per l'ordine degli anni, non per i valori.\n\n"
        f"**Resa del mais.** Le annate buone e cattive del mais seguono quelle delle rese provinciali: "
        f"{_r(mais)}, su {mais['n'] if mais else 'n.d.'} anni. Gli intervalli sono larghi: è un buon segno, non una garanzia.")

    st.subheader("Cosa NON è confermato")
    st.warning(
        f"**Soia.** Le rese simulate non seguono in modo affidabile quelle reali: {_r(soia)}. "
        "L'intervallo comprende lo zero, quindi non si può escludere che sia un caso. "
        "Le rese provinciali di soia variano poco e includono la soia di secondo raccolto, che il modello non simula.\n\n"
        "**Quanta acqua ha la coltura.** SMAP guarda solo i primi centimetri: non conferma né smentisce "
        "il bilancio dell'acqua alle radici, né l'effetto dell'irrigazione. "
        "I tre scenari d'acqua non si distinguono nel confronto con SMAP né con l'NDVI.\n\n"
        "**Il 2017.** Per il modello è l'anno più stressato, ma il verde misurato è nella norma: lo stress simulato è esagerato.")

    st.subheader("Cosa è negativo")
    st.error(
        f"**Frumento.** La correlazione con le rese reali è opposta a quella attesa: {_r(fru)}. "
        "Il modello vede solo la siccità di primavera e penalizza gli anni secchi. "
        "In pianura padana le perdite del frumento arrivano invece dagli anni molto piovosi. "
        f"**{AVVISO_FRUMENTO}**")

    st.subheader("Cosa non è stato validato")
    nv = list(v.get("non_validato", [])) + [
        "effetto delle cover crop e penalità di successione (la resa provinciale non le separa)",
        "volumi irrigui per anno",
        "gli anni dopo il 2022 (la pioggia di POWER non è affidabile)"]
    st.markdown("Mancano misure con cui confrontare:\n" + "\n".join(f"- {x}" for x in nv)
                + "\n\nI numeri su azoto, humus e perdite di azoto sono quindi **ordini di grandezza**, non misure.")

    _sensibilita(dati.sensibilita(), rapp)

    st.subheader("Le figure")
    fig = v.get("figure", {})
    didascalie = {"smap": "Umidità superficiale: anomalie mensili di SMAP e del modello.",
                  "ndvi": "Verde (NDVI) e stress idrico simulato del mais, anno per anno.",
                  "istat": "Rese provinciali (scarto dal trend) e resa simulata.",
                  "caso_2022": "Il caso dell'annata 2022."}
    for k, rel in fig.items():
        p = Path(config.ROOT) / rel
        if p.exists():
            st.image(str(p), caption=didascalie.get(k, k), width="stretch")
    with st.expander("Tutti i confronti con le rese provinciali"):
        righe = []
        for c in v["istat"]["confronti"]:
            d = c["detrend"]
            righe.append({"Coltura": c["coltura"], "Scenario d'acqua": ET["scenari"].get(c["scenario"], c["scenario"]),
                          "Simulazione": c["simulazione"].replace("_", " "), "Anni": d["n"],
                          "Correlazione": round(d["pearson"], 2),
                          "Intervallo 95%": f"{d['pearson_ic95'][0]:+.2f} / {d['pearson_ic95'][1]:+.2f}"})
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
        st.caption("Correlazione tra lo scarto della resa reale dal suo andamento nel tempo e la resa simulata. "
                   "Vicino a +1: vanno nella stessa direzione. Vicino a −1: direzioni opposte. Vicino a 0: nessun legame.")
    st.caption(AVVISO)


def _sensibilita(sens: dict | None, rapp: str):
    """Sezione sulla sensibilita': mostra la conclusione se il riepilogo esiste (altrimenti niente)."""
    if not sens:
        return
    st.subheader("Quanto cambiano i risultati se cambiano le ipotesi")
    mc = sens.get("montecarlo", {})
    n_par = len(sens.get("oat", []))
    st.markdown(
        "Il modello ha molti numeri incerti (coefficienti delle colture, soglie, tetti di irrigazione). "
        f"Abbiamo cambiato {n_par} di questi numeri, prima uno alla volta e poi tutti insieme "
        f"({sens.get('montecarlo_n', 'n.d.')} combinazioni a caso), e guardato se la classifica delle rotazioni cambia. "
        "Nessun numero è stato ritoccato per far tornare i conti.")
    if rapp in mc:
        m = mc[rapp]
        fragile = m["prima_resta"] < 0.5
        st.info(
            f"**Conclusione, scenario «{ET['scenari'][rapp]}».** Con tutti i numeri incerti cambiati insieme, "
            f"la rotazione che oggi risulta prima resta prima nel {pct(m['prima_resta'])} dei casi, "
            f"e le prime tre restano le stesse nel {pct(m['top3_restano'])}. "
            f"La tua rotazione attuale (base: {bella(sens['base'][rapp]['attuale'])}) resta nell'ultimo quarto della classifica "
            f"nel {pct(m['attuale_ultimo_quarto'])} dei casi. "
            + ("Quindi **l'ordine preciso delle alternative non è affidabile**, mentre è più solido il messaggio "
               "su dove sta la rotazione attuale." if fragile and m["attuale_ultimo_quarto"] > 0.5 else
               "Leggi la classifica con cautela."))
    righe = []
    for sc, m in mc.items():
        righe.append({"Scenario d'acqua": ET["scenari"].get(sc, sc), "Prima resta prima": pct(m["prima_resta"]),
                      "Prime tre restano": pct(m["top3_restano"]),
                      "Attuale nell'ultimo quarto": pct(m["attuale_ultimo_quarto"]),
                      "Somiglianza dell'ordine (tau mediano)": num(m["tau_mediana"], 2)})
    if righe:
        st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
    nc = len(sens.get("non_contano", []))
    if n_par and nc:
        st.markdown(f"Dei {n_par} numeri provati, {nc} non cambiano mai la decisione: sono i parametri su cui conviene "
                    "non spendere tempo. Gli altri sono elencati nel rapporto di sensibilità.")
    st.caption("Il tau è 1 se l'ordine delle rotazioni è identico a quello di partenza; più è basso, più l'ordine cambia.")
    with st.expander("Conclusione tecnica (testo del riepilogo)"):
        st.write(sens.get("conclusione", ""))
    did = {"sensibilita_tornado_punteggio": "I parametri che spostano di più il punteggio della prima rotazione.",
           "sensibilita_montecarlo_tau": "Quanto cambia l'ordine delle rotazioni nelle combinazioni a caso."}
    for f in sorted(Path(config.FIGURE_DIR).glob("sensibilita_*")):
        if f.stem in did:
            st.image(str(f), caption=did[f.stem], width="stretch")


# ---------------------------------------------------------------------------------------------
def limiti(sintesi: pd.DataFrame | None, scenario: str):
    st.title("Limiti e fonti")
    st.warning(AVVISO)
    st.header("Cosa il modello non sa fare")
    extra_humus = extra_n = ""
    if sintesi is not None:
        s = sintesi[(sintesi["scenario"] == scenario) & (sintesi["n_simulazioni"] > 0)]
        if len(s):
            extra_humus = (f" Nello scenario scelto l'humus cala in {int((s['humus_t_ha'] < 0).sum())} "
                           f"rotazioni su {len(s)}.")
            extra_n = (f" Nello scenario scelto, in metà delle rotazioni almeno una coltura supera il limite "
                       f"in più del {pct(s['quota_oltre_limite_n'].median())} delle annate.")
    anni_ok = dati.anni_affidabili()
    limiti_ = [
        ("Falda superficiale non modellata",
         "In zona la falda è vicina (110–150 cm) e porta acqua alle radici. Il modello non lo sa, "
         "quindi lo stress nei campi in asciutto è sovrastimato, soprattutto per il frumento in primavera."),
        ("Effluenti zootecnici non modellati",
         "Letame e liquame non entrano nel bilancio. Per questo l'humus cala in quasi tutte le rotazioni: "
         "in un'azienda con stalla non è detto che succeda." + extra_humus),
        ("Azoto",
         "L'azoto non limita mai la resa nel modello, e il limite di legge risulta spesso superato." + extra_n +
         " Non è stato confrontato con misure."),
        ("Cover crop",
         "È rappresentata in modo prudente: solo se c'è tempo di seminarla e di terminarla nei termini del disciplinare. "
         "Quando non è praticabile il modello la tratta come terreno nudo."),
        ("Eccessi d'acqua",
         "Il ristagno e le piogge troppo abbondanti non riducono la resa nel modello. "
         "È il motivo del risultato negativo per il frumento."),
        ("Stress da caldo",
         "È debole nel modello e non è confermato dai dati per il 2022: dipende molto dalla fonte delle temperature."),
        (f"Annate dopo il {anni_ok[1]} escluse",
         f"La pioggia di NASA POWER dopo il {anni_ok[1]} è molto più alta di quella dei pluviometri. "
         f"Il modello usa solo le annate {anni_ok[0]}–{anni_ok[1]}."),
        ("Una sola zona",
         "I controlli sono fatti sul punto pilota in provincia di Cremona. Altrove i risultati non sono stati verificati."),
    ]
    for t, x in limiti_:
        with st.container(border=True):
            st.markdown(f"**{t}.** {x}")

    st.header("Fonti dei dati")
    lat, lon = dati.PILOTA
    righe = []
    for f in dati.fonti_scaricate(lat, lon):
        periodo = (dati.testo_data(f["dal"]) if f["dal"] == f["al"]
                   else f"{dati.testo_data(f['dal'])} – {dati.testo_data(f['al'])}") if f["dal"] else "non disponibile"
        righe.append({"Fonte": f["nome"], "A cosa serve": f["uso"], "Prodotto": f["prodotto"] or "—",
                      "Scaricato il": periodo})
    st.dataframe(pd.DataFrame(righe), hide_index=True, width="stretch")
    st.caption("La data è quella del download, letta dai metadati salvati insieme ai dati.")
    st.markdown(
        "FIELDWISE usa dati aperti di diversi enti. Non è un prodotto di nessuno di questi enti "
        "e non ha la loro approvazione.")
