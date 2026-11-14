"""Test del metodo a doppio coefficiente di ``fieldwise.water`` (FAO-56, cap. 7).

Specifica verificata (``run_water_balance(..., metodo_et="doppio"|"singolo")``):
traspirazione tr = Ks Kcb ET0; evaporazione ev = Ke ET0 con Ke = Kr (Kc max - Kcb) limitato da
few Kc max; ETc = (Kcb + Ke) ET0; ETa = tr + ev. Chiusura del bilancio, vincoli fisici,
Ks, andamento dell'evaporazione, confronto cover / suolo nudo (il difetto che ha motivato il
cambio di metodo), coltura appena seminata, irrigazione, ruscellamento, continuita' dello
stato, metodo singolo ancora disponibile, prestazioni. Nessuna rete; i valori attesi che
dipendono dai parametri vengono da ``fieldwise.params``.
"""
import dataclasses
import math
import time

import numpy as np
import pytest

from fieldwise import params as fparams
from fieldwise import water as w

TOL_MM = 0.01
EPS = 1e-9
N_SERIES = ("etc", "eta", "ks", "kr", "irr", "runoff", "dp", "w1", "w2", "de", "tr", "ev")


# =============================================================================
# Costruzione degli ingressi
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def soil(pars):
    return w.soil_from_params(pars)


def _g(pars, key):
    return float(fparams.get(pars, key))


def _arr(x, n, dt=float):
    a = np.asarray(x, dtype=dt)
    return np.full(n, a) if a.ndim == 0 else a


def mk(et0, rain, kcb, kcmx, fcov, zr, p_tab, surface, irrigable, segment, cn, kc=None):
    """DailyInputs con i campi del doppio coefficiente; `kc` (solo metodo singolo) di default Kcb + 0,1."""
    n = len(et0)
    kcb = _arr(kcb, n)
    return w.DailyInputs(
        et0=_arr(et0, n), rain=_arr(rain, n), kc=_arr(kcb + 0.1 if kc is None else kc, n),
        zr=_arr(zr, n), p_tab=_arr(p_tab, n), surface=_arr(surface, n, int),
        irrigable=_arr(irrigable, n, int), segment=_arr(segment, n, int),
        cn_class=_arr(cn, n, int), kcb=kcb, kc_max=_arr(kcmx, n), fc=_arr(fcov, n))


def kcmax_default(soil, kcb, h=0.0):
    """Kc max dell'eq. 72 con u2 = 2 m/s e RHmin = 45 % (termine climatico nullo)."""
    return w.kc_max_eq72(soil.kc_max, kcb, 2.0, 45.0, h)


def series(kind, n, soil, pars):
    """Serie di un tratto: 'mais' | 'cover' | 'bare' -> dict di array (kcb, kc_max, fc, zr, ...)."""
    if kind == "mais":
        fasi = fparams.get(pars, "crops.mais.fasi_giorni")
        f_ini, f_dev, f_mid = w.stage_fractions(fasi)
        frac = (np.arange(n) + 1.0) / n
        kcb = w.kc_curve(frac, _g(pars, "crops.mais.kcb.ini"), _g(pars, "crops.mais.kcb.mid"),
                         _g(pars, "crops.mais.kcb.end"), f_ini, f_dev, f_mid)
        h = w.plant_height(frac, _g(pars, "crops.mais.h_max"), f_dev)
        kc, zr, pt = w.crop_daily_curves(pars, "mais", n, z_profile=soil.depth)
        surf, cn = w.SURF_CROP, w.cn_class("mais")
    elif kind == "cover":
        kcb = np.full(n, _g(pars, "cover_crop.acqua.kcb.ini"))
        h = np.full(n, _g(pars, "cover_crop.acqua.altezza"))
        kc, zr, pt = w.cover_daily_curves(pars, n, _g(pars, "cover_crop.acqua.profondita_radicale_iniziale"),
                                          z_profile=soil.depth)
        surf, cn = w.SURF_COVER, w.cn_class("cover")
    else:
        kcb, h = np.full(n, soil.kcb_bare), np.zeros(n)
        kc, zr, pt = np.zeros(n), np.zeros(n), np.zeros(n)
        surf, cn = w.SURF_BARE, w.cn_class("suolo_nudo")
    kcmx = w.kc_max_eq72(soil.kc_max, kcb, 2.0, 45.0, h)
    fcov = w.cover_fraction_eq76(kcb, kcmx, soil.kc_min, h)
    return dict(kcb=np.asarray(kcb, float), kcmx=np.asarray(kcmx, float), fcov=np.asarray(fcov, float),
                zr=np.asarray(zr, float), p_tab=np.asarray(pt, float), kc=np.asarray(kc, float),
                surface=np.full(n, surf), cn=np.full(n, cn))


def synthetic_weather(n, seed_phase=0.0):
    """Meteo sintetico deterministico: ET0 stagionale, pioggia periodica con eventi intensi."""
    d = np.arange(n)
    et0 = np.clip(3.5 + 2.5 * np.sin(2 * np.pi * (d - 60) / 365.0 + seed_phase), 0.3, None)
    rain = np.zeros(n)
    rain[::9] = 6.0
    rain[4::23] = 18.0
    rain[11::61] = 55.0
    return et0, rain


def maize_inputs(soil, pars, n=150, irrigable=1, rain_scale=1.0):
    et0, rain = synthetic_weather(n)
    s = series("mais", n, soil, pars)
    return mk(et0, rain * rain_scale, s["kcb"], s["kcmx"], s["fcov"], s["zr"], s["p_tab"],
              s["surface"], irrigable, 0, s["cn"], kc=s["kc"])


def multi_inputs(soil, pars, blocks, irrigable_segments=(0,), seed=None, rain_scale=1.0):
    """Tratti consecutivi [(kind, n), ...] con meteo sintetico (o casuale se `seed`)."""
    n_tot = sum(b[1] for b in blocks)
    if seed is None:
        et0, rain = synthetic_weather(n_tot)
        rain = rain * rain_scale
    else:
        rng = np.random.default_rng(seed)
        et0 = np.clip(3.5 + 2.5 * np.sin(2 * np.pi * (np.arange(n_tot) - 60) / 365.0), 0.3, None)
        rain = np.where(rng.random(n_tot) < 0.12, rng.exponential(8.0, n_tot), 0.0) * rain_scale
    parts = {k: [] for k in ("kcb", "kcmx", "fcov", "zr", "p_tab", "kc", "surface", "cn", "seg", "irr")}
    for k, (kind, n) in enumerate(blocks):
        s = series(kind, n, soil, pars)
        for key in ("kcb", "kcmx", "fcov", "zr", "p_tab", "kc", "surface", "cn"):
            parts[key].append(s[key])
        parts["seg"].append(np.full(n, k))
        parts["irr"].append(np.full(n, 1 if (kind == "mais" and k in irrigable_segments) else 0))
    c = {k: np.concatenate(v) for k, v in parts.items()}
    return mk(et0, rain, c["kcb"], c["kcmx"], c["fcov"], c["zr"], c["p_tab"], c["surface"], c["irr"],
              c["seg"], c["cn"], kc=c["kc"])


THREE_YEARS = [("mais", 150), ("bare", 120), ("cover", 200), ("bare", 100), ("mais", 150), ("bare", 375)]


def three_year_inputs(soil, pars, **kw):
    return multi_inputs(soil, pars, THREE_YEARS, irrigable_segments=(0, 4), **kw)


def random_inputs(n=20000, seed=20240607):
    rng = np.random.default_rng(seed)
    et0 = rng.uniform(0.0, 8.0, n)
    rain = np.where(rng.random(n) < 0.25, rng.exponential(12.0, n), 0.0)
    rain[rng.random(n) < 0.01] += 90.0
    kcb = rng.uniform(0.1, 1.3, n)
    kcmx = np.maximum(1.2, kcb + 0.05)
    return mk(et0, rain, kcb, kcmx, rng.uniform(0.0, 0.99, n), rng.uniform(0.1, 1.5, n),
              rng.uniform(0.3, 0.7, n), rng.integers(0, 3, n), rng.integers(0, 2, n),
              np.arange(n) // 50, rng.integers(0, 3, n))


def run(inp, soil, frac=None, **kw):
    kw.setdefault("metodo_et", "doppio")
    return w.run_water_balance(inp, soil, w.initial_water_state(soil, frac), **kw)


def slice_inputs(inp, a, b):
    return w.DailyInputs(**{f.name: getattr(inp, f.name)[a:b] for f in dataclasses.fields(inp)})


def residuals(res):
    return abs(w.water_balance_residual(res)), float(np.max(np.abs(w.water_balance_daily_residual(res))))


def assert_closed(res):
    tot, day = residuals(res)
    assert tot <= TOL_MM, tot
    assert day <= TOL_MM, day


# =============================================================================
# 1. Chiusura del bilancio idrico
# =============================================================================

class TestChiusura:
    def test_stagione_mais(self, soil, pars):
        inp = maize_inputs(soil, pars)
        for cap in (math.inf, 0.0, 80.0):
            res = run(inp, soil, irr_cap=cap)
            assert res.metodo_et == "doppio"
            assert_closed(res)

    def test_stagione_mais_percolazione(self, soil, pars):
        """Pioggia abbondante su suolo a capacita' di campo: il bilancio chiude con dp > 0."""
        res = run(maize_inputs(soil, pars, rain_scale=2.0), soil, frac=1.0, irr_cap=0.0)
        assert res.dp.sum() > 0
        assert_closed(res)

    @pytest.mark.parametrize("amc", [False, True])
    def test_tre_anni_piu_segmenti(self, soil, pars, amc):
        inp = three_year_inputs(soil, pars)
        assert len(inp.et0) == 1095
        res = run(inp, soil, frac=0.6, irr_cap=np.full(6, 120.0), use_amc=amc)
        assert res.irr.sum() > 0
        assert_closed(res)

    @pytest.mark.parametrize("amc", [False, True])
    def test_serie_casuale_lunga(self, soil, amc):
        inp = random_inputs()
        k = np.arange(400) % 3
        caps = np.where(k == 0, 0.0, np.where(k == 1, 60.0, np.inf))
        res = run(inp, soil, frac=0.3, irr_cap=caps, use_amc=amc)
        assert_closed(res)


# =============================================================================
# 2. Vincoli fisici e identita' tra le uscite
# =============================================================================

def _check_physics(res, inp, soil):
    assert np.all(np.isfinite(res.eta)) and np.all(np.isfinite(res.w1)) and np.all(np.isfinite(res.w2))
    assert np.allclose(res.eta, res.tr + res.ev, atol=1e-9, rtol=0)
    assert res.tr.min() >= 0.0 and res.ev.min() >= 0.0
    assert np.all(res.eta <= res.etc + 1e-9)
    assert res.w1.max() <= soil.fc1_mm + 1e-9 and res.w2.max() <= soil.fc2_mm + 1e-9
    assert res.w1.min() >= soil.w1_min_mm - 1e-9           # limite inferiore dello strato 1 (eq. 73)
    assert res.w2.min() >= soil.wp2_mm - 1e-9              # limite inferiore dello strato 2
    assert res.de.min() >= -1e-9 and res.de.max() <= soil.tew + 1e-9
    assert res.ks.min() >= 0.0 and res.ks.max() <= 1.0 + 1e-12
    assert res.kr.min() >= 0.0 and res.kr.max() <= 1.0 + 1e-12
    assert res.runoff.min() >= 0.0 and res.dp.min() >= 0.0 and res.irr.min() >= 0.0
    # regole della specifica
    assert np.all(res.tr <= res.ks * inp.kcb * inp.et0 + 1e-9)            # tr = Ks Kcb ET0 (o meno se manca acqua)
    assert np.all(res.ev <= res.kr * (inp.kc_max - inp.kcb).clip(0) * inp.et0 + 1e-9)       # Ke <= Kr (Kc max - Kcb)
    assert np.all(res.ev <= inp.kc_max * inp.et0 + 1e-9)
    assert np.allclose(res.etc, inp.kcb * inp.et0 + res.ev, atol=1e-9, rtol=0)  # ETc = (Kcb + Ke) ET0


class TestVincoli:
    def test_stagione_mais(self, soil, pars):
        inp = maize_inputs(soil, pars)
        for cap in (math.inf, 0.0):
            _check_physics(run(inp, soil, irr_cap=cap), inp, soil)

    def test_tre_anni(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        for amc in (False, True):
            _check_physics(run(inp, soil, frac=0.5, irr_cap=100.0, use_amc=amc), inp, soil)

    def test_tre_anni_pioggia_forte(self, soil, pars):
        inp = three_year_inputs(soil, pars, rain_scale=3.0)
        res = run(inp, soil, frac=1.0, irr_cap=0.0)
        assert res.dp.sum() > 0
        _check_physics(res, inp, soil)

    def test_serie_casuale(self, soil):
        inp = random_inputs()
        res = run(inp, soil, frac=0.3, irr_cap=40.0)
        _check_physics(res, inp, soil)

    def test_suolo_nudo_secco_non_scende_sotto_il_limite(self, soil):
        """Un anno di suolo nudo quasi senza pioggia: lo strato 1 non scende sotto il limite inferiore."""
        n = 365
        s = dict(kcb=soil.kcb_bare, kcmx=1.2, fcov=0.0)
        inp = mk(np.full(n, 6.0), np.zeros(n), s["kcb"], s["kcmx"], s["fcov"], 0.0, 0.5,
                 w.SURF_BARE, 0, 0, w.CN_BARE)
        res = run(inp, soil, frac=1.0, irr_cap=0.0)
        _check_physics(res, inp, soil)
        assert res.w1[-1] >= soil.w1_min_mm - 1e-9
        # lo strato evaporante e' esaurito (De = TEW) e lo strato 1 e' sceso almeno a wp1
        assert res.de[-1] == pytest.approx(soil.tew, abs=1e-9) and res.ev[-1] == 0.0
        assert res.w1[-1] <= soil.wp1_mm + 1e-9


# =============================================================================
# 3. Traspirazione con suolo ben rifornito
# =============================================================================

class TestTraspirazione:
    def test_ks_uno_tr_uguale_kcb_et0(self, soil):
        n, kcb = 10, 0.9
        inp = mk(np.full(n, 5.0), np.zeros(n), kcb, 1.2, 0.5, 1.0, 0.55, w.SURF_CROP, 0, 0, w.CN_ROW_CROPS)
        res = run(inp, soil, frac=1.0, irr_cap=0.0)
        assert np.all(res.ks == 1.0)
        assert np.allclose(res.tr, kcb * 5.0, atol=1e-12, rtol=0)

    def test_stagione_irrigazione_libera(self, soil, pars):
        inp = maize_inputs(soil, pars)
        res = run(inp, soil, frac=1.0, irr_cap=math.inf)
        ok = res.ks == 1.0
        assert ok.mean() > 0.95
        assert np.allclose(res.tr[ok], (inp.kcb * inp.et0)[ok], atol=1e-9, rtol=0)
        assert np.all(res.tr[~ok] < (inp.kcb * inp.et0)[~ok] + 1e-9)

    def test_stress_riduce_solo_la_traspirazione(self, soil):
        """Con stress (Ks < 1) tr = Ks Kcb ET0 e l'evaporazione non e' ridotta da Ks."""
        n = 20
        inp = mk(np.full(n, 5.0), np.zeros(n), 1.0, 1.2, 0.8, 1.0, 0.55, w.SURF_CROP, 0, 0, w.CN_ROW_CROPS)
        res = run(inp, soil, frac=0.25, irr_cap=0.0)
        assert res.ks.min() < 0.9 and res.ks[0] < 1.0
        # tr = Ks Kcb ET0 finche' l'acqua disponibile basta
        assert np.allclose(res.tr, res.ks * 1.0 * 5.0, atol=1e-6, rtol=0)
        assert np.all(res.etc - res.eta >= -1e-9)
        assert np.allclose(res.etc - res.eta, 5.0 - res.tr, atol=1e-9)    # perso = solo traspirazione


# =============================================================================
# 4. Evaporazione: cala quando la superficie si asciuga, riparte dopo la pioggia
# =============================================================================

class TestEvaporazione:
    def _bare(self, soil, n, rain=None, et0=5.0):
        rain = np.zeros(n) if rain is None else rain
        return mk(np.full(n, et0), rain, soil.kcb_bare, 1.2, 0.0, 0.0, 0.5, w.SURF_BARE, 0, 0, w.CN_BARE)

    def test_primo_giorno_ke_massimo(self, soil):
        res = run(self._bare(soil, 3), soil, frac=1.0, irr_cap=0.0)
        assert res.kr[0] == 1.0
        assert res.ev[0] == pytest.approx(1.0 * (1.2 - soil.kcb_bare) * 5.0, abs=1e-9)

    def test_ev_non_crescente_senza_pioggia(self, soil):
        res = run(self._bare(soil, 40), soil, frac=1.0, irr_cap=0.0)
        ev = res.ev
        assert np.all(np.diff(ev[3:]) <= 1e-9), ev
        assert ev[-1] < 0.3 * ev[0]
        assert np.all(np.diff(res.kr) <= 1e-12)           # Kr non cresce
        assert res.kr[-1] < 1.0

    def test_ripartenza_dopo_la_pioggia(self, soil):
        n = 40
        rain = np.zeros(n)
        rain[25] = 20.0
        res = run(self._bare(soil, n, rain), soil, frac=1.0, irr_cap=0.0)
        assert res.ev[26] > 2.0 * res.ev[24]
        assert res.kr[26] > res.kr[24]
        # dopo una bagnatura abbondante torna al massimo (Kr = 1 con De <= REW)
        assert res.kr[26] == 1.0 and res.ev[26] == pytest.approx(1.0 * (1.2 - soil.kcb_bare) * 5.0, abs=1e-9)

    def test_ev_limitata_da_few_kcmax(self, soil):
        """Frazione coperta 0,9: few = 0,1 e E <= few Kc max ET0."""
        n = 5
        inp = mk(np.full(n, 5.0), np.zeros(n), 0.3, 1.2, 0.9, 1.0, 0.55, w.SURF_CROP, 0, 0, w.CN_ROW_CROPS)
        res = run(inp, soil, frac=1.0, irr_cap=0.0)
        assert res.ev[0] <= 0.1 * 1.2 * 5.0 + 1e-9
        assert res.ev[0] == pytest.approx(min(1.0 * (1.2 - 0.3), 0.1 * 1.2) * 5.0, abs=1e-9)


# =============================================================================
# 5. Il difetto che ha motivato il cambio: cover contro suolo nudo
# =============================================================================

def _winter_weather(n, seed):
    """Intervallo autunno-invernale piovoso: ET0 bassa e decrescente, pioggia frequente."""
    rng = np.random.default_rng(seed)
    d = np.arange(n)
    et0 = np.clip(1.0 + 0.8 * np.sin(2 * np.pi * (d + 90) / 365.0), 0.2, None)
    rain = np.where(rng.random(n) < 0.35, rng.exponential(9.0, n), 0.0)
    return et0, rain


def _surface_inputs(soil, pars, kind, et0, rain):
    n = len(et0)
    s = series(kind, n, soil, pars)
    return mk(et0, rain, s["kcb"], s["kcmx"], s["fcov"], s["zr"], s["p_tab"], s["surface"], 0, 0, s["cn"],
              kc=s["kc"])


class TestCoverControNudo:
    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    @pytest.mark.parametrize("frac", [0.5, 1.0])
    def test_cover_non_consuma_meno_ne_percola_di_piu(self, soil, pars, seed, frac):
        et0, rain = _winter_weather(120, seed)
        assert rain.sum() > 3 * et0.sum() * 0.5            # intervallo davvero piovoso
        cov = run(_surface_inputs(soil, pars, "cover", et0, rain), soil, frac=frac, irr_cap=0.0)
        bare = run(_surface_inputs(soil, pars, "bare", et0, rain), soil, frac=frac, irr_cap=0.0)
        assert cov.eta.sum() >= bare.eta.sum() - 1.0, (cov.eta.sum(), bare.eta.sum())
        assert cov.dp.sum() <= 1.10 * bare.dp.sum() + EPS, (cov.dp.sum(), bare.dp.sum())
        assert_closed(cov) and assert_closed(bare)

    def test_intervallo_con_percolazione_non_banale(self, soil, pars):
        """Il confronto non e' vacuo: nello scenario di prova il suolo nudo percola."""
        et0, rain = _winter_weather(120, 1)
        bare = run(_surface_inputs(soil, pars, "bare", et0, rain), soil, frac=1.0, irr_cap=0.0)
        assert bare.dp.sum() > 5.0


# =============================================================================
# 6. Coltura appena seminata ~ suolo nudo
# =============================================================================

class TestSemina:
    @pytest.mark.parametrize("frac", [0.7, 1.0])
    def test_eta_vicina_al_suolo_nudo(self, soil, pars, frac):
        n = 20
        et0 = np.full(n, 4.0)
        rain = np.zeros(n)
        rain[::3] = 8.0                                    # suolo bagnato
        ini = series("mais", 150, soil, pars)              # primi giorni del ciclo: Kcb iniziale
        crop = mk(et0, rain, ini["kcb"][:n], ini["kcmx"][:n], ini["fcov"][:n], ini["zr"][:n],
                  ini["p_tab"][:n], w.SURF_CROP, 0, 0, w.CN_ROW_CROPS)
        assert ini["kcb"][0] == pytest.approx(_g(pars, "crops.mais.kcb.ini"))
        assert ini["fcov"][:n].max() < 0.05                # frazione coperta quasi nulla
        bare = _surface_inputs(soil, pars, "bare", et0, rain)
        rc = run(crop, soil, frac=frac, irr_cap=0.0)
        rb = run(bare, soil, frac=frac, irr_cap=0.0)
        assert rc.eta.sum() == pytest.approx(rb.eta.sum(), rel=0.15)
        assert rc.ev.sum() == pytest.approx(rb.ev.sum(), rel=0.15)


# =============================================================================
# 7. Irrigazione
# =============================================================================

class TestIrrigazione:
    def test_tetto_zero_nessuna_irrigazione(self, soil, pars):
        for inp in (maize_inputs(soil, pars), three_year_inputs(soil, pars)):
            res = run(inp, soil, frac=0.4, irr_cap=0.0)
            assert res.irr.sum() == 0.0

    def test_entro_il_tetto_per_segmento(self, soil, pars):
        blocks = [("mais", 150), ("bare", 100), ("mais", 150), ("mais", 150)]
        inp = multi_inputs(soil, pars, blocks, irrigable_segments=(0, 2, 3), seed=7)
        caps = np.array([40.0, 0.0, 15.0, math.inf])
        res = run(inp, soil, frac=0.5, irr_cap=caps)
        agg = w.aggregate_segments(res)
        assert np.all(agg["irr"][:3] <= caps[:3] + 1e-9)
        assert agg["irr"][0] > 0 and agg["irr"][2] > 0           # i tetti stringono davvero
        assert np.isclose(agg["irr"][:3], caps[:3], atol=1e-6).any()      # almeno un tetto e' raggiunto
        assert agg["irr"][1] == 0.0
        assert_closed(res)

    def test_non_irriga_dove_non_irrigabile(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        res = run(inp, soil, frac=0.3, irr_cap=math.inf)
        assert res.irr[inp.irrigable == 0].sum() == 0.0
        assert res.irr[inp.surface != w.SURF_CROP].sum() == 0.0

    def test_irrigazione_libera_ks_resta_uno(self, soil, pars):
        inp = maize_inputs(soil, pars)
        res = run(inp, soil, frac=1.0, irr_cap=math.inf)
        assert res.irr.sum() > 0
        assert res.ks.min() >= 0.9
        assert res.ks.mean() >= 0.99


# =============================================================================
# 8. Ruscellamento
# =============================================================================

class TestRuscellamento:
    def test_ia_su_s_piu_alto_meno_ruscellamento(self, soil, pars):
        """Giorno per giorno, stesso stato iniziale: con Ia/S piu' alto il ruscellamento non sale."""
        inp = three_year_inputs(soil, pars)
        giorni = np.nonzero(inp.rain > 0)[0]
        assert len(giorni) > 50
        prev = None
        for r in (0.02, 0.05, 0.1, 0.2, 0.3, 0.5):
            s = dataclasses.replace(soil, ia_ratio=r)
            day = np.array([w.run_water_balance(slice_inputs(inp, i, i + 1), s,
                                                w.initial_water_state(s, 0.6), irr_cap=0.0,
                                                metodo_et="doppio").runoff[0] for i in giorni])
            if prev is not None:
                assert np.all(day <= prev + 1e-9)
            prev = day
        assert prev.sum() >= 0.0

    def test_ia_su_s_sulla_serie(self, soil, pars):
        """Sull'intera serie il ruscellamento totale non cresce con Ia/S (stesso ingresso)."""
        inp = maize_inputs(soil, pars, rain_scale=1.5)
        tot = []
        for r in (0.05, 0.1, 0.2, 0.3):
            s = dataclasses.replace(soil, ia_ratio=r)
            tot.append(w.run_water_balance(inp, s, w.initial_water_state(s, 0.6), irr_cap=0.0,
                                           metodo_et="doppio").runoff.sum())
        assert tot[0] > 0
        assert all(b <= a + 0.5 for a, b in zip(tot, tot[1:]))      # lieve deriva dell'umidita' ammessa
        assert tot[-1] < tot[0]

    @pytest.mark.parametrize("amc", [False, True])
    @pytest.mark.parametrize("rain", [8.0, 30.0, 80.0])
    def test_default_non_dipende_dalla_superficie(self, soil, pars, amc, rain):
        assert soil.metodo_cn == "aquacrop"
        out = []
        for surf in (w.SURF_CROP, w.SURF_COVER, w.SURF_BARE):
            for cn in (w.CN_ROW_CROPS, w.CN_SMALL_GRAIN, w.CN_BARE):
                kcb = soil.kcb_bare if surf == w.SURF_BARE else 0.7
                inp = mk([3.0], [rain], kcb, 1.2, 0.3, 0.8, 0.55, surf, 0, 0, cn)
                res = run(inp, soil, frac=0.6, irr_cap=0.0, use_amc=amc)
                out.append(res.runoff[0])
        assert max(out) - min(out) < 1e-12, out
        assert out[0] > 0 or rain < 10


# =============================================================================
# 9. Continuita' dello stato: serie unica = serie spezzata
# =============================================================================

class TestContinuita:
    @pytest.mark.parametrize("cap", [0.0, math.inf])
    @pytest.mark.parametrize("amc", [False, True])
    @pytest.mark.parametrize("cut", [137, 400, 700])
    def test_spezzata_in_due(self, soil, pars, cap, amc, cut):
        inp = three_year_inputs(soil, pars)
        n = len(inp.et0)
        full = run(inp, soil, frac=0.5, irr_cap=cap, use_amc=amc)
        a = run(slice_inputs(inp, 0, cut), soil, frac=0.5, irr_cap=cap, use_amc=amc)
        b = w.run_water_balance(slice_inputs(inp, cut, n), soil, a.state_end, irr_cap=cap,
                                use_amc=amc, metodo_et="doppio")
        for k in N_SERIES:
            joined = np.concatenate([getattr(a, k), getattr(b, k)])
            assert np.allclose(joined, getattr(full, k), atol=1e-9, rtol=0), k
        for k in ("w1", "w2", "de"):
            assert getattr(b.state_end, k) == pytest.approx(getattr(full.state_end, k), abs=1e-9)
        assert abs(w.water_balance_residual(a)) <= TOL_MM and abs(w.water_balance_residual(b)) <= TOL_MM

    def test_stato_iniziale_non_viene_modificato(self, soil, pars):
        st = w.initial_water_state(soil, 0.5)
        before = st.copy()
        w.run_water_balance(maize_inputs(soil, pars), soil, st, irr_cap=math.inf, metodo_et="doppio")
        assert (st.w1, st.w2, st.de) == (before.w1, before.w2, before.de)


# =============================================================================
# 10. Il metodo singolo resta disponibile e non e' un sinonimo
# =============================================================================

class TestMetodoSingolo:
    def test_default_dipende_dalla_presenza_di_kcb(self, soil, pars):
        inp = maize_inputs(soil, pars)
        assert run(inp, soil, metodo_et=None, irr_cap=0.0).metodo_et == "doppio"
        senza = dataclasses.replace(inp, kcb=None, kc_max=None, fc=None)
        assert run(senza, soil, metodo_et=None, irr_cap=0.0).metodo_et == "singolo"

    def test_doppio_senza_kcb_errore(self, soil, pars):
        senza = dataclasses.replace(maize_inputs(soil, pars), kcb=None)
        with pytest.raises(ValueError):
            run(senza, soil, metodo_et="doppio")

    def test_metodo_sconosciuto(self, soil, pars):
        with pytest.raises(ValueError):
            run(maize_inputs(soil, pars), soil, metodo_et="triplo")

    @pytest.mark.parametrize("cap", [0.0, math.inf])
    def test_singolo_diverso_dal_doppio(self, soil, pars, cap):
        inp = three_year_inputs(soil, pars)
        d = run(inp, soil, frac=0.6, irr_cap=cap, metodo_et="doppio")
        s = run(inp, soil, frac=0.6, irr_cap=cap, metodo_et="singolo")
        assert s.metodo_et == "singolo" and d.metodo_et == "doppio"
        assert_closed(s) and assert_closed(d)
        assert not np.allclose(s.eta, d.eta, atol=1e-3)
        assert abs(s.eta.sum() - d.eta.sum()) > 1.0
        assert not np.allclose(s.etc, d.etc, atol=1e-3)

    def test_singolo_ignora_i_campi_del_doppio(self, soil, pars):
        inp = maize_inputs(soil, pars)
        senza = dataclasses.replace(inp, kcb=None, kc_max=None, fc=None)
        a = run(inp, soil, metodo_et="singolo", irr_cap=60.0)
        b = run(senza, soil, metodo_et="singolo", irr_cap=60.0)
        for k in N_SERIES:
            assert np.allclose(getattr(a, k), getattr(b, k), atol=1e-12, rtol=0), k

    def test_kc_max_e_fc_di_default(self, soil, pars):
        """Senza kc_max e fc il doppio usa eq. 72 (senza termine climatico) ed eq. 76 con h = 0."""
        inp = maize_inputs(soil, pars)
        kcmx = np.maximum(soil.kc_max, inp.kcb + 0.05)
        fc = w.cover_fraction_eq76(inp.kcb, kcmx, soil.kc_min, 0.0)
        esplicito = dataclasses.replace(inp, kc_max=kcmx, fc=fc)
        implicito = dataclasses.replace(inp, kc_max=None, fc=None)
        a = run(esplicito, soil, irr_cap=60.0)
        b = run(implicito, soil, irr_cap=60.0)
        for k in N_SERIES:
            assert np.allclose(getattr(a, k), getattr(b, k), atol=1e-12, rtol=0), k


# =============================================================================
# 11. Prestazioni
# =============================================================================

def test_un_milione_di_passi_in_meno_di_3_secondi(soil, pars):
    n_blk, m = 1000, 1000
    base = three_year_inputs(soil, pars)
    reps = -(-n_blk * m // len(base.et0))
    tile = lambda x: np.tile(x, reps)[:n_blk * m]                       # noqa: E731
    seg = np.arange(n_blk * m) // m
    inp = w.DailyInputs(et0=tile(base.et0), rain=tile(base.rain), kc=tile(base.kc), zr=tile(base.zr),
                        p_tab=tile(base.p_tab), surface=tile(base.surface), irrigable=tile(base.irrigable),
                        segment=seg, cn_class=tile(base.cn_class), kcb=tile(base.kcb),
                        kc_max=tile(base.kc_max), fc=tile(base.fc))
    st = w.initial_water_state(soil, 0.5)
    w.run_water_balance(slice_inputs(inp, 0, 3000), soil, st, irr_cap=100.0, metodo_et="doppio")   # riscaldamento
    t0 = time.perf_counter()
    res = w.run_water_balance(inp, soil, st, irr_cap=100.0, metodo_et="doppio")
    dt = time.perf_counter() - t0
    print(f"\n1e6 passi (doppio): {dt:.3f} s")
    assert len(res.eta) == 1_000_000
    assert dt < 3.0, f"{dt:.2f} s"
