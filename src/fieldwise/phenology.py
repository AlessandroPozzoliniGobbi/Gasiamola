"""Fenologia in gradi-giorno (fase 4): calendario del ciclo di una coltura.

Tutti i numeri agronomici vengono da ``params/crops.yaml`` (via ``fieldwise.params``):
``t_base``, ``t_upper``, ``gdd_emergenza``, ``gdd_fine_ini``, ``gdd_fine_sviluppo``,
``gdd_fine_mid``, ``gdd_fioritura``, ``gdd_maturita``, ``semina``.

Metodo (crops.yaml ``_meta.metodo_gdd``, "Method 1" di AquaCrop, Reference Manual
cap. 3 par. 3.3.1):  GDD_d = max(0, min(Tmedia_d, t_upper) - t_base), con Tmedia = T2M
di NASA POWER (colonna ``tmean`` del meteo) o (Tmax + Tmin)/2 se manca.

Convenzioni (scelte dichiarate):
- il giorno di semina ``sow`` accumula i suoi GDD: GDD cumulati al giorno d =
  somma dei GDD da ``sow`` a ``d`` compresi;
- una fase finisce nel primo giorno in cui i GDD cumulati raggiungono (>=) la soglia;
- la maturita' fisiologica coincide con la raccolta (fine della fase finale FAO-56);
- frazione di sviluppo del giorno d = GDD cumulati / gdd_maturita, limitata a [0, 1].
  Kc e radici seguono questa frazione (punti di passaggio f_ini, f_dev, f_mid =
  soglie GDD / gdd_maturita, costanti per coltura), non i giorni.

Casi limite:
- ``STATO_FUORI_SERIE``: la maturita' non e' raggiunta entro la fine della serie meteo.
  Il ciclo NON e' simulabile: gli indici non raggiunti valgono -1 e il calendario non va
  usato per i bilanci (nessuna data inventata).
- ``STATO_OLTRE_LIMITE``: la maturita' cade dopo ``deadline_idx`` dato dal chiamante.
  crops.yaml NON contiene una data limite di raccolta ne' una durata massima del ciclo
  (voce mancante): il modulo non ne inventa una e, senza ``deadline_idx``, non tronca il
  ciclo (comportamento prudente: il ciclo termina solo con la somma termica). Il chiamante
  (rotation.py) deve passare come limite la data entro cui la coltura successiva va
  seminata (es. ``semina_max`` della coltura seguente, che e' in crops.yaml) e trattare
  ``oltre_limite`` come conflitto di calendario, non come raccolta anticipata.

Il nucleo (``cumulative_gdd``, ``threshold_days``) e' vettoriale: una somma cumulata
per coltura e una ``searchsorted`` per tutte le semine e soglie insieme.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import params as _params
from . import water as _water

STATO_OK = "ok"
STATO_FUORI_SERIE = "fuori_serie"
STATO_OLTRE_LIMITE = "oltre_limite"

# Ordine delle soglie nel calendario (chiavi di crops.yaml).
SOGLIE = ("gdd_emergenza", "gdd_fine_ini", "gdd_fine_sviluppo", "gdd_fine_mid",
          "gdd_fioritura", "gdd_maturita")
_EVENTI = ("emergence", "end_ini", "end_dev", "end_mid", "flowering", "maturity")


@dataclass(frozen=True)
class PhenoParams:
    """Parametri fenologici di una coltura letti da crops.yaml."""
    crop: str
    t_base: float
    t_upper: float
    thresholds: tuple  # GDD dalla semina, nell'ordine di SOGLIE
    semina: str        # "MM-GG"

    @property
    def gdd_maturita(self) -> float:
        return self.thresholds[-1]

    @property
    def breakpoints(self) -> tuple[float, float, float]:
        """(f_ini, f_dev, f_mid) per ``water.kc_curve`` e ``water.root_depth``:
        soglie di fine fase iniziale, sviluppo e piena stagione / gdd_maturita."""
        gm = self.gdd_maturita
        return (self.thresholds[1] / gm, self.thresholds[2] / gm, self.thresholds[3] / gm)


def crop_pheno_params(p: dict, crop: str) -> PhenoParams:
    """Legge le soglie della coltura e controlla che siano crescenti
    (emergenza < fine ini < fine sviluppo < fine mid < maturita', fioritura < maturita')."""
    g = _params.get
    thr = tuple(float(g(p, f"crops.{crop}.{k}")) for k in SOGLIE)
    em, ini, dev, mid, fio, mat = thr
    if not (0 <= em < ini < dev < mid < mat and em < fio < mat):
        raise ValueError(f"soglie GDD non ordinate per {crop}: {dict(zip(SOGLIE, thr))}")
    return PhenoParams(crop, float(g(p, f"crops.{crop}.t_base")),
                       float(g(p, f"crops.{crop}.t_upper")), thr,
                       str(g(p, f"crops.{crop}.semina")))


def tmean_of(forcing: pd.DataFrame) -> np.ndarray:
    """Tmedia giornaliera secondo crops.yaml _meta.metodo_gdd: T2M (``tmean``), oppure
    (Tmax + Tmin)/2 nei giorni in cui ``tmean`` manca."""
    tm = forcing["tmean"].to_numpy(float)
    alt = (forcing["tmax"].to_numpy(float) + forcing["tmin"].to_numpy(float)) / 2.0
    return np.where(np.isnan(tm), alt, tm)


def daily_gdd(tmean, t_base: float, t_upper: float) -> np.ndarray:
    """GDD giornalieri = max(0, min(Tmedia, t_upper) - t_base) (AquaCrop Method 1)."""
    tm = np.asarray(tmean, float)
    return np.maximum(0.0, np.minimum(tm, t_upper) - t_base)


def cumulative_gdd(gdd) -> np.ndarray:
    """Somma cumulata con uno zero iniziale: C[k] = GDD dei giorni 0..k-1.
    GDD da ``s`` a ``d`` compresi = C[d+1] - C[s]."""
    g = np.asarray(gdd, float)
    if np.isnan(g).any():
        raise ValueError("GDD con NaN: meteo incompleto")
    return np.concatenate(([0.0], np.cumsum(g)))


def threshold_days(cum: np.ndarray, sow_idx, thresholds) -> np.ndarray:
    """Indice del primo giorno d >= sow con GDD(sow..d) >= soglia, per ogni semina e
    soglia (vettoriale). Restituisce un array int (n_semine, n_soglie); -1 se la soglia
    non e' raggiunta entro la fine della serie."""
    s = np.atleast_1d(np.asarray(sow_idx, dtype=np.int64))
    thr = np.atleast_1d(np.asarray(thresholds, float))
    n = len(cum) - 1
    if (s < 0).any() or (s >= n).any():
        raise IndexError("indice di semina fuori dalla serie meteo")
    target = cum[s][:, None] + thr[None, :]
    # primo k con cum[k] >= target -> giorno d = k - 1; k <= s non e' possibile se thr > 0
    k = np.searchsorted(cum, target.ravel(), side="left").reshape(target.shape)
    k = np.maximum(k, s[:, None] + 1)
    d = k - 1
    d[k > n] = -1
    return d


@dataclass
class CycleCalendar:
    """Calendario di un ciclo. Indici = righe del meteo (assoluti); -1 se non raggiunto.

    ``gdd_cum`` e ``frac`` hanno un valore per giorno da ``sow`` a ``maturity`` compresi
    (con stato ``fuori_serie``: fino alla fine della serie, solo per ispezione)."""
    crop: str
    sow: int
    emergence: int
    end_ini: int
    end_dev: int
    end_mid: int
    flowering: int
    maturity: int
    status: str
    gdd_maturita: float
    breakpoints: tuple
    gdd_cum: np.ndarray = field(repr=False)
    frac: np.ndarray = field(repr=False)

    @property
    def ok(self) -> bool:
        return self.status == STATO_OK

    @property
    def n_days(self) -> int:
        """Durata del ciclo in giorni, semina e maturita' comprese (0 se fuori serie)."""
        return self.maturity - self.sow + 1 if self.maturity >= 0 else 0

    @property
    def harvest(self) -> int:
        """Raccolta = maturita' fisiologica."""
        return self.maturity

    def events(self) -> dict:
        return {k: getattr(self, k) for k in ("sow",) + _EVENTI}

    def as_dates(self, dates) -> dict:
        """Eventi come date (NaT se non raggiunti); ``dates`` = colonna date del meteo."""
        dd = pd.to_datetime(pd.Series(dates)).reset_index(drop=True)
        return {k: (dd[v] if v >= 0 else pd.NaT) for k, v in self.events().items()}


def _gdd_series(p: dict, crop: str, forcing) -> tuple[PhenoParams, np.ndarray]:
    pp = crop_pheno_params(p, crop)
    return pp, daily_gdd(tmean_of(forcing), pp.t_base, pp.t_upper)


def calendar_from_cum(pp: PhenoParams, cum: np.ndarray, sow: int,
                      deadline_idx: int | None = None, ev: np.ndarray | None = None
                      ) -> CycleCalendar:
    """Calendario di un ciclo da GDD cumulati gia' calcolati (``cumulative_gdd``).
    ``ev``: riga gia' calcolata di ``threshold_days`` (per i lotti)."""
    if ev is None:
        ev = threshold_days(cum, [sow], pp.thresholds)[0]
    ev = [int(x) for x in ev]
    mat = ev[-1]
    n = len(cum) - 1
    if mat < 0:
        status, last = STATO_FUORI_SERIE, n - 1
    else:
        status, last = STATO_OK, mat
        if deadline_idx is not None and mat > deadline_idx:
            status = STATO_OLTRE_LIMITE
    gc = cum[sow + 1:last + 2] - cum[sow]
    frac = np.clip(gc / pp.gdd_maturita, 0.0, 1.0)
    return CycleCalendar(pp.crop, int(sow), *ev, status, pp.gdd_maturita,
                         pp.breakpoints, gc, frac)


def cycle_calendar(p: dict, crop: str, forcing, sow_idx: int,
                   deadline_idx: int | None = None) -> CycleCalendar:
    """Calendario del ciclo di ``crop`` seminato alla riga ``sow_idx`` del meteo
    (``fieldwise.weather.load_forcing``): emergenza, fine delle quattro fasi FAO-56
    (end_ini, end_dev, end_mid, maturity), fioritura, maturita' = raccolta, e frazione
    di sviluppo giornaliera. Vedi il docstring del modulo per stati e convenzioni."""
    pp, gdd = _gdd_series(p, crop, forcing)
    return calendar_from_cum(pp, cumulative_gdd(gdd), int(sow_idx), deadline_idx)


def cycle_calendars(p: dict, crop: str, forcing, sow_idx, deadline_idx=None
                    ) -> list[CycleCalendar]:
    """Come ``cycle_calendar`` per molte semine (una sola somma cumulata e una sola
    ricerca vettoriale). ``deadline_idx``: None, un intero o un array come ``sow_idx``."""
    pp, gdd = _gdd_series(p, crop, forcing)
    cum = cumulative_gdd(gdd)
    s = np.atleast_1d(np.asarray(sow_idx, dtype=np.int64))
    evs = threshold_days(cum, s, pp.thresholds)
    dl = np.broadcast_to(np.asarray(-1 if deadline_idx is None else deadline_idx), s.shape)
    return [calendar_from_cum(pp, cum, int(si), None if deadline_idx is None else int(di), ev)
            for si, di, ev in zip(s, dl, evs)]


def event_table(p: dict, crop: str, forcing, sow_idx) -> np.ndarray:
    """Solo gli indici degli eventi (n_semine, 6) nell'ordine emergence, end_ini,
    end_dev, end_mid, flowering, maturity; -1 se non raggiunti. La via piu' veloce
    per molte semine."""
    pp, gdd = _gdd_series(p, crop, forcing)
    return threshold_days(cumulative_gdd(gdd), sow_idx, pp.thresholds)


def sowing_index(forcing, year: int, mmdd: str) -> int:
    """Riga del meteo con data ``year-mmdd`` ("MM-GG"); KeyError se manca."""
    dates = pd.to_datetime(forcing["date"]).dt.normalize()
    hit = np.flatnonzero((dates == pd.Timestamp(f"{year}-{mmdd}")).to_numpy())
    if hit.size == 0:
        raise KeyError(f"data {year}-{mmdd} non presente nel meteo")
    return int(hit[0])


def typical_sowing_index(p: dict, crop: str, forcing, year: int) -> int:
    """Riga della semina tipica (crops.<crop>.semina) nell'anno ``year`` (per il
    frumento autunnale: l'anno della semina, la raccolta cade nell'anno seguente)."""
    return sowing_index(forcing, year, str(_params.get(p, f"crops.{crop}.semina")))


def crop_daily_curves_gdd(p: dict, crop: str, cal: CycleCalendar,
                          z_profile: float | None = None, u2_mid: float | None = None,
                          rhmin_mid: float | None = None, u2_end: float | None = None,
                          rhmin_end: float | None = None):
    """Serie (kc, zr, p_tab) del ciclo, lunghe ``cal.n_days``, con la frazione di
    sviluppo in gradi-giorno al posto di quella in giorni di ``water.crop_daily_curves``.
    Usa ``water.kc_curve`` e ``water.root_depth`` con i punti di passaggio
    ``cal.breakpoints``; correzioni climatiche di Kc mid/end (FAO-56 eq. 62 e 65) come
    in ``water.crop_daily_curves``."""
    if cal.status == STATO_FUORI_SERIE:
        raise ValueError("ciclo non simulabile: maturita' oltre la fine della serie meteo")
    g = _params.get
    f_ini, f_dev, f_mid = cal.breakpoints
    kc_ini = float(g(p, f"crops.{crop}.kc.ini"))
    kc_mid = float(g(p, f"crops.{crop}.kc.mid"))
    kc_end = float(g(p, f"crops.{crop}.kc.end"))
    h = float(g(p, f"crops.{crop}.h_max"))
    if u2_mid is not None and rhmin_mid is not None:
        kc_mid = _water.kc_climate_correction(kc_mid, u2_mid, rhmin_mid, h)
    if u2_end is not None and rhmin_end is not None:
        kc_end = _water.kc_end_climate_correction(kc_end, u2_end, rhmin_end, h)
    kc = _water.kc_curve(cal.frac, kc_ini, kc_mid, kc_end, f_ini, f_dev, f_mid)
    zr = _water.root_depth(cal.frac, float(g(p, f"crops.{crop}.zr_ini")),
                           float(g(p, f"crops.{crop}.zr_max")), f_dev, z_profile)
    ptab = np.full(cal.n_days, float(g(p, f"crops.{crop}.p")))
    return np.asarray(kc, float), np.asarray(zr, float), ptab
