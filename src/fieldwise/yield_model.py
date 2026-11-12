"""Modello di resa (fase 4):  Y = Y_pot x f_acqua x f_caldo x f_rotazione.

Ogni fattore e' in [0, 1], ha una fonte in ``params/`` e resta visibile nell'output
(``crop_yield`` restituisce resa e fattori separati).

- f_acqua: FAO-33 / FAO-56 eq. 90, riuso di ``water.relative_yield_fao33``.
- f_caldo: Deryng et al. (2014) App. A.3 eq. A.6-A.7 (params/heat.yaml); alternative
  selezionabili per l'incertezza strutturale: AquaCrop (Ks_pol,h logistico su Tmax) e le
  soglie di Teixeira et al. (2013) nella forma di Deryng.
- f_rotazione: params/rotation_rules.yaml ``_meta.uso_dei_fattori_di_resa`` (penalita' di
  ristoppio; la precessione favorevole NON si applica, ``usato_dal_motore: false``).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import params as _params
from . import phenology as _ph
from . import water as _water

METODI_CALDO = ("deryng", "aquacrop", "teixeira")
FINESTRE = ("giorni_emergenza_maturita", "gdd_semina_maturita")
SCENARI_ACQUA = ("irriguo", "asciutto")

# AquaCrop Reference Manual cap. 3 v7.3, eq. 3.2c (forma logistica): Ks = Sn Sx /
# (Sn + (Sx - Sn) exp(-r (1 - Srel))). Il manuale chiede "a small value for Sn" senza
# darne il valore e di correggere Ks per quel valore: costanti numeriche dell'equazione
# (non agronomiche), scelta dichiarata. Sx = 1 (nessuno stress alla soglia superiore di Ks).
# r si ricava da Ks = 0.5 a Srel = 0.5 (stesso paragrafo).
_AQ_SN = 0.001
_AQ_SX = 1.0
_AQ_R = -2.0 * math.log(_AQ_SN * (2 * _AQ_SX - 1) / (_AQ_SX - _AQ_SN))


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


# ----------------------------------------------------------------- f_acqua
def water_factor(eta_sum: float, etc_sum: float, ky: float) -> float:
    """f_acqua = 1 - Ky (1 - ETa/ETc) in [0, 1] (``water.relative_yield_fao33``)."""
    return _clip01(_water.relative_yield_fao33(eta_sum, etc_sum, ky))


# ----------------------------------------------------------------- f_caldo
@dataclass
class HeatResult:
    """Esito di ``heat_factor``. Indici = righe del meteo."""
    f_caldo: float
    metodo: str
    finestra: str
    window_start: int
    window_end: int
    n_window_days: int
    n_hot_days: int        # giorni della finestra con T usata >= soglia critica del metodo
    t_soglia: float        # soglia critica usata per n_hot_days
    flowering_in_window: bool
    f_daily: np.ndarray


def _window_mask(cal: _ph.CycleCalendar, finestra: str, f0: float, f1: float) -> np.ndarray:
    """Maschera sui giorni del ciclo (sow..maturity) della finestra sensibile (TSP)."""
    n = cal.n_days
    if finestra == "giorni_emergenza_maturita":
        # Deryng 2014 App. A.3: frazione della GPL (emergenza -> maturita', in giorni)
        gpl = cal.maturity - cal.emergence
        d = np.arange(cal.sow, cal.sow + n)
        phi = (d - cal.emergence) / gpl if gpl > 0 else np.full(n, np.nan)
    elif finestra == "gdd_semina_maturita":
        phi = cal.frac  # adattamento: GDD(semina->d) / GDD(semina->maturita')
    else:
        raise ValueError(f"finestra sconosciuta: {finestra} (ammesse {FINESTRE})")
    return (phi >= f0) & (phi <= f1)


def _linear_daily(t: np.ndarray, tcr: float, tlim: float) -> np.ndarray:
    """Deryng 2014 eq. A.6: 1 sotto Tcr, lineare fino a 0 a Tlim, 0 oltre."""
    return np.clip(1.0 - (t - tcr) / (tlim - tcr), 0.0, 1.0)


def _aquacrop_daily(tmax: np.ndarray, tx_heat: float, delta: float) -> np.ndarray:
    """Ks_pol,h di AquaCrop (cap. 3 v7.3, par. 3.12.5 ed eq. 3.2c): 1 per Tmax <= Tx_heat,
    0 per Tmax >= Tx_heat + delta, logistico in mezzo; Srel = (Tmax - Tx_heat)/delta.
    Correzione per Sn piccolo: Ks riscalato linearmente perche' valga 1 a Srel = 0 e 0
    a Srel = 1 (il manuale chiede la correzione senza darne la forma: scelta dichiarata)."""
    srel = np.clip((tmax - tx_heat) / delta, 0.0, 1.0)

    def ks(sr):
        return _AQ_SN * _AQ_SX / (_AQ_SN + (_AQ_SX - _AQ_SN) * np.exp(-_AQ_R * (1.0 - sr)))
    k0, k1 = ks(0.0), ks(1.0)
    return np.clip((ks(srel) - k1) / (k0 - k1), 0.0, 1.0)


def heat_factor(p: dict, crop: str, forcing, cal: _ph.CycleCalendar,
                metodo: str = "deryng", finestra: str | None = None,
                teixeira_temp: str = "teff") -> HeatResult:
    """f_caldo del ciclo ``cal`` (da ``phenology.cycle_calendar``).

    metodo: 'deryng' (default; heat.yaml colture.<crop>.t_critica/t_limite su Teff =
    (T2M + Tmax)/2), 'aquacrop' (alternative.aquacrop: Ks_pol,h su Tmax), 'teixeira'
    (alternative.teixeira_2013: soglie di Teixeira nella forma lineare di Deryng, sulla
    temperatura ``teixeira_temp`` = 'teff' o 'tmax', perche' la fonte non e' stata letta).
    finestra: None = default per coltura in heat.yaml colture.<crop>.finestra_definizione
    (mais e soia 'giorni_emergenza_maturita', Deryng fedele; frumento autunnale
    'gdd_semina_maturita', adattamento per la pausa invernale); oppure una delle due.
    Fattore stagionale = media dei fattori giornalieri nella finestra (Deryng eq. A.7;
    per AquaCrop e' un'approssimazione dichiarata in heat.yaml alternative.aquacrop.forma).
    """
    if cal.status == _ph.STATO_FUORI_SERIE:
        raise ValueError("ciclo non simulabile: maturita' oltre la fine della serie meteo")
    g = _params.get
    fin = str(g(p, f"heat.colture.{crop}.finestra_definizione")) if finestra is None else finestra
    f0 = float(g(p, f"heat.colture.{crop}.finestra_inizio_frazione"))
    f1 = float(g(p, f"heat.colture.{crop}.finestra_fine_frazione"))
    sl = slice(cal.sow, cal.sow + cal.n_days)
    tmax = forcing["tmax"].to_numpy(float)[sl]
    tmean = _ph.tmean_of(forcing)[sl]
    teff = (tmean + tmax) / 2.0  # Deryng 2014 App. A.3
    if metodo == "deryng":
        tcr = float(g(p, f"heat.colture.{crop}.t_critica"))
        t_used, fd = teff, _linear_daily(teff, tcr, float(g(p, f"heat.colture.{crop}.t_limite")))
    elif metodo == "teixeira":
        tcr = float(g(p, f"heat.alternative.teixeira_2013.t_critica_{crop}"))
        tlim = float(g(p, f"heat.alternative.teixeira_2013.t_limite_{crop}"))
        if teixeira_temp not in ("teff", "tmax"):
            raise ValueError("teixeira_temp deve essere 'teff' o 'tmax'")
        t_used = teff if teixeira_temp == "teff" else tmax
        fd = _linear_daily(t_used, tcr, tlim)
    elif metodo == "aquacrop":
        tcr = float(g(p, f"heat.alternative.aquacrop.tx_heat_{crop}"))
        t_used = tmax
        fd = _aquacrop_daily(tmax, tcr, float(g(p, "heat.alternative.aquacrop.delta_zero")))
    else:
        raise ValueError(f"metodo sconosciuto: {metodo} (ammessi {METODI_CALDO})")
    m = _window_mask(cal, fin, f0, f1)
    idx = np.flatnonzero(m)
    if idx.size == 0:
        raise ValueError("finestra sensibile vuota")
    f = _clip01(float(fd[m].mean()))
    ws, we = cal.sow + int(idx[0]), cal.sow + int(idx[-1])
    return HeatResult(f, metodo, fin, ws, we, int(m.sum()), int((t_used[m] >= tcr).sum()),
                      tcr, bool(ws <= cal.flowering <= we), fd)


# ------------------------------------------------------------- f_rotazione
def _irrigated(p: dict, crop: str, scenario: str) -> bool:
    if scenario not in SCENARI_ACQUA:
        raise ValueError(f"scenario d'acqua sconosciuto: {scenario} (ammessi {SCENARI_ACQUA})")
    return scenario == "irriguo" and int(_params.get(p, f"crops.{crop}.irrigabile")) == 1


def rotation_factor(p: dict, crop: str, prev1: str | None, prev2: str | None,
                    scenario: str) -> tuple[float, str]:
    """f_rotazione di ``crop`` date le due colture principali precedenti (None = ignota,
    trattata come diversa) e lo scenario d'acqua ('irriguo' o 'asciutto'), secondo
    rotation_rules.yaml _meta.uso_dei_fattori_di_resa. Restituisce (f, caso) con caso in
    'nessun_ristoppio', 'primo_ristoppio', 'monosuccessione_continua'. Ristoppio =
    stessa chiave di coltura (tra le colture modellate l'unico cereale autunno-vernino e'
    il frumento). Le cover crop non vanno passate: non interrompono il ristoppio."""
    if prev1 != crop:
        return 1.0, "nessun_ristoppio"
    caso = "monosuccessione_continua" if prev2 == crop else "primo_ristoppio"
    g = _params.get
    if crop == "mais":
        if _irrigated(p, crop, scenario):
            f = g(p, "rotation_rules.f_rotazione.mais_dopo_mais.irriguo")
        else:
            f = g(p, f"rotation_rules.f_rotazione.mais_dopo_mais.asciutto.{caso}")
    elif crop == "soia":
        _irrigated(p, crop, scenario)  # valida lo scenario; stesso valore nei due scenari
        f = g(p, "rotation_rules.f_rotazione.soia_dopo_soia")
    elif crop == "frumento":
        _irrigated(p, crop, scenario)
        f = g(p, f"rotation_rules.f_rotazione.frumento_dopo_frumento.{caso}")
    else:
        raise KeyError(f"nessun fattore di ristoppio per la coltura {crop}")
    return _clip01(float(f)), caso


def rotation_factors(p: dict, sequence, scenario: str, n_years: int | None = None,
                     precedenti=None) -> list[tuple[float, str]]:
    """f_rotazione anno per anno di una rotazione ``sequence`` ripetuta ciclicamente
    (A B C A B C ...) per ``n_years`` (default len(sequence)).
    precedenti=None: rotazione gia' a regime, le colture prima del primo anno sono quelle
    del ciclo (ciclo ripetuto). precedenti=[]: nessuna coltura nota prima del primo anno
    (lettura letterale di _meta: in A-A-A il 1o anno vale 1, il 2o primo ristoppio).
    precedenti=[..., penultima, ultima]: storia esplicita."""
    seq = list(sequence)
    n = len(seq) if n_years is None else int(n_years)
    years = [seq[i % len(seq)] for i in range(n)]
    if precedenti is None:
        hist = [seq[(-2) % len(seq)], seq[-1]] if len(seq) > 1 else [seq[0], seq[0]]
    else:
        hist = list(precedenti)[-2:]
    hist = [None] * (2 - len(hist)) + hist
    out = []
    for c in years:
        out.append(rotation_factor(p, c, hist[-1], hist[-2], scenario))
        hist = [hist[-1], c]
    return out


# -------------------------------------------------------------------- resa
def potential_yield(p: dict, crop: str) -> float:
    """Resa potenziale [t/ha] (crops.<crop>.resa_potenziale, umidita' nell'unita' della voce)."""
    return float(_params.get(p, f"crops.{crop}.resa_potenziale"))


def crop_yield(p: dict, crop: str, f_acqua: float, f_caldo: float,
               f_rotazione: float) -> dict:
    """Resa e fattori separati: {'resa', 'resa_potenziale', 'f_acqua', 'f_caldo',
    'f_rotazione', 'f_totale'}; ogni fattore e' limitato a [0, 1]."""
    fa, fc, fr = _clip01(f_acqua), _clip01(f_caldo), _clip01(f_rotazione)
    ypot = potential_yield(p, crop)
    tot = fa * fc * fr
    return {"resa": ypot * tot, "resa_potenziale": ypot, "f_acqua": fa, "f_caldo": fc,
            "f_rotazione": fr, "f_totale": tot}
