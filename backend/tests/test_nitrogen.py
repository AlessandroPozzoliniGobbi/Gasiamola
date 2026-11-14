"""Test di ``fieldwise.nitrogen`` (bilancio dell'azoto e dell'humus a fine segmento).

Verificano la specifica: chiusura dei bilanci di azoto e humus, soia (fissazione, nessun
concime, deficit), mais e frumento (concime, perdite, MAS), lisciviazione, cover crop,
humus, immutabilita' dello stato e prestazioni. I valori attesi si ricavano dai parametri
caricati (``fieldwise.params``), non da numeri fissi. Nessuna rete.
"""
import copy
import dataclasses
import math
import time

import numpy as np
import pytest

from fieldwise import humus as hm
from fieldwise import nitrogen as nt
from fieldwise import params as fparams

TOL_N = 1e-6      # kg N/ha
TOL_H = 1e-6      # t SO/ha
EPS = 1e-9
DP_GRID = (0.0, 100.0, 300.0)
CROPS = ("mais", "soia", "frumento")
DAYS = {nt.SEG_CROP: 140.0, nt.SEG_BARE: 90.0, nt.SEG_COVER: 150.0}


# =============================================================================
# Ingressi
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def npar(pars):
    return nt.nitrogen_params(pars)


@pytest.fixture(scope="module")
def yields(pars):
    """Rese potenziali dai parametri [t/ha]."""
    return {c: float(fparams.get(pars, f"crops.{c}.resa_potenziale")) for c in CROPS}


def water(kind, dp, days=None):
    return {"days": DAYS[kind] if days is None else days, "dp": float(dp)}


def state_with(npar, n_min, **kw):
    return dataclasses.replace(nt.initial_state(npar), n_min=float(n_min), **kw)


def initial_states(npar):
    return {"basso": state_with(npar, 2.0), "alto": state_with(npar, 250.0),
            "iniziale": nt.initial_state(npar)}


def assert_closure(s0, s1, bil):
    rn = nt.n_balance_residual(bil)
    rh = nt.humus_balance_residual(s0, s1, bil)
    assert abs(rn) < TOL_N, f"residuo azoto {rn}"
    assert abs(rh) < TOL_H, f"residuo humus {rh}"
    return abs(rn), abs(rh)


def assert_non_negative(state):
    for f in ("n_min", "n_res", "n_cov", "h"):
        assert getattr(state, f) >= -EPS, f"{f} negativo: {getattr(state, f)}"


def segment_specs(yields):
    """(etichetta, kind, crop, resa) dei segmenti di prova."""
    out = [(c, nt.SEG_CROP, c, yields[c]) for c in CROPS]
    out += [("nudo", nt.SEG_BARE, None, 0.0), ("cover", nt.SEG_COVER, None, 0.0)]
    return out


# =============================================================================
# 1) Chiusura dei bilanci
# =============================================================================

@pytest.mark.parametrize("asportati", [False, True])
@pytest.mark.parametrize("dp", DP_GRID)
@pytest.mark.parametrize("stato", ["basso", "alto", "iniziale"])
@pytest.mark.parametrize("etichetta", ["mais", "soia", "frumento", "nudo", "cover"])
def test_chiusura_segmento(npar, yields, etichetta, stato, dp, asportati):
    spec = {s[0]: s for s in segment_specs(yields)}[etichetta]
    _, kind, crop, resa = spec
    s0 = initial_states(npar)[stato]
    s1, bil = nt.update_segment(s0, kind, crop, water(kind, dp), resa, npar,
                                residui_asportati=asportati)
    assert_closure(s0, s1, bil)
    assert_non_negative(s1)


@pytest.mark.parametrize("dp", DP_GRID)
@pytest.mark.parametrize("stato", ["basso", "alto", "iniziale"])
@pytest.mark.parametrize("asportati", [False, True])
def test_chiusura_rotazione_tre_anni(npar, yields, stato, dp, asportati):
    """Mais, soia, frumento con suolo nudo e cover tra le colture: lo stato passa da un
    segmento al successivo e ogni passo chiude."""
    s_init = initial_states(npar)[stato]
    seq = []
    for crop, tra in (("mais", nt.SEG_BARE), ("soia", nt.SEG_COVER), ("frumento", nt.SEG_BARE)):
        seq.append((nt.SEG_CROP, crop, water(nt.SEG_CROP, dp), yields[crop], asportati))
        seq.append((tra, None, water(tra, dp), 0.0))
    s_fin, bils = nt.run_segments(s_init, seq, npar)
    assert len(bils) == len(seq)
    # lo stato passa davvero: ripetendo a mano segmento per segmento si ottiene lo stesso
    s = s_init
    for seg, b in zip(seq, bils):
        s_next, b_man = nt.update_segment(s, *seg[:4], npar, *seg[4:5])
        assert_closure(s, s_next, b_man)
        assert_non_negative(s_next)
        assert b_man["d_n_min"] == pytest.approx(b["d_n_min"], abs=1e-12)
        assert s_next.n_min == pytest.approx(s.n_min + b["d_n_min"], abs=1e-9)
        assert s_next.n_res == pytest.approx(s.n_res + b["d_n_res"], abs=1e-9)
        assert s_next.h == pytest.approx(s.h + b["d_h"], abs=1e-12)
        s = s_next
    assert s == s_fin
    # bilancio cumulato: somma di entrate/uscite = variazione totale degli stock
    n_hum0 = s_init.n_hum(npar.hp.n_humus)
    n_hum1 = s_fin.n_hum(npar.hp.n_humus)
    d_tot = ((s_fin.n_min - s_init.n_min) + (s_fin.n_res - s_init.n_res)
             + (s_fin.n_cov - s_init.n_cov) + (n_hum1 - n_hum0))
    cum = sum(b["entrate"] - b["uscite"] for b in bils)
    assert cum - d_tot == pytest.approx(0.0, abs=TOL_N)


def test_chiusura_casuale_stati_estremi(npar, yields):
    """Stati iniziali casuali (anche con credito negativo e residui) chiudono e restano >= 0."""
    rng = np.random.default_rng(20260115)
    for _ in range(300):
        s0 = nt.NState(n_min=float(rng.uniform(0, 400)), n_res=float(rng.uniform(0, 120)),
                       n_cov=0.0, h=float(rng.uniform(0.01, 150)),
                       cred=float(rng.uniform(-60, 60)))
        label, kind, crop, resa = segment_specs(yields)[int(rng.integers(0, 5))]
        resa = resa * float(rng.uniform(0.2, 1.1)) if kind == nt.SEG_CROP else 0.0
        acqua = {"days": float(rng.uniform(10, 365)), "dp": float(rng.choice([0, 30, 100, 300, 800]))}
        s1, bil = nt.update_segment(s0, kind, crop, acqua, resa, npar,
                                    residui_asportati=bool(rng.integers(0, 2)))
        assert_closure(s0, s1, bil)
        assert_non_negative(s1)


def test_residui_massimi_documentati(npar, yields):
    """Tutte le combinazioni dei test di chiusura: massimo residuo ben sotto la tolleranza."""
    mx_n = mx_h = 0.0
    for stato, s0 in initial_states(npar).items():
        for dp in DP_GRID:
            for _, kind, crop, resa in segment_specs(yields):
                for asp in (False, True):
                    s1, bil = nt.update_segment(s0, kind, crop, water(kind, dp), resa, npar, asp)
                    rn, rh = assert_closure(s0, s1, bil)
                    mx_n, mx_h = max(mx_n, rn), max(mx_h, rh)
    assert mx_n < TOL_N and mx_h < TOL_H


# =============================================================================
# 2) Soia
# =============================================================================

N_MIN_GRID = (0.0, 5.0, 10.0, 20.0, 40.0, 60.0, 80.0, 120.0, 200.0, 400.0)


def test_soia_nessun_concime(npar, yields):
    for n0 in N_MIN_GRID:
        for dp in DP_GRID:
            _, bil = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, "soia",
                                       water(nt.SEG_CROP, dp), yields["soia"], npar)
            assert bil["fert"] == 0.0
            assert bil["perd_f"] == 0.0


def test_soia_quota_fissata_non_crescente_con_n_min(npar, yields):
    quote = []
    for n0 in N_MIN_GRID:
        _, bil = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, "soia",
                                   water(nt.SEG_CROP, 100.0), yields["soia"], npar)
        assert bil["u"] > 0
        quote.append(bil["fix"] / bil["u"])
    assert all(b <= a + EPS for a, b in zip(quote, quote[1:])), quote
    assert quote[0] > quote[-1], "la fissazione deve calare quando il suolo e' ricco"
    assert max(quote) <= npar.fix_quota + EPS
    assert min(quote) >= 0.0


def test_soia_composizione_assorbimento(npar, yields):
    for n0 in N_MIN_GRID:
        _, b = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, "soia",
                                 water(nt.SEG_CROP, 100.0), yields["soia"], npar)
        assert b["u"] == pytest.approx(yields["soia"] * npar.n_ass["soia"])
        assert b["u_suolo"] <= b["u"] + EPS
        assert b["u_eff"] == pytest.approx(b["u_suolo"] + b["fix"])
        assert b["deficit_n"] == pytest.approx(b["u"] - b["u_eff"], abs=1e-9)
        assert b["deficit_n"] >= -EPS


def test_soia_suolo_poverissimo_deficit_senza_concime(npar, yields):
    """Nessun humus ne' azoto minerale: l'assorbimento non e' coperto da suolo e fissazione."""
    s0 = nt.NState(n_min=0.0, n_res=0.0, n_cov=0.0, h=0.0, cred=0.0)
    s1, b = nt.update_segment(s0, nt.SEG_CROP, "soia", water(nt.SEG_CROP, 100.0),
                              yields["soia"], npar)
    assert b["deficit_n"] > 0.0
    assert b["deficit_n_presente"] is True or bool(b["deficit_n_presente"])
    assert b["fert"] == 0.0
    assert b["fix"] <= npar.fix_quota * b["u"] + EPS
    assert_closure(s0, s1, b)


def test_soia_suolo_ricco_nessun_deficit(npar, yields):
    _, b = nt.update_segment(state_with(npar, 600.0), nt.SEG_CROP, "soia",
                             water(nt.SEG_CROP, 0.0), yields["soia"], npar)
    assert b["deficit_n"] == pytest.approx(0.0, abs=1e-9)
    assert not b["deficit_n_presente"]
    assert b["fix"] == pytest.approx(0.0, abs=1e-9)


# =============================================================================
# 3) Mais e frumento: concime, perdite, MAS
# =============================================================================

@pytest.mark.parametrize("crop", ["mais", "frumento"])
def test_concime_cresce_con_la_resa(npar, yields, crop):
    s0 = state_with(npar, 5.0)
    rese = [0.3, 0.5, 0.7, 0.9, 1.0]
    fert, n_disp, u = [], [], []
    for f in rese:
        _, b = nt.update_segment(s0, nt.SEG_CROP, crop, water(nt.SEG_CROP, 100.0),
                                 f * yields[crop], npar)
        fert.append(b["fert"])
        n_disp.append(b["n_disp"])
        u.append(b["u"])
    assert all(uu > nd for uu, nd in zip(u, n_disp)), "precondizione: assorbimento > N disponibile"
    assert all(b > a for a, b in zip(fert, fert[1:])), fert


@pytest.mark.parametrize("crop", ["mais", "frumento"])
def test_concime_cala_con_n_min(npar, yields, crop):
    fert = []
    for n0 in N_MIN_GRID:
        _, b = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, crop,
                                 water(nt.SEG_CROP, 100.0), yields[crop], npar)
        fert.append(b["fert"])
        assert b["fert"] >= 0.0
        assert b["u_suolo"] <= b["u"] + EPS
    assert all(b <= a + EPS for a, b in zip(fert, fert[1:])), fert
    assert fert[0] > fert[-1]
    # suolo piu' ricco dell'assorbimento: concime nullo
    assert fert[-1] == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize("crop", ["mais", "frumento"])
def test_concime_perdite_e_recupero(npar, pars, yields, crop):
    rec = float(fparams.get(pars, f"nitrogen.efficienza_concime.recupero_apparente.{crop}"))
    for n0 in (0.0, 20.0, 60.0):
        _, b = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, crop,
                                 water(nt.SEG_CROP, 100.0), yields[crop], npar)
        assert b["perd_f"] == pytest.approx(b["fert"] * (1.0 - rec), abs=1e-9)
        # il concime copre il deficit al recupero apparente
        assert b["fert"] * rec == pytest.approx(b["u"] - b["u_suolo"], abs=1e-9)


@pytest.mark.parametrize("crop", ["mais", "frumento", "soia"])
def test_supera_mas_coerente(npar, pars, yields, crop):
    eff = float(fparams.get(pars, "nitrogen.efficienza_concime.minerale_convenzione_normativa"))
    base = float(fparams.get(pars, f"nitrogen.vincoli.mas.{crop}"))
    esiti = set()
    for f in (0.4, 0.7, 1.0, 1.2):
        resa = f * yields[crop]
        for n0 in (0.0, 50.0, 400.0):
            _, b = nt.update_segment(state_with(npar, n0), nt.SEG_CROP, crop,
                                     water(nt.SEG_CROP, 100.0), resa, npar)
            assert b["mas"] == pytest.approx(nt.mas_limit(crop, resa, npar))
            assert b["mas"] >= base - EPS
            assert bool(b["supera_mas"]) == (b["fert"] * eff > b["mas"])
            esiti.add(bool(b["supera_mas"]))
    if crop != "soia":
        assert esiti == {True, False}, "la griglia deve coprire entrambi gli esiti"
    else:
        assert esiti == {False}


def test_mas_cresce_con_la_resa_oltre_il_riferimento(npar, pars):
    for crop in ("mais", "frumento"):
        rif = float(fparams.get(pars, f"nitrogen.vincoli.mas.{crop}_resa_riferimento"))
        base = float(fparams.get(pars, f"nitrogen.vincoli.mas.{crop}"))
        corr = float(fparams.get(pars, f"nitrogen.vincoli.mas.{crop}_fattore_correttivo"))
        assert nt.mas_limit(crop, rif * 0.5, npar) == pytest.approx(base)
        assert nt.mas_limit(crop, rif + 2.0, npar) == pytest.approx(base + 2.0 * corr)


# =============================================================================
# 4) Lisciviazione
# =============================================================================

def test_frazione_lisciviata(npar, pars):
    assert nt.leaching_fraction(0.0, npar) == 0.0
    ae = float(fparams.get(pars, "nitrogen.lisciviazione.anion_excl"))
    frac = [nt.leaching_fraction(d, npar) for d in (10.0, 50.0, 100.0, 300.0, 1000.0)]
    assert all(0.0 < f < 1.0 for f in frac)
    assert all(b > a for a, b in zip(frac, frac[1:]))
    sat = npar.sat_mm
    assert nt.leaching_fraction(100.0, npar) == pytest.approx(
        1.0 - math.exp(-100.0 / ((1.0 - ae) * sat)))


@pytest.mark.parametrize("kind,crop", [(nt.SEG_BARE, None), (nt.SEG_COVER, None),
                                       (nt.SEG_CROP, "mais"), (nt.SEG_CROP, "soia"),
                                       (nt.SEG_CROP, "frumento")])
def test_lisciviazione_nulla_crescente_limitata(npar, yields, kind, crop):
    resa = yields[crop] if crop else 0.0
    # N_min abbondante: dopo l'assorbimento della coltura resta azoto da lisciviare
    s0 = state_with(npar, 800.0)
    ls = []
    for dp in (0.0, 25.0, 100.0, 200.0, 300.0, 600.0):
        _, b = nt.update_segment(s0, kind, crop, water(kind, dp), resa, npar)
        ls.append(b["l"])
        assert b["l"] >= -EPS
        assert b["l"] <= b["n_disp"] + EPS
    assert ls[0] == pytest.approx(0.0, abs=1e-12)
    assert all(b > a for a, b in zip(ls, ls[1:])), ls


def test_lisciviazione_mai_oltre_azoto_disponibile_stati_estremi(npar, yields):
    for n0 in N_MIN_GRID:
        for dp in (50.0, 300.0, 5000.0):
            for _, kind, crop, resa in segment_specs(yields):
                _, b = nt.update_segment(state_with(npar, n0), kind, crop,
                                         water(kind, dp), resa, npar)
                assert -EPS <= b["l"] <= b["n_disp"] + EPS


@pytest.mark.parametrize("dp", [50.0, 100.0, 300.0])
@pytest.mark.parametrize("n0", [20.0, 80.0, 250.0])
def test_cover_lisciva_meno_del_suolo_nudo(npar, dp, n0):
    s0 = state_with(npar, n0)
    acqua = {"days": 120.0, "dp": dp}
    _, nudo = nt.update_segment(s0, nt.SEG_BARE, None, acqua, 0.0, npar)
    _, cover = nt.update_segment(s0, nt.SEG_COVER, None, acqua, 0.0, npar)
    assert cover["l"] < nudo["l"]


# =============================================================================
# 5) Cover crop
# =============================================================================

@pytest.mark.parametrize("dp", DP_GRID)
def test_cover_assorbimento_e_biomassa(npar, dp):
    ratio = npar.hp.cov_biomassa / npar.cov_n_ass
    ucov = []
    for n0 in (0.0, 5.0, 20.0, 60.0, 150.0, 400.0):
        s1, b = nt.update_segment(state_with(npar, n0), nt.SEG_COVER, None,
                                  water(nt.SEG_COVER, dp), 0.0, npar)
        ucov.append(b["u_cov"])
        assert -EPS <= b["u_cov"] <= npar.cov_n_ass + EPS
        # Il tetto u_cov <= 0,70 x azoto disponibile e' stato tolto per progetto quando il
        # bilancio dell'azoto e' passato a passo giornaliero: l'assorbimento della cover e'
        # limitato dal valore di riferimento (cov_n_ass, controllato sopra) e dall'azoto
        # minerale presente giorno per giorno, quindi non puo' superare quello disponibile
        # nel segmento (n_disp = N_min iniziale + mineralizzazione - dispersione + deposizione
        # + rilascio dei residui); a suolo povero puo' assorbirne anche tutto.
        assert b["u_cov"] <= b["n_disp"] + EPS
        assert b["cov_biomassa"] == pytest.approx(b["u_cov"] * ratio, abs=1e-12)
        assert b["cov_biomassa"] <= npar.hp.cov_biomassa + EPS
        assert s1.n_cov == 0.0, "la cover e' terminata a fine segmento"
    assert all(b >= a - EPS for a, b in zip(ucov, ucov[1:]))
    assert ucov[-1] == pytest.approx(npar.cov_n_ass), "suolo ricco: assorbimento di riferimento"
    assert ucov[0] < ucov[-1]


def test_cover_azoto_nel_pool_residui(npar):
    """L'azoto della cover finisce nei residui (N_res) a terminazione, il bilancio chiude."""
    s0 = state_with(npar, 150.0)
    s1, b = nt.update_segment(s0, nt.SEG_COVER, None, water(nt.SEG_COVER, 0.0), 0.0, npar)
    assert b["u_cov"] > 0
    assert s1.n_res > s0.n_res
    assert b["h_cov"] > 0
    assert_closure(s0, s1, b)


# =============================================================================
# 6) Humus
# =============================================================================

def test_humus_suolo_nudo_solo_mineralizzazione(npar):
    s0 = nt.initial_state(npar)
    s1, b = nt.update_segment(s0, nt.SEG_BARE, None, water(nt.SEG_BARE, 100.0), 0.0, npar)
    assert b["h_min"] > 0.0
    assert b["h_res"] == 0.0 and b["h_cov"] == 0.0
    assert s1.h < s0.h
    assert b["d_h"] == pytest.approx(-b["h_min"])
    assert b["d_n_hum"] == pytest.approx(b["d_h"] * npar.n_per_t_humus)
    assert b["d_n_hum"] < 0.0


@pytest.mark.parametrize("crop", CROPS)
def test_humus_residui_aumentano_lo_stock(npar, yields, crop):
    s0 = nt.initial_state(npar)
    acqua = water(nt.SEG_CROP, 100.0)
    s_int, b_int = nt.update_segment(s0, nt.SEG_CROP, crop, acqua, yields[crop], npar, False)
    s_asp, b_asp = nt.update_segment(s0, nt.SEG_CROP, crop, acqua, yields[crop], npar, True)
    assert b_int["h_res"] > 0.0
    assert b_int["d_h"] == pytest.approx(b_int["h_res"] - b_int["h_min"])
    assert s_int.h > s_asp.h
    assert b_asp["h_res"] == 0.0
    assert s_asp.h < s0.h
    assert b_asp["exp"] > b_int["exp"], "residui asportati: l'azoto esce dal campo"


def test_humus_cover_aumenta_lo_stock(npar):
    s0 = state_with(npar, 100.0)
    _, b = nt.update_segment(s0, nt.SEG_COVER, None, water(nt.SEG_COVER, 100.0), 0.0, npar)
    assert b["h_cov"] > 0.0
    assert b["d_h"] == pytest.approx(b["h_cov"] - b["h_min"])


def test_humus_residui_crescono_con_la_resa(npar, yields):
    s0 = nt.initial_state(npar)
    h_res = []
    for f in (0.3, 0.6, 1.0):
        _, b = nt.update_segment(s0, nt.SEG_CROP, "mais", water(nt.SEG_CROP, 100.0),
                                 f * yields["mais"], npar)
        h_res.append(b["h_res"])
    assert all(b > a for a, b in zip(h_res, h_res[1:])), h_res


def test_stato_mai_negativo_stati_poveri(npar, yields):
    """Suolo privo di azoto minerale, residui e humus: nessuno stock diventa negativo."""
    for h0 in (0.0, 1e-6, 0.01, 1.0):
        for cred in (-80.0, 0.0, 80.0):
            for _, kind, crop, resa in segment_specs(yields):
                for asp in (False, True):
                    s0 = nt.NState(n_min=0.0, n_res=0.0, n_cov=0.0, h=h0, cred=cred)
                    s1, b = nt.update_segment(s0, kind, crop, water(kind, 300.0, 365.0),
                                              resa, npar, asp)
                    assert_non_negative(s1)
                    assert_closure(s0, s1, b)


def test_stato_mai_negativo_catena_lunga(npar, yields):
    """Venti anni di mais-soia-frumento con cover e nudo: nessuno stock negativo, lo stato
    finale e' finito."""
    s = nt.initial_state(npar)
    for i in range(20):
        crop = CROPS[i % 3]
        for seg in ((nt.SEG_CROP, crop, water(nt.SEG_CROP, 150.0), yields[crop], i % 2 == 0),
                    (nt.SEG_COVER if i % 2 else nt.SEG_BARE, None,
                     water(nt.SEG_COVER, 80.0), 0.0)):
            s0 = s
            s, b = nt.update_segment(s0, *seg[:4], npar, *seg[4:5])
            assert_non_negative(s)
            assert_closure(s0, s, b)
    assert all(math.isfinite(getattr(s, f)) for f in ("n_min", "n_res", "n_cov", "h", "cred"))


# =============================================================================
# 7) Immutabilita'
# =============================================================================

def test_stato_immutabile(npar, yields):
    s0 = state_with(npar, 40.0, n_res=12.0, cred=3.0)
    snap = dataclasses.astuple(s0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s0.n_min = 1.0  # type: ignore[misc]
    acqua = water(nt.SEG_CROP, 100.0)
    acqua_copia = copy.deepcopy(acqua)
    for _, kind, crop, resa in segment_specs(yields):
        s1, _ = nt.update_segment(s0, kind, crop, acqua, resa, npar)
        assert s1 is not s0
        assert dataclasses.astuple(s0) == snap
        assert acqua == acqua_copia
    nt.run_segments(s0, [(nt.SEG_CROP, "mais", acqua, yields["mais"])], npar)
    assert dataclasses.astuple(s0) == snap


def test_aggiornamento_deterministico(npar, yields):
    s0 = state_with(npar, 40.0)
    a = nt.update_segment(s0, nt.SEG_CROP, "mais", water(nt.SEG_CROP, 100.0), yields["mais"], npar)
    b = nt.update_segment(s0, nt.SEG_CROP, "mais", water(nt.SEG_CROP, 100.0), yields["mais"], npar)
    assert a[0] == b[0] and a[1] == b[1]


# =============================================================================
# 8) Prestazioni
# =============================================================================

def test_prestazioni_100000_aggiornamenti(npar, yields):
    s0 = nt.initial_state(npar)
    acqua = water(nt.SEG_CROP, 100.0)
    resa = yields["mais"]
    t0 = time.perf_counter()
    for _ in range(100_000):
        nt.update_segment(s0, nt.SEG_CROP, "mais", acqua, resa, npar)
    dt = time.perf_counter() - t0
    print(f"\n100000 aggiornamenti: {dt:.3f} s")
    assert dt < 5.0, f"troppo lento: {dt:.2f} s"
