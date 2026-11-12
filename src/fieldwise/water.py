"""Bilancio idrico giornaliero a due strati (FAO-56, Allen et al. 1998, cap. 7 e 8).

Fonte: Allen R.G., Pereira L.S., Raes D., Smith M. (1998). Crop evapotranspiration.
FAO Irrigation and Drainage Paper 56. https://www.fao.org/4/x0490e/x0490e00.htm
(cap. 6: x0490e0b.htm; cap. 7: x0490e0c.htm; cap. 8: x0490e0e.htm).

Architettura (PLAN.md, D6): il calendario della rotazione e' precalcolato; questo
modulo riceve serie giornaliere gia' pronte (ET0, pioggia, Kc, Zr, p, tipo di
superficie, ...) e attraversa TUTTA la rotazione in un unico ciclo senza mai
azzerare lo stato. Il nucleo `_kernel` usa solo scalari e array ed e' compilato
con numba (`@njit`); senza numba gira in Python puro con lo stesso codice.

Nessun numero agronomico vive qui: suolo, CN, REW, Ze, Kc max, umidita' iniziale,
Kc, radici e p vengono da params/*.yaml. Nel codice restano solo le costanti
interne delle equazioni pubblicate, con il numero dell'equazione (D9).

Modello (scelte dichiarate)
---------------------------
Stato: W1 [mm] acqua nello strato 1 (0 - z1), W2 [mm] nello strato 2 (z1 - z1+z2),
De [mm] esaurimento dello strato evaporante superficiale (spessore Ze, contenuto
dentro lo strato 1; non e' un serbatoio separato, e' una variabile diagnostica
della parte alta di W1). Acqua immagazzinata S = W1 + W2.

Passi di ogni giorno i:
 1. Ruscellamento RO con il Curve Number SCS applicato alla pioggia giornaliera
    (NRCS NEH 630 cap. 10, eq. 10-9 e 10-11, Ia = 0,2 S). Opzionale: CN corretto
    per l'umidita' dello strato 1 interpolando tra ARC I (a wp) e ARC III (a fc),
    con ARC II a meta' (regola di soil.yaml, da AquaCrop v7.3 sez. 3.7.4).
 2. Infiltrazione P - RO nello strato 1; l'eccesso oltre la capacita' di campo
    drena nello stesso giorno nello strato 2 e da questo sotto il profilo
    (percolazione profonda DP). FAO-56 cap. 8, eq. 88 e testo 'Deep percolation'.
 3. Zona radicale: frazioni f1 = min(Zr, z1)/z1 e f2 = clip((Zr - z1)/z2, 0, 1)
    degli strati raggiunti dalle radici, acqua distribuita uniformemente in ogni
    strato. TAW = f1 TAW1 + f2 TAW2 (eq. 82 per strato), Dr = f1 (FC1 - W1) +
    f2 (FC2 - W2) (eq. 87 per strato), limitato a [0, TAW] (eq. 86) nel calcolo
    di Ks. p corretto con l'ETc del giorno (tab. 22, nota: p = p_tab + 0,04 (5 - ETc),
    0,1 <= p <= 0,8); RAW = p TAW (eq. 83).
 4. Irrigazione (solo superficie 'coltura' con coltura irrigabile): se Dr > RAW,
    dose netta I = Dr (riporta la zona radicale alla capacita' di campo; FAO-56
    cap. 8: 'Ii <= Dr,i'), limitata dal tetto residuo del segmento. Nessun
    ruscellamento sull'irrigazione (pioggia o goccia a intensita' infiltrabile).
 5. Coltura o cover crop (Kc singolo, cap. 6): ETc = Kc ET0; Ks = 1 se Dr <= RAW,
    altrimenti Ks = (TAW - Dr) / ((1 - p) TAW) (eq. 84), limitato a [0, 1];
    ETa = Ks ETc (eq. 80-81), mai oltre l'acqua disponibile sopra wp nella zona
    radicale. Ripartizione tra gli strati proporzionale all'acqua disponibile
    (sopra wp) di ciascuno nella zona radicale: nessuno strato scende sotto wp.
    Lo strato evaporante perde la quota Ze/z1 del prelievo dallo strato 1
    (prelievo uniforme nello strato).
    Suolo nudo (cap. 7, formulazione piu' semplice citabile): Kcb = 0 e
    E = Kr Kc_max ET0 (eq. 71 con few = 1 e Kcb = 0, come indicato nel testo di
    FAO-56 per il suolo nudo), Kr = 1 se De <= REW, altrimenti
    Kr = (TEW - De) / (TEW - REW) (eq. 74), TEW = 1000 (theta_FC - 0,5 theta_WP) Ze
    (eq. 73); E tolta allo strato evaporante (De, eq. 77) e quindi allo strato 1.
    Nei giorni di suolo nudo ETc = Kc_max ET0 (evaporazione potenziale) e Ks = 1.
    E non supera l'acqua sopra il limite inferiore dello strato 1 (vedi sotto).
 6. Esaurimento dello strato evaporante: De diminuisce con l'acqua infiltrata
    (eq. 77, la pioggia bagna prima la superficie) e vale 0 quando W1 >= FC1.

Coerenza tra De e W1 (limite inferiore dello strato 1)
------------------------------------------------------
Lo strato 1 e' diviso in due parti: i primi Ze m (strato evaporante) e i restanti
z1 - Ze m. FAO-56 eq. 73 (TEW = 1000 (theta_FC - 0,5 theta_WP) Ze) ammette che lo
strato evaporante si asciughi fino a 0,5 theta_WP; la parte sottostante perde acqua
solo per traspirazione, che si ferma a theta_WP (eq. 82-84). Quindi:
  W1_min = 1000 (theta_WP z1 - 0,5 theta_WP Ze)            [mm]  (eq. 73 + eq. 82)
  De in [max(0, (FC1 - W1) - TAW_sotto), min(TEW, FC1 - W1)],
  TAW_sotto = 1000 (theta_FC - theta_WP) (z1 - Ze)          (eq. 82 sulla parte sotto Ze)
Il limite inferiore di De dice che l'esaurimento dello strato 1 non contenuto nella
parte sotto Ze sta per forza nello strato evaporante: dopo una coltura che ha
portato W1 a wp, De vale almeno l'esaurimento di Ze a wp e il suolo nudo puo'
evaporare solo la quota 0,5 theta_WP Ze (eq. 73-74). Il limite e' imposto dopo
l'infiltrazione e a fine giorno; con E <= W1 - W1_min lo strato 1 non scende mai
sotto W1_min (che e' sotto wp1 di 500 theta_WP Ze mm). La traspirazione resta
limitata a wp in entrambi gli strati.

Limiti: falda e risalita capillare non modellate (CR = 0 in eq. 85, vedi
soil.yaml _meta.limiti); acqua oltre fc drenata in un giorno (eq. 88).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import params as _params
from .et0 import saturation_vapour_pressure

try:  # numba se disponibile, altrimenti Python puro con lo stesso codice
    from numba import njit
    HAVE_NUMBA = True
except Exception:  # pragma: no cover - dipende dall'ambiente
    HAVE_NUMBA = False

    def njit(*args, **kwargs):  # type: ignore[no-redef]
        if args and callable(args[0]):
            return args[0]
        return lambda f: f

# tipi di superficie
SURF_CROP = 0    # coltura principale (irrigabile secondo `irrigable`)
SURF_COVER = 1   # cover crop (mai irrigata)
SURF_BARE = 2    # suolo nudo

# classi di Curve Number (indici nelle liste di soil.yaml ruscellamento.umidita_antecedente)
CN_ROW_CROPS = 0     # colture_a_file (mais, soia)
CN_SMALL_GRAIN = 1   # cereali_a_paglia (frumento; segale da cover per analogia)
CN_BARE = 2          # suolo_nudo
_CN_KEYS = ("colture_a_file", "cereali_a_paglia", "suolo_nudo")
_CN_CLASS_OF = {"mais": CN_ROW_CROPS, "soia": CN_ROW_CROPS,
                "frumento": CN_SMALL_GRAIN, "cover": CN_SMALL_GRAIN, "suolo_nudo": CN_BARE}


# =============================================================================
# Parametri del suolo e stato
# =============================================================================

@dataclass(frozen=True)
class SoilWaterParams:
    """Parametri idrici del profilo a due strati (da soil.yaml e crops.yaml.suolo_nudo).

    z1, z2: spessori [m]; fc*, wp*, sat*: contenuti idrici [m3/m3];
    ze [m] spessore dello strato evaporante; rew, tew [mm]; kc_max [-];
    cn_ii, cn_i, cn_iii: Curve Number per classe (ARC II, I, III), tuple di 3.
    """
    z1: float
    z2: float
    fc1: float
    wp1: float
    sat1: float
    fc2: float
    wp2: float
    sat2: float
    ze: float
    rew: float
    tew: float
    kc_max: float
    cn_ii: tuple
    cn_i: tuple
    cn_iii: tuple
    frazione_iniziale: float

    @property
    def fc1_mm(self) -> float:
        return 1000.0 * self.fc1 * self.z1

    @property
    def fc2_mm(self) -> float:
        return 1000.0 * self.fc2 * self.z2

    @property
    def wp1_mm(self) -> float:
        return 1000.0 * self.wp1 * self.z1

    @property
    def wp2_mm(self) -> float:
        return 1000.0 * self.wp2 * self.z2

    @property
    def taw1(self) -> float:
        """TAW dello strato 1 [mm], FAO-56 eq. 82."""
        return 1000.0 * (self.fc1 - self.wp1) * self.z1

    @property
    def taw2(self) -> float:
        """TAW dello strato 2 [mm], FAO-56 eq. 82."""
        return 1000.0 * (self.fc2 - self.wp2) * self.z2

    @property
    def w1_min_mm(self) -> float:
        """Limite inferiore dell'acqua nello strato 1 [mm]: i primi Ze m a 0,5 theta_WP
        (FAO-56 eq. 73), il resto dello strato a theta_WP (eq. 82).
        W1_min = 1000 (theta_WP z1 - 0,5 theta_WP Ze)."""
        return 1000.0 * (self.wp1 * self.z1 - 0.5 * self.wp1 * self.ze)

    @property
    def depth(self) -> float:
        return self.z1 + self.z2

    @property
    def sat_mm(self) -> float:
        """Acqua a saturazione dell'intero profilo [mm] (serve alla lisciviazione)."""
        return 1000.0 * (self.sat1 * self.z1 + self.sat2 * self.z2)


def tew_fao56(fc: float, wp: float, ze: float) -> float:
    """Acqua totale evaporabile [mm]. FAO-56 eq. 73: TEW = 1000 (theta_FC - 0.5 theta_WP) Ze."""
    return 1000.0 * (fc - 0.5 * wp) * ze


def soil_from_params(p: dict | None = None) -> SoilWaterParams:
    """Costruisce i parametri idrici dal dizionario di `fieldwise.params.load_params()`.

    REW da soil.yaml (evaporazione.rew, vale per il punto pilota); Ze e Kc_max da
    crops.yaml (suolo_nudo); TEW calcolata con eq. 73 dai theta dello strato 1.
    """
    p = _params.load_params() if p is None else p
    g = _params.get
    z1, z2 = (float(x) for x in g(p, "soil.profilo.spessore_strati"))
    s1, s2 = "soil.profilo.strato_superficiale", "soil.profilo.strato_profondo"
    fc1, wp1, sat1 = (float(g(p, f"{s1}.{k}")) for k in ("fc", "wp", "sat"))
    fc2, wp2, sat2 = (float(g(p, f"{s2}.{k}")) for k in ("fc", "wp", "sat"))
    ze = float(g(p, "crops.suolo_nudo.ze"))
    cn_ii = tuple(float(g(p, f"soil.ruscellamento.cn.{k}")) for k in _CN_KEYS)
    cn_i = tuple(float(x) for x in g(p, "soil.ruscellamento.umidita_antecedente.arc_i"))
    cn_iii = tuple(float(x) for x in g(p, "soil.ruscellamento.umidita_antecedente.arc_iii"))
    return SoilWaterParams(
        z1=z1, z2=z2, fc1=fc1, wp1=wp1, sat1=sat1, fc2=fc2, wp2=wp2, sat2=sat2,
        ze=ze, rew=float(g(p, "soil.evaporazione.rew")), tew=tew_fao56(fc1, wp1, ze),
        kc_max=float(g(p, "crops.suolo_nudo.kc_max")),
        cn_ii=cn_ii, cn_i=cn_i, cn_iii=cn_iii,
        frazione_iniziale=float(g(p, "soil.umidita_iniziale.frazione_acqua_disponibile")),
    )


@dataclass
class WaterState:
    """Stato idrico del suolo (mai azzerato tra i segmenti).

    w1, w2 [mm]: acqua negli strati 1 e 2; de [mm]: esaurimento dello strato
    evaporante (0 = a capacita' di campo, TEW = secco all'aria).
    """
    w1: float
    w2: float
    de: float

    @property
    def storage(self) -> float:
        return self.w1 + self.w2

    def copy(self) -> "WaterState":
        return WaterState(self.w1, self.w2, self.de)


def initial_water_state(soil: SoilWaterParams, frazione: float | None = None) -> WaterState:
    """Stato iniziale: theta = wp + frazione (fc - wp) in ciascuno strato
    (soil.yaml umidita_iniziale); De = esaurimento corrispondente dei primi Ze m
    (eq. 87 applicata allo strato evaporante), limitato a [0, TEW]."""
    f = soil.frazione_iniziale if frazione is None else float(frazione)
    th1 = soil.wp1 + f * (soil.fc1 - soil.wp1)
    th2 = soil.wp2 + f * (soil.fc2 - soil.wp2)
    de = min(max(1000.0 * (soil.fc1 - th1) * soil.ze, 0.0), soil.tew)
    return WaterState(1000.0 * th1 * soil.z1, 1000.0 * th2 * soil.z2, de)


# =============================================================================
# Curve stagionali: Kc, radici, p, correzione climatica
# =============================================================================

def stage_fractions(fasi_giorni) -> tuple[float, float, float]:
    """Frazioni di sviluppo a fine fase iniziale, sviluppo e piena stagione, dalle
    durate in giorni [L_ini, L_dev, L_mid, L_late] (FAO-56 tab. 11)."""
    L = np.asarray(fasi_giorni, dtype=float)
    c = np.cumsum(L) / L.sum()
    return float(c[0]), float(c[1]), float(c[2])


def kc_curve(frac, kc_ini, kc_mid, kc_end, f_ini, f_dev, f_mid):
    """Kc a quattro tratti in funzione della frazione di sviluppo `frac` in [0, 1].

    Costante kc_ini fino a f_ini; lineare fino a kc_mid a f_dev; costante fino a
    f_mid; lineare fino a kc_end a 1. FAO-56 cap. 6, fig. 25 ed eq. 66
    (interpolazione lineare nelle fasi di sviluppo e finale). `frac` puo' essere
    un array; valori fuori da [0, 1] sono limitati.
    """
    x = np.clip(np.asarray(frac, dtype=float), 0.0, 1.0)
    dev = kc_ini + (x - f_ini) / max(f_dev - f_ini, 1e-12) * (kc_mid - kc_ini)    # eq. 66
    late = kc_mid + (x - f_mid) / max(1.0 - f_mid, 1e-12) * (kc_end - kc_mid)     # eq. 66
    out = np.where(x <= f_ini, kc_ini,
                   np.where(x <= f_dev, dev, np.where(x <= f_mid, kc_mid, late)))
    return out if out.ndim else float(out)


def root_depth(frac, zr_ini, zr_max, f_dev, z_profile: float | None = None):
    """Profondita' radicale [m]: lineare da zr_ini alla semina a zr_max a fine fase
    di sviluppo (frazione f_dev), poi costante; limitata a z_profile se dato.

    FAO-56 non da' una legge generale di crescita (cap. 8, es. 38 interpola
    linearmente Zr nel tempo); il massimo a inizio piena stagione segue la
    convenzione di FAO-56 cap. 8 (Zr max quando la coltura e' pienamente
    sviluppata). Scelta dichiarata.
    """
    x = np.clip(np.asarray(frac, dtype=float), 0.0, 1.0)
    z = zr_ini + np.clip(x / max(f_dev, 1e-12), 0.0, 1.0) * (zr_max - zr_ini)
    if z_profile is not None:
        z = np.minimum(z, z_profile)
    return z if z.ndim else float(z)


def rhmin_from_temperature(tmax, tmin):
    """RHmin [%] stimata con Tdew ~ Tmin. FAO-56 eq. 63: RHmin = 100 e0(Tdew)/e0(Tmax);
    Tdew ~ Tmin come in eq. 48 (ea = e0(Tmin)) quando mancano dati di umidita'."""
    return 100.0 * saturation_vapour_pressure(tmin) / saturation_vapour_pressure(tmax)


def kc_climate_correction(kc_tab: float, u2: float, rhmin: float, h: float) -> float:
    """Kc mid corretto per il clima. FAO-56 eq. 62:
    Kc = Kc(tab) + [0.04 (u2 - 2) - 0.004 (RHmin - 45)] (h/3)^0.3,
    con u2 (media della fase, m/s) limitato a 1-6, RHmin (%) a 20-80 e h (m) a
    0.1-10, come prescrive il testo dell'equazione."""
    u2 = min(max(float(u2), 1.0), 6.0)
    rh = min(max(float(rhmin), 20.0), 80.0)
    h = min(max(float(h), 0.1), 10.0)
    return float(kc_tab + (0.04 * (u2 - 2.0) - 0.004 * (rh - 45.0)) * (h / 3.0) ** 0.3)


def kc_end_climate_correction(kc_tab: float, u2: float, rhmin: float, h: float) -> float:
    """Kc end corretto per il clima. FAO-56 eq. 65 (stessa forma di eq. 62), che si
    applica solo se Kc end (tab) >= 0.45; altrimenti il valore resta quello tabulato."""
    if kc_tab < 0.45:
        return float(kc_tab)
    return kc_climate_correction(kc_tab, u2, rhmin, h)


def p_adjusted(p_tab, etc):
    """Frazione di esaurimento corretta con l'ETc del giorno [mm/g].
    FAO-56 tab. 22, nota: p = p_tab + 0.04 (5 - ETc), limitata a 0.1 <= p <= 0.8."""
    return np.clip(p_tab + 0.04 * (5.0 - np.asarray(etc, dtype=float)), 0.1, 0.8)


def crop_daily_curves(p: dict, crop: str, n_days: int, z_profile: float | None = None,
                      fasi_giorni=None, u2_mid: float | None = None,
                      rhmin_mid: float | None = None, u2_end: float | None = None,
                      rhmin_end: float | None = None):
    """Serie giornaliere (kc, zr, p_tab) di una coltura di crops.yaml lunga n_days.

    La frazione di sviluppo del giorno j e' (j + 1) / n_days; i passaggi tra le
    fasi vengono da `fasi_giorni` (default crops.yaml <crop>.fasi_giorni). Se u2 e
    RHmin sono dati, Kc mid ed end sono corretti con eq. 62 e 65 (h = h_max).
    Nella fase 4 la frazione verra' dalle somme termiche.
    """
    g = _params.get
    fasi = g(p, f"crops.{crop}.fasi_giorni") if fasi_giorni is None else fasi_giorni
    f_ini, f_dev, f_mid = stage_fractions(fasi)
    kc_ini = float(g(p, f"crops.{crop}.kc.ini"))
    kc_mid = float(g(p, f"crops.{crop}.kc.mid"))
    kc_end = float(g(p, f"crops.{crop}.kc.end"))
    h = float(g(p, f"crops.{crop}.h_max"))
    if u2_mid is not None and rhmin_mid is not None:
        kc_mid = kc_climate_correction(kc_mid, u2_mid, rhmin_mid, h)
    if u2_end is not None and rhmin_end is not None:
        kc_end = kc_end_climate_correction(kc_end, u2_end, rhmin_end, h)
    frac = (np.arange(n_days) + 1.0) / n_days
    kc = kc_curve(frac, kc_ini, kc_mid, kc_end, f_ini, f_dev, f_mid)
    zr = root_depth(frac, float(g(p, f"crops.{crop}.zr_ini")),
                    float(g(p, f"crops.{crop}.zr_max")), f_dev, z_profile)
    ptab = np.full(n_days, float(g(p, f"crops.{crop}.p")))
    return np.asarray(kc, float), np.asarray(zr, float), ptab


def cover_daily_curves(p: dict, n_days: int, zr_ini: float, z_profile: float | None = None):
    """Serie (kc, zr, p_tab) della cover crop (cover_crop.yaml acqua.*): Kc costante;
    radici lineari da `zr_ini` a profondita_radicale_max lungo tutto l'intervallo.

    cover_crop.yaml non da' una profondita' iniziale: `zr_ini` e' un argomento
    obbligatorio (parametro mancante, vedi rapporto)."""
    g = _params.get
    kc = np.full(n_days, float(g(p, "cover_crop.acqua.kc")))
    frac = (np.arange(n_days) + 1.0) / n_days
    zr = root_depth(frac, zr_ini, float(g(p, "cover_crop.acqua.profondita_radicale_max")),
                    1.0, z_profile)
    ptab = np.full(n_days, float(g(p, "cover_crop.acqua.frazione_p")))
    return kc, np.asarray(zr, float), ptab


def cn_class_index(classe: str) -> int:
    """Indice CN_* di una classe di soil.yaml ruscellamento ('colture_a_file',
    'cereali_a_paglia', 'suolo_nudo')."""
    return _CN_KEYS.index(classe)


def cn_class(name: str) -> int:
    """Classe di Curve Number di soil.yaml per una coltura/superficie
    ('mais','soia' -> colture a file; 'frumento','cover' -> cereali a paglia;
    'suolo_nudo' -> suolo nudo)."""
    return _CN_CLASS_OF[name]


# =============================================================================
# Nucleo numerico (numba)
# =============================================================================

@njit(cache=True)
def _scs_runoff(p_mm, cn):
    """Ruscellamento SCS [mm]. NRCS NEH 630 cap. 10: S = 25400/CN - 254 (eq. 10-11),
    Ia = 0.2 S, Q = (P - Ia)^2 / (P - Ia + S) per P > Ia (eq. 10-9)."""
    if cn <= 0.0 or p_mm <= 0.0:
        return 0.0
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    if p_mm <= ia:
        return 0.0
    return (p_mm - ia) * (p_mm - ia) / (p_mm - ia + s)


@njit(cache=True)
def _de_consistent(de, w1, fc1mm, tew, taw_below):
    """Riporta De nell'intervallo coerente con W1 (vedi docstring del modulo):
    max(0, (FC1 - W1) - TAW_sotto) <= De <= min(TEW, FC1 - W1). FAO-56 eq. 73, 77, 82."""
    hi = fc1mm - w1
    if hi > tew:
        hi = tew
    lo = (fc1mm - w1) - taw_below
    if de < lo:
        de = lo
    if de > hi:
        de = hi
    if de < 0.0:
        de = 0.0
    return de


@njit(cache=True)
def _kernel(et0, rain, kc, zr, p_tab, surf, irrigable, seg, cap_seg, cn_cls,
            cn_ii, cn_i, cn_iii, use_amc,
            z1, z2, fc1, wp1, fc2, wp2, ze, tew, rew, kc_max,
            w1_0, w2_0, de_0,
            o_etc, o_eta, o_ks, o_kr, o_irr, o_ro, o_dp, o_w1, o_w2, o_de,
            o_taw, o_raw, o_dr):
    n = et0.shape[0]
    fc1mm = 1000.0 * fc1 * z1
    fc2mm = 1000.0 * fc2 * z2
    wp1mm = 1000.0 * wp1 * z1
    wp2mm = 1000.0 * wp2 * z2
    taw1 = fc1mm - wp1mm                     # eq. 82, strato 1
    taw2 = fc2mm - wp2mm                     # eq. 82, strato 2
    taw_below = 1000.0 * (fc1 - wp1) * (z1 - ze)       # eq. 82, strato 1 sotto Ze
    w1_min = 1000.0 * (wp1 * z1 - 0.5 * wp1 * ze)      # eq. 73: Ze fino a 0,5 theta_WP
    used = np.zeros(cap_seg.shape[0])
    w1 = w1_0
    w2 = w2_0
    de = de_0
    for i in range(n):
        # ---- 1. ruscellamento (CN)
        c = cn_cls[i]
        cn = cn_ii[c]
        if use_amc:
            th = (w1 / (1000.0 * z1) - wp1) / (fc1 - wp1)   # 0 a wp, 1 a fc
            if th < 0.0:
                th = 0.0
            if th > 1.0:
                th = 1.0
            if th <= 0.5:
                cn = cn_i[c] + (cn_ii[c] - cn_i[c]) * th / 0.5
            else:
                cn = cn_ii[c] + (cn_iii[c] - cn_ii[c]) * (th - 0.5) / 0.5
        p_mm = rain[i]
        ro = _scs_runoff(p_mm, cn)
        # ---- 2. infiltrazione e drenaggio a cascata (eq. 88)
        inf = p_mm - ro
        w1 += inf
        de -= inf                            # eq. 77: la pioggia riduce prima De
        dp = 0.0
        if w1 > fc1mm:
            w2 += w1 - fc1mm
            w1 = fc1mm
        if w2 > fc2mm:
            dp += w2 - fc2mm
            w2 = fc2mm
        # ---- 3. zona radicale
        z = zr[i]
        f1 = z / z1
        if f1 > 1.0:
            f1 = 1.0
        if f1 < 0.0:
            f1 = 0.0
        f2 = (z - z1) / z2
        if f2 > 1.0:
            f2 = 1.0
        if f2 < 0.0:
            f2 = 0.0
        taw = f1 * taw1 + f2 * taw2          # eq. 82
        s_type = surf[i]
        if s_type == 2:
            etc = kc_max * et0[i]
        else:
            etc = kc[i] * et0[i]
        p = p_tab[i] + 0.04 * (5.0 - etc)    # tab. 22, nota
        if p < 0.1:
            p = 0.1
        if p > 0.8:
            p = 0.8
        raw = p * taw                        # eq. 83
        dr = f1 * (fc1mm - w1) + f2 * (fc2mm - w2)   # eq. 87 per strato
        if dr < 0.0:
            dr = 0.0
        # ---- 4. irrigazione (Dr > RAW -> I = Dr, entro il tetto del segmento)
        irr = 0.0
        if s_type == 0 and irrigable[i] != 0 and dr > raw and taw > 0.0:
            k = seg[i]
            left = cap_seg[k] - used[k]
            irr = dr
            if irr > left:
                irr = left
            if irr < 0.0:
                irr = 0.0
            if irr > 0.0:
                used[k] += irr
                w1 += irr
                de -= irr
                if w1 > fc1mm:
                    w2 += w1 - fc1mm
                    w1 = fc1mm
                if w2 > fc2mm:
                    dp += w2 - fc2mm
                    w2 = fc2mm
                dr = f1 * (fc1mm - w1) + f2 * (fc2mm - w2)
                if dr < 0.0:
                    dr = 0.0
        de = _de_consistent(de, w1, fc1mm, tew, taw_below)
        # ---- 5. evapotraspirazione
        ks = 1.0
        kr = 1.0
        if s_type == 2:
            # suolo nudo: E = Kr Kc_max ET0 (eq. 71 con Kcb = 0, few = 1; eq. 74)
            if de > rew:
                kr = (tew - de) / (tew - rew)
                if kr < 0.0:
                    kr = 0.0
            eta = kr * etc
            if eta > tew - de:
                eta = tew - de
            if eta > w1 - w1_min:            # limite inferiore dello strato 1 (eq. 73)
                eta = w1 - w1_min
            if eta < 0.0:
                eta = 0.0
            w1 -= eta
            de += eta                        # eq. 77
        else:
            if dr > raw and taw > 0.0:
                ddr = dr
                if ddr > taw:
                    ddr = taw                # eq. 86
                ks = (taw - ddr) / ((1.0 - p) * taw)   # eq. 84
                if ks < 0.0:
                    ks = 0.0
                if ks > 1.0:
                    ks = 1.0
            eta = ks * etc                   # eq. 80-81
            a1 = w1 - wp1mm
            if a1 < 0.0:
                a1 = 0.0
            a1 *= f1
            a2 = w2 - wp2mm
            if a2 < 0.0:
                a2 = 0.0
            a2 *= f2
            avail = a1 + a2
            if eta > avail:
                eta = avail
            if avail > 0.0:
                e1 = eta * a1 / avail
                e2 = eta - e1
            else:
                e1 = 0.0
                e2 = 0.0
            w1 -= e1
            w2 -= e2
            de += e1 * ze / z1               # prelievo uniforme nello strato 1
        # ---- 6. coerenza dello strato evaporante con W1
        de = _de_consistent(de, w1, fc1mm, tew, taw_below)
        o_etc[i] = etc
        o_eta[i] = eta
        o_ks[i] = ks
        o_kr[i] = kr
        o_irr[i] = irr
        o_ro[i] = ro
        o_dp[i] = dp
        o_w1[i] = w1
        o_w2[i] = w2
        o_de[i] = de
        o_taw[i] = taw
        o_raw[i] = raw
        o_dr[i] = dr
    return w1, w2, de


# =============================================================================
# Interfaccia Python
# =============================================================================

@dataclass
class DailyInputs:
    """Serie giornaliere della rotazione (tutte lunghe n).

    et0, rain [mm/g]; kc [-] (ignorato sul suolo nudo); zr [m]; p_tab [-];
    surface: SURF_CROP / SURF_COVER / SURF_BARE; irrigable: 1 se la coltura del
    giorno e' irrigabile; segment: indice del segmento 0..nseg-1; cn_class:
    CN_ROW_CROPS / CN_SMALL_GRAIN / CN_BARE.
    """
    et0: np.ndarray
    rain: np.ndarray
    kc: np.ndarray
    zr: np.ndarray
    p_tab: np.ndarray
    surface: np.ndarray
    irrigable: np.ndarray
    segment: np.ndarray
    cn_class: np.ndarray

    def __post_init__(self):
        n = len(self.et0)
        for name in ("rain", "kc", "zr", "p_tab", "surface", "irrigable", "segment", "cn_class"):
            if len(getattr(self, name)) != n:
                raise ValueError(f"DailyInputs: '{name}' ha lunghezza diversa da et0 ({n})")
        if n and (np.any(~np.isfinite(self.et0)) or np.any(~np.isfinite(self.rain))):
            raise ValueError("DailyInputs: et0 o rain contengono NaN")


@dataclass
class WaterResult:
    """Uscite giornaliere [mm o -] e stato iniziale/finale.

    etc, eta, ks, kr, irr, runoff, dp, w1, w2, de, taw, raw, dr (Dr prima dell'ET,
    dopo pioggia e irrigazione); theta_e = contenuto idrico volumetrico dello
    strato evaporante (Ze) a fine giorno; storage = w1 + w2.
    """
    etc: np.ndarray
    eta: np.ndarray
    ks: np.ndarray
    kr: np.ndarray
    irr: np.ndarray
    runoff: np.ndarray
    dp: np.ndarray
    w1: np.ndarray
    w2: np.ndarray
    de: np.ndarray
    taw: np.ndarray
    raw: np.ndarray
    dr: np.ndarray
    theta_e: np.ndarray
    rain: np.ndarray
    segment: np.ndarray
    state0: WaterState
    state_end: WaterState
    extra: dict = field(default_factory=dict)

    @property
    def storage(self) -> np.ndarray:
        return self.w1 + self.w2


def _cap_array(irr_cap, nseg: int) -> np.ndarray:
    cap = np.asarray(irr_cap, dtype=float)
    if cap.ndim == 0:
        cap = np.full(nseg, float(cap))
    if cap.shape[0] < nseg:
        raise ValueError(f"irr_cap: servono {nseg} valori (uno per segmento)")
    return cap


def run_water_balance(inp: DailyInputs, soil: SoilWaterParams, state0: WaterState,
                      irr_cap=math.inf, use_amc: bool = False) -> WaterResult:
    """Bilancio idrico giornaliero su tutta la serie, in un unico ciclo.

    irr_cap: tetto irriguo netto [mm] per segmento (scalare = stesso tetto per
    tutti; 0 = solo pioggia; math.inf = irrigazione libera). Il tetto e' contato
    PER CHIAMATA: l'acqua gia' usata da un segmento riparte da zero a ogni
    chiamata. Nell'architettura del motore una rotazione intera e' una sola
    chiamata, quindi il tetto vale per segmento lungo tutta la rotazione; chiamate
    separate per pezzi della stessa coltura raddoppierebbero il tetto.
    use_amc: correzione del CN con l'umidita' dello strato 1 (soil.yaml regola_umidita).
    """
    n = len(inp.et0)
    seg = np.ascontiguousarray(inp.segment, dtype=np.int64)
    nseg = int(seg.max()) + 1 if n else 0
    cap = _cap_array(irr_cap, max(nseg, 1))
    out = {k: np.empty(n) for k in ("etc", "eta", "ks", "kr", "irr", "runoff", "dp",
                                     "w1", "w2", "de", "taw", "raw", "dr")}
    f = lambda a: np.ascontiguousarray(a, dtype=np.float64)  # noqa: E731
    i8 = lambda a: np.ascontiguousarray(a, dtype=np.int64)   # noqa: E731
    w1, w2, de = _kernel(
        f(inp.et0), f(inp.rain), f(inp.kc), f(inp.zr), f(inp.p_tab),
        i8(inp.surface), i8(inp.irrigable), seg, f(cap), i8(inp.cn_class),
        f(soil.cn_ii), f(soil.cn_i), f(soil.cn_iii), bool(use_amc),
        soil.z1, soil.z2, soil.fc1, soil.wp1, soil.fc2, soil.wp2,
        soil.ze, soil.tew, soil.rew, soil.kc_max,
        float(state0.w1), float(state0.w2), float(state0.de),
        out["etc"], out["eta"], out["ks"], out["kr"], out["irr"], out["runoff"], out["dp"],
        out["w1"], out["w2"], out["de"], out["taw"], out["raw"], out["dr"])
    theta_e = soil.fc1 - out["de"] / (1000.0 * soil.ze)
    return WaterResult(theta_e=theta_e, rain=np.asarray(inp.rain, float), segment=seg,
                       state0=state0.copy(), state_end=WaterState(w1, w2, de), **out)


def water_balance_residual(res: WaterResult) -> float:
    """Scarto di chiusura [mm] su tutta la serie:
    (S_fine - S_inizio) - (P + I - RO - ETa - DP), con S = W1 + W2 (eq. 85 integrata)."""
    ds = res.state_end.storage - res.state0.storage
    flux = res.rain.sum() + res.irr.sum() - res.runoff.sum() - res.eta.sum() - res.dp.sum()
    return float(ds - flux)


def water_balance_daily_residual(res: WaterResult) -> np.ndarray:
    """Scarto giornaliero [mm] dello stesso bilancio (deve essere ~0 ogni giorno)."""
    s = res.storage
    s_prev = np.concatenate(([res.state0.storage], s[:-1]))
    return (s - s_prev) - (res.rain + res.irr - res.runoff - res.eta - res.dp)


def aggregate_segments(res: WaterResult) -> dict[str, np.ndarray]:
    """Somme per segmento: days, rain, eta, etc, irr, runoff, dp [mm] e
    storage_end [mm] (acqua nel profilo all'ultimo giorno del segmento).
    Indici = numero del segmento; segmenti senza giorni hanno days = 0."""
    seg = res.segment
    nseg = int(seg.max()) + 1 if seg.size else 0
    agg = {"days": np.bincount(seg, minlength=nseg).astype(float)}
    for k, arr in (("rain", res.rain), ("eta", res.eta), ("etc", res.etc), ("irr", res.irr),
                   ("runoff", res.runoff), ("dp", res.dp)):
        agg[k] = np.bincount(seg, weights=arr, minlength=nseg)
    end = np.full(nseg, np.nan)
    st = res.storage
    for k in range(nseg):
        idx = np.nonzero(seg == k)[0]
        if idx.size:
            end[k] = st[idx[-1]]
    agg["storage_end"] = end
    return agg


def relative_yield_fao33(eta_sum: float, etc_sum: float, ky: float) -> float:
    """Resa relativa per la sola risposta all'acqua (Doorenbos e Kassam 1979, FAO-33;
    FAO-56 eq. 90): Y/Ym = 1 - Ky (1 - ETa/ETc), limitata a [0, 1]."""
    if etc_sum <= 0.0:
        return 1.0
    return float(min(max(1.0 - ky * (1.0 - eta_sum / etc_sum), 0.0), 1.0))

