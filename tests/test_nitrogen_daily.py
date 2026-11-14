"""Test del nucleo giornaliero dell'azoto `nitrogen.run_daily`.

Serie sintetiche (nessun meteo): segmenti di coltura, suolo nudo e cover con percolazione e
quote di assorbimento scelte dal test. I valori attesi dipendenti dai parametri sono ricavati
da `fieldwise.params` / `NitrogenParams`.
"""
from __future__ import annotations

import dataclasses
import math

import numpy as np
import pytest

from fieldwise import nitrogen as nt
from fieldwise import params as fparams

TOL_N = 1e-6
EPS = 1e-9
CROPS = ("mais", "soia", "frumento")


@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def npar(pars):
    return nt.nitrogen_params(pars)


@pytest.fixture(scope="module")
def yields(pars):
    return {c: float(fparams.get(pars, f"crops.{c}.resa_potenziale")) for c in CROPS}


def state_with(npar, n_min, **kw):
    return dataclasses.replace(nt.initial_state(npar), n_min=float(n_min), **kw)


def build(spec, yields, dp=None, share=None, seed=0):
    """spec: lista (kind, crop, ndays). Restituisce gli argomenti di run_daily
    (segment, kinds, crops, rese, dp, share). dp casuale (giorni asciutti e piogge) se None;
    share uniforme su ogni segmento se None."""
    kinds = [s[0] for s in spec]
    crops = [s[1] for s in spec]
    nd = [s[2] for s in spec]
    rese = [yields[c] if k == nt.SEG_CROP else 0.0 for k, c in zip(kinds, crops)]
    segment = np.repeat(np.arange(len(spec)), nd)
    n = segment.size
    if dp is None:
        rng = np.random.default_rng(seed)
        dp = np.where(rng.random(n) < 0.25, rng.exponential(12.0, n), 0.0)
    if share is None:
        share = np.concatenate([np.full(d, 1.0 / d) for d in nd])
    return segment, kinds, crops, rese, np.asarray(dp, float), np.asarray(share, float)


CICLO = [(nt.SEG_BARE, None, 60), (nt.SEG_CROP, "mais", 140), (nt.SEG_BARE, None, 40),
         (nt.SEG_COVER, None, 150), (nt.SEG_BARE, None, 30), (nt.SEG_CROP, "soia", 120),
         (nt.SEG_BARE, None, 45), (nt.SEG_CROP, "frumento", 250), (nt.SEG_BARE, None, 60)]


def total_closure(state0, state1, bils, npar):
    nph = npar.n_per_t_humus
    stock = lambda s: s.n_min + s.n_res + s.n_cov + s.h * nph   # noqa: E731
    entrate = sum(b["entrate"] for b in bils)
    uscite = sum(b["uscite"] for b in bils)
    return (stock(state1) - stock(state0)) - (entrate - uscite)


# =============================================================================
# 1) Chiusura
# =============================================================================

@pytest.mark.parametrize("n0", [0.0, 20.0, 150.0, 500.0])
@pytest.mark.parametrize("asportati", [False, True])
@pytest.mark.parametrize("seed", [0, 1])
def test_chiusura_serie_con_piu_segmenti(npar, yields, n0, asportati, seed):
    args = build(CICLO, yields, seed=seed)
    s0 = state_with(npar, n0)
    s1, bils, res = nt.run_daily(s0, *args, npar, residui_asportati=asportati)
    assert np.abs(res.residuo).max() < TOL_N
    assert abs(total_closure(s0, s1, bils, npar)) < TOL_N
    assert max(abs(nt.n_balance_residual(b)) for b in bils) < TOL_N


def test_chiusura_tre_anni_concatenati(npar, yields):
    spec = CICLO * 3
    segment, kinds, crops, rese, dp, share = build(spec, yields, seed=7)
    # rese diverse da un anno all'altro
    rese = [r * f for r, f in zip(rese, np.tile(np.linspace(0.6, 1.0, len(CICLO)), 3))]
    s0 = nt.initial_state(npar)
    s1, bils, res = nt.run_daily(s0, segment, kinds, crops, rese, dp, share, npar)
    assert res.residuo.shape == dp.shape
    assert np.abs(res.residuo).max() < TOL_N
    assert abs(total_closure(s0, s1, bils, npar)) < TOL_N
    # stock finali non negativi
    for f in ("n_min", "n_res", "n_cov", "h"):
        assert getattr(s1, f) >= -EPS


# =============================================================================
# 2) Nessuno stock negativo, lisciviazione >= 0 e nulla senza percolazione
# =============================================================================

@pytest.mark.parametrize("n0", [0.0, 3.0, 100.0, 600.0])
def test_stock_non_negativi_ogni_giorno(npar, yields, n0):
    segment, kinds, crops, rese, dp, share = build(CICLO, yields, seed=3)
    s0 = state_with(npar, n0)
    _, _, res = nt.run_daily(s0, segment, kinds, crops, rese, dp, share, npar)
    assert res.n_min.min() >= -EPS
    # stock a ogni 20 giorni: serie troncata (il nucleo chiude l'ultimo segmento a fine serie)
    for m in range(20, segment.size + 1, 20):
        sub = np.unique(segment[:m]).size
        s, _, r = nt.run_daily(s0, segment[:m], kinds[:sub], crops[:sub], rese[:sub], dp[:m],
                               share[:m], npar)
        for f in ("n_min", "n_res", "n_cov", "h"):
            assert getattr(s, f) >= -EPS, (m, f, getattr(s, f))
        assert r.n_min.min() >= -EPS


def test_lisciviazione_non_negativa_e_nulla_senza_percolazione(npar, yields):
    for seed in range(4):
        segment, kinds, crops, rese, dp, share = build(CICLO, yields, seed=seed)
        assert (dp == 0).sum() > 0 and (dp > 0).sum() > 0
        _, _, res = nt.run_daily(nt.initial_state(npar), segment, kinds, crops, rese, dp,
                                 share, npar)
        assert res.l.min() >= 0.0
        assert np.all(res.l[dp == 0] == 0.0)
        assert np.all(res.l[dp > 0] >= 0.0)
        assert res.l[dp > 0].sum() > 0
    # nessuna percolazione in assoluto: nessuna lisciviazione
    segment, kinds, crops, rese, dp, share = build(CICLO, yields, dp=np.zeros(sum(s[2] for s in CICLO)))
    s, bils, res = nt.run_daily(nt.initial_state(npar), segment, kinds, crops, rese, dp, share, npar)
    assert res.l.sum() == 0.0
    assert all(b["l"] == 0.0 for b in bils)


# =============================================================================
# 3) La lisciviazione cresce con la percolazione
# =============================================================================

@pytest.mark.parametrize("spec", [[(nt.SEG_BARE, None, 120)],
                                  [(nt.SEG_CROP, "mais", 140)],
                                  [(nt.SEG_COVER, None, 150)],
                                  CICLO], ids=["nudo", "mais", "cover", "ciclo"])
def test_lisciviazione_cresce_con_la_percolazione(npar, yields, spec):
    base = build(spec, yields, seed=5)
    dp0 = base[4]
    tot = []
    for f in (0.0, 0.5, 1.0, 2.0, 4.0):
        s, bils, res = nt.run_daily(state_with(npar, 80.0), *base[:4], dp0 * f, base[5], npar)
        tot.append(res.l.sum())
        assert res.l.sum() == pytest.approx(sum(b["l"] for b in bils), abs=1e-9)
    assert tot[0] == 0.0
    assert all(b > a for a, b in zip(tot, tot[1:])), tot


def test_lisciviazione_giornaliera_cresce_con_dp_stesso_giorno(npar, yields):
    """Un solo giorno di pioggia in posizione fissa: l cresce con la sua intensita'."""
    spec = [(nt.SEG_BARE, None, 30)]
    segment, kinds, crops, rese, _, share = build(spec, yields)
    out = []
    for d in (0.0, 5.0, 20.0, 80.0, 300.0):
        dp = np.zeros(30)
        dp[10] = d
        _, _, res = nt.run_daily(state_with(npar, 100.0), segment, kinds, crops, rese, dp,
                                 share, npar)
        out.append(res.l[10])
    assert out[0] == 0.0
    assert all(b > a for a, b in zip(out, out[1:])), out
    # non oltre l'azoto minerale presente
    assert out[-1] <= 100.0 + 5.0


# =============================================================================
# 4) Assorbimento tardivo con percolazione precoce -> piu' lisciviazione
# =============================================================================

def test_assorbimento_tardivo_lisciva_piu_di_quello_uniforme(npar, yields):
    nd = 140
    spec = [(nt.SEG_CROP, "mais", nd)]
    segment, kinds, crops, rese, _, uniforme = build(spec, yields)
    dp = np.zeros(nd)
    dp[:30] = 12.0                                    # percolazione concentrata all'inizio
    w = np.linspace(0.0, 1.0, nd) ** 4 + 1e-3        # pesi spostati verso la fine
    tardivo = w / w.sum()
    assert tardivo.sum() == pytest.approx(1.0) and uniforme.sum() == pytest.approx(1.0)
    assert tardivo[:30].sum() < uniforme[:30].sum()
    for n0 in (60.0, 120.0):
        s0 = state_with(npar, n0)
        _, bu, ru = nt.run_daily(s0, segment, kinds, crops, rese, dp, uniforme, npar)
        _, bt, rt_ = nt.run_daily(s0, segment, kinds, crops, rese, dp, tardivo, npar)
        # stessa domanda totale della coltura
        assert bu[0]["u"] == pytest.approx(bt[0]["u"])
        assert rt_.l.sum() > ru.l.sum(), (n0, rt_.l.sum(), ru.l.sum())
        assert np.abs(rt_.residuo).max() < TOL_N and np.abs(ru.residuo).max() < TOL_N


def test_assorbimento_precoce_lisciva_meno_di_quello_tardivo(npar, yields):
    """Stessa percolazione precoce: l'ordine uniforme < tardivo e precoce <= uniforme."""
    nd = 140
    segment, kinds, crops, rese, _, uniforme = build([(nt.SEG_CROP, "mais", nd)], yields)
    dp = np.zeros(nd)
    dp[:30] = 12.0
    t = np.arange(nd)
    for w, nome in ((np.exp(-t / 20.0), "precoce"), (np.exp(t / 20.0), "tardivo")):
        w = w / w.sum()
        _, _, r = nt.run_daily(state_with(npar, 100.0), segment, kinds, crops, rese, dp, w, npar)
        if nome == "precoce":
            l_pre = r.l.sum()
        else:
            l_tar = r.l.sum()
    _, _, r = nt.run_daily(state_with(npar, 100.0), segment, kinds, crops, rese, dp, uniforme, npar)
    assert l_pre <= r.l.sum() + EPS <= l_tar + 2 * EPS


# =============================================================================
# 5) Soia: nessun concime
# =============================================================================

@pytest.mark.parametrize("n0", [0.0, 5.0, 40.0, 150.0, 600.0])
@pytest.mark.parametrize("dpf", [0.0, 1.0, 5.0])
@pytest.mark.parametrize("tardivo", [False, True])
def test_soia_concime_nullo(npar, yields, n0, dpf, tardivo):
    nd = 120
    segment, kinds, crops, rese, dp, share = build([(nt.SEG_CROP, "soia", nd)], yields, seed=2)
    if tardivo:
        w = np.linspace(0, 1, nd) ** 3 + 1e-3
        share = w / w.sum()
    s0 = state_with(npar, n0)
    s1, bils, res = nt.run_daily(s0, segment, kinds, crops, rese, dp * dpf, share, npar)
    assert bils[0]["fert"] == 0.0
    assert bils[0]["perd_f"] == 0.0
    assert bils[0]["fert_efficiente"] == 0.0
    assert bils[0]["fix"] >= 0.0 and bils[0]["fix"] <= npar.fix_quota * bils[0]["u"] + EPS
    assert np.abs(res.residuo).max() < TOL_N


def test_soia_in_serie_senza_concime_mais_si(npar, yields):
    args = build(CICLO, yields, seed=4)
    _, bils, _ = nt.run_daily(state_with(npar, 1.0), *args, npar)
    for b in bils:
        if b["crop"] == "soia":
            assert b["fert"] == 0.0
        if b["crop"] in ("mais", "frumento"):
            assert b["fert"] > 0.0
        if b["kind"] != nt.SEG_CROP:
            assert b["fert"] == 0.0


# =============================================================================
# 6) Coerenza con l'involucro update_segment
# =============================================================================

@pytest.mark.parametrize("kind,crop,nd", [(nt.SEG_CROP, "mais", 140), (nt.SEG_CROP, "soia", 120),
                                          (nt.SEG_CROP, "frumento", 250), (nt.SEG_BARE, None, 90),
                                          (nt.SEG_COVER, None, 150)])
@pytest.mark.parametrize("dp_tot", [0.0, 100.0, 300.0])
@pytest.mark.parametrize("asportati", [False, True])
def test_coerenza_con_update_segment(npar, yields, kind, crop, nd, dp_tot, asportati):
    resa = yields[crop] if crop else 0.0
    s0 = state_with(npar, 40.0, n_res=15.0)
    s_a, b_a = nt.update_segment(s0, kind, crop, {"days": nd, "dp": dp_tot}, resa, npar,
                                 residui_asportati=asportati)
    s_b, bils, _ = nt.run_daily(s0, np.zeros(nd, np.int64), [kind], [crop], [resa],
                                np.full(nd, dp_tot / nd), np.full(nd, 1.0 / nd), npar,
                                residui_asportati=asportati)
    b_b = bils[0]
    for f in ("n_min", "n_res", "n_cov", "h", "cred"):
        assert getattr(s_a, f) == pytest.approx(getattr(s_b, f), abs=1e-9)
    assert set(b_a) == set(b_b)
    for k, v in b_a.items():
        if isinstance(v, float) and not math.isnan(v):
            assert v == pytest.approx(b_b[k], abs=1e-9), k
        elif not isinstance(v, float):
            assert v == b_b[k], k
    assert abs(nt.n_balance_residual(b_a)) < TOL_N


# =============================================================================
# 7) Il rilascio dell'azoto dei residui non avviene in un giorno
# =============================================================================

def test_rilascio_residui_graduale(npar, yields):
    rel = npar.rel_days
    assert rel > 1
    crop_args = build([(nt.SEG_CROP, "mais", 140)], yields)
    s0 = state_with(npar, 60.0)
    s_h, _, _ = nt.run_daily(s0, *crop_args, npar)
    n_res = s_h.n_res
    assert n_res > 5.0, "residui trascurabili: il test sarebbe vuoto"

    nb = rel + 40
    spec = [(nt.SEG_CROP, "mais", 140), (nt.SEG_BARE, None, nb)]
    segment, kinds, crops, rese, _, share = build(spec, yields)
    dp = np.zeros(segment.size)                      # niente lisciviazione ne' uptake
    s_f, bils, res = nt.run_daily(s0, segment, kinds, crops, rese, dp, share, npar)
    bare = bils[1]
    base_day = (bare["min"] - bare["disp"] + bare["dep"]) / nb      # apporto medio giornaliero
    inc = np.diff(res.n_min)[140:]                                   # variazioni nei giorni nudi
    rel_day = n_res / rel
    # nessun salto pari all'azoto dei residui: l'incremento massimo e' ~ rilascio/giorno + base
    assert inc.max() < base_day * 1.05 + rel_day * 1.05 + 1e-9
    assert inc.max() < 0.5 * n_res
    # il rilascio totale nei giorni nudi e' il residuo, distribuito sul periodo previsto
    assert bare["rilascio_res"] == pytest.approx(n_res, abs=1e-6)
    assert s_f.n_res == pytest.approx(0.0, abs=1e-6)
    # con meno giorni del rilascio, l'azoto resta nei residui
    sp = build([(nt.SEG_CROP, "mais", 140), (nt.SEG_BARE, None, rel // 2)], yields)
    s_p, _, _ = nt.run_daily(s0, sp[0], sp[1], sp[2], sp[3], np.zeros(sp[0].size), sp[5], npar)
    assert 0.0 < s_p.n_res < n_res
    assert s_p.n_res == pytest.approx(n_res * (1 - (rel // 2) / rel), abs=1e-6)


# =============================================================================
# 8) Temperatura: fattore Q10 normalizzato (nitrogen.suolo.temperatura.q10)
# =============================================================================

def _sinusoide(n, t_media=13.0, ampiezza=10.0):
    """Temperatura sintetica: giorno 0 = meta' gennaio (minimo), massimo a meta' luglio."""
    d = np.arange(n)
    return t_media - ampiezza * np.cos(2 * np.pi * d / 365.0)


def test_fattore_temperatura_media_uno_e_monotono(npar):
    t = _sinusoide(3 * 365)
    f = nt.temperature_factor(t, 2.0)
    assert f.mean() == pytest.approx(1.0, abs=1e-12)
    assert f[0] < 1.0 < f[182]                         # gennaio sotto, luglio sopra la media
    assert np.all(np.diff(f[:182]) > 0)                # cresce con la temperatura
    assert np.array_equal(nt.temperature_factor(t, 1.0), np.ones_like(t))
    t_nan = t.copy()
    t_nan[5] = np.nan
    assert nt.temperature_factor(t_nan, 2.0)[5] == 1.0


def test_f_temp_unitario_identico_a_senza_temperatura(npar, yields):
    args = build(CICLO, yields, seed=3)
    s0 = state_with(npar, 40.0, n_res=20.0, cred=-15.0)
    s_a, b_a, r_a = nt.run_daily(s0, *args, npar)
    s_b, b_b, r_b = nt.run_daily(s0, *args, npar, f_temp=np.ones(args[0].size))
    assert s_a == s_b
    assert np.array_equal(r_a.l, r_b.l) and np.array_equal(r_a.n_min, r_b.n_min)
    with pytest.raises(ValueError):
        nt.run_daily(s0, *args, npar, f_temp=np.ones(args[0].size - 1))


@pytest.mark.parametrize("q10", [1.7, 2.0, 3.0])
@pytest.mark.parametrize("seed", [0, 1])
def test_chiusura_con_temperatura(npar, yields, q10, seed):
    args = build(CICLO * 3, yields, seed=seed)
    ft = nt.temperature_factor(_sinusoide(args[0].size), q10)
    s0 = nt.initial_state(npar)
    s1, bils, res = nt.run_daily(s0, *args, npar, f_temp=ft)
    assert abs(total_closure(s0, s1, bils, npar)) < TOL_N
    assert np.abs(res.residuo).max() < TOL_N
    assert all(abs(nt.n_balance_residual(b)) < TOL_N for b in bils)
    assert min(s1.n_min, s1.n_res, s1.n_cov, s1.h) >= -EPS


def test_rilascio_e_mineralizzazione_piu_lenti_in_inverno(npar, yields):
    """A parita' di residui, l'N minerale cresce meno nel mese freddo che in quello caldo;
    il rilascio totale resta l'N dei residui (massa conservata in giorni normalizzati)."""
    zero = {c: 0.0 for c in npar.cred_int}
    npar = dataclasses.replace(npar, cred_int=zero, cred_asp=zero)
    nd_crop, nb = 140, 3 * 365
    segment, kinds, crops, rese, _, share = build(
        [(nt.SEG_CROP, "mais", nd_crop), (nt.SEG_BARE, None, nb)], yields)
    n = segment.size
    # giorno di raccolta = meta' gennaio: il primo mese nudo e' il piu' freddo
    t = _sinusoide(n + 365)[365 - nd_crop:365 - nd_crop + n]
    ft = nt.temperature_factor(t, 2.0)
    s0 = state_with(npar, 60.0)
    s1, bils, res = nt.run_daily(s0, segment, kinds, crops, rese, np.zeros(n), share, npar,
                                 f_temp=ft)
    inc = np.diff(res.n_min)[nd_crop:]
    freddo, caldo = inc[:30].sum(), inc[167:197].sum()
    assert freddo < 0.6 * caldo
    s_h, _, _ = nt.run_daily(s0, segment[:nd_crop], kinds[:1], crops[:1], rese[:1],
                             np.zeros(nd_crop), share[:nd_crop], npar, f_temp=ft[:nd_crop])
    assert bils[1]["rilascio_res"] == pytest.approx(s_h.n_res, rel=1e-9)
    assert s1.n_res == pytest.approx(0.0, abs=1e-6)

