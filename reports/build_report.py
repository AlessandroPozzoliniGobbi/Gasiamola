"""Genera il report per il team: reports/FIELDWISE_report.pdf e il sorgente reports/FIELDWISE_report.md.

Uso (dalla radice del repository):   .venv/bin/python reports/build_report.py

Regola: i numeri dei risultati NON sono scritti a mano. Si leggono dalla cache al momento della
generazione:
  data/processed/<punto>/ensemble_sintesi.csv, ensemble_dettaglio.csv, ensemble_meta.json
  data/processed/<punto>/validation_summary.json
  data/processed/<punto>/sensitivity_summary.json
  params/*.yaml (via fieldwise.params)
I pochi numeri scritti nel testo (rapporti di pioggia POWER/ARPA, f_caldo del 2022, risultati
del confronto senza il 2022, numeri della proposta originale) vengono da file del repository
indicati accanto: PLAN.md, data/CHECKS.md, reports/validation.md, reports/engine_review.md,
legacy/FIELDWISE_proposta_modello.pdf. Rilanciare lo script dopo ogni nuovo ensemble.

Il contenuto e' descritto una sola volta come lista di blocchi e reso sia in Markdown sia in PDF
(reportlab, font standard Helvetica/Courier: nel testo solo caratteri Latin-1).
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fieldwise import config, ranking  # noqa: E402
from fieldwise import ensemble as ens  # noqa: E402
from fieldwise import params as P  # noqa: E402
from fieldwise import rotation as rt  # noqa: E402

PD = config.PROCESSED_DIR / f"lat{config.PILOT_LAT:.3f}_lon{config.PILOT_LON:.3f}"
REP = ROOT / "reports"
FIG = REP / "figure"
OUT_PDF = REP / "FIELDWISE_report.pdf"
OUT_MD = REP / "FIELDWISE_report.md"

SC = ("solo_pioggia", "tetto_irriguo", "irrigazione_libera")
SC_NOME = {"solo_pioggia": "solo pioggia", "tetto_irriguo": "tetto irriguo", "irrigazione_libera": "irrigazione libera"}
SC_PRINC = "tetto_irriguo"


# =============================================================================== formati
def n(x, d=2, segno=False):
    """Numero all'italiana (virgola decimale)."""
    if x is None or (isinstance(x, float) and x != x):
        return "n.d."
    s = f"{x:+.{d}f}" if segno else f"{x:.{d}f}"
    return s.replace(".", ",")


def pc(x, d=0):
    return n(100 * x, d) + "%"


def ic(lst, d=2):
    return f"[{n(lst[0], d, True)}, {n(lst[1], d, True)}]"


# =============================================================================== dati
sin = pd.read_csv(PD / "ensemble_sintesi.csv")
meta = json.loads((PD / "ensemble_meta.json").read_text(encoding="utf-8"))
det = pd.read_csv(PD / "ensemble_dettaglio.csv")
VAL = json.loads((PD / "validation_summary.json").read_text(encoding="utf-8"))
SEN = json.loads((PD / "sensitivity_summary.json").read_text(encoding="utf-8"))
PAR = P.load_params()


def classe(label: str) -> str:
    r = ens.parse_rotazione(label)
    if r.n < 3 and 3 % r.n == 0:
        r = rt.Rotation(r.crops * (3 // r.n), r.cover * (3 // r.n))
    return r.canonical().label


def riga(sc: str, label: str) -> pd.Series:
    x = sin[(sin["scenario"] == sc) & (sin["classe"] == classe(label))]
    if x.empty:
        raise KeyError(f"{label} / {sc}")
    return x.iloc[0]


RANK = {sc: ranking.score(sin, ranking.PESI_UGUALI if hasattr(ranking, "PESI_UGUALI") else
                          {k: 1.0 for k in ranking.PRIORITA}, sc) for sc in SC}
ATT = "mais"
ATT_CL = classe(ATT)
REGIME = "conformita_" + ranking.REGIME_PREDEFINITO
CONF = {"conforme": "conforme", "conforme_solo_in_deroga": "in deroga", "non_conforme": "non conforme"}


def pos(sc, label):
    r = RANK[sc]
    return int(r.loc[r["classe"] == classe(label), "posizione"].iloc[0]), len(r)


def pos_txt():
    return ", ".join(f"{pos(sc, ATT)[0]}a su {pos(sc, ATT)[1]} ({SC_NOME[sc]})" for sc in SC)


def conf(row):
    return CONF.get(row[REGIME], str(row[REGIME]))


def stat_params():
    tot = ass = nonv = der = 0
    for _, v in P.iter_entries(PAR):
        tot += 1
        ass += bool(v.get("assunzione"))
        nonv += v.get("verificato") is not True
        der += bool(v.get("derivato"))
    return tot, ass, nonv, der, len(P.sensitivity_entries(PAR))


N_PAR, N_ASS, N_NONV, N_DER, N_SENS = stat_params()
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def gm(mmgg):
    m, g = mmgg.split("-")
    return f"{int(g)} {MESI[int(m) - 1]}"

KY = {c: P.get(PAR, f"crops.{c}.ky") for c in ("mais", "soia", "frumento")}
YP = {c: P.get(PAR, f"crops.{c}.resa_potenziale") for c in ("mais", "soia", "frumento")}
SEMINA = {c: P.get(PAR, f"crops.{c}.semina") for c in ("mais", "soia", "frumento")}
TCR = {c: (P.get(PAR, f"heat.colture.{c}.t_critica"), P.get(PAR, f"heat.colture.{c}.t_limite")) for c in KY}
FROT = {"mais_irr": P.get(PAR, "rotation_rules.f_rotazione.mais_dopo_mais.irriguo"),
        "mais_asc1": P.get(PAR, "rotation_rules.f_rotazione.mais_dopo_mais.asciutto.primo_ristoppio"),
        "mais_asc2": P.get(PAR, "rotation_rules.f_rotazione.mais_dopo_mais.asciutto.monosuccessione_continua"),
        "soia": P.get(PAR, "rotation_rules.f_rotazione.soia_dopo_soia"),
        "fru1": P.get(PAR, "rotation_rules.f_rotazione.frumento_dopo_frumento.primo_ristoppio"),
        "fru2": P.get(PAR, "rotation_rules.f_rotazione.frumento_dopo_frumento.monosuccessione_continua")}
TETTO = P.get(PAR, "scenarios.scenari.tetto_irriguo.tetto_irriguo")
AWC = P.get(PAR, "soil.profilo.acqua_disponibile_totale")
SO = P.get(PAR, "soil.strati_soilgrids.s0_30.sostanza_organica")
FCALDO_MAIS = det[det["classe"] == classe("mais")]["f_caldo"]
SIM_OK, SIM_SCART = meta["n_simulazioni"], meta["n_scartate"]
ANNATE = meta["annate_partenza_con_risultati"]
ANNI_VAL = meta["anni_valutati"]
N_ANNATE = ANNATE[1] - ANNATE[0] + 1
N_ROT = int(round((SIM_OK + SIM_SCART) / (23 * 3)))               # 216 rotazioni x 23 partenze x 3 scenari
N_CL = meta["n_classi"]
N_NONEQ = int((sin[sin["scenario"] == SC_PRINC]["equivalente_a"] == "nessuno").sum())
HUMUS_NEG = int((sin[sin["scenario"] == SC_PRINC]["humus_t_ha"] < 0).sum())
HUMUS_TOT = int((sin["scenario"] == SC_PRINC).sum())


# =============================================================================== blocchi
BL: list[tuple] = []


def H(lv, t):
    BL.append(("h", lv, t))


def Pg(t):
    BL.append(("p", t))


def Bu(items):
    BL.append(("ul", items))


def T(head, rows, widths, note=None, small=False):
    BL.append(("t", head, rows, widths, note, small))


def Fg(files, caption, width_cm):
    BL.append(("f", files if isinstance(files, list) else [files], caption, width_cm))


def Box(t):
    BL.append(("box", t))


def PB():
    BL.append(("pb",))


# =============================================================================== contenuto
oggi = dt.date.today().isoformat()
r_m_tet, r_m_pio, r_m_lib = (riga(s, "mais") for s in ("tetto_irriguo", "solo_pioggia", "irrigazione_libera"))
msf = {s: riga(s, "mais > soia > frumento") for s in SC}
mmm = {s: riga(s, "mais") for s in SC}
mc = {s: riga(s, "mais+cover") for s in SC}
fff = {s: riga(s, "frumento") for s in SC}
pm = SEN["montecarlo"]
oat = pd.DataFrame(SEN["oat"])
strut = {x["chiave"]: x for x in SEN["strutturali"]}


def red(a, b):          # riduzione relativa di b rispetto ad a
    return (a - b) / a if a else float("nan")


H(1, "FIELDWISE - report per il team")
Pg(f"<i>NASA Space Apps Challenge 2026 - Field Shift: Adapting Farms with NASA Data.</i> Punto pilota lat {n(config.PILOT_LAT, 1)}, "
   f"lon {n(config.PILOT_LON, 1)} (provincia di Cremona). Stato del {oggi}. Questo documento aggiorna la proposta di "
   "modello che avevamo discusso (<c>legacy/FIELDWISE_proposta_modello.pdf</c>) con quello che il codice fa adesso, "
   "con i risultati veri e con quello che non funziona.")
Pg(f"<b>Dove leggere i numeri.</b> Tutti i risultati di questo report sono letti dai file in <c>data/processed/</c> al momento "
   f"della generazione (<c>reports/build_report.py</c>): ensemble calcolato il {meta['calcolato_il'][:10]}, "
   f"hash dei parametri {meta['hash_parametri'][:12]}. Rilanciare lo script dopo ogni nuovo ensemble. "
   "Le pagine di dettaglio sono <c>reports/validation.md</c>, <c>reports/sensitivity.md</c>, <c>reports/engine_review.md</c>, "
   "<c>data/CHECKS.md</c> e <c>PLAN.md</c>.")

H(2, "In breve")
Bu([
    "Teniamo l'idea di Lorenzo: ogni coltura eredita il suolo lasciato dalla precedente; lo stato del suolo non si azzera mai.",
    "Al posto dei vettori dinamici ci sono bilanci di massa di acqua, azoto e humus a passo giornaliero, con le formule di FAO-56, "
    "FAO-33 e AquaCrop. Ogni parametro ha una fonte e un campo <c>verificato</c>.",
    f"L'ensemble prova {N_ROT} rotazioni su {N_ANNATE} annate di partenza (meteo reale NASA POWER) in tre scenari d'acqua: "
    f"{SIM_OK:,} simulazioni riuscite in {n(meta['tempo_s'], 1)} s.".replace(",", "."),
    "Validazione contro osservazioni: il mais regge (resa ISTAT), la soia no, il frumento va nella direzione sbagliata (sezione 10). "
    "Questo pesa su come leggere le classifiche.",
    f"La prima rotazione della classifica cambia con molti parametri incerti; il giudizio sul mais continuo (nell'ultimo quarto della "
    f"classifica nel {pc(min(pm[x]['attuale_ultimo_quarto'] for x in SC))}-{pc(max(pm[x]['attuale_ultimo_quarto'] for x in SC))} dei campioni) "
    f"invece regge, con una sfumatura: nel caso di base il mais continuo è {pos_txt()} (sezione 11).",
])

H(2, "Cosa è cambiato rispetto alla proposta originale")
Pg("La proposta era una prima versione non tarata. Strada facendo abbiamo corretto errori e preso decisioni che cambiano i "
   "numeri: le righe in grassetto sono quelle che si notano di più.")
T(["Tema", "Proposta originale", "Ora"], [
    ["Meteo", "NASA POWER 2000-2025, 23 annate.",
     f"POWER 2000-2022: la pioggia POWER 2023-2025 è sovrastimata (rapporto con il pluviometro 1,02 fino al 2022, 1,46 dopo; "
     f"<c>data/CHECKS.md</c> D1). Con un ciclo di avviamento restano {N_ANNATE} annate di partenza ({ANNATE[0]}-{ANNATE[1]})."],
    ["ET0", "Hargreaves (solo temperature).", "Penman-Monteith FAO-56 con radiazione, umidità e vento di POWER."],
    ["<b>Acqua</b>", "Kc singolo, un solo strato di 1,5 m, ruscellamento oltre 60 mm/giorno.",
     "<b>Doppio coefficiente</b> FAO-56 (Kcb + Ke) per tutte le superfici, strato evaporante a parte, "
     "Curve Number di AquaCrop (72, Ia = 0,05 S)."],
    ["Fasi", "Giorni fissi.", "Gradi-giorno da POWER."],
    ["<b>Azoto</b>", "Aggiornato a fine segmento.",
     "<b>Passo giornaliero</b> (<c>PLAN.md</c> D14): a fine segmento la cover aumentava la lisciviazione e sotto il frumento "
     "la lisciviazione risultava zero."],
    ["Resa", "FAO-33 sull'acqua e basta.", "Resa = potenziale x f_acqua x f_caldo x f_rotazione (sezione 4)."],
    ["Rotazione", "Nessuna penalità.", "Penalità di ristoppio da letteratura; conformità ai disciplinari come etichetta, nessuna rotazione esclusa."],
    ["<b>Cover crop</b>", "Dimezza o più la lisciviazione (57 a 19 kg N/ha/anno, mais continuo irriguo).",
     f"<b>Riduce meno</b>: mais continuo con cover ogni anno, lisciviazione {n(mmm['irrigazione_libera']['n_lisciviato_kg_n'], 1)} "
     f"a {n(mc['irrigazione_libera']['n_lisciviato_kg_n'], 1)} kg N/ha/anno in irrigazione libera "
     f"({pc(red(mmm['irrigazione_libera']['n_lisciviato_kg_n'], mc['irrigazione_libera']['n_lisciviato_kg_n']))}). "
     "Per singolo intervallo la riduzione è 51% dopo il mais e 62% dopo il frumento (<c>PLAN.md</c>)."],
    ["Suolo", "Franco di default, 2% di sostanza organica.",
     f"Tessitura e densità SoilGrids; sostanza organica 0-30 cm ERSAF {n(SO, 2)}% (SoilGrids dà 3,56%, in sensibilità); "
     f"acqua disponibile {n(AWC, 1)} mm su 1,5 m."],
    ["<b>Primi risultati</b>", "Irrigazione libera: mais continuo 320 mm e 283 kg N; mais > soia > frumento 213 mm e 157 kg N.",
     f"Irrigazione libera: mais continuo {n(mmm['irrigazione_libera']['irrigazione_mm'], 0)} mm e "
     f"{n(mmm['irrigazione_libera']['concime_kg_n'], 0)} kg N; mais > soia > frumento "
     f"{n(msf['irrigazione_libera']['irrigazione_mm'], 0)} mm e {n(msf['irrigazione_libera']['concime_kg_n'], 0)} kg N "
     "(sezione 9, letti dalla cache)."],
    ["Caldo 2022", "\"Una penalità termica farebbe emergere il 2022\".",
     "Penalità aggiunta (Deryng et al. 2014) senza taratura: il criterio non è soddisfatto, f_caldo 0,958 nel 2022 "
     "(<c>PLAN.md</c> D16). La perdita del 2022 nel modello viene dall'acqua."],
    ["Validazione", "Da fare (SMAP, NDVI, ISTAT).", "Fatta: mais confermato, soia non confermata, frumento negativo."],
    ["Parametri", "\"Indicativi, da verificare\".",
     f"{N_PAR} voci, ognuna con fonte; {N_ASS} dichiarate assunzioni, {N_NONV} non verificate sulla fonte "
     "(<c>python -m fieldwise.params --check</c>)."],
], [2.3, 5.2, 9.8], small=True)

# ----------------------------------------------------------------------------------------------- 1
H(2, "1. Il problema dei vettori dinamici")
Pg("L'idea di partenza descriveva suolo e coltura come due traiettorie, F(t) = [W, N, T, OM] e C(t) = [Wr, Nr, Tr, R], e misurava la "
   "compatibilità come somma pesata di punteggi istantanei. Resta valido il giudizio della proposta: il punteggio non ha unità di "
   "misura (i pesi li sceglieremmo noi e non si può verificare con un satellite o con una resa reale); suolo e coltura non sono "
   "indipendenti (la pianta consuma l'acqua oggi e domani il suolo è diverso); la risposta della pianta non è lineare (soglie ed "
   "eccessi). Le equazioni non si inventano: vengono dai bilanci di massa. Il gradiente non serve per scegliere tra mais, soia e "
   "frumento (scelta discreta, si provano tutte le combinazioni).")
Pg("<b>Cosa teniamo.</b> L'intuizione più forte del documento originale: il terreno cambia dopo ogni coltura e la successiva parte da lì. "
   "Nel motore lo stato non viene mai azzerato tra una coltura e l'altra. È un principio del progetto (<c>PLAN.md</c>, principio 4).")

# ----------------------------------------------------------------------------------------------- 2
H(2, "2. Il modello FAO")
Pg("<b>FAO-56</b> (Allen et al., 1998): l'ET0 è l'acqua che evapora da un prato di riferimento, solo dal meteo; la coltura consuma "
   "ETc = Kc x ET0; l'acqua utilizzabile dalle radici è TAW (differenza tra capacità di campo e punto di appassimento per la profondità "
   "radicale); la pianta consuma senza fatica fino alla soglia RAW = p x TAW, poi Ks scende linearmente a zero e ETa = Ks x ETc. "
   "<b>FAO-33</b> (Doorenbos e Kassam, 1979): 1 - Y/Ymax = Ky x (1 - ETa/ETc), un coefficiente per coltura "
   f"(Ky: mais {n(KY['mais'])}, soia {n(KY['soia'])}, frumento {n(KY['frumento'])}, da <c>params/crops.yaml</c>).")
Pg(f"<b>Cosa è diverso da prima.</b> L'ET0 è Penman-Monteith (con POWER il totale annuo medio 2000-2022 è 890 mm, "
   "<c>data/CHECKS.md</c> D2; Hargreaves sovrastima del 17% in media). Il coefficiente colturale è <i>doppio</i>: Kcb per la traspirazione "
   "più Ke per l'evaporazione dello strato superficiale, applicato anche a suolo nudo e cover crop. Prima, con Kc singolo, una cover "
   "consumava meno del suolo nudo bagnato e faceva salire la percolazione: è l'errore 1 di <c>reports/engine_review.md</c>. "
   "Il suolo ha due strati, con parametri da SoilGrids e pedotrasferimento di Saxton e Rawls. Il ruscellamento usa il Curve Number "
   "di AquaCrop (72, Ia = 0,05 S) invece della soglia dei 60 mm: con il CN del suolo nudo del NEH (91) il ruscellamento era 83-94 mm/anno, "
   "troppo (E1 della stessa revisione). Le fasi seguono i gradi-giorno. L'azoto e l'humus restano contabilità semplici, "
   "ma con coefficienti dalle fonti e non indicativi (sezione 3).")

# ----------------------------------------------------------------------------------------------- 3
H(2, "3. Il motore")
Pg("Tre bilanci di massa, a passo giornaliero, in un ciclo unico che attraversa tutta la rotazione (calcolo compilato con numba). "
   "Il calendario di ogni rotazione (semine, fasi, raccolte) dipende solo dal meteo e si precalcola; poi un unico ciclo giornaliero "
   "dell'acqua percorre tutta la simulazione senza azzerare lo stato (<c>PLAN.md</c> D6).")
T(["Bilancio", "Come funziona", "Fonti"], [
    ["Acqua", "Pioggia + irrigazione - ruscellamento - ETa - drenaggio = variazione dello stato. Ks sulla zona radicale, drenaggio in cascata "
              "tra gli strati. Chiusura sotto 1e-11 mm nella verifica indipendente (<c>engine_review.md</c> sez. C) e nei test.",
     "FAO-56 cap. 7-8; AquaCrop v7.3 (Curve Number)"],
    ["Azoto", "Mineralizzazione dell'humus + fissazione (soia) + residui + concime - assorbimento - lisciviazione; assorbimento ripartito sulla "
              "traspirazione; lisciviazione per mm drenato con la forma di SWAT. Il concime copre la domanda giorno per giorno.",
     "Disciplinari Lombardia ed Emilia-Romagna; Salvagiotti et al. 2008; SWAT"],
    ["Humus", "Hénin-Dupuis: dH = k1 x residui - k2 x H; k2 dalla formula di Machet (tessitura, C/N). La cover aggiunge biomassa e il suo isoumico.",
     "Mémento Agro-Transfert; BENCO"],
], [1.7, 11.0, 4.6], small=True)
Pg("<b>Cosa non fa.</b> L'azoto non limita la resa (il concime copre il fabbisogno e se ne conta il costo e il rischio: concime, "
   "lisciviazione, quota di annate sopra il limite di legge); non c'è la falda né la risalita capillare; il concime non passa mai dal pool "
   "di azoto minerale del suolo, quindi la lisciviazione è probabilmente sottostimata (sezione 12).")

# ----------------------------------------------------------------------------------------------- 4 (NUOVA)
H(2, "4. Fattori di resa: acqua, caldo, rotazione (sezione nuova)")
Pg("La resa relativa di una coltura è il prodotto di tre fattori, tutti tra 0 e 1, ognuno con la sua fonte e visibile separatamente nell'output "
   "(<c>ensemble_dettaglio.csv</c>: <c>f_acqua</c>, <c>f_caldo</c>, <c>f_rotazione</c>). La resa in t/ha è questa resa relativa per "
   f"il potenziale (mais {n(YP['mais'], 1)}, soia {n(YP['soia'], 1)}, frumento {n(YP['frumento'], 1)} t/ha; "
   "il potenziale del mais è una resa sperimentale, quello di soia e frumento è un'assunzione e le tre colture non sono "
   "perfettamente paragonabili: <c>reports/params_review.md</c>).")
Bu([
    "<b>Acqua (f_acqua).</b> In parole: la resa cala di Ky volte la frazione di acqua che la coltura non ha potuto consumare rispetto a quella che "
    "avrebbe voluto (ETa rispetto a ETc, sommate su tutta la stagione). Fonte: FAO-33 e FAO-56 eq. 90. È il fattore che muove quasi tutto: "
    f"per il mais continuo la mediana di f_acqua è {n(r_m_pio['f_acqua'])} con solo pioggia, {n(r_m_tet['f_acqua'])} con il tetto irriguo "
    f"e {n(r_m_lib['f_acqua'])} con irrigazione libera.",
    "<b>Caldo (f_caldo).</b> In parole: per ogni giorno della finestra della fioritura, se la temperatura efficace (media tra media e massima) supera "
    "la soglia critica, il fattore scende linearmente fino a zero alla soglia limite; il fattore è la media sulla finestra. Fonte: Deryng et al. "
    f"(2014), App. A.3, usata senza taratura. Soglie critica/limite: mais {n(TCR['mais'][0], 0)}/{n(TCR['mais'][1], 0)} °C, "
    f"soia {n(TCR['soia'][0], 0)}/{n(TCR['soia'][1], 0)}, frumento {n(TCR['frumento'][0], 0)}/{n(TCR['frumento'][1], 0)}. "
    "Alternative in sensibilità: AquaCrop (logistica sulla Tmax) e le soglie di Teixeira et al. (2013).",
    "<b>Rotazione (f_rotazione).</b> In parole: se la stessa coltura segue sé stessa la resa si riduce di una quota fissa. Mais dopo mais: "
    f"{n(FROT['mais_irr'], 3)} se irriguo; in asciutto {n(FROT['mais_asc1'], 3)} al primo ristoppio e {n(FROT['mais_asc2'], 3)} in monosuccessione "
    f"continua; soia dopo soia {n(FROT['soia'], 3)}; frumento dopo frumento {n(FROT['fru1'], 3)} e {n(FROT['fru2'], 3)}. Fonti: "
    "Seifert et al. (2017, studio osservazionale USA su mais e soia), Marini et al. (2020) e AHDB (UK, frumento). Sono fonti di altri "
    "contesti: non c'è una prova di lungo periodo in Pianura Padana e la penalità può contenere un effetto azoto (doppio conteggio parziale; "
    "variante f_rotazione = 1 in sensibilità). La precessione favorevole non si applica alla resa.",
])
Box("<b>Il criterio sul caldo del 2022 non è soddisfatto.</b> Ci aspettavamo che il fattore caldo del mais fosse chiaramente basso nel 2022. "
    "Non lo è: f_caldo vale 0,958 con le temperature POWER e circa 0,99 con le stazioni ARPA (<c>PLAN.md</c> D16, "
    "<c>data/CHECKS.md</c> D3). "
    f"In tutto l'ensemble il f_caldo del mais continuo sta tra {n(FCALDO_MAIS.min(), 3)} e {n(FCALDO_MAIS.max(), 3)}: il caldo in fioritura "
    "incide poco in questo clima con questa funzione. Non l'abbiamo tarata per ottenere il risultato che speravamo (sarebbe stata una "
    "taratura sul risultato). Nel modello la perdita del 2022 viene dall'acqua: nel confronto con l'NDVI f_acqua del 2022 è tra le tre peggiori "
    "del periodo (sezione 10).")

# ----------------------------------------------------------------------------------------------- 5
H(2, "5. La catena di rotazione")
Pg(f"Una rotazione è una sequenza ciclica di tre colture (mais, soia, frumento), ognuna con o senza cover crop (segale) nell'intervallo dopo il "
   f"raccolto: {N_ROT} rotazioni, {N_CL} classi cicliche per scenario (la stessa sequenza partita da un altro anno è la stessa classe) "
   f"di cui {N_NONEQ} non equivalenti (le altre sono equivalenti perché la cover non è praticabile e il risultato è identico). "
   "Ogni simulazione parte il 1 gennaio con il profilo a capacità di campo, percorre un ciclo di <i>avviamento</i> e si valuta sul secondo "
   "ciclo (<c>PLAN.md</c> D15): senza avviamento concime e lisciviazione dipendono da uno stato iniziale arbitrario. Semina alla data tipica "
   f"(mais {gm(SEMINA['mais'])}, soia {gm(SEMINA['soia'])}, frumento {gm(SEMINA['frumento'])}), o appena possibile dopo almeno 10 giorni dalla raccolta; "
   "se la maturità non arriva in tempo c'è un conflitto di calendario e la rotazione si scarta o si rinvia. La cover si semina solo se il "
   "calendario agronomico lo consente; altrimenti suolo nudo e il motivo resta nell'output.")
Pg("Le rotazioni non si escludono: i disciplinari 2026 di Lombardia ed Emilia-Romagna non vietano successioni tra queste tre colture, limitano "
   "i ristoppi. Ogni rotazione ha un'etichetta (conforme, conforme in deroga, non conforme) e quella attuale dell'agricoltore si mostra sempre "
   "(<c>PLAN.md</c> D17).")

# ----------------------------------------------------------------------------------------------- 6
H(2, "6. Come tratta il futuro")
Pg(f"Non prevede il meteo. Ogni rotazione parte da ogni annata storica ({ANNATE[0]}-{ANNATE[1]}) come se fossero {N_ANNATE} futuri possibili; "
   f"gli anni valutati vanno dal {ANNI_VAL[0]} al {ANNI_VAL[1]}. Gli indicatori sono la mediana (anno tipico) e il caso peggiore (rischio). "
   "Il messaggio è \"nella metà delle annate passate saresti andato almeno qui, nella peggiore fino a qui\". Differenze dalla proposta: "
   "il limite è 2022 e non 2025 (pioggia POWER non affidabile dopo il 2022, con IMERG che sovrastima i totali annui del 21% e resta solo "
   f"come forzante alternativa); le annate di partenza utili sono {N_ANNATE} e non 23 perché serve un ciclo di avviamento. Il limite "
   "della proposta resta: il clima cambia e il passato può sottostimare gli estremi futuri, e le piogge POWER hanno troppa pioviggine e "
   "pochi eventi intensi (sezione 12).")

# ----------------------------------------------------------------------------------------------- 7
H(2, "7. Ottimizzazione")
Pg(f"Come nella proposta: enumerazione completa (non ci sono variabili continue da ottimizzare). {SIM_OK:,} simulazioni riuscite, "
   f"{SIM_SCART:,} scartate (annate di partenza troppo vicine alla fine della serie affidabile) in {n(meta['tempo_s'], 1)} s sulla "
   "macchina di sviluppo.".replace(",", ".") +
   " I pesi dell'agricoltore entrano solo nella classifica finale: cinque priorità (resa, rischio, risparmio d'acqua, risparmio di concime, "
   "salute del suolo), un punteggio relativo all'insieme confrontato, e il fronte delle rotazioni non dominate. Il punteggio serve a ordinare, "
   "non è una misura assoluta e non è confrontabile tra scenari (<c>src/fieldwise/ranking.py</c>).")

# ----------------------------------------------------------------------------------------------- 8
H(2, "8. Cosa mostriamo all'agricoltore")
Pg("Un'app Streamlit a cinque pagine (<c>app/streamlit_app.py</c>): <i>Confronto</i> (la rotazione attuale contro almeno due alternative, "
   "slider delle cinque priorità, fronte non dominato, frasi con evidenze e rischi), <i>Dettaglio di una annata</i>, <i>Capire i dati</i>, "
   "<i>Validazione</i>, <i>Limiti e fonti</i>. Gira offline con i dati in cache. Mostra sempre la rotazione attuale, le etichette di "
   "conformità e gli avvisi (per esempio quando con certi pesi le rotazioni non si distinguono). L'aspetto nel browser non è stato "
   "controllato da una persona (sezione 12).")

# ----------------------------------------------------------------------------------------------- 9
H(2, "9. Primi risultati")
Pg("Sostituiscono i numeri della proposta, che erano di una versione non tarata. Valori mediani sulle annate; le rotazioni sono quelle della "
   "tabella originale. Humus in kg/ha all'anno (negativo = perdita). Mais continuo = rotazione attuale di riferimento.")
ORDINE = [("mais", "mais > mais > mais"), ("mais+cover", "mais+cover ogni anno"), ("mais > soia > frumento", "mais > soia > frumento"),
          ("mais > frumento+cover > soia", "mais > frumento+cover > soia"), ("frumento", "frumento continuo")]
for sc in SC:
    rows = []
    for lab, nome in ORDINE:
        r = riga(sc, lab)
        rows.append([nome, n(r["resa_rel_mediana"]), n(r["resa_rel_min"]), n(r["irrigazione_mm"], 0), n(r["concime_kg_n"], 0),
                     n(r["n_lisciviato_kg_n"], 0), n(1000 * r["humus_t_ha"], 0), conf(r)])
    T([f"Scenario: {SC_NOME[sc]}", "Resa mediana", "Resa annata peggiore", "Irrig. (mm)", "Concime (kg N)", "N lisciv. (kg N)", "Humus (kg/ha)",
       "Disciplinare"], rows, [4.6, 1.8, 2.2, 1.6, 1.9, 1.9, 1.7, 2.0], small=True)
mmm_l, msf_l = mmm["irrigazione_libera"], msf["irrigazione_libera"]
Pg(f"<b>Cosa si vede, cosa no.</b> (1) <b>La rotazione risparmia acqua e concime, ma meno di quanto sembrava.</b> In irrigazione libera "
   f"mais > soia > frumento usa {pc(red(mmm_l['irrigazione_mm'], msf_l['irrigazione_mm']))} di acqua in meno e "
   f"{pc(red(mmm_l['concime_kg_n'], msf_l['concime_kg_n']))} di concime in meno del mais continuo (la proposta diceva circa un terzo e il 45%). "
   f"(2) <b>La cover riduce la lisciviazione meno</b> di prima: mais continuo, {pc(red(mmm_l['n_lisciviato_kg_n'], mc['irrigazione_libera']['n_lisciviato_kg_n']))} "
   "in irrigazione libera, contro il 67% della proposta (da 57 a 19), e l'humus passa da "
   f"{n(1000 * mmm_l['humus_t_ha'], 0, True)} a {n(1000 * mc['irrigazione_libera']['humus_t_ha'], 0, True)} kg/ha/anno (la proposta: da +9 a +244). "
   f"(3) <b>Il frumento continuo resta alto in asciutto</b> ({n(fff['solo_pioggia']['resa_rel_mediana'])} contro "
   f"{n(mmm['solo_pioggia']['resa_rel_mediana'])} del mais continuo): la penalità di ristoppio {n(FROT['fru2'])} c'è, ma non basta a togliere "
   "il difetto che la proposta segnalava (il frumento cresce quando piove). Dato che la validazione sul frumento è negativa, questo risultato va "
   f"letto con prudenza (sezioni 10 e 12). (4) <b>L'humus cala in {HUMUS_NEG} classi su {HUMUS_TOT}</b> nel tetto irriguo: gli effluenti zootecnici "
   "non sono modellati.")
rows = []
for sc in SC:
    r = RANK[sc]
    top = r.iloc[0]
    p_att, tot = pos(sc, ATT)
    rows.append([SC_NOME[sc], f"{top['classe']} ({conf(top)})", f"{p_att}a su {tot}", n(top["punteggio"], 2),
                 n(float(r.loc[r["classe"] == ATT_CL, "punteggio"].iloc[0]), 2)])
for i, sc in enumerate(SC):
    rc = ranking.score(sin, {k: 1.0 for k in ranking.PRIORITA}, sc, solo_conformi=True).iloc[0]
    rows[i].append(f"{rc['classe']} ({n(rc['punteggio'], 2)})")
T(["Scenario", "Prima in classifica (pesi uguali)", "Mais continuo", "Punt. prima", "Punt. mais continuo", "Prima tra le conformi (punteggio)"], rows,
  [2.5, 5.2, 1.7, 1.6, 1.9, 4.9], note="Punteggio relativo all'insieme confrontato (0-1), solo per ordinare. Pesi uguali sulle cinque priorità. "
  "Disciplinare: Lombardia, impegno quinquennale.", small=True)
Pg(f"Posizione del mais continuo nel caso di base: {pos_txt()}.")
Pg("Attenzione alla conformità: la prima della classifica può essere non conforme al disciplinare (l'ultima colonna mostra la prima tra le sole "
   "rotazioni conformi, con il punteggio ricalcolato sull'insieme ristretto). L'app permette di filtrare. "
   "La classifica dipende dai pesi (cambia la prima con pesi diversi: sezione 11) e va letta insieme alle sezioni su validazione e limiti.")

# ----------------------------------------------------------------------------------------------- 10 (NUOVA)
H(2, "10. Validazione contro osservazioni (sezione nuova)")
Pg("Le scelte di metodo sono state fissate prima di guardare i risultati: nessun parametro è stato toccato e tutti i confronti calcolati "
   "sono riportati, anche i negativi. Gli intervalli sono al 95%: bootstrap a blocchi di 6 mesi per le serie mensili (l'anomalia SMAP è "
   "autocorrelata), Fisher e Bonett-Wright per le annuali. Pioggia delle simulazioni: POWER (uguale al default fino al 2022). Scenario "
   "rappresentativo scelto a priori: tetto irriguo (nella provincia mais e soia sono in prevalenza irrigati).")


def esito(c):
    lo, hi = c[1]
    return "confermato" if lo > 0 else ("negativo" if hi < 0 else "non confermato")


rows = []
smap = {(c["configurazione"], c["scenario"], c["periodo"]): c for c in VAL["smap"]["confronti"]}
for conf_s in ("mais continuo", "mais > soia > frumento"):
    c = smap[(conf_s, SC_PRINC, "principale")]
    a = c["anomalie"]
    rows.append([f"SMAP, anomalie mensili, {conf_s}", "tetto irriguo", str(c["mesi"]), n(a["pearson"], 2, True) + " " + ic(a["pearson_ic95"]),
                 n(a["spearman"], 2, True) + " " + ic(a["spearman_ic95"]), esito((a["pearson"], a["pearson_ic95"]))])
for c in VAL["ndvi"]["confronti"]:
    if c["indicatore"] == "ndvi_lug_ago":
        rows.append(["NDVI MODIS lug-ago contro f_acqua mais", SC_NOME[c["scenario"]], str(c["n"]),
                     n(c["pearson"], 2, True) + " " + ic(c["pearson_ic95"]), n(c["spearman"], 2, True) + " " + ic(c["spearman_ic95"]),
                     esito((c["pearson"], c["pearson_ic95"]))])
for col in ("mais", "soia", "frumento"):
    for c in VAL["istat"]["confronti"]:
        if c["coltura"] == col and c["simulazione"] == "monosuccessione" and (col == "frumento" or c["scenario"] in ("solo_pioggia", SC_PRINC)):
            d = c["detrend"]
            rows.append([f"ISTAT {col} (residuo dal trend)", SC_NOME[c["scenario"]] + (" (non irrigato)" if col == "frumento" else ""),
                         str(d["n"]), n(d["pearson"], 2, True) + " " + ic(d["pearson_ic95"]),
                         n(d["spearman"], 2, True) + " " + ic(d["spearman_ic95"]), esito((d["pearson"], d["pearson_ic95"]))])
T(["Confronto", "Scenario", "n", "Pearson [IC 95%]", "Spearman [IC 95%]", "Esito"], rows, [5.1, 2.5, 0.8, 3.7, 3.7, 2.0],
  note="n = mesi (SMAP) o anni (NDVI, ISTAT). Esito: confermato se l'intervallo sta sopra zero, negativo se sta sotto, "
       "non confermato se comprende lo zero. Tutte le righe: <c>reports/validation.md</c>.", small=True)
ist = {(c["coltura"], c["scenario"], c["simulazione"]): c["detrend"] for c in VAL["istat"]["confronti"]}
mais_t, soia_t, fru = ist[("mais", SC_PRINC, "monosuccessione")], ist[("soia", SC_PRINC, "monosuccessione")], ist[("frumento", "solo_pioggia", "monosuccessione")]
Bu([
    f"<b>Mais: confermato, con cautela.</b> Scenario rappresentativo r = {n(mais_t['pearson'], 2)} {ic(mais_t['pearson_ic95'])} su n = {mais_t['n']}. "
    "Regge con le differenze prime e con la media delle rotazioni; togliendo il 2022 r vale ancora 0,63 (verifica diagnostica aggiunta dopo, "
    "<c>reports/validation.md</c>). Sbaglia il 2013 (primavera piovosa, semine ritardate) e il 2017 (perdita prevista che non c'è stata). "
    "In irrigazione libera f_acqua vale 1 in tutti gli anni e resta r = 0,53 solo grazie al caldo: il fattore caldo porta un segnale debole.",
    f"<b>Soia: non confermata.</b> r = {n(soia_t['pearson'], 2)} {ic(soia_t['pearson_ic95'])}: l'intervallo comprende lo zero. Le rese "
    "provinciali della soia variano poco e includono la soia di secondo raccolto, che il modello non simula.",
    f"<b>Frumento: negativo.</b> r = {n(fru['pearson'], 2)} {ic(fru['pearson_ic95'])}: la direzione è opposta a quella attesa. Il modello penalizza "
    "solo la siccità primaverile; in Pianura Padana le perdite reali del frumento vengono dagli anni umidi (malattie, allettamento, ristagno), "
    "che il modello non rappresenta. La resa relativa del frumento non va letta come indicatore di rischio annuale.",
    "<b>SMAP</b> conferma la dinamica dello strato superficiale (anomalie mensili r circa 0,7) ma non distingue gli scenari irrigui e non dice nulla "
    "sulla zona radicale. Una parte dell'accordo misura la qualità della pioggia POWER nel giorno giusto. <b>NDVI</b>: gli anni di siccità "
    "coincidono (2003, 2012, 2022), ma la relazione è solo ordinale, la finestra da 2 km mescola colture e il modello esagera il 2017.",
])
Fg(["validazione_smap_anomalie.png", "validazione_ndvi_stress.png"], "In alto: anomalie mensili SMAP contro modello. In basso: NDVI MODIS di luglio-agosto contro stress idrico simulato del mais.", 16.5)
Fg(["validazione_istat_rese.png", "validazione_caso_2022.png"], "In alto: rese ISTAT detrendizzate contro resa simulata. In basso: il caso 2022 (NDVI della finestra e stress simulato).", 16.5)
Pg("<b>Cosa NON è validato:</b> " + "; ".join(VAL["non_validato"]) + "; effetto delle cover crop e penalità di rotazione (la resa provinciale non le separa); "
   "volumi irrigui e ruscellamento per anno; gli anni dopo il 2022. Per queste grandezze non ci sono osservazioni nel repository.")

# ----------------------------------------------------------------------------------------------- 11 (NUOVA)
H(2, "11. Sensibilità: cosa è robusto e cosa no (sezione nuova)")
tot_oat = len(oat)
n_prima = {sc: int(oat["prima_cambia" + ("" if sc == SC_PRINC else "_" + sc)].sum()) for sc in SC}
n_conta = int(oat["conta"].sum())
n_inatt = int(oat["inattiva"].sum())
oat["effetto"] = oat[["d_prima_meno", "d_prima_piu"]].abs().max(axis=1)
top5 = oat[oat["prima_cambia"]].sort_values("effetto", ascending=False).head(5)["percorso"].tolist()
Pg(f"Domanda: quali parametri incerti cambiano la <i>decisione</i> (la classifica e le alternative proposte) e quali no. {tot_oat} parametri "
   f"presi uno alla volta a x0,7 e x1,3 (ristretti all'intervallo della fonte, alle frazioni a 1 e alle soglie ordinate), {len(SEN['strutturali'])} scelte "
   f"strutturali, e un Monte Carlo a ipercubo latino con {SEN['montecarlo_n']} campioni (seme {SEN['seme']}; {SEN['montecarlo_falliti']} non "
   "eseguibili per soglie incompatibili). Nessuna taratura: si riporta ciò che esce. Il sottoinsieme di rotazioni usato riproduce la classifica "
   "completa (tau 1,00 e stessa prima in tutti e tre gli scenari).")
Bu([
    f"<b>Non robusto: la scelta fine tra le prime alternative.</b> Cambiano la prima rotazione nel tetto irriguo {n_prima[SC_PRINC]} parametri su "
    f"{tot_oat} (solo pioggia: {n_prima['solo_pioggia']}; irrigazione libera: {n_prima['irrigazione_libera']}), soprattutto: "
    + ", ".join(f"<c>{k}</c>" for k in top5) + ". Con l'incertezza congiunta la prima resta prima nel "
    f"{pc(pm['solo_pioggia']['prima_resta'])} (solo pioggia), {pc(pm['tetto_irriguo']['prima_resta'])} (tetto), "
    f"{pc(pm['irrigazione_libera']['prima_resta'])} (libera) dei campioni, e le prime tre restano le stesse solo nel "
    f"{pc(pm['solo_pioggia']['top3_restano'])}, {pc(pm['tetto_irriguo']['top3_restano'])} e {pc(pm['irrigazione_libera']['top3_restano'])}.",
    f"<b>Robusto: il giudizio sul mais continuo.</b> Nell'ultimo quarto della classifica nel {pc(pm['solo_pioggia']['attuale_ultimo_quarto'])}, "
    f"{pc(pm['tetto_irriguo']['attuale_ultimo_quarto'])} e {pc(pm['irrigazione_libera']['attuale_ultimo_quarto'])} dei campioni "
    "(solo pioggia, tetto, libera). Attenzione: nel caso di base, senza perturbazioni, il mais continuo è " + pos_txt() +
    ": in fondo senza irrigazione o con irrigazione libera, a due terzi della classifica col tetto irriguo. Il giudizio è robusto nel senso che le "
    "perturbazioni lo spingono verso il fondo, non nel senso che in ogni scenario sia tra gli ultimi.",
    f"<b>Non contano:</b> {tot_oat - n_conta} parametri su {tot_oat} non cambiano la decisione, di cui {n_inatt} non hanno alcun effetto "
    "(non sono usati dal motore nella configurazione di base: per esempio i parametri delle sole alternative strutturali). Tra le scelte "
    f"strutturali, con la sostanza organica al valore SoilGrids la prima non cambia in nessuno scenario (tau da {n(min(strut['so_soilgrids'][s]['tau'] for s in SC), 2)}); "
    "con la pioggia IMERG o con un'altra funzione del caldo la prima resta, ma le prime tre o le alternative cambiano in alcuni scenari (tabella).",
])
srows = []
for k, x in strut.items():
    t = [x[s] for s in SC]
    if x["esito"] != "ok" or any(v is None for v in t):
        srows.append([x["descrizione"], "non eseguibile", "", ""])
        continue
    srows.append([x["descrizione"], " / ".join(n(v["tau"], 2) for v in t),
                  " / ".join("sì" if v["prima_cambia"] else "no" for v in t), (x["tetto_irriguo"]["prima"])])
T(["Scelta strutturale (una alla volta)", "Tau di Kendall (solo pioggia / tetto / libera)", "Cambia la prima", "Prima nel tetto irriguo"], srows,
  [6.0, 4.0, 2.4, 5.0], note="Tau = accordo con la classifica di base (1 = identica). Il valore più estremo: penalità di rotazione azzerate. "
  "Senza penalità vince il frumento continuo.", small=True)
mrows = [[SC_NOME[s], str(pm[s]["n_validi"]), n(pm[s]["tau_mediana"], 2), n(pm[s]["tau_p5"], 2), pc(pm[s]["prima_resta"]), pc(pm[s]["top3_restano"]),
          pc(pm[s]["attuale_ultimo_quarto"]), pc(pm[s]["alternative_restano"])] for s in SC]
T(["Monte Carlo", "Campioni validi", "Tau mediano", "Tau 5° perc.", "Prima resta prima", "Prime tre restano", "Mais continuo nell'ultimo quarto",
   "Alternative restano"], mrows, [3.0, 1.8, 1.8, 1.8, 2.2, 2.2, 2.6, 2.0], small=True)
Fg(["sensibilita_tornado_punteggio.png", "sensibilita_tornado_tau.png"], "Parametri più influenti (uno alla volta, tetto irriguo). A sinistra: effetto sul punteggio della prima rotazione; a destra: tau di Kendall minimo.", 15.0)
Fg(["sensibilita_montecarlo_tau.png"], "Monte Carlo: distribuzione del tau di Kendall rispetto alla classifica di base.", 11.0)
pw = SEN["pesi"]
Pg(f"<b>Pesi dell'utente</b> (non è incertezza del modello): cambiando solo i pesi arrivano prime {pw['solo_pioggia']['n_prime_diverse_totale']} rotazioni "
   f"diverse in solo pioggia, {pw['tetto_irriguo']['n_prime_diverse_totale']} nel tetto irriguo e {pw['irrigazione_libera']['n_prime_diverse_totale']} in "
   "irrigazione libera. È il motivo per cui l'app mostra più alternative e non una sola risposta. Le correlazioni di rango parziali (PRCC) del Monte Carlo "
   "sono indicative (173 parametri su 256 campioni), non indici di Sobol.")

# ----------------------------------------------------------------------------------------------- 12
H(2, "12. Limiti")
Box("<b>Questi limiti pesano sull'uso dei risultati.</b> Lo strumento confronta rotazioni in modo coerente; non prevede la resa di un campo.")
Bu([
    "<b>Frumento.</b> La validazione è negativa e il modello non vede le perdite degli anni umidi. Il frumento compare spesso in alto nelle "
    "classifiche: va letto con questo avvertimento.",
    "<b>Soia.</b> Validazione non confermata (intervalli che comprendono lo zero).",
    "<b>Acqua in asciutto.</b> Nessuna falda né risalita capillare (110-150 cm in zona): lo stress del mais senza irrigazione è probabilmente "
    f"sovrastimato (f_acqua mediana {n(r_m_pio['f_acqua'])} in solo pioggia).",
    "<b>Azoto.</b> Il concime non passa dal pool di azoto minerale: la lisciviazione (qui "
    f"{n(sin['n_lisciviato_kg_n'].min(), 0)}-{n(sin['n_lisciviato_kg_n'].max(), 0)} kg N/ha/anno tra tutte le classi; per il mais irriguo in Pianura Padana la "
    "letteratura citata nella revisione riporta in genere diverse decine) è probabilmente sottostimata, e la riduzione relativa della cover è bassa perché quella assoluta è piccola. L'azoto non "
    "limita la resa. Nessuna validazione di azoto, humus, lisciviazione, percolazione, ruscellamento.",
    "<b>Humus.</b> Gli effluenti zootecnici non sono modellati: quasi tutte le rotazioni perdono humus.",
    "<b>Caldo.</b> Effetto piccolo con la funzione di Deryng; il criterio del 2022 non è soddisfatto; le temperature POWER sono deboli sugli estremi "
    "(giorni sopra 35 °C: correlazione 0,46 con le stazioni).",
    "<b>Pioggia.</b> POWER ha troppa pioviggine (31% di giorni piovosi contro 21%) e pochi eventi intensi; il Curve Number si applica a piogge "
    "giornaliere su griglia da 50 km. I dati POWER 2023-2025 (e IMERG sopra il pluviometro) sono esclusi.",
    "<b>Penalità di rotazione.</b> Da studi di altri contesti; possono contenere un effetto azoto; azzerandole vince il frumento continuo.",
    "<b>Un punto, un suolo.</b> Cella POWER di circa 50 km a 171 m contro un campo a 45 m; suolo da SoilGrids (la sostanza organica è un valore ERSAF, "
    f"decisione D13); {N_ASS} parametri sono assunzioni dichiarate e {N_NONV} non sono stati verificati sulla fonte originale.",
    "<b>Validazione.</b> Rese ISTAT provinciali (irriguo e asciutto mescolati, n = 17); SMAP 0-5 cm su 9 km; NDVI da una finestra di 2 km che mescola colture.",
    "<b>Sensibilità.</b> Il Monte Carlo è indicativo; il passato non copre il clima futuro.",
    "<b>App.</b> Il suo aspetto nel browser non è stato controllato da una persona.",
])

# ----------------------------------------------------------------------------------------------- 13
H(2, "13. Miglioramenti possibili")
T(["Fatto dalla proposta", "Ancora da fare (in ordine di utilità per le decisioni)"], [
    ["Penman-Monteith; fasi in gradi-giorno; suolo da SoilGrids; coefficienti dalle fonti; penalità di ristoppio; caldo in fioritura; "
     "due strati e doppio coefficiente; validazione SMAP, NDVI, ISTAT; sensibilità.",
     "Falda e risalita capillare. Concime attraverso il pool di azoto minerale. Perdite del frumento negli anni umidi (malattie, ristagno). "
     "Effluenti zootecnici. Dati di campo: resa, irrigazione e coltura per appezzamento, per sostituire le rese provinciali. NDVI a 10 m "
     "per campo al posto della finestra da 2 km. Rimisurare le penalità di rotazione su dati padani. Estendere oltre il 2022 quando POWER sarà "
     "corretto o con una pioggia diversa."],
], [6.5, 10.8], small=True)

H(2, "Riferimenti principali")
Pg("Allen R.G. et al. (1998), FAO Irrigation and Drainage Paper 56. Doorenbos J., Kassam A.H. (1979), FAO Paper 33. FAO AquaCrop Reference Manual "
   "v7.3. Deryng D. et al. (2014), Environ. Res. Lett. 9, 034011. Teixeira E.I. et al. (2013), Agric. For. Meteorol. 170. Seifert C.A. et al. (2017), "
   "Agron. J. 109. Marini L. et al. (2020), Environ. Res. Lett. 15. Saxton K.E., Rawls W.J. (2006), SSSAJ 70. Salvagiotti F. et al. (2008), "
   "Field Crops Res. 108. Marino S. et al. (2008) per le PRCC. Elenco completo con DOI in <c>docs/fonti_*.md</c>. "
   "Dati: NASA POWER, GPM IMERG V07, SMAP SPL3SMP_E V006, MODIS MOD13Q1 (ORNL DAAC), SoilGrids 2.0 (ISRIC), ISTAT, ARPA Lombardia "
   "(<c>README.md</c>). Uso dell'intelligenza artificiale: <c>AI_USAGE.md</c>.")


# =============================================================================== resa Markdown
def md_inline(t: str) -> str:
    t = re.sub(r"</?b>", "**", t)
    t = re.sub(r"</?i>", "*", t)
    t = re.sub(r"</?c>", "`", t)
    return t


def render_md() -> str:
    out = []
    for b in BL:
        k = b[0]
        if k == "h":
            out.append("#" * b[1] + " " + md_inline(b[2]) + "\n")
        elif k == "p":
            out.append(md_inline(b[1]) + "\n")
        elif k == "box":
            out.append("> " + md_inline(b[1]) + "\n")
        elif k == "ul":
            out.append("\n".join("- " + md_inline(i) for i in b[1]) + "\n")
        elif k == "t":
            head, rows, _, note, _s = b[1:]
            esc = lambda s: md_inline(str(s)).replace("|", "\\|")      # noqa: E731
            out.append("| " + " | ".join(esc(h) for h in head) + " |")
            out.append("|" + "---|" * len(head))
            out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
            if note:
                out.append("\n*" + md_inline(note) + "*")
            out.append("")
        elif k == "f":
            for f in b[1]:
                out.append(f"![{md_inline(b[2])}](figure/{f})")
            out.append("\n*" + md_inline(b[2]) + "*\n")
    return "\n".join(out)


# =============================================================================== resa PDF
def render_pdf(path: Path) -> int:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)
    from PIL import Image as PILImage

    VERDE, GRIGIO, CHIARO = colors.HexColor("#1f5e3a"), colors.HexColor("#555555"), colors.HexColor("#eef3ef")
    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=11.6, alignment=TA_LEFT, spaceAfter=4.5)
    st = {"p": base,
          "h1": ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold", fontSize=19, leading=23, textColor=VERDE, spaceAfter=6),
          "h2": ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold", fontSize=11.5, leading=14, textColor=VERDE, spaceBefore=8, spaceAfter=4),
          "h3": ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold", fontSize=10, leading=12, spaceBefore=5, spaceAfter=3),
          "li": ParagraphStyle("li", parent=base, leftIndent=11, bulletIndent=2, spaceAfter=2.5),
          "cell": ParagraphStyle("cell", parent=base, fontSize=7.6, leading=9.2, spaceAfter=0),
          "cellh": ParagraphStyle("cellh", parent=base, fontName="Helvetica-Bold", fontSize=7.6, leading=9.2, spaceAfter=0, textColor=colors.white),
          "cap": ParagraphStyle("cap", parent=base, fontSize=7.8, leading=9.5, textColor=GRIGIO, spaceAfter=7),
          "box": ParagraphStyle("box", parent=base, backColor=CHIARO, borderColor=VERDE, borderWidth=0.8, borderPadding=5, spaceBefore=4, spaceAfter=9)}

    def fix(t: str) -> str:
        parts = re.split(r"(</?[bic]>)", t)
        out = []
        for s in parts:
            if re.fullmatch(r"</?[bic]>", s):
                out.append({"<c>": '<font name="Courier" size="8">', "</c>": "</font>"}.get(s, s))
            else:
                out.append(html.escape(s, quote=False))
        return "".join(out)

    flow = []
    for b in BL:
        k = b[0]
        if k == "h":
            flow.append(Paragraph(fix(b[2]), st["h1" if b[1] == 1 else "h2"]))
        elif k == "p":
            flow.append(Paragraph(fix(b[1]), st["p"]))
        elif k == "box":
            flow.append(Paragraph(fix(b[1]), st["box"]))
        elif k == "ul":
            for i in b[1]:
                flow.append(Paragraph(fix(i), st["li"], bulletText="•"))
            flow.append(Spacer(1, 3))
        elif k == "t":
            head, rows, widths, note, small = b[1:]
            tot = sum(widths)
            cw = [w / tot * 17.4 * cm for w in widths]
            data = [[Paragraph(fix(str(h)), st["cellh"]) for h in head]] + \
                   [[Paragraph(fix(str(c)), st["cell"]) for c in r] for r in rows]
            tb = Table(data, colWidths=cw, repeatRows=1)
            tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), VERDE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CHIARO]),
                                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#b8c4bb")),
                                    ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                                    ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
            flow.append(CondPageBreak(3.5 * cm))
            blocco = [tb] + ([Paragraph(fix(note), st["cap"])] if note else [Spacer(1, 6)])
            flow.append(KeepTogether(blocco) if len(rows) <= 12 else tb)
            if len(rows) > 12 and note:
                flow.append(Paragraph(fix(note), st["cap"]))
        elif k == "f":
            files, cap, wcm = b[1:]
            imgs = []
            wt = wcm if len(files) == 1 else wcm / len(files) - 0.1
            for f in files:
                w, h = PILImage.open(FIG / f).size
                imgs.append(Image(str(FIG / f), width=wt * cm, height=wt * cm * h / w))
            if len(files) == 1:
                row = imgs[0]
            else:
                # figure larghe una sotto l'altra, figure strette (tornado) affiancate
                wide = all(PILImage.open(FIG / f).size[0] / PILImage.open(FIG / f).size[1] > 1.6 for f in files)
                if wide:
                    imgs = []
                    for f in files:
                        w, h = PILImage.open(FIG / f).size
                        imgs.append(Image(str(FIG / f), width=wcm * cm * 0.8, height=wcm * cm * 0.8 * h / w))
                    row = imgs
                else:
                    row = Table([imgs], colWidths=[(wcm / len(files)) * cm] * len(files))
            if isinstance(row, list):
                flow.append(KeepTogether(row + [Paragraph(fix(cap), st["cap"])]))
            else:
                flow.append(KeepTogether([row, Paragraph(fix(cap), st["cap"])]))
        elif k == "pb":
            flow.append(PageBreak())

    def pie(canv, doc):
        canv.saveState()
        canv.setFont("Helvetica", 7.5)
        canv.setFillColor(GRIGIO)
        canv.drawString(1.8 * cm, 1.1 * cm, f"FIELDWISE - report per il team - {oggi}")
        canv.drawRightString(A4[0] - 1.8 * cm, 1.1 * cm, f"pagina {doc.page}")
        canv.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.8 * cm,
                            title="FIELDWISE - report per il team", author="Team FIELDWISE", subject="NASA Space Apps Challenge 2026")
    doc.build(flow, onFirstPage=pie, onLaterPages=pie)
    return doc.page


if __name__ == "__main__":
    OUT_MD.write_text(render_md(), encoding="utf-8")
    pagine = render_pdf(OUT_PDF)
    print(f"scritti {OUT_MD.relative_to(ROOT)} e {OUT_PDF.relative_to(ROOT)} ({pagine} pagine)")
