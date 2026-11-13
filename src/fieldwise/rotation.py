"""Catena di rotazione (fase 4): calendario, bilancio idrico unico, azoto/humus, resa, regole.

Tutti i numeri agronomici vengono da ``params/*.yaml`` (via ``fieldwise.params``):
crops.yaml (semina, semina_max, irrigabile, ky), cover_crop.yaml (calendario_agronomico,
acqua.*, requisiti_sra06), rotation_rules.yaml (calendario_rotazione.giorni_minimi_raccolta_semina,
successioni_vietate, f_rotazione), scenarios.yaml (tetti irrigui e regime di ristoppio).

Uso tipico (ensemble)::

    ctx = build_context()                       # una volta: meteo, parametri, GDD, curve
    rot = Rotation(("mais", "soia", "frumento"), (False, True, False))
    cal = build_calendar(ctx, rot, 2005, n_avviamento=1)    # indipendente dallo scenario
    for sc in SCENARI:
        out = simulate(ctx, rot, 2005, sc, calendario=cal)

Convenzioni (scelte dichiarate):
- ``anno`` = anno di inizio della simulazione: lo stato iniziale (profilo a capacita' di
  campo, N_min da n_pronto, humus H0) vale il 1 gennaio di ``anno``; segue il tratto di suolo
  nudo fino alla prima semina, poi ``n_avviamento`` cicli interi della stessa rotazione, poi
  il ciclo valutato. Le uscite riguardano solo il ciclo valutato (``anno_valutato`` = anno
  della sua prima semina). Lo stato non si azzera mai: un'unica chiamata a
  ``water.run_water_balance`` per tutta la simulazione, stato azoto-humus passato da un
  segmento al successivo.
- Ciclo valutato = dalla semina della prima coltura alla vigilia della semina della prima
  coltura del ciclo seguente (rotazione ciclica): comprende l'intervallo dopo l'ultima coltura.
- Semina: prima occasione utile dopo raccolta + giorni_minimi_raccolta_semina. Se la data
  tipica (crops.<c>.semina) della stagione non e' ancora passata si semina alla data tipica;
  se e' passata ma non e' passata semina_max si semina appena possibile ("ritardata"). La
  stagione di destinazione e' la prima finestra [semina, semina_max] con semina_max >= giorno
  dopo la raccolta; se raccolta + preparazione supera quel semina_max e' un CONFLITTO
  (maturita' non raggiunta in tempo per la semina successiva): con ``in_conflitto="rinvia"``
  la semina passa alla data tipica dell'anno seguente e il conflitto e' riportato; con
  ``"esito"`` la rotazione non viene simulata (esito ``conflitto_calendario``).
- Raccolta = maturita' fisiologica in gradi-giorno (``phenology``).
- Cover (segale) nell'intervallo dopo una coltura solo se richiesta e se il calendario
  agronomico lo consente: semina = max(raccolta + preparazione, semina_inizio_ottimale) entro
  semina_max dello stesso anno; terminazione = terminazione_tipica dell'anno seguente, almeno
  durata_minima_giorni dopo la semina e almeno ``giorni_minimi_raccolta_semina`` + 1 giorni
  prima della semina successiva. Altrimenti suolo nudo, con il motivo in uscita. I requisiti
  SRA06 producono solo avvertenze.
- Ciclo che esce dalla serie meteo affidabile (oltre il 31/12 dell'ultimo anno di
  ``weather.available_years``) o maturita' mai raggiunta: esito ``non_simulabile``, nessun numero.
- Ciclo con una fase di piena stagione vuota o con la finestra sensibile al caldo vuota (caso
  degenere dei parametri): esito ``parametri_degeneri`` con il motivo, nessun numero.
- Suolo nudo: Kc, Zr e p non entrano nel bilancio (evaporazione dallo strato superficiale,
  ``water`` usa Kc_max); si passano zeri, valori inerti, non parametri.
- Kc mid ed end corretti per il clima (FAO-56 eq. 62 e 65) con u2 e RHmin medi delle fasi di
  piena stagione e finale del ciclo (RHmin da ``water.rhmin_from_temperature``).
- f_rotazione con le due colture principali precedenti della rotazione ciclica (le cover non
  contano), regime 'irriguo'/'asciutto' dallo scenario (scenarios.yaml regime_rotazione).
- L'azoto non riduce la resa (``nitrogen``: il superamento del MAS e il deficit della soia
  sono indicatori, non fattori).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np

from . import config as _config
from . import nitrogen as _n
from . import params as _params
from . import phenology as _ph
from . import water as _water
from . import weather as _weather
from . import yield_model as _ym

SCENARI = ("solo_pioggia", "tetto_irriguo", "irrigazione_libera")
RIPARTI = ("traspirazione", "eta", "eta_et0")   # riparto giornaliero dell'assorbimento di N
ESITO_OK = "ok"
ESITO_NON_SIMULABILE = "non_simulabile"
ESITO_CONFLITTO = "conflitto_calendario"
ESITO_DEGENERE = "parametri_degeneri"   # fase o finestra del ciclo vuota: nessun numero
TETTO_ILLIMITATO = "illimitato"
COVER_TAG = "+cover"
SEP = " > "
_DAYS_PER_YEAR = 365.25   # convenzione per la durata in anni della rotazione (calendario)


# =============================================================================
# Rotazione
# =============================================================================
@dataclass(frozen=True)
class Rotation:
    """Sequenza di colture principali e, per ogni coltura, se nell'intervallo che la segue
    (fino alla coltura successiva, ciclicamente) e' richiesta la cover crop."""
    crops: tuple
    cover: tuple

    def __post_init__(self):
        object.__setattr__(self, "crops", tuple(self.crops))
        object.__setattr__(self, "cover", tuple(bool(c) for c in self.cover))
        if not self.crops or len(self.crops) != len(self.cover):
            raise ValueError("Rotation: crops e cover devono avere la stessa lunghezza (>= 1)")

    @property
    def n(self) -> int:
        return len(self.crops)

    @property
    def label(self) -> str:
        """Etichetta leggibile, es. 'mais > soia+cover > frumento'."""
        return SEP.join(c + (COVER_TAG if k else "") for c, k in zip(self.crops, self.cover))

    @classmethod
    def from_label(cls, label: str) -> "Rotation":
        parts = [s.strip() for s in label.split(SEP.strip())]
        crops = tuple(s.replace(COVER_TAG, "").strip() for s in parts)
        return cls(crops, tuple(s.endswith(COVER_TAG) for s in parts))

    def shifted(self, k: int) -> "Rotation":
        """Permutazione ciclica che parte dalla coltura k."""
        k %= self.n
        return Rotation(self.crops[k:] + self.crops[:k], self.cover[k:] + self.cover[:k])

    def canonical(self) -> "Rotation":
        """Rappresentante della classe di permutazioni cicliche (minimo lessicografico)."""
        return min((self.shifted(k) for k in range(self.n)),
                   key=lambda r: (r.crops, tuple(not c for c in r.cover)))


# =============================================================================
# Regole di rotazione
# =============================================================================
def main_crops(p: dict) -> list[str]:
    """Colture principali di crops.yaml: le voci con un ciclo fenologico (gdd_maturita);
    esclude _meta e suolo_nudo."""
    return [c for c, v in p["crops"].items()
            if c != _params.META_KEY and isinstance(v, dict) and "gdd_maturita" in v]


def compliance(p: dict, crops) -> dict:
    """Stato di conformita' ai disciplinari della sequenza ``crops`` (cover ignorate, come in
    rotation_rules._meta) per ciascun regime di rotation_rules.successioni_vietate:
    {regime: 'conforme' | 'conforme_solo_in_deroga' | 'non_conforme'}. La tabella e' indicizzata
    per una permutazione ciclica della sequenza; permutazioni cicliche hanno lo stesso stato.
    Sequenze non tabulate (es. lunghezza diversa da 3): {regime: None}."""
    table = p["rotation_rules"]["successioni_vietate"]
    seq = list(crops)
    regimes = None
    for k in range(len(seq)):
        key = "_".join(seq[k:] + seq[:k])
        if key in table:
            return {r: str(_params.get(table, f"{key}.{r}")) for r in table[key]}
        regimes = regimes or list(next(iter(table.values())).keys())
    return {r: None for r in (regimes or [])}


def enumerate_rotations(p: dict, length: int = 3, crops=None) -> list[dict]:
    """Tutte le rotazioni di ``length`` colture (colture da crops.yaml se ``crops`` e' None) con
    cover si'/no per ogni intervallo: per 3 colture e 3 posizioni 27 x 8 = 216. Nessuna e'
    esclusa. Ogni voce: {'rotation', 'label', 'classe' (etichetta del rappresentante ciclico),
    'rappresentante' (True per una sola rotazione della classe), 'n_equivalenti', 'conformita'}."""
    crops = main_crops(p) if crops is None else list(crops)
    out = []
    for seq in itertools.product(crops, repeat=length):
        for cov in itertools.product((False, True), repeat=length):
            r = Rotation(seq, cov)
            can = r.canonical()
            out.append({"rotation": r, "label": r.label, "classe": can.label,
                        "rappresentante": r == can, "conformita": compliance(p, seq)})
    sizes: dict = {}
    for e in out:
        sizes[e["classe"]] = sizes.get(e["classe"], 0) + 1
    for e in out:
        e["n_equivalenti"] = sizes[e["classe"]]
    return out


# =============================================================================
# Contesto riusabile
# =============================================================================
@dataclass
class RotationContext:
    """Tutto cio' che non dipende dalla rotazione: meteo come array, parametri letti una volta,
    GDD cumulati per coltura, suolo, stati iniziali, scenari e cache per (coltura, semina)."""
    p: dict
    forcing: object
    dates: np.ndarray            # datetime64[D]
    year: np.ndarray
    et0: np.ndarray
    rain: np.ndarray
    wind: np.ndarray
    rhmin: np.ndarray
    last_idx: int                # ultimo giorno della serie affidabile
    pheno: dict
    cum: dict
    crop: dict                   # coltura -> dict(semina, semina_max, irrigabile, ky, cn)
    gap: int
    cover: dict
    soil: _water.SoilWaterParams
    w0: _water.WaterState
    npar: _n.NitrogenParams
    n0: _n.NState
    scenarios: dict              # nome -> dict(cap={coltura: mm}, regime)
    _cycle: dict = field(default_factory=dict, repr=False)
    _heat: dict = field(default_factory=dict, repr=False)
    _cover_curves: dict = field(default_factory=dict, repr=False)

    def idx(self, year: int, mmdd: str) -> int:
        """Riga del meteo per year-mmdd (puo' essere fuori serie: <0 o > ultima riga)."""
        return int((np.datetime64(f"{int(year):04d}-{mmdd}") - self.dates[0]).astype(int))

    def date(self, i: int) -> str:
        return str(self.dates[i]) if 0 <= i < len(self.dates) else ""

    def cycle(self, crop: str, sow: int) -> dict:
        """Calendario, curve (kc, zr, p) e fattore di caldo del ciclo (crop, sow), in cache."""
        key = (crop, sow)
        c = self._cycle.get(key)
        if c is not None:
            return c
        cal = _ph.calendar_from_cum(self.pheno[crop], self.cum[crop], sow)
        c = {"cal": cal}
        if cal.ok and cal.maturity <= self.last_idx:
            mid = slice(cal.end_dev + 1, cal.end_mid + 1)
            end = slice(cal.end_mid + 1, cal.maturity + 1)
            if end.start >= end.stop:
                end = slice(cal.maturity, cal.maturity + 1)
            if mid.start >= mid.stop:
                c["degenere"] = (f"fase di piena stagione vuota per {crop} seminato il "
                                 f"{self.date(sow)}: vento e umidita' minima non definiti")
            else:
                kc, zr, pt = _ph.crop_daily_curves_gdd(
                    self.p, crop, cal, self.soil.depth,
                    float(self.wind[mid].mean()), float(self.rhmin[mid].mean()),
                    float(self.wind[end].mean()), float(self.rhmin[end].mean()))
                u2m, rhm = float(self.wind[mid].mean()), float(self.rhmin[mid].mean())
                u2e, rhe = float(self.wind[end].mean()), float(self.rhmin[end].mean())
                try:
                    heat = _ym.heat_factor(self.p, crop, self.forcing, cal)
                except _ym.FinestraVuota as ex:
                    c["degenere"] = f"{ex} per {crop} seminato il {self.date(sow)}"
                else:
                    c.update(kc=kc, zr=zr, pt=pt, heat=heat,
                             kcb=self._kcb_curve(crop, cal, u2m, rhm, u2e, rhe),
                             h=np.asarray(_water.plant_height(
                                 cal.frac, float(_params.get(self.p, f"crops.{crop}.h_max")),
                                 cal.breakpoints[1]), float))
        self._cycle[key] = c
        return c

    def heat(self, crop: str, sow: int, metodo: str = "deryng"):
        """``HeatResult`` del ciclo (crop, sow) con la funzione del caldo ``metodo``, in cache.
        Il ciclo deve essere calcolabile (non degenere): lo garantisce ``build_calendar``."""
        if metodo not in _ym.METODI_CALDO:
            raise ValueError(f"metodo_caldo sconosciuto: {metodo} (ammessi {_ym.METODI_CALDO})")
        c = self.cycle(crop, sow)
        if metodo == "deryng":
            return c["heat"]
        key = (crop, sow, metodo)
        h = self._heat.get(key)
        if h is None:
            h = self._heat[key] = _ym.heat_factor(self.p, crop, self.forcing, c["cal"], metodo=metodo)
        return h

    def _kcb_curve(self, crop, cal, u2m, rhm, u2e, rhe):
        """Kcb del ciclo (FAO-56 Tab. 17): stessa curva a quattro tratti e stessi punti di
        passaggio di Kc (``cal.breakpoints``), correzione climatica di mid ed end come Kc
        (eq. 70, stessa forma di eq. 62)."""
        g = _params.get
        h = float(g(self.p, f"crops.{crop}.h_max"))
        ini = float(g(self.p, f"crops.{crop}.kcb.ini"))
        mid = _water.kc_climate_correction(float(g(self.p, f"crops.{crop}.kcb.mid")), u2m, rhm, h)
        end = _water.kc_end_climate_correction(float(g(self.p, f"crops.{crop}.kcb.end")), u2e, rhe, h)
        f_ini, f_dev, f_mid = cal.breakpoints
        return np.asarray(_water.kc_curve(cal.frac, ini, mid, end, f_ini, f_dev, f_mid), float)

    def cover_curves(self, n_days: int):
        c = self._cover_curves.get(n_days)
        if c is None:
            c = _water.cover_daily_curves(self.p, n_days, self.cover["zr_ini"], self.soil.depth)
            self._cover_curves[n_days] = c
        return c


def _cap_value(v) -> float:
    if isinstance(v, str):
        if v != TETTO_ILLIMITATO:
            raise ValueError(f"tetto irriguo non riconosciuto: {v!r}")
        return math.inf
    return float(v)


def build_context(p: dict | None = None, forcing=None, lat: float | None = None,
                  lon: float | None = None) -> RotationContext:
    """Prepara il contesto una volta sola (parametri, meteo del punto, GDD cumulati, suolo,
    stati iniziali, scenari). Default: params/ e il punto pilota di ``config``."""
    p = _params.load_params() if p is None else p
    if forcing is None:
        forcing = _weather.load_forcing(_config.PILOT_LAT if lat is None else lat,
                                        _config.PILOT_LON if lon is None else lon)
    g = _params.get
    dates = np.asarray(forcing["date"].to_numpy(), dtype="datetime64[D]")
    if len(dates) > 1 and not np.all(np.diff(dates).astype(int) == 1):
        raise ValueError("meteo non giornaliero contiguo")
    year = dates.astype("datetime64[Y]").astype(int) + 1970
    last_year = max(_weather.available_years(forcing))
    last_idx = int(np.flatnonzero(year <= last_year)[-1])
    tmean = _ph.tmean_of(forcing)
    crops = main_crops(p)
    pheno, cum, info = {}, {}, {}
    for c in crops:
        pp = _ph.crop_pheno_params(p, c)
        pheno[c] = pp
        cum[c] = _ph.cumulative_gdd(_ph.daily_gdd(tmean, pp.t_base, pp.t_upper))
        info[c] = {"semina": str(g(p, f"crops.{c}.semina")),
                   "semina_max": str(g(p, f"crops.{c}.semina_max")),
                   "irrigabile": int(g(p, f"crops.{c}.irrigabile")),
                   "ky": float(g(p, f"crops.{c}.ky")),
                   "cn": _water.cn_class(c)}
    doy = (dates - dates.astype("datetime64[Y]")).astype(int) + 1
    for c in crops:   # giorno dell'anno mediano della raccolta con semina tipica (dal meteo)
        hv = []
        for y in range(int(year[0]), last_year):
            try:
                s = _ph.sowing_index(forcing, y, info[c]["semina"])
            except KeyError:
                continue
            m = _ph.threshold_days(cum[c], [s], [pheno[c].gdd_maturita])[0, 0]
            if 0 <= m <= last_idx:
                hv.append(doy[m])
        info[c]["doy_raccolta_tipica"] = float(np.median(hv))
        info[c]["doy_semina"] = int(doy[_ph.sowing_index(forcing, int(year[0]), info[c]["semina"])])
    ca = "cover_crop.calendario_agronomico"
    sra = "cover_crop.requisiti_sra06"
    cover = {"semina_inizio": str(g(p, f"{ca}.semina_inizio_ottimale")),
             "semina_max": str(g(p, f"{ca}.semina_max")),
             "terminazione": str(g(p, f"{ca}.terminazione_tipica")),
             "durata_min": int(g(p, f"{ca}.durata_minima_giorni")),
             "zr_ini": float(g(p, "cover_crop.acqua.profondita_radicale_iniziale")),
             "cn": _water.cn_class_index(str(g(p, "cover_crop.acqua.classe_curve_number"))),
             "kcb": float(g(p, "cover_crop.acqua.kcb.ini")),
             "h": float(g(p, "cover_crop.acqua.altezza")),
             "sra_max_racc_sem": int(g(p, f"{sra}.max_giorni_raccolta_semina")),
             "sra_durata_min": int(g(p, f"{sra}.durata_minima_giorni")),
             "sra_term_non_prima": str(g(p, f"{sra}.terminazione_non_prima_di")),
             "sra_max_term_sem": int(g(p, f"{sra}.max_giorni_terminazione_semina_successiva"))}
    scen = {}
    for name, node in p["scenarios"]["scenari"].items():
        v = _params.values(node)
        scen[name] = {"cap": {c: _cap_value(x) for c, x in v["tetto_irriguo"].items()},
                      "regime": str(v["regime_rotazione"])}
    soil = _water.soil_from_params(p)
    npar = _n.nitrogen_params(p, soil)
    return RotationContext(
        p=p, forcing=forcing, dates=dates, year=year,
        et0=forcing["et0"].to_numpy(float), rain=forcing["rain"].to_numpy(float),
        wind=forcing["wind"].to_numpy(float),
        rhmin=np.asarray(_water.rhmin_from_temperature(forcing["tmax"].to_numpy(float),
                                                       forcing["tmin"].to_numpy(float)), float),
        last_idx=last_idx, pheno=pheno, cum=cum, crop=info,
        gap=int(g(p, "rotation_rules.calendario_rotazione.giorni_minimi_raccolta_semina")),
        cover=cover, soil=soil, w0=_water.initial_water_state(soil), npar=npar,
        n0=_n.initial_state(npar), scenarios=scen)


# =============================================================================
# Calendario
# =============================================================================
@dataclass
class Segment:
    """Tratto omogeneo della simulazione (indici di riga del meteo, estremi compresi)."""
    kind: str            # nitrogen.SEG_CROP | SEG_BARE | SEG_COVER
    start: int
    end: int
    crop: str | None = None
    pos: int = -1        # posizione della coltura (o dell'intervallo dopo la coltura) nella rotazione
    cycle: int = -1      # -1 = tratto iniziale; 0..n_avviamento = cicli (l'ultimo e' valutato)


@dataclass
class RotationCalendar:
    """Esito di ``build_calendar``. Con esito diverso da 'ok' i segmenti sono vuoti."""
    rotation: Rotation
    anno: int
    n_avviamento: int
    esito: str
    motivo: str = ""
    segments: list = field(default_factory=list)
    crops: list = field(default_factory=list)       # una voce per coltura simulata
    intervals: list = field(default_factory=list)   # una voce per intervallo tra colture
    eval_start: int = -1
    eval_end: int = -1
    conflitti: list = field(default_factory=list)
    _inputs: object = field(default=None, repr=False)
    _kcb: object = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.esito == ESITO_OK

    @property
    def durata_anni(self) -> float:
        return (self.eval_end - self.eval_start + 1) / _DAYS_PER_YEAR if self.ok else math.nan


def _next_sowing(ctx: RotationContext, crop: str, harvest: int | None, t0: int,
                 prev: str | None = None):
    """(semina, modo, conflitto) della coltura ``crop`` dopo la raccolta ``harvest`` di
    ``prev`` (None = prima coltura, dal giorno t0). modo: 'tipica' | 'ritardata' | 'rinviata'.
    Stagione di destinazione: l'anno della raccolta se la semina tipica di ``crop`` cade dopo
    la raccolta tipica di ``prev`` (giorno dell'anno mediano, dal meteo), altrimenti l'anno
    seguente; cosi' una raccolta precoce non crea un secondo raccolto nello stesso anno."""
    ci = ctx.crop[crop]
    if harvest is None:
        y = int(ctx.year[t0])
        s = ctx.idx(y, ci["semina"])
        return (s, "tipica", None) if s >= t0 else (ctx.idx(y + 1, ci["semina"]), "tipica", None)
    earliest = harvest + 1 + ctx.gap
    y = int(ctx.year[min(harvest, len(ctx.year) - 1)])
    if ci["doy_semina"] <= ctx.crop[prev]["doy_raccolta_tipica"]:
        y += 1
    typ, mx = ctx.idx(y, ci["semina"]), ctx.idx(y, ci["semina_max"])
    if earliest <= typ:
        return typ, "tipica", None
    if earliest <= mx:
        return earliest, "ritardata", None
    return ctx.idx(y + 1, ci["semina"]), "rinviata", (
        f"{crop}: raccolta di {prev} + preparazione ({ctx.date(earliest) or earliest}) oltre "
        f"semina_max {y}-{ci['semina_max']}")


def _cover_window(ctx: RotationContext, harvest: int, next_sow: int):
    """(semina, terminazione, None) se la segale entra nell'intervallo, altrimenti (None, None,
    motivo). Calendario agronomico di cover_crop.yaml; vedi docstring del modulo."""
    cv = ctx.cover
    earliest = harvest + 1 + ctx.gap
    y = int(ctx.year[min(earliest, len(ctx.year) - 1)])
    cs = max(earliest, ctx.idx(y, cv["semina_inizio"]))
    if cs > ctx.idx(y, cv["semina_max"]):
        return None, None, f"semina della cover possibile solo dal {ctx.date(cs)}, oltre semina_max"
    term = ctx.idx(y + 1, cv["terminazione"])
    if term - cs < cv["durata_min"]:
        return None, None, f"durata {term - cs} g < durata_minima_giorni"
    if term + 1 + ctx.gap > next_sow:
        return None, None, "terminazione non compatibile con la semina successiva"
    return cs, term, None


def _sra06_warnings(ctx, harvest, cs, term, next_sow) -> list:
    cv = ctx.cover
    w = []
    if cs - harvest > cv["sra_max_racc_sem"]:
        w.append("SRA06: semina della cover oltre max_giorni_raccolta_semina dalla raccolta")
    if term - cs < cv["sra_durata_min"]:
        w.append("SRA06: durata inferiore a durata_minima_giorni")
    if term < ctx.idx(int(ctx.year[term]), cv["sra_term_non_prima"]):
        w.append("SRA06: terminazione prima di terminazione_non_prima_di")
    if next_sow - term > cv["sra_max_term_sem"]:
        w.append("SRA06: semina successiva oltre max_giorni_terminazione_semina_successiva")
    return w


def build_calendar(ctx: RotationContext, rotation: Rotation, anno: int, n_avviamento: int = 1,
                   in_conflitto: str = "rinvia") -> RotationCalendar:
    """Calendario completo della simulazione (tratto iniziale, ``n_avviamento`` cicli, ciclo
    valutato) a partire dal 1 gennaio di ``anno``. Non dipende dallo scenario d'acqua: si
    calcola una volta e si passa a ``simulate`` per i tre scenari."""
    if in_conflitto not in ("rinvia", "esito"):
        raise ValueError("in_conflitto: 'rinvia' o 'esito'")
    n = rotation.n
    rc = RotationCalendar(rotation, int(anno), int(n_avviamento), ESITO_OK)
    t0 = ctx.idx(anno, "01-01")
    if t0 < 0 or t0 > ctx.last_idx:
        rc.esito, rc.motivo = ESITO_NON_SIMULABILE, f"anno {anno} fuori dalla serie meteo"
        return rc
    lim = ctx.date(ctx.last_idx)
    n_crops = (n_avviamento + 1) * n
    sows, modes, cyc = [], [], []
    harvest = None
    for k in range(n_crops + 1):
        crop = rotation.crops[k % n]
        s, mode, confl = _next_sowing(ctx, crop, harvest, t0, rotation.crops[(k - 1) % n])
        if confl:
            rc.conflitti.append({"ciclo": k // n, "pos": k % n, "descrizione": confl})
            if in_conflitto == "esito":
                rc.esito, rc.motivo = ESITO_CONFLITTO, confl
                return rc
        if s > ctx.last_idx + (1 if k == n_crops else 0):
            rc.esito = ESITO_NON_SIMULABILE
            rc.motivo = f"semina di {crop} oltre la serie meteo affidabile ({lim})"
            return rc
        sows.append(s)
        modes.append(mode)
        if k == n_crops:
            break
        c = ctx.cycle(crop, s)
        cal = c["cal"]
        if not cal.ok or cal.maturity > ctx.last_idx:
            rc.esito = ESITO_NON_SIMULABILE
            rc.motivo = (f"maturita' di {crop} seminato il {ctx.date(s)} oltre la serie meteo "
                         f"affidabile ({lim})")
            return rc
        if "degenere" in c:
            rc.esito, rc.motivo = ESITO_DEGENERE, c["degenere"]
            return rc
        cyc.append(cal)
        harvest = cal.maturity
    segs = rc.segments
    if sows[0] > t0:
        segs.append(Segment(_n.SEG_BARE, t0, sows[0] - 1, None, -1, -1))
    for k in range(n_crops):
        pos, cy = k % n, k // n
        crop, cal = rotation.crops[pos], cyc[k]
        segs.append(Segment(_n.SEG_CROP, cal.sow, cal.maturity, crop, pos, cy))
        rc.crops.append({"ciclo": cy, "pos": pos, "crop": crop, "seg": len(segs) - 1,
                         "sow": cal.sow, "flowering": cal.flowering, "harvest": cal.maturity,
                         "modo_semina": modes[k]})
        h, ns = cal.maturity, sows[k + 1]
        iv = {"ciclo": cy, "pos": pos, "dopo": crop, "start": h + 1, "end": ns - 1,
              "cover_richiesta": rotation.cover[pos], "cover": False, "motivo_nudo": "",
              "avvertenze": [], "segs": []}
        if rotation.cover[pos]:
            cs, term, why = _cover_window(ctx, h, ns)
            if why is None:
                iv.update(cover=True, cover_semina=cs, cover_terminazione=term,
                          avvertenze=_sra06_warnings(ctx, h, cs, term, ns))
                parts = [(_n.SEG_BARE, h + 1, cs - 1), (_n.SEG_COVER, cs, term),
                         (_n.SEG_BARE, term + 1, ns - 1)]
            else:
                iv["motivo_nudo"] = why
                parts = [(_n.SEG_BARE, h + 1, ns - 1)]
        else:
            parts = [(_n.SEG_BARE, h + 1, ns - 1)]
        for kind, a, b in parts:
            if b >= a:
                segs.append(Segment(kind, a, b, None, pos, cy))
                iv["segs"].append(len(segs) - 1)
        rc.intervals.append(iv)
    rc.eval_start = sows[n_avviamento * n]
    rc.eval_end = sows[-1] - 1
    return rc


def _daily_inputs(ctx: RotationContext, rc: RotationCalendar) -> _water.DailyInputs:
    """Serie giornaliere della simulazione (in cache nel calendario)."""
    if rc._inputs is not None:
        return rc._inputs
    kcs, zrs, pts, surf, irr, seg, cns, kcbs, hs = [], [], [], [], [], [], [], [], []
    for k, s in enumerate(rc.segments):
        m = s.end - s.start + 1
        if s.kind == _n.SEG_CROP:
            c = ctx.cycle(s.crop, s.start)
            kc, zr, pt = c["kc"], c["zr"], c["pt"]
            kcbs.append(c["kcb"])
            hs.append(c["h"])
            sf, ir, cn = _water.SURF_CROP, ctx.crop[s.crop]["irrigabile"], ctx.crop[s.crop]["cn"]
        elif s.kind == _n.SEG_COVER:
            kc, zr, pt = ctx.cover_curves(m)
            kcbs.append(np.full(m, ctx.cover["kcb"]))
            hs.append(np.full(m, ctx.cover["h"]))
            sf, ir, cn = _water.SURF_COVER, 0, ctx.cover["cn"]
        else:
            kc = zr = pt = np.zeros(m)
            kcbs.append(np.full(m, ctx.soil.kcb_bare))     # crops.suolo_nudo.kcb_suolo_nudo
            hs.append(np.zeros(m))
            sf, ir, cn = _water.SURF_BARE, 0, _water.CN_BARE
        kcs.append(kc)
        zrs.append(zr)
        pts.append(pt)
        surf.append(np.full(m, sf, np.int64))
        irr.append(np.full(m, ir, np.int64))
        seg.append(np.full(m, k, np.int64))
        cns.append(np.full(m, cn, np.int64))
    a, b = rc.segments[0].start, rc.segments[-1].end
    cat = np.concatenate
    kcb, h = cat(kcbs), cat(hs)
    # doppio coefficiente (FAO-56 cap. 7): Kc max del giorno (eq. 72), frazione coperta (eq. 76)
    kcmx = _water.kc_max_eq72(ctx.soil.kc_max, kcb, ctx.wind[a:b + 1], ctx.rhmin[a:b + 1], h)
    fcov = _water.cover_fraction_eq76(kcb, kcmx, ctx.soil.kc_min, h)
    rc._kcb = kcb
    rc._inputs = _water.DailyInputs(ctx.et0[a:b + 1], ctx.rain[a:b + 1], cat(kcs), cat(zrs),
                                    cat(pts), cat(surf), cat(irr), cat(seg), cat(cns),
                                    kcb=kcb, kc_max=kcmx, fc=fcov)
    return rc._inputs


# =============================================================================
# Simulazione
# =============================================================================
def _caps(ctx: RotationContext, rc: RotationCalendar, scenario: str) -> np.ndarray:
    sc = ctx.scenarios[scenario]
    cap = np.zeros(len(rc.segments))
    for k, s in enumerate(rc.segments):
        if s.kind == _n.SEG_CROP and ctx.crop[s.crop]["irrigabile"]:
            if s.crop not in sc["cap"]:
                raise KeyError(f"scenarios.{scenario}: manca il tetto irriguo di {s.crop}")
            cap[k] = sc["cap"][s.crop]
    return cap


def simulate(ctx: RotationContext, rotation: Rotation, anno: int, scenario: str,
             n_avviamento: int = 1, calendario: RotationCalendar | None = None,
             dettaglio: bool = False, in_conflitto: str = "rinvia",
             riparto: str = "traspirazione", metodo_et: str = "doppio",
             metodo_caldo: str = "deryng") -> dict:
    """Simula la rotazione dal 1 gennaio di ``anno`` nello ``scenario`` d'acqua (uno di
    ``SCENARI``) e restituisce le uscite del ciclo valutato (vedi ``_meta`` del rapporto e le
    chiavi: 'esito', 'motivo', 'label', 'conformita', 'colture', 'intervalli', 'indicatori',
    'residui', 'durata_anni', 'anno_valutato', 'conflitti'). ``calendario``: risultato di
    ``build_calendar`` gia' calcolato (stessa rotazione, anno e avviamento). ``dettaglio``:
    aggiunge 'acqua' (WaterResult), 'aggregati' e 'azoto' (voci per segmento).
    ``riparto``: peso giornaliero dell'assorbimento di N di colture e cover (``RIPARTI``):
    'traspirazione' (default: la traspirazione ``tr`` calcolata dal nucleo idrico, Ks Kcb ET0
    nel metodo doppio; nel metodo singolo coincide con ETa di colture e cover), 'eta' (ETa),
    'eta_et0' (ETa/ET0); le ultime due servono solo all'analisi di sensibilita'.
    ``metodo_et``: 'doppio' (FAO-56 cap. 7, default) o 'singolo' (Kc singolo, sensibilita').
    ``metodo_caldo``: funzione del caldo di ``yield_model.heat_factor`` (``METODI_CALDO``:
    'deryng' default, 'aquacrop', 'teixeira'; le ultime due per la sensibilita')."""
    if metodo_caldo not in _ym.METODI_CALDO:
        raise ValueError(f"metodo_caldo sconosciuto: {metodo_caldo} (ammessi {_ym.METODI_CALDO})")
    p = ctx.p
    rc = calendario or build_calendar(ctx, rotation, anno, n_avviamento, in_conflitto)
    out = {"esito": rc.esito, "motivo": rc.motivo, "label": rotation.label,
           "rotazione": rotation, "scenario": scenario, "anno": int(anno),
           "n_avviamento": rc.n_avviamento, "conformita": compliance(p, rotation.crops),
           "conflitti": list(rc.conflitti)}
    if not rc.ok:
        return out
    sc = ctx.scenarios[scenario]
    inp = _daily_inputs(ctx, rc)
    res = _water.run_water_balance(inp, ctx.soil, ctx.w0, irr_cap=_caps(ctx, rc, scenario),
                                   metodo_et=metodo_et)
    agg = _water.aggregate_segments(res)
    n = rotation.n
    rot_f = [_ym.rotation_factor(p, c, rotation.crops[(i - 1) % n], rotation.crops[(i - 2) % n],
                                 sc["regime"]) for i, c in enumerate(rotation.crops)]
    seg_yield, rese = {}, []
    for k, s in enumerate(rc.segments):
        resa = 0.0
        if s.kind == _n.SEG_CROP:
            ci = ctx.crop[s.crop]
            fa = _ym.water_factor(agg["eta"][k], agg["etc"][k], ci["ky"])
            heat = ctx.heat(s.crop, s.start, metodo_caldo)
            fr, caso = rot_f[s.pos]
            y = _ym.crop_yield(p, s.crop, fa, heat.f_caldo, fr)
            y.update(caso_rotazione=caso, n_hot_days=heat.n_hot_days)
            seg_yield[k] = y
            resa = y["resa"]
        rese.append(resa)
    # quota giornaliera dell'assorbimento (colture e cover), normalizzata sul segmento
    if riparto == "traspirazione":
        w = res.tr.copy()          # una sola definizione di traspirazione nel motore
    elif riparto == "eta":
        w = res.eta.copy()
    elif riparto == "eta_et0":
        w = np.divide(res.eta, inp.et0, out=np.zeros_like(res.eta), where=inp.et0 > 0)
    else:
        raise ValueError(f"riparto sconosciuto: {riparto} (ammessi {RIPARTI})")
    wsum = np.bincount(res.segment, weights=w, minlength=len(rc.segments))
    days = agg["days"]
    share = np.where(wsum[res.segment] > 0, w / np.where(wsum > 0, wsum, 1.0)[res.segment],
                     1.0 / days[res.segment])
    kinds = [s.kind for s in rc.segments]
    state, bils, nday = _n.run_daily(ctx.n0, res.segment, kinds, [s.crop for s in rc.segments],
                                     rese, res.dp, share, ctx.npar)
    h_at = [ctx.n0.h]
    for b in bils:
        h_at.append(h_at[-1] + b["d_h"])
    n_res_max = max(abs(_n.n_balance_residual(b)) for b in bils)
    tot_in = sum(b["entrate"] for b in bils)
    tot_out = sum(b["uscite"] for b in bils)
    nph = ctx.npar.n_per_t_humus
    stock = lambda st: st.n_min + st.n_res + st.n_cov + st.h * nph   # noqa: E731
    n_rot_res = (stock(state) - stock(ctx.n0)) - (tot_in - tot_out)

    last = rc.n_avviamento
    ev = [k for k, s in enumerate(rc.segments) if s.cycle == last]
    colture = []
    for c in rc.crops:
        if c["ciclo"] != last:
            continue
        k = c["seg"]
        y, b = seg_yield[k], bils[k]
        colture.append({
            "coltura": c["crop"], "semina": ctx.date(c["sow"]), "fioritura": ctx.date(c["flowering"]),
            "raccolta": ctx.date(c["harvest"]), "modo_semina": c["modo_semina"],
            "giorni": int(agg["days"][k]), "resa": y["resa"], "resa_potenziale": y["resa_potenziale"],
            "resa_relativa": y["f_totale"], "f_acqua": y["f_acqua"], "f_caldo": y["f_caldo"],
            "f_rotazione": y["f_rotazione"], "caso_rotazione": y["caso_rotazione"],
            "etc": agg["etc"][k], "eta": agg["eta"][k], "traspirazione": agg["tr"][k],
            "evaporazione": agg["ev"][k], "irrigazione": agg["irr"][k],
            "pioggia": agg["rain"][k], "ruscellamento": agg["runoff"][k],
            "percolazione": agg["dp"][k], "concime": b["fert"], "lisciviazione": b["l"],
            "fissazione": b["fix"], "giorni_caldo": y["n_hot_days"], "supera_mas": b["supera_mas"],
            "eccedenza_mas": b["eccedenza_mas"], "deficit_n": b["deficit_n"]})
    intervalli = []
    for iv in rc.intervals:
        if iv["ciclo"] != last:
            continue
        ks = iv["segs"]
        intervalli.append({
            "dopo": iv["dopo"], "tipo": "cover" if iv["cover"] else "nudo",
            "cover_richiesta": iv["cover_richiesta"], "motivo_nudo": iv["motivo_nudo"],
            "inizio": ctx.date(iv["start"]), "fine": ctx.date(iv["end"]),
            "cover_semina": ctx.date(iv["cover_semina"]) if iv["cover"] else "",
            "cover_terminazione": ctx.date(iv["cover_terminazione"]) if iv["cover"] else "",
            "giorni": int(sum(agg["days"][k] for k in ks)),
            "lisciviazione": float(sum(bils[k]["l"] for k in ks)),
            "percolazione": float(sum(agg["dp"][k] for k in ks)),
            "ruscellamento": float(sum(agg["runoff"][k] for k in ks)),
            "avvertenze": iv["avvertenze"]})
    years = rc.durata_anni
    tot = lambda key: float(sum(agg[key][k] for k in ev))          # noqa: E731
    totb = lambda key: float(sum(bils[k][key] for k in ev))        # noqa: E731
    rr = [c["resa_relativa"] for c in colture]
    h0, h1 = h_at[ev[0]], h_at[ev[-1] + 1]
    ind = {
        "resa_relativa_media": float(np.mean(rr)), "resa_relativa_minima": float(np.min(rr)),
        "f_acqua_medio": float(np.mean([c["f_acqua"] for c in colture])),
        "f_caldo_medio": float(np.mean([c["f_caldo"] for c in colture])),
        "f_rotazione_medio": float(np.mean([c["f_rotazione"] for c in colture])),
        "irrigazione_anno": tot("irr") / years, "concime_anno": totb("fert") / years,
        "n_lisciviato_anno": totb("l") / years, "humus_variazione_anno": (h1 - h0) / years,
        "giorni_caldo_anno": sum(c["giorni_caldo"] for c in colture) / years,
        "ruscellamento_anno": tot("runoff") / years, "percolazione_anno": tot("dp") / years,
        "etc_anno": tot("etc") / years, "eta_anno": tot("eta") / years,
        "traspirazione_anno": tot("tr") / years, "evaporazione_anno": tot("ev") / years,
        "fissazione_anno": totb("fix") / years,
        "n_colture_oltre_mas": int(sum(c["supera_mas"] for c in colture)),
        "deficit_n_anno": totb("deficit_n") / years,
    }
    out.update(
        anno_valutato=int(ctx.year[rc.eval_start]), inizio=ctx.date(rc.eval_start),
        fine=ctx.date(rc.eval_end), durata_anni=years, colture=colture,
        intervalli=intervalli, indicatori=ind,
        residui={"acqua_mm": _water.water_balance_residual(res),
                 "azoto_max_segmento_kg": n_res_max,
                 "azoto_max_giorno_kg": float(np.abs(nday.residuo).max()),
                 "azoto_rotazione_kg": float(n_rot_res)},
        stato_finale={"acqua": res.state_end, "azoto": state})
    if dettaglio:
        out.update(acqua=res, aggregati=agg, azoto=bils, azoto_giornaliero=nday, quota_assorbimento=share,
                   segmenti=rc.segments)
    return out


def start_years(ctx: RotationContext, rotation: Rotation, n_avviamento: int = 1,
                in_conflitto: str = "rinvia") -> list[int]:
    """Anni di inizio per cui la rotazione e' simulabile entro la serie affidabile."""
    y0, y1 = int(ctx.year[0]), int(ctx.year[ctx.last_idx])
    return [y for y in range(y0, y1 + 1)
            if build_calendar(ctx, rotation, y, n_avviamento, in_conflitto).ok]


__all__ = ["Rotation", "RotationContext", "RotationCalendar", "Segment", "SCENARI",
           "RIPARTI", "build_context", "build_calendar", "simulate", "start_years", "compliance",
           "enumerate_rotations", "main_crops", "ESITO_OK", "ESITO_NON_SIMULABILE", "ESITO_CONFLITTO",
           "ESITO_DEGENERE"]
