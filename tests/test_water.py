"""Test di ``fieldwise.water`` (bilancio idrico giornaliero FAO-56 a due strati).

Verificano la specifica: chiusura del bilancio, coefficiente di stress Ks, vincoli
fisici, continuita' dello stato, funzioni di supporto, parametri reali, prestazioni e
un confronto su dati reali del punto pilota (saltato se la cache manca).
Nessuna rete.
"""
import math
import time

import numpy as np
import pytest

from fieldwise import params as fparams
from fieldwise import water as w

TOL_MM = 0.01
EPS = 1e-9


# =============================================================================
# Costruzione degli ingressi
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def soil(pars):
    return w.soil_from_params(pars)


def _mk(et0, rain, kc, zr, p_tab, surface, irrigable, segment, cn):
    n = len(et0)

    def arr(x, dt):
        a = np.asarray(x, dtype=dt)
        return np.full(n, a) if a.ndim == 0 else a

    return w.DailyInputs(
        et0=arr(et0, float), rain=arr(rain, float), kc=arr(kc, float), zr=arr(zr, float),
        p_tab=arr(p_tab, float), surface=arr(surface, int), irrigable=arr(irrigable, int),
        segment=arr(segment, int), cn_class=arr(cn, int))


def synthetic_weather(n, seed_phase=0.0):
    """Meteo sintetico deterministico: ET0 stagionale, pioggia periodica con eventi intensi."""
    d = np.arange(n)
    et0 = 3.5 + 2.5 * np.sin(2 * np.pi * (d - 60) / 365.0 + seed_phase)
    et0 = np.clip(et0, 0.3, None)
    rain = np.zeros(n)
    rain[::9] = 6.0
    rain[4::23] = 18.0
    rain[11::61] = 55.0          # eventi intensi: ruscellamento e percolazione
    return et0, rain


def maize_inputs(soil, pars, n=150, irrigable=1, rain_scale=1.0):
    et0, rain = synthetic_weather(n)
    kc, zr, ptab = w.crop_daily_curves(pars, "mais", n, z_profile=soil.depth)
    return _mk(et0, rain * rain_scale, kc, zr, ptab, w.SURF_CROP, irrigable,
               0, w.cn_class("mais"))


def three_year_inputs(soil, pars):
    """Tre anni continui, cinque segmenti: mais, nudo, cover, nudo, mais (non irrigabile)."""
    blocks = [("mais", 150), ("bare", 120), ("cover", 200), ("bare", 100), ("mais", 150),
              ("bare", 375)]
    et0s, rains, kcs, zrs, pts, surf, irrb, seg, cns = ([] for _ in range(9))
    n_tot = sum(b[1] for b in blocks)
    et0_all, rain_all = synthetic_weather(n_tot)
    pos = 0
    for k, (kind, n) in enumerate(blocks):
        et0s.append(et0_all[pos:pos + n])
        rains.append(rain_all[pos:pos + n])
        pos += n
        if kind == "mais":
            kc, zr, pt = w.crop_daily_curves(pars, "mais", n, z_profile=soil.depth)
            s, ir, cn = w.SURF_CROP, 1 if k == 0 else 0, w.cn_class("mais")
        elif kind == "cover":
            kc, zr, pt = w.cover_daily_curves(pars, n, 0.2, z_profile=soil.depth)
            s, ir, cn = w.SURF_COVER, 0, w.cn_class("cover")
        else:
            kc, zr, pt = np.zeros(n), np.full(n, 0.1), np.full(n, 0.5)
            s, ir, cn = w.SURF_BARE, 0, w.cn_class("suolo_nudo")
        kcs.append(kc)
        zrs.append(zr)
        pts.append(pt)
        surf.append(np.full(n, s))
        irrb.append(np.full(n, ir))
        seg.append(np.full(n, k))
        cns.append(np.full(n, cn))
    cat = np.concatenate
    return _mk(cat(et0s), cat(rains), cat(kcs), cat(zrs), cat(pts), cat(surf), cat(irrb),
               cat(seg), cat(cns))


def random_inputs(n=20000, seed=20240607):
    rng = np.random.default_rng(seed)
    et0 = rng.uniform(0.0, 8.0, n)
    rain = np.where(rng.random(n) < 0.25, rng.exponential(12.0, n), 0.0)
    rain[rng.random(n) < 0.01] += 90.0
    return _mk(et0, rain, rng.uniform(0.1, 1.3, n), rng.uniform(0.1, 1.5, n),
               rng.uniform(0.3, 0.7, n), rng.integers(0, 3, n), rng.integers(0, 2, n),
               np.arange(n) // 50, rng.integers(0, 3, n))


def dry_rotation_inputs(soil, pars, seed=1):
    """Rotazione realistica a blocchi (mais asciutto, nudo, cover, nudo) con pioggia sporadica."""
    rng = np.random.default_rng(seed)
    blocks = [("mais", 150), ("bare", 200), ("cover", 150), ("bare", 150)]
    n = sum(b[1] for b in blocks)
    et0 = np.clip(3.5 + 2.5 * np.sin(2 * np.pi * (np.arange(n) - 60) / 365.0), 0.3, None)
    rain = np.where(rng.random(n) < 0.12, rng.exponential(8.0, n), 0.0)
    kc, zr, pt, sf, sg, cn = ([] for _ in range(6))
    for k, (kind, m) in enumerate(blocks):
        if kind == "mais":
            a, b, c = w.crop_daily_curves(pars, "mais", m, z_profile=soil.depth)
            s, c_ = w.SURF_CROP, w.cn_class("mais")
        elif kind == "cover":
            a, b, c = w.cover_daily_curves(pars, m, 0.2, z_profile=soil.depth)
            s, c_ = w.SURF_COVER, w.cn_class("cover")
        else:
            a, b, c = np.zeros(m), np.full(m, 0.1), np.full(m, 0.5)
            s, c_ = w.SURF_BARE, w.cn_class("suolo_nudo")
        kc.append(a); zr.append(b); pt.append(c)
        sf.append(np.full(m, s)); sg.append(np.full(m, k)); cn.append(np.full(m, c_))
    cat = np.concatenate
    return _mk(et0, rain, cat(kc), cat(zr), cat(pt), cat(sf), 0, cat(sg), cat(cn))


def _slice(inp, a, b):
    return w.DailyInputs(**{k: getattr(inp, k)[a:b] for k in
                            ("et0", "rain", "kc", "zr", "p_tab", "surface", "irrigable",
                             "segment", "cn_class")})


# =============================================================================
# 1. Chiusura del bilancio
# =============================================================================

class TestChiusura:
    def _check(self, res):
        assert abs(w.water_balance_residual(res)) <= TOL_MM
        assert np.max(np.abs(w.water_balance_daily_residual(res))) <= TOL_MM

    def test_stagione_mais(self, soil, pars):
        inp = maize_inputs(soil, pars)
        for cap in (math.inf, 0.0, 80.0):
            res = w.run_water_balance(inp, soil, w.initial_water_state(soil), irr_cap=cap)
            self._check(res)
        # la stagione sintetica attiva davvero ruscellamento, percolazione e irrigazione
        res = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.5))
        assert res.runoff.sum() > 0 and res.dp.sum() > 0 and res.irr.sum() > 0

    def test_tre_anni_piu_segmenti(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        assert len(inp.et0) == 1095
        for amc in (False, True):
            res = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.6),
                                      irr_cap=np.full(6, 120.0), use_amc=amc)
            self._check(res)

    def test_serie_casuale_lunga(self, soil):
        inp = random_inputs()
        caps = np.where(np.arange(400) % 3 == 0, 0.0, np.where(np.arange(400) % 3 == 1, 60.0, np.inf))
        for amc in (False, True):
            res = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3),
                                      irr_cap=caps, use_amc=amc)
            self._check(res)

    def test_aggregate_segments_coerente(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        res = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.6), irr_cap=100.0)
        agg = w.aggregate_segments(res)
        assert set(agg) >= {"days", "rain", "eta", "etc", "irr", "runoff", "dp", "storage_end"}
        assert agg["days"].sum() == len(inp.et0)
        assert agg["rain"].sum() == pytest.approx(inp.rain.sum())
        assert agg["eta"].sum() == pytest.approx(res.eta.sum())
        assert agg["dp"].sum() == pytest.approx(res.dp.sum())
        # storage_end = acqua nel profilo all'ultimo giorno di ogni segmento
        ends = np.nonzero(np.diff(inp.segment, append=-1))[0]
        assert np.allclose(agg["storage_end"], res.storage[ends])


# =============================================================================
# 2. Coefficiente di stress Ks
# =============================================================================

def _one_day(soil, x, *, zr=1.0, p_tab=0.55, kc=1.0, et0=5.0):
    """Un giorno senza pioggia con deficit di zona radicale pari a x * TAW (uniforme per strato)."""
    st = w.WaterState(soil.fc1_mm - x * soil.taw1, soil.fc2_mm - x * soil.taw2, 0.0)
    inp = _mk([et0], [0.0], [kc], [zr], [p_tab], [w.SURF_CROP], [0], [0], [w.CN_ROW_CROPS])
    return w.run_water_balance(inp, soil, st, irr_cap=0.0)


class TestStress:
    def test_ks_uno_sotto_raw(self, soil):
        for x in (0.0, 0.1, 0.3, 0.5):
            r = _one_day(soil, x)
            assert r.dr[0] <= r.raw[0] + EPS
            assert r.ks[0] == pytest.approx(1.0, abs=1e-9)

    def test_ks_uno_a_raw(self, soil):
        r = _one_day(soil, 0.55)           # p = 0.55 con ETc = 5 mm/g
        assert r.raw[0] == pytest.approx(0.55 * r.taw[0])
        assert r.dr[0] == pytest.approx(r.raw[0], abs=1e-9)
        assert r.ks[0] == pytest.approx(1.0, abs=1e-9)

    def test_ks_zero_al_punto_di_appassimento(self, soil):
        r = _one_day(soil, 1.0)
        assert r.dr[0] == pytest.approx(r.taw[0])
        assert r.ks[0] == 0.0
        assert r.eta[0] == pytest.approx(0.0, abs=EPS)

    def test_ks_intermedio_decrescente(self, soil):
        xs = np.linspace(0.6, 0.98, 12)
        res = [_one_day(soil, x) for x in xs]
        ks = np.array([r.ks[0] for r in res])
        dr = np.array([r.dr[0] for r in res])
        assert np.all(np.diff(dr) > 0)
        assert np.all((ks > 0) & (ks < 1))
        assert np.all(np.diff(ks) < 0)
        # FAO-56 eq. 84: Ks = (TAW - Dr) / ((1 - p) TAW)
        for r in res:
            assert r.ks[0] == pytest.approx((r.taw[0] - r.dr[0]) / ((1 - 0.55) * r.taw[0]))

    def test_taw_zona_radicale(self, soil):
        r = _one_day(soil, 0.0, zr=1.0)
        assert r.taw[0] == pytest.approx(soil.taw1 + (1.0 - soil.z1) / soil.z2 * soil.taw2)
        r = _one_day(soil, 0.0, zr=0.2)
        assert r.taw[0] == pytest.approx(0.2 / soil.z1 * soil.taw1)


# =============================================================================
# 3. Fisica
# =============================================================================

def scenario(name, soil, pars):
    if name == "mais":
        return maize_inputs(soil, pars), w.initial_water_state(soil, 0.4)
    if name == "tre_anni":
        return three_year_inputs(soil, pars), w.initial_water_state(soil, 0.7)
    if name == "casuale":
        return random_inputs(5000), w.initial_water_state(soil, 0.2)
    if name == "rotazione_secca":
        return dry_rotation_inputs(soil, pars), w.initial_water_state(soil, 0.5)
    raise KeyError(name)


class TestFisica:
    @pytest.fixture(scope="class", params=["mais", "tre_anni", "casuale"])
    def run(self, request, soil, pars):
        inp, st = scenario(request.param, soil, pars)
        return inp, w.run_water_balance(inp, soil, st, irr_cap=90.0, use_amc=True)

    def test_eta_non_supera_etc(self, run):
        _, r = run
        assert np.all(r.eta <= r.etc + EPS)
        assert np.all(r.eta >= -EPS)

    def test_strati_nei_limiti(self, run, soil):
        _, r = run
        assert r.w1.max() <= soil.fc1_mm + EPS
        assert r.w2.max() <= soil.fc2_mm + EPS
        assert r.w2.min() >= soil.wp2_mm - EPS

    @pytest.mark.parametrize("name", ["mais", "tre_anni", "casuale", "rotazione_secca"])
    def test_strato1_non_sotto_appassimento(self, name, soil, pars):
        inp, st = scenario(name, soil, pars)
        r = w.run_water_balance(inp, soil, st, irr_cap=90.0, use_amc=True)
        # Negli scenari con suolo nudo ('casuale', 'rotazione_secca') l'evaporazione puo'
        # portare i primi Ze m fino a 0,5 theta_WP (FAO-56 cap. 7, eq. 73:
        # TEW = 1000 (theta_FC - 0,5 theta_WP) Ze), mentre il resto dello strato 1 resta
        # >= theta_WP (eq. 82). Il limite fisico e' quindi
        # W1_min = 1000 (theta_WP z1 - 0,5 theta_WP Ze) = wp1_mm - 500 theta_WP Ze,
        # non wp1_mm. Gli scenari solo colturali restano sopra wp1_mm.
        lim = soil.w1_min_mm if name in ("casuale", "rotazione_secca") else soil.wp1_mm
        assert r.w1.min() >= lim - EPS, (
            f"w1 scende {lim - r.w1.min():.2f} mm sotto il limite inferiore dello strato 1")

    def test_flussi_non_negativi(self, run):
        _, r = run
        assert r.runoff.min() >= 0 and r.dp.min() >= 0 and r.irr.min() >= 0
        assert np.all((r.ks >= 0) & (r.ks <= 1))

    def test_irrigazione_nulla_con_tetto_zero(self, run, soil):
        inp, _ = run
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=0.0)
        assert np.all(r.irr == 0.0)

    def test_tetto_per_segmento(self, run, soil):
        inp, _ = run
        nseg = int(inp.segment.max()) + 1
        caps = np.linspace(10.0, 70.0, nseg)
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=caps)
        per_seg = np.bincount(inp.segment, weights=r.irr, minlength=nseg)
        assert np.all(per_seg <= caps + EPS)
        assert np.all(w.aggregate_segments(r)["irr"] <= caps + EPS)

    def test_coltura_non_irrigabile(self, soil, pars):
        inp = maize_inputs(soil, pars, irrigable=0)
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=math.inf)
        assert np.all(r.irr == 0.0)

    def test_cover_e_nudo_mai_irrigati(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        inp.irrigable[:] = 1
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=math.inf)
        assert np.all(r.irr[inp.surface != w.SURF_CROP] == 0.0)

    def test_irrigazione_libera_ks_uno_resa_uno(self, soil, pars):
        inp = maize_inputs(soil, pars, irrigable=1, rain_scale=0.0)    # stagione secca
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=math.inf)
        assert r.irr.sum() > 100
        assert r.ks.min() >= 1.0 - 1e-6
        ky = fparams.get(pars, "crops.mais.ky")
        assert w.relative_yield_fao33(r.eta.sum(), r.etc.sum(), ky) == pytest.approx(1.0, abs=1e-6)

    def test_senza_irrigazione_in_siccita_c_e_stress(self, soil, pars):
        inp = maize_inputs(soil, pars, irrigable=1, rain_scale=0.0)
        r = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.3), irr_cap=0.0)
        ky = fparams.get(pars, "crops.mais.ky")
        assert r.ks.min() < 0.5
        assert w.relative_yield_fao33(r.eta.sum(), r.etc.sum(), ky) < 0.9


# =============================================================================
# 4. Continuita' dello stato
# =============================================================================

class TestContinuita:
    FIELDS = ("etc", "eta", "ks", "kr", "irr", "runoff", "dp", "w1", "w2", "de", "taw",
              "raw", "dr", "theta_e")

    @pytest.mark.parametrize("cap", [math.inf, 0.0])
    @pytest.mark.parametrize("cut", [1, 57, 300, 730])
    def test_spezzata_uguale_unica(self, soil, pars, cap, cut):
        inp = three_year_inputs(soil, pars)
        st0 = w.initial_water_state(soil, 0.5)
        full = w.run_water_balance(inp, soil, st0, irr_cap=cap)
        r1 = w.run_water_balance(_slice(inp, 0, cut), soil, st0, irr_cap=cap)
        r2 = w.run_water_balance(_slice(inp, cut, None), soil, r1.state_end, irr_cap=cap)
        for f in self.FIELDS:
            joined = np.concatenate([getattr(r1, f), getattr(r2, f)])
            np.testing.assert_allclose(joined, getattr(full, f), rtol=0, atol=1e-9, err_msg=f)
        assert r2.state0.storage == pytest.approx(r1.state_end.storage)
        assert r2.state_end.storage == pytest.approx(full.state_end.storage, abs=1e-9)
        assert r2.state_end.de == pytest.approx(full.state_end.de, abs=1e-9)

    def test_stato_iniziale_non_modificato(self, soil, pars):
        st0 = w.initial_water_state(soil, 0.5)
        keep = st0.copy()
        res = w.run_water_balance(maize_inputs(soil, pars), soil, st0)
        assert (st0.w1, st0.w2, st0.de) == (keep.w1, keep.w2, keep.de)
        assert res.state0 is not st0

    def test_stato_non_si_azzera_tra_segmenti(self, soil, pars):
        inp = three_year_inputs(soil, pars)
        res = w.run_water_balance(inp, soil, w.initial_water_state(soil, 0.5), irr_cap=0.0)
        # a ogni cambio di segmento lo stoccaggio riparte dall'ultimo valore del segmento precedente
        change = np.nonzero(np.diff(inp.segment))[0]
        assert len(change) >= 4
        for i in change:
            jump = res.storage[i + 1] - res.storage[i]
            assert abs(jump) <= inp.rain[i + 1] + inp.et0[i + 1] * 1.3 + EPS
            assert res.storage[i + 1] >= w.initial_water_state(soil, 0.0).storage - EPS

    def test_waterstate_copy(self, soil):
        s = w.initial_water_state(soil, 0.5)
        c = s.copy()
        c.w1 += 10.0
        assert s.w1 != c.w1
        assert s.storage == pytest.approx(s.w1 + s.w2)


# =============================================================================
# 5. Funzioni di supporto
# =============================================================================

class TestSupporto:
    F = (0.1, 0.35, 0.8)            # f_ini, f_dev, f_mid

    def kc(self, x):
        return w.kc_curve(x, 0.3, 1.2, 0.6, *self.F)

    def test_kc_curve_fasi(self):
        assert self.kc(0.0) == pytest.approx(0.3)
        assert self.kc(0.05) == pytest.approx(0.3)
        assert self.kc(0.1) == pytest.approx(0.3)
        assert self.kc(0.35) == pytest.approx(1.2)
        assert self.kc(0.6) == pytest.approx(1.2)
        assert self.kc(0.8) == pytest.approx(1.2)
        assert self.kc(1.0) == pytest.approx(0.6)

    def test_kc_curve_lineare_nei_tratti(self):
        # sviluppo: da 0.3 a 1.2 su [0.1, 0.35]
        for x in (0.15, 0.2, 0.25, 0.3):
            assert self.kc(x) == pytest.approx(0.3 + (x - 0.1) / 0.25 * 0.9)
        # fase finale: da 1.2 a 0.6 su [0.8, 1.0]
        for x in (0.85, 0.9, 0.95):
            assert self.kc(x) == pytest.approx(1.2 + (x - 0.8) / 0.2 * (0.6 - 1.2))
        v = self.kc(np.linspace(0.1, 0.35, 11))
        assert np.allclose(np.diff(v, 2), 0.0, atol=1e-12)

    def test_kc_curve_array_e_limiti(self):
        out = self.kc(np.array([-1.0, 0.5, 2.0]))
        assert out.shape == (3,)
        assert out[0] == pytest.approx(0.3) and out[2] == pytest.approx(0.6)

    def test_stage_fractions(self):
        assert w.stage_fractions([30, 40, 50, 30]) == pytest.approx((0.2, 0.46666667, 0.8))

    def test_root_depth(self):
        x = np.linspace(0.0, 1.0, 101)
        z = w.root_depth(x, 0.3, 1.7, 0.4)
        assert z[0] == pytest.approx(0.3)
        assert np.all(np.diff(z) >= -1e-12)
        assert z[x >= 0.4][0] == pytest.approx(1.7) and z[-1] == pytest.approx(1.7)
        assert w.root_depth(0.2, 0.3, 1.7, 0.4) == pytest.approx(1.0)
        zp = w.root_depth(x, 0.3, 1.7, 0.4, z_profile=1.5)
        assert zp.max() == pytest.approx(1.5) and np.all(zp <= 1.5 + 1e-12)

    def test_p_adjusted(self):
        assert w.p_adjusted(0.55, 5.0) == pytest.approx(0.55)
        assert w.p_adjusted(0.55, 7.0) == pytest.approx(0.47)
        assert w.p_adjusted(0.55, 3.0) == pytest.approx(0.63)
        assert w.p_adjusted(0.55, 100.0) == pytest.approx(0.1)
        assert w.p_adjusted(0.55, -100.0) == pytest.approx(0.8)
        v = w.p_adjusted(np.array([0.05, 0.5, 0.95]), np.array([5.0, 5.0, 5.0]))
        assert v.min() >= 0.1 and v.max() <= 0.8

    def test_kc_climate_correction(self):
        assert w.kc_climate_correction(1.2, 2.0, 45.0, 2.0) == pytest.approx(1.2)
        assert w.kc_climate_correction(0.5, 2.0, 45.0, 0.3) == pytest.approx(0.5)
        # vento forte e aria secca aumentano Kc, vento debole e aria umida lo riducono
        assert w.kc_climate_correction(1.2, 4.0, 30.0, 2.0) > 1.2
        assert w.kc_climate_correction(1.2, 1.0, 70.0, 2.0) < 1.2
        # eq. 62 a mano: [0.04 (4 - 2) - 0.004 (30 - 45)] (2/3)^0.3
        assert w.kc_climate_correction(1.2, 4.0, 30.0, 2.0) == pytest.approx(
            1.2 + (0.08 + 0.06) * (2.0 / 3.0) ** 0.3)

    def test_kc_end_climate_correction(self):
        assert w.kc_end_climate_correction(0.35, 4.0, 30.0, 2.0) == pytest.approx(0.35)
        assert w.kc_end_climate_correction(0.6, 2.0, 45.0, 2.0) == pytest.approx(0.6)
        assert w.kc_end_climate_correction(0.6, 4.0, 30.0, 2.0) > 0.6

    def test_rhmin_from_temperature(self):
        v = w.rhmin_from_temperature(30.0, 15.0)
        assert 0.0 < v < 100.0
        assert w.rhmin_from_temperature(20.0, 20.0) == pytest.approx(100.0)
        assert w.rhmin_from_temperature(35.0, 10.0) < w.rhmin_from_temperature(25.0, 10.0)

    def test_relative_yield_fao33(self):
        assert w.relative_yield_fao33(300.0, 300.0, 1.25) == pytest.approx(1.0)
        assert w.relative_yield_fao33(350.0, 300.0, 1.25) == pytest.approx(1.0)   # limite alto
        assert w.relative_yield_fao33(240.0, 300.0, 1.25) == pytest.approx(1 - 1.25 * 0.2)
        assert w.relative_yield_fao33(0.0, 300.0, 1.25) == 0.0                     # limite basso
        assert w.relative_yield_fao33(0.0, 300.0, 3.0) == 0.0
        assert w.relative_yield_fao33(10.0, 0.0, 1.25) == 1.0
        for e in np.linspace(0, 400, 21):
            assert 0.0 <= w.relative_yield_fao33(e, 300.0, 1.25) <= 1.0

    def test_tew_fao56_a_mano(self):
        # 1000 (0.30 - 0.5 * 0.12) * 0.10 = 24.0 mm
        assert w.tew_fao56(0.30, 0.12, 0.10) == pytest.approx(24.0)
        # 1000 (0.25 - 0.5 * 0.10) * 0.15 = 30.0 mm
        assert w.tew_fao56(0.25, 0.10, 0.15) == pytest.approx(30.0)

    def test_valueerror_lunghezze_e_nan(self):
        ok = dict(et0=np.ones(5), rain=np.zeros(5), kc=np.ones(5), zr=np.ones(5),
                  p_tab=np.full(5, 0.5), surface=np.zeros(5, int), irrigable=np.zeros(5, int),
                  segment=np.zeros(5, int), cn_class=np.zeros(5, int))
        w.DailyInputs(**ok)
        for k in ok:
            if k == "et0":
                continue
            bad = dict(ok)
            bad[k] = ok[k][:4]
            with pytest.raises(ValueError):
                w.DailyInputs(**bad)
        bad = dict(ok, et0=np.array([1, 1, np.nan, 1, 1.0]))
        with pytest.raises(ValueError):
            w.DailyInputs(**bad)
        bad = dict(ok, rain=np.array([0, 0, 0, np.nan, 0.0]))
        with pytest.raises(ValueError):
            w.DailyInputs(**bad)

    def test_crop_e_cover_daily_curves(self, pars, soil):
        kc, zr, pt = w.crop_daily_curves(pars, "mais", 150, z_profile=soil.depth)
        assert kc.shape == zr.shape == pt.shape == (150,)
        assert kc.max() == pytest.approx(fparams.get(pars, "crops.mais.kc.mid"))
        assert kc[-1] == pytest.approx(fparams.get(pars, "crops.mais.kc.end"))
        assert zr.max() <= soil.depth + EPS and np.all(np.diff(zr) >= -1e-12)
        kc2, zr2, pt2 = w.cover_daily_curves(pars, 100, 0.2, z_profile=soil.depth)
        assert np.all(kc2 == kc2[0]) and np.all(np.diff(zr2) >= -1e-12)
        assert zr2.max() <= soil.depth + EPS

    def test_water_state_e_iniziale(self, soil):
        full = w.initial_water_state(soil, 1.0)
        assert full.w1 == pytest.approx(soil.fc1_mm) and full.w2 == pytest.approx(soil.fc2_mm)
        assert full.de == pytest.approx(0.0, abs=1e-9)
        dry = w.initial_water_state(soil, 0.0)
        assert dry.w1 == pytest.approx(soil.wp1_mm) and dry.w2 == pytest.approx(soil.wp2_mm)
        assert 0.0 <= dry.de <= soil.tew
        assert full.storage == pytest.approx(full.w1 + full.w2)


# =============================================================================
# 6. Parametri reali
# =============================================================================

class TestParametriReali:
    def test_coerenza_soil_from_params(self):
        s = w.soil_from_params()
        assert 0 < s.wp1 < s.fc1 < s.sat1 < 1
        assert 0 < s.wp2 < s.fc2 < s.sat2 < 1
        assert 0 < s.wp1_mm < s.fc1_mm and 0 < s.wp2_mm < s.fc2_mm
        assert s.taw1 == pytest.approx(s.fc1_mm - s.wp1_mm)
        assert s.taw2 == pytest.approx(s.fc2_mm - s.wp2_mm)
        assert s.sat_mm > s.fc1_mm + s.fc2_mm
        assert s.depth == pytest.approx(s.z1 + s.z2) and s.depth > 0
        assert 0 < s.rew < s.tew
        assert s.tew == pytest.approx(w.tew_fao56(s.fc1, s.wp1, s.ze))
        assert s.ze < s.z1
        assert len(s.cn_ii) == len(s.cn_i) == len(s.cn_iii) == 3
        assert all(a < b < c for a, b, c in zip(s.cn_i, s.cn_ii, s.cn_iii))
        assert 0.0 <= s.frazione_iniziale <= 1.0

    def test_coincide_con_dizionario_esplicito(self, pars):
        assert w.soil_from_params(pars) == w.soil_from_params()


# =============================================================================
# 7. Prestazioni
# =============================================================================

@pytest.mark.slow
def test_un_milione_di_passi_sotto_2_secondi(soil, pars):
    if not w.HAVE_NUMBA:
        pytest.skip("numba non disponibile: il vincolo di prestazioni vale solo con numba")
    rng = np.random.default_rng(7)
    n = 1_000_000
    inp = _mk(rng.uniform(0, 7, n), np.where(rng.random(n) < 0.2, rng.exponential(10, n), 0.0),
              rng.uniform(0.2, 1.2, n), rng.uniform(0.3, 1.5, n), np.full(n, 0.55),
              rng.integers(0, 3, n), 1, np.arange(n) // 365, rng.integers(0, 3, n))
    st = w.initial_water_state(soil)
    w.run_water_balance(_slice(inp, 0, 400), soil, st, irr_cap=100.0)     # riscaldamento (compilazione)
    best = math.inf
    for _ in range(3):
        t0 = time.perf_counter()
        res = w.run_water_balance(inp, soil, st, irr_cap=100.0)
        best = min(best, time.perf_counter() - t0)
    print(f"\n[perf] 1e6 passi: {best:.3f} s (migliore di 3)")
    assert len(res.eta) == n
    assert best < 2.0


# =============================================================================
# 8. Dati reali del punto pilota
# =============================================================================

PILOT = (45.2, 10.0)


@pytest.fixture(scope="module")
def forcing():
    from fieldwise import weather
    from fieldwise.data import cache
    try:
        return weather.load_forcing(*PILOT)
    except cache.CacheMiss as e:
        pytest.skip(f"cache del punto pilota assente: {e}")


def _maize_season(forcing, year, soil, pars, irr_cap=0.0):
    f = forcing.set_index("date")
    fasi = fparams.get(pars, "crops.mais.fasi_giorni")
    n = int(sum(fasi))
    start = f"{year}-04-15"
    sel = f.loc[start:].iloc[:n]
    assert len(sel) == n
    kc, zr, pt = w.crop_daily_curves(pars, "mais", n, z_profile=soil.depth)
    inp = _mk(sel["et0"].to_numpy(), sel["rain"].to_numpy(), kc, zr, pt, w.SURF_CROP, 1, 0,
              w.cn_class("mais"))
    res = w.run_water_balance(inp, soil, w.initial_water_state(soil), irr_cap=irr_cap)
    ky = fparams.get(pars, "crops.mais.ky")
    return res, w.relative_yield_fao33(res.eta.sum(), res.etc.sum(), ky)


def test_dati_reali_mais_2022_vs_2014_asciutto(forcing, soil, pars):
    r22, y22 = _maize_season(forcing, 2022, soil, pars)
    r14, y14 = _maize_season(forcing, 2014, soil, pars)
    for r in (r22, r14):
        assert abs(w.water_balance_residual(r)) <= TOL_MM
        assert np.max(np.abs(w.water_balance_daily_residual(r))) <= TOL_MM
        assert np.all(r.irr == 0.0)
    print(f"\n[reale] resa FAO-33 mais asciutto: 2022={y22:.3f} 2014={y14:.3f}; "
          f"ETa/ETc 2022={r22.eta.sum() / r22.etc.sum():.3f} 2014={r14.eta.sum() / r14.etc.sum():.3f}")
    assert 0.0 <= y22 <= 1.0 and 0.0 <= y14 <= 1.0
    assert y22 < y14 - 0.05
