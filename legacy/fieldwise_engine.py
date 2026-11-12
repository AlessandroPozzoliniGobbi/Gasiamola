"""
FIELDWISE - motore di simulazione delle rotazioni colturali
============================================================

COSA FA, IN UNA FRASE
    Prende il meteo reale di un punto (NASA POWER, 2000-2025), un suolo e una
    lista di colture, e simula giorno per giorno cosa succede all'acqua del
    suolo; a fine di ogni coltura aggiorna azoto e sostanza organica; passa il
    suolo cosi' com'e' alla coltura successiva; ripete per tutte le rotazioni
    possibili e per tutte le annate storiche di partenza.

STRUTTURA DEL FILE (in ordine di lettura)
    0. Parametri      colture, suolo, ipotesi di contabilita'
    1. Meteo          download NASA POWER, calcolo di ET0, meteo finto di test
    2. Punto 3        run_segment()       bilancio idrico GIORNALIERO (FAO-56)
    3. Punto 4        update_soil()       azoto e humus a FINE SEGMENTO
    4. Punto 5        simulate_rotation() catena di colture, stato mai azzerato
                      ensemble()          ogni rotazione x ogni annata storica
    5. main           esempio d'uso su Cremona

LO "STATO DEL SUOLO" (sostituisce il vettore dinamico del terreno F(t))
    E' un dizionario di tre numeri che vengono modificati man mano:
        st["D"]  deficit idrico, in mm: quanta acqua MANCA al profilo per
                 essere pieno (0 = suolo a capacita' di campo, cioe' pieno;
                 TAW = suolo al punto di appassimento, cioe' vuoto per la pianta)
        st["N"]  azoto minerale disponibile, in kg/ha
        st["H"]  humus (sostanza organica stabile) dei primi 30 cm, in t/ha
    Si usa il DEFICIT invece dell'acqua contenuta perche' e' la convenzione
    FAO-56: le formule dello stress sono scritte in termini di deficit.

LA COLTURA (sostituisce il vettore dinamico della coltura C(t))
    Non e' un vettore da confrontare col suolo. E' una riga di parametri
    (classe Crop) piu' una funzione, kc_and_roots(), che dato il giorno dalla
    semina restituisce quanto la pianta "chiede" (Kc) e fin dove "pesca" (radici).
    La compatibilita' non e' un punteggio: e' lo STRESS che risulta quando la
    richiesta della pianta incontra lo stato reale del suolo.

AVVERTENZA SUI NUMERI
    I parametri sono valori indicativi presi da FAO-56 (tabelle 11, 12, 22),
    FAO-33 (Ky) e letteratura agronomica generale. NON sono calibrati sulla
    Pianura Padana. Prima della consegna vanno verificati uno per uno e citati.

DIPENDENZE
    pip install numpy pandas requests
"""
from dataclasses import dataclass
import datetime as dt
import itertools
import math
import os

import numpy as np
import pandas as pd


# =============================================================================
# 0. PARAMETRI
# =============================================================================

@dataclass(frozen=True)
class Crop:
    """Tutto quello che il motore deve sapere di una coltura.

    frozen=True rende l'oggetto immutabile: una coltura e' un insieme di
    costanti, non deve cambiare durante la simulazione (cambia il suolo).
    """
    name: str
    sow: tuple            # (mese, giorno) della semina tipica in Pianura Padana
    stages: tuple         # durata in giorni delle 4 fasi FAO-56:
                          #   iniziale, sviluppo, piena stagione, finale
                          #   la somma e' la durata del ciclo (semina -> raccolta)
    kc: tuple             # coefficiente colturale Kc nelle fasi iniziale,
                          #   piena stagione, finale (FAO-56 tab. 12).
                          #   Consumo della coltura = Kc x consumo del prato (ET0)
    zr_max: float         # profondita' massima delle radici, in metri
    p: float              # frazione dell'acqua disponibile che la pianta
                          #   estrae SENZA andare in stress (FAO-56 tab. 22)
    ky: float             # sensibilita' della resa allo stress idrico (FAO-33):
                          #   perdita di resa % = Ky x deficit di traspirazione %
    y_pot: float          # resa potenziale di granella senza stress, t/ha
    n_uptake: float       # kg di azoto assorbiti dalla pianta intera
                          #   per ogni tonnellata di granella prodotta
    n_fix: float          # quota dell'azoto presa dall'aria (solo leguminose)
    n_export: float       # quota dell'azoto assorbito che esce dal campo con
                          #   la granella; il resto resta nei residui
    res_release: float    # quota dell'azoto dei residui che si libera in tempo
                          #   utile per la coltura successiva (alta per la soia,
                          #   residui ricchi di N; bassa per paglia e stocchi)
    hi: float             # indice di raccolta = granella / biomassa aerea.
                          #   Serve per stimare quanti residui restano in campo
    k1: float             # coefficiente isoumico: quota della sostanza secca
                          #   dei residui che diventa humus stabile (Henin-Dupuis)
    irrigable: bool       # se la coltura viene irrigata quando serve


#                name        semina    fasi (gg)        Kc ini/mid/end      Zr   p     Ky    Yp    Nup  fix   exp   rel   HI    k1   irr
MAIS = Crop("mais", (4, 10), (30, 40, 50, 30), (0.30, 1.20, 0.50), 1.2, 0.55,
            1.25, 12.0, 22.0, 0.00, 0.65, 0.10, 0.50, 0.12, True)
SOIA = Crop("soia", (5, 5), (20, 35, 60, 25), (0.40, 1.15, 0.50), 1.0, 0.50,
            0.85, 4.5, 75.0, 0.55, 0.75, 0.50, 0.42, 0.10, True)
# Il frumento non viene irrigato: cresce in inverno-primavera, quando piove
FRUMENTO = Crop("frumento", (10, 25), (30, 140, 40, 30), (0.70, 1.15, 0.30), 1.5,
                0.55, 1.05, 7.5, 28.0, 0.00, 0.75, 0.10, 0.45, 0.13, False)
CROPS = [MAIS, SOIA, FRUMENTO]


@dataclass(frozen=True)
class Soil:
    """Proprieta' fisse del suolo. Valori di default: suolo franco tipico.

    Per un campo reale si ricavano da SoilGrids (sabbia, argilla, carbonio
    organico) con le funzioni di pedotrasferimento di Saxton-Rawls.
    """
    fc: float = 0.32        # capacita' di campo: acqua trattenuta dopo che il
                            #   suolo ha smesso di drenare (m3 acqua / m3 suolo)
    wp: float = 0.17        # punto di appassimento: sotto questo valore la
                            #   pianta non riesce piu' a estrarre acqua
    z_max: float = 1.5      # spessore del profilo simulato, in metri
    som_pct: float = 2.0    # sostanza organica (%) nei primi 30 cm
    bulk: float = 1.4       # densita' apparente del suolo (t/m3)
    k2: float = 0.017       # coefficiente di mineralizzazione: quota
                            #   dell'humus che si decompone ogni anno

    @property
    def taw(self):
        """TAW, acqua totale disponibile nell'intero profilo, in mm.

        (fc - wp) e' l'acqua utilizzabile per metro cubo di suolo;
        x 1000 converte metri d'acqua in millimetri; x z_max su tutto il profilo.
        Suolo di default: (0,32 - 0,17) x 1000 x 1,5 = 225 mm.
        """
        return 1000 * (self.fc - self.wp) * self.z_max

    @property
    def h0(self):
        """Humus iniziale dei primi 30 cm, in t/ha.

        % sostanza organica x densita' (t/m3) x spessore (0,30 m) x 10.000 m2/ha.
        Default: 0,02 x 1,4 x 0,30 x 10.000 = 84 t/ha.
        """
        return self.som_pct / 100 * self.bulk * 0.30 * 10000


# Ipotesi della contabilita' di azoto e humus (punto 4).
# Sono tutte qui, in un posto solo, perche' sono le piu' incerte del modello:
# devono essere visibili, discutibili e sostituibili con valori citati.
HUMUS_N = 0.05          # l'humus contiene circa il 5% di azoto (rapporto C/N ~10)
FERT_EFF = 0.70         # quota del concime che la coltura riesce davvero ad
                        #   assorbire; il resto si perde o resta nel suolo
FERT_RESIDUAL = 0.15    # quota del concime che resta nel suolo dopo la raccolta
COVER_CATCH = 50.0      # kg N/ha che una cover crop assorbe in autunno-inverno,
                        #   sottraendoli alla lisciviazione
COVER_RETURN = 0.50     # quota di quell'azoto che torna disponibile quando la
                        #   cover viene interrata
COVER_BIOMASS = 3.0     # sostanza secca prodotta dalla cover crop, t/ha
COVER_K1 = 0.08         # coefficiente isoumico della cover (biomassa giovane,
                        #   si decompone in fretta: rende meno humus della paglia)
COVER_MIN_DAYS = 100    # se l'intervallo tra due colture e' piu' corto, la
                        #   cover non ha tempo di crescere e non si semina
N_START = 40.0          # azoto minerale nel suolo a inizio simulazione, kg/ha
IRR_DOSE = 40.0         # mm d'acqua per ogni turno di irrigazione
RAIN_MAX = 60.0         # mm al giorno che il suolo riesce a infiltrare; oltre,
                        #   l'acqua scorre via in superficie (ruscellamento)
HEAT_T = 35.0           # soglia di temperatura massima per contare un giorno
                        #   di stress termico durante la fioritura


# =============================================================================
# 1. METEO
# =============================================================================

class Weather:
    """Serie meteo giornaliera pronta per il motore.

    Converte la tabella in array numpy (accesso veloce per indice) e calcola
    subito ET0 per tutti i giorni, cosi' il motore non lo ricalcola mai.
    """

    def __init__(self, df, lat):
        # df: colonne date, tmax (°C), tmin (°C), rain (mm/giorno), senza buchi
        df = df.sort_values("date").reset_index(drop=True)
        self.start = pd.Timestamp(df["date"].iloc[0]).date()
        self.end = pd.Timestamp(df["date"].iloc[-1]).date()
        self.tmax = df["tmax"].to_numpy(float)
        self.tmin = df["tmin"].to_numpy(float)
        self.rain = df["rain"].to_numpy(float)
        doy = pd.to_datetime(df["date"]).dt.dayofyear.to_numpy()   # giorno dell'anno
        self.et0 = hargreaves_et0(self.tmax, self.tmin, doy, lat)

    def idx(self, date):
        """Converte una data nella posizione corrispondente negli array."""
        return (date - self.start).days


def hargreaves_et0(tmax, tmin, doy, lat_deg):
    """ET0 (mm/giorno) con la formula di Hargreaves, FAO-56 equazione 52.

    ET0 e' l'acqua che evapora in un giorno da un prato di riferimento ben
    irrigato. Dipende solo dal clima, non dalla coltura.

    Hargreaves usa solo le temperature: piu' fa caldo e piu' e' ampia
    l'escursione tra giorno e notte (cielo sereno), piu' acqua evapora.
    La radiazione solare "teorica" in cima all'atmosfera (Ra) dipende solo
    dalla latitudine e dal giorno dell'anno, e si calcola con la geometria
    sole-terra (FAO-56 equazioni 21-25).

    Per la versione finale conviene Penman-Monteith (libreria pyet), che usa
    anche radiazione misurata, umidita' e vento di NASA POWER ed e' piu' precisa.
    """
    phi = math.radians(lat_deg)                                   # latitudine in radianti
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)                # distanza relativa terra-sole
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)          # declinazione solare
    ws = np.arccos(-np.tan(phi) * np.tan(delta))                  # angolo orario al tramonto
    ra = (24 * 60 / np.pi) * 0.0820 * dr * (                      # radiazione extraterrestre,
        ws * np.sin(phi) * np.sin(delta)                          #   MJ/m2/giorno
        + np.cos(phi) * np.cos(delta) * np.sin(ws))
    tmean = (tmax + tmin) / 2
    # 0,408 converte MJ/m2 in mm di acqua evaporata
    return 0.0023 * (tmean + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0)) * ra * 0.408


def fetch_power(lat, lon, start="20000101", end="20251231"):
    """Scarica il meteo giornaliero da NASA POWER. Non serve nessun login.

    community="AG" restituisce i dati nelle unita' usate in agronomia.
    PRECTOTCORR e' la precipitazione corretta per i bias, T2M_MAX/T2M_MIN le
    temperature a 2 metri. Risoluzione: celle di circa 50 km.
    """
    import requests
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    par = dict(parameters="T2M_MAX,T2M_MIN,PRECTOTCORR", community="AG",
               longitude=lon, latitude=lat, start=start, end=end, format="JSON")
    js = requests.get(url, params=par, timeout=120).json()
    p = js["properties"]["parameter"]
    df = pd.DataFrame({"tmax": p["T2M_MAX"], "tmin": p["T2M_MIN"],
                       "rain": p["PRECTOTCORR"]})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    # POWER indica i dati mancanti con -999: li sostituiamo interpolando
    df = df.replace(-999, np.nan).interpolate().bfill().ffill()
    return df.rename_axis("date").reset_index()


def synthetic_weather(seed=0, dry_years=(2003, 2012, 2022)):
    """Meteo FINTO con stagioni tipo Pianura Padana. Serve SOLO a collaudare il
    codice quando non c'e' rete: i risultati non hanno valore agronomico."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2000-01-01", "2025-12-31", freq="D")
    doy = dates.dayofyear.to_numpy()
    season = -np.cos(2 * np.pi * (doy - 15) / 365)           # -1 inverno, +1 estate
    dry = np.isin(dates.year, dry_years) & (dates.month >= 5) & (dates.month <= 8)
    tmean = 13.5 + 11 * season + rng.normal(0, 2.5, len(dates)) + 2.5 * dry
    spread = 9 + 2 * season + 1.5 * dry
    wet = rng.random(len(dates)) < np.where(dry, 0.08, 0.27)
    rain = np.where(wet, rng.gamma(0.8, 10.0, len(dates)), 0.0)
    return pd.DataFrame({"date": dates, "tmax": tmean + spread / 2,
                         "tmin": tmean - spread / 2, "rain": rain})


# =============================================================================
# 2. PUNTO 3 - BILANCIO IDRICO GIORNALIERO (FAO-56)
# =============================================================================

def kc_and_roots(crop, d):
    """Quanto chiede la pianta e fin dove arriva, al giorno d dalla semina.

    Kc segue la curva a quattro tratti di FAO-56 (figura 34):
      - fase iniziale:   costante a Kc_ini (pianta piccola, suolo quasi nudo)
      - sviluppo:        sale in linea retta da Kc_ini a Kc_mid
      - piena stagione:  costante a Kc_mid (chioma che copre tutto il suolo)
      - fase finale:     scende in linea retta verso Kc_end (maturazione)
    Le radici partono da 15 cm alla semina e crescono in linea retta fino a
    zr_max, che raggiungono alla fine della fase di sviluppo.
    """
    l1, l2, l3, l4 = crop.stages
    kci, kcm, kce = crop.kc
    if d < l1:
        kc = kci
    elif d < l1 + l2:
        kc = kci + (kcm - kci) * (d - l1) / l2
    elif d < l1 + l2 + l3:
        kc = kcm
    else:
        kc = kcm + (kce - kcm) * (d - l1 - l2 - l3) / l4
    zr = min(crop.zr_max, 0.15 + (crop.zr_max - 0.15) * d / (l1 + l2))
    return kc, zr


def run_segment(w, i0, i1, st, soil, crop=None, cover=False, irrig_cap=0.0):
    """Fa avanzare l'acqua del suolo dal giorno i0 al giorno i1 (escluso).

    Un "segmento" e' un tratto di tempo con un solo uso del suolo:
      crop=Crop       una coltura dalla semina alla raccolta
      crop=None       un intervallo tra due colture: suolo nudo,
                      oppure cover crop se cover=True
    irrig_cap e' il massimo di mm irrigabili nel segmento (0 = solo pioggia).

    Modifica st["D"] sul posto e restituisce i totali del segmento, che poi
    update_soil() usa per resa, azoto e lisciviazione.
    """
    eta = etc = irr = drain = 0.0
    heat = 0
    for i in range(i0, i1):
        d = i - i0                          # giorni trascorsi dall'inizio del segmento

        # (1) Cosa chiede la superficie oggi e quanto e' profonda la zona radicale
        if crop is not None:
            kc, zr = kc_and_roots(crop, d)
            p = crop.p
        elif cover:
            kc, zr, p = 0.60, 0.60, 0.50    # cover crop: copertura media, radici a 60 cm
        else:
            kc, zr, p = 0.25, 0.30, 0.40    # suolo nudo: solo evaporazione dallo strato
                                            #   superficiale

        # (2) Acqua che la pianta puo' vedere. Il modello ha UN solo strato di
        # suolo, quindi assume che il deficit sia distribuito uniformemente:
        # la zona radicale contiene la frazione zr / z_max di tutto.
        frac = zr / soil.z_max
        taw = soil.taw * frac               # TAW della zona radicale (mm)
        raw = p * taw                       # RAW: acqua estraibile senza stress (mm)
        dr = st["D"] * frac                 # deficit nella zona radicale (mm)

        # (3) Irrigazione: se la pianta sta per entrare in stress e resta budget,
        # si da' un turno di IRR_DOSE mm (mai piu' del deficit: non si
        # irriga oltre la capacita' di campo).
        if crop is not None and crop.irrigable and dr > raw and irr < irrig_cap:
            dose = min(IRR_DOSE, irrig_cap - irr, st["D"])
            irr += dose
            st["D"] -= dose
            dr = st["D"] * frac

        # (4) Coefficiente di stress Ks (FAO-56 eq. 84).
        # Finche' il deficit non supera RAW la pianta traspira al massimo (Ks=1).
        # Oltre RAW, Ks cala in linea retta fino a 0 quando il suolo e' al punto
        # di appassimento (deficit = TAW). E' qui la non-linearita' del modello.
        ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / (taw - raw))

        # (5) Consumo potenziale (ETc) e consumo reale (ETa)
        e_c = kc * w.et0[i]                 # quanto consumerebbe senza stress
        e_a = ks * e_c                      # quanto consuma davvero

        # (6) Bilancio di massa: il deficit cresce con il consumo e cala con
        # la pioggia infiltrata (oltre RAIN_MAX mm/giorno l'acqua ruscella via)
        st["D"] += e_a - min(w.rain[i], RAIN_MAX)

        # (7) Drenaggio: se il deficit diventa negativo il profilo e' piu' che
        # pieno, l'eccesso scende sotto le radici e si perde (porta via azoto).
        if st["D"] < 0:
            drain -= st["D"]
            st["D"] = 0.0
        # il deficit non puo' superare TAW (suolo gia' al punto di appassimento)
        st["D"] = min(st["D"], soil.taw)

        eta += e_a
        etc += e_c

        # (8) Stress termico: giorni con Tmax oltre soglia in piena stagione,
        # cioe' attorno alla fioritura, quando il caldo fa piu' danni
        if crop is not None:
            l1, l2, l3, _ = crop.stages
            if l1 + l2 <= d < l1 + l2 + l3 and w.tmax[i] > HEAT_T:
                heat += 1

    return dict(eta=eta, etc=etc, irr=irr, drain=drain, heat=heat, days=i1 - i0)


# =============================================================================
# 3. PUNTO 4 - AZOTO E HUMUS A FINE SEGMENTO
# =============================================================================

def update_soil(st, soil, seg, crop=None, cover=False):
    """Aggiorna st["N"] e st["H"] alla fine di un segmento, usando i totali
    calcolati da run_segment(). Restituisce resa, concime e lisciviazione.

    Perche' a fine segmento e non ogni giorno: azoto e humus cambiano
    lentamente, e una contabilita' di entrate e uscite per ciclo e' abbastanza
    precisa per confrontare rotazioni, con molti meno parametri da inventare.
    """
    out = dict(rel=None, yield_t=0.0, fert=0.0, leach=0.0)
    years = seg["days"] / 365

    # (1) Mineralizzazione: ogni anno si decompone la quota k2 dell'humus.
    # L'humus perso libera azoto minerale (HUMUS_N = 5% del peso; x1000 da t a kg).
    miner_h = soil.k2 * st["H"] * years
    miner_n = miner_h * 1000 * HUMUS_N
    st["H"] -= miner_h

    # (2) Lisciviazione: l'acqua che drena sotto le radici porta via nitrati.
    # La quota persa e' il drenaggio diviso per l'acqua contenuta nel profilo
    # a capacita' di campo: se drena un profilo intero, si perde tutto.
    # La cover crop assorbe fino a COVER_CATCH kg e li mette al riparo.
    # Solo meta' dell'azoto mineralizzato e' esposto (si libera nel tempo).
    catch = min(st["N"], COVER_CATCH) if cover else 0.0
    exposed = st["N"] - catch + 0.5 * miner_n
    leach = exposed * min(1.0, seg["drain"] / (1000 * soil.fc * soil.z_max))
    st["N"] = st["N"] - catch + miner_n - leach
    out["leach"] = leach

    # (3) Cover crop: quando viene interrata restituisce una parte dell'azoto
    # catturato e lascia biomassa che diventa humus
    if cover:
        st["N"] += COVER_RETURN * catch
        st["H"] += COVER_K1 * COVER_BIOMASS

    if crop is not None:
        # (4) Resa relativa con FAO-33: 1 - Ky x (1 - ETa/ETc).
        # ETa/ETc e' la frazione d'acqua che la pianta ha davvero potuto usare.
        rel = max(0.0, 1 - crop.ky * (1 - seg["eta"] / seg["etc"]))
        y = crop.y_pot * rel                         # resa in t/ha

        # (5) Fabbisogno di azoto: proporzionale alla resa ottenuta.
        # Le leguminose ne prendono una parte dall'aria (n_fix).
        uptake = y * crop.n_uptake                   # azoto totale nella pianta
        demand = uptake * (1 - crop.n_fix)           # azoto chiesto al suolo
        if crop.n_fix > 0:                           # leguminosa: se il suolo e'
            demand = min(demand, st["N"])            # povero fissa di piu', niente concime

        # (6) Concime: quello che il suolo non copre, diviso l'efficienza
        # (per far arrivare 70 kg alla pianta ne servono 100 nel campo)
        fert = max(0.0, demand - st["N"]) / FERT_EFF
        st["N"] = max(0.0, st["N"] - demand) + FERT_RESIDUAL * fert

        # (7) Residui: l'azoto che non esce con la granella resta nei residui,
        # e una parte (res_release) torna disponibile per la coltura dopo.
        # Qui si vede l'effetto della soia: residui ricchi di azoto.
        st["N"] += crop.res_release * uptake * (1 - crop.n_export)

        # (8) Humus dai residui (Henin-Dupuis): biomassa dei residui
        # = granella x (1 - HI) / HI; una quota k1 diventa humus stabile.
        st["H"] += crop.k1 * y * (1 - crop.hi) / crop.hi

        out.update(rel=rel, yield_t=y, fert=fert)
    return out


# =============================================================================
# 4. PUNTO 5 - CATENA DI ROTAZIONE ED ENSEMBLE STORICO
# =============================================================================

def next_date(after, month, day):
    """Prima data (mese, giorno) uguale o successiva a 'after'.
    Esempio: dopo il 20 settembre 2010, la prossima semina del frumento
    (25 ottobre) e' il 25 ottobre 2010; quella del mais (10 aprile) e' il 2011."""
    d = dt.date(after.year, month, day)
    return d if d >= after else dt.date(after.year + 1, month, day)


def simulate_rotation(w, seq, covers, start_year, soil, irrig_cap=0.0):
    """Simula una rotazione completa partendo da un certo anno.

    seq       lista di Crop, per esempio [MAIS, SOIA, FRUMENTO]
    covers    lista di True/False: covers[k] indica se nell'intervallo DOPO
              la coltura k si semina una cover crop
    irrig_cap mm irrigabili per coltura (0 = asciutto, valore enorme = libero)

    Restituisce gli indicatori medi per anno, oppure None se la serie meteo
    finisce prima che la rotazione sia completa.
    """
    # Stato iniziale del suolo: profilo pieno d'acqua (D=0) al 1° gennaio,
    # azoto di partenza, humus calcolato dalla % di sostanza organica
    st = dict(D=0.0, N=N_START, H=soil.h0)
    t = dt.date(start_year, 1, 1)
    first_sow = next_date(t, *seq[0].sow)

    # Avviamento: suolo nudo dal 1° gennaio alla prima semina. Serve solo a
    # portare l'acqua del suolo in una condizione realistica; i suoi numeri
    # non entrano negli indicatori.
    seg = run_segment(w, w.idx(t), w.idx(first_sow), st, soil)
    update_soil(st, soil, seg)
    h_start = st["H"]

    t = first_sow
    tot = dict(irr=0.0, fert=0.0, leach=0.0, heat=0.0)
    rels = []
    n = len(seq)
    for k, crop in enumerate(seq):
        # (1) Date: raccolta = semina + durata del ciclo. La coltura dopo si
        # semina alla sua prima data utile, almeno 10 giorni dopo la raccolta
        # (tempo per lavorare il terreno). Dopo l'ultima coltura si torna alla
        # prima: cosi' il ciclo si chiude e la rotazione dura anni interi.
        harvest = t + dt.timedelta(days=sum(crop.stages))
        nxt = seq[(k + 1) % n]
        next_sow = next_date(harvest + dt.timedelta(days=10), *nxt.sow)
        if next_sow > w.end:
            return None                     # meteo insufficiente per finire

        # (2) Segmento della coltura: acqua giorno per giorno, poi resa,
        # azoto e humus. Lo stato st esce modificato.
        seg = run_segment(w, w.idx(t), w.idx(harvest), st, soil, crop=crop,
                          irrig_cap=irrig_cap)
        res = update_soil(st, soil, seg, crop=crop)
        rels.append(res["rel"])
        tot["irr"] += seg["irr"]
        tot["heat"] += seg["heat"]
        tot["fert"] += res["fert"]
        tot["leach"] += res["leach"]

        # (3) Intervallo fino alla semina successiva: suolo nudo o cover crop.
        # Qui avviene gran parte della lisciviazione (piogge autunno-inverno).
        use_cover = covers[k] and (next_sow - harvest).days >= COVER_MIN_DAYS
        seg = run_segment(w, w.idx(harvest), w.idx(next_sow), st, soil,
                          cover=use_cover)
        res = update_soil(st, soil, seg, cover=use_cover)
        tot["leach"] += res["leach"]

        # (4) Il punto chiave: st NON viene azzerato. La coltura successiva
        # parte dall'acqua, dall'azoto e dall'humus lasciati da questa.
        t = next_sow

    # Indicatori divisi per la durata in anni, per confrontare rotazioni
    # che durano 3, 4 o 5 anni (dipende da come si incastrano le semine)
    years = (t - first_sow).days / 365
    return dict(years=round(years, 1),
                resa_rel=float(np.mean(rels)),           # resa relativa media
                resa_min=float(np.min(rels)),            # coltura andata peggio
                irrigazione_mm=tot["irr"] / years,
                concime_kgN=tot["fert"] / years,
                lisciviazione_kgN=tot["leach"] / years,
                humus_kg=(st["H"] - h_start) / years * 1000,   # variazione kg/ha/anno
                giorni_caldo=tot["heat"] / years)


def label(seq, covers):
    """Nome leggibile della rotazione, es. 'mais > soia+cover > frumento'."""
    return " > ".join(c.name + ("+cover" if cv else "") for c, cv in zip(seq, covers))


def ensemble(w, soil, crops=CROPS, length=3, irrig_cap=0.0):
    """Prova TUTTE le rotazioni su TUTTE le annate di partenza.

    Rotazioni: 3 colture in 3 posizioni = 27 sequenze, ciascuna con o senza
    cover in ogni intervallo = 8 varianti, totale 216. Sono poche: le si prova
    tutte (enumerazione completa) invece di usare un ottimizzatore. Il gradiente
    qui non serve, perche' la scelta della coltura e' discreta.

    Annate: ogni rotazione parte da ogni anno disponibile. Ogni partenza e' un
    "futuro possibile" ricostruito dal passato: non e' una previsione meteo,
    e' una stima di come va la rotazione in un anno medio e in uno pessimo.

    Restituisce (dettaglio di ogni simulazione, sintesi per rotazione).
    """
    rows = []
    for seq in itertools.product(crops, repeat=length):
        for covers in itertools.product([False, True], repeat=length):
            for year in range(w.start.year, w.end.year + 1):
                r = simulate_rotation(w, seq, covers, year, soil, irrig_cap)
                if r is not None:
                    rows.append(dict(rotazione=label(seq, covers), anno=year, **r))
    detail = pd.DataFrame(rows)
    g = detail.groupby("rotazione")
    summary = pd.DataFrame({
        "resa_mediana": g["resa_rel"].median(),           # anno tipico
        "resa_anno_peggiore": g["resa_rel"].min(),         # rischio
        "irrigazione_mm": g["irrigazione_mm"].median(),
        "concime_kgN": g["concime_kgN"].median(),
        "lisciviazione_kgN": g["lisciviazione_kgN"].median(),
        "humus_kg": g["humus_kg"].median(),
        "partenze": g.size(),                              # quante annate usate
    })
    return detail, summary


# =============================================================================
# 5. ESEMPIO D'USO
# =============================================================================

def load_weather(lat, lon, cache="power_cremona.csv"):
    """Usa il file salvato se c'e' (demo senza rete), altrimenti scarica da
    NASA POWER e salva; se non c'e' rete, ripiega sul meteo finto."""
    if os.path.exists(cache):
        return pd.read_csv(cache, parse_dates=["date"]), "cache locale"
    try:
        df = fetch_power(lat, lon)
        df.to_csv(cache, index=False)
        return df, "NASA POWER"
    except Exception as exc:
        return synthetic_weather(), "meteo sintetico (%s)" % type(exc).__name__


if __name__ == "__main__":
    LAT, LON = 45.2, 10.0                    # cella NASA POWER vicino a Cremona
    data, source = load_weather(LAT, LON)
    print("Meteo:", source)
    weather = Weather(data, LAT)

    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 20)
    show = ["mais > mais > mais", "mais+cover > mais+cover > mais+cover",
            "mais > soia > frumento", "mais > frumento+cover > soia",
            "soia > soia > soia", "frumento > frumento > frumento"]

    # Tre scenari d'acqua: solo pioggia, irrigazione limitata, irrigazione libera
    for cap, name in [(0.0, "solo pioggia"), (200.0, "max 200 mm per coltura"),
                      (1e9, "irrigazione libera")]:
        detail, summary = ensemble(weather, Soil(), irrig_cap=cap)
        print("\n=== %s (%d rotazioni)" % (name, len(summary)))
        print(summary.loc[show].round(2).to_string())
