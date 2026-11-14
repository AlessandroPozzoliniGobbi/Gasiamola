"""Test di ``fieldwise.humus`` (bilancio dell'humus di Henin-Dupuis a fine segmento).

Chiusura, mineralizzazione proporzionale al tempo, residui crescenti con la resa, stock
all'equilibrio. I valori attesi si ricavano dai parametri caricati. Nessuna rete.
"""
import math

import pytest

from fieldwise import humus as hm
from fieldwise import params as fparams

TOL = 1e-9
CROPS = hm.CROPS


@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def hp(pars):
    return hm.humus_params(pars)


@pytest.fixture(scope="module")
def yields(pars):
    return {c: float(fparams.get(pars, f"crops.{c}.resa_potenziale")) for c in CROPS}


# --------------------------------------------------------------------- parametri
def test_stock_iniziale_da_parametri(pars, hp):
    s = "soil.strati_soilgrids.s0_30"
    atteso = (float(fparams.get(pars, f"{s}.sostanza_organica")) / 100.0
              * float(fparams.get(pars, "nitrogen.suolo.profondita_humus")) * 10000.0
              * float(fparams.get(pars, f"{s}.densita_apparente")))
    assert hm.initial_humus(hp) == pytest.approx(atteso)
    assert hm.initial_humus(hp) > 0.0


def test_anni_da_giorni():
    assert hm.years(365.0) == pytest.approx(1.0)
    assert hm.years(73.0) == pytest.approx(0.2)
    assert hm.years(0.0) == 0.0


def test_k2_positivo_e_dai_parametri(pars, hp):
    assert hp.k2 > 0.0
    assert hp.k2 == pytest.approx(hm.k2_from_params(pars))
    assert 0.0 < hp.h_tetto


# --------------------------------------------------------------------- mineralizzazione
def test_mineralizzazione_proporzionale_al_tempo(hp):
    h = 0.5 * hp.h_tetto
    base = hm.mineralization(h, 0.25, hp)
    assert base > 0.0
    for k in (2, 4, 8):
        assert hm.mineralization(h, 0.25 * k, hp) == pytest.approx(k * base)
    assert hm.mineralization(h, 0.0, hp) == 0.0


def test_mineralizzazione_formula_e_tetto(hp):
    anni = 0.7
    h = 0.3 * hp.h_tetto
    assert hm.mineralization(h, anni, hp) == pytest.approx(hp.k2 * h * anni)
    # sotto il tetto proporzionale allo stock
    assert hm.mineralization(2 * h, anni, hp) == pytest.approx(2 * hm.mineralization(h, anni, hp))
    # oltre il tetto costante
    m_tetto = hm.mineralization(hp.h_tetto, anni, hp)
    assert hm.mineralization(2.0 * hp.h_tetto, anni, hp) == pytest.approx(m_tetto)
    assert hm.mineralization(0.0, anni, hp) == 0.0


# --------------------------------------------------------------------- residui
@pytest.mark.parametrize("crop", CROPS)
def test_residui_crescenti_con_la_resa(hp, yields, crop):
    rese = [yields[crop] * f for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    ss = [hm.residue_dry_matter(crop, r, hp) for r in rese]
    hh = [hm.residue_humus(crop, r, hp) for r in rese]
    assert ss[0] == 0.0 and hh[0] == 0.0
    assert all(b > a for a, b in zip(ss, ss[1:])), ss
    assert all(b > a for a, b in zip(hh, hh[1:])), hh
    # proporzionalita' alla resa
    assert hh[4] == pytest.approx(2.0 * hh[2])
    assert hh[1] == pytest.approx(0.5 * hh[2])


@pytest.mark.parametrize("crop", CROPS)
def test_residui_formula_da_parametri(pars, hp, yields, crop):
    resa = yields[crop]
    um = hm.grain_moisture(pars, crop)
    hi = float(fparams.get(pars, f"crops.{crop}.hi"))
    ss = resa * (1.0 - um) * (1.0 / hi - 1.0)
    assert hm.residue_dry_matter(crop, resa, hp) == pytest.approx(ss)
    k1 = float(fparams.get(pars, f"nitrogen.{crop}.k1_residui"))
    c = float(fparams.get(pars, "nitrogen.suolo.residui.c_residui"))
    f = float(fparams.get(pars, "nitrogen.suolo.fattore_so_c"))
    assert hm.residue_humus(crop, resa, hp) == pytest.approx(k1 * ss * c * f)


def test_humus_cover_proporzionale_alla_biomassa(hp):
    assert hm.cover_humus(hp) == pytest.approx(hm.cover_humus(hp, hp.cov_biomassa))
    assert hm.cover_humus(hp, 0.0) == 0.0
    assert hm.cover_humus(hp, 2 * hp.cov_biomassa) == pytest.approx(2 * hm.cover_humus(hp))
    assert hm.cover_humus(hp) > 0.0


# --------------------------------------------------------------------- aggiornamento e chiusura
@pytest.mark.parametrize("anni", [0.0, 0.1, 0.5, 1.0, 3.0])
@pytest.mark.parametrize("frac_h", [0.05, 0.5, 1.0, 3.0])
def test_chiusura_update_humus(hp, anni, frac_h):
    h = frac_h * hp.h_tetto
    h_res = hm.residue_humus("mais", 10.0, hp)
    h_cov = hm.cover_humus(hp)
    for hr, hc in ((0.0, 0.0), (h_res, 0.0), (0.0, h_cov), (h_res, h_cov)):
        h1, voci = hm.update_humus(h, anni, hp, hr, hc)
        assert abs(hm.humus_balance_residual(h, h1, voci)) < TOL
        assert h1 == pytest.approx(h - voci["h_min"] + hr + hc)
        assert voci["d_h"] == pytest.approx(h1 - h)
        assert voci["h_min"] == pytest.approx(hm.mineralization(h, anni, hp))


def test_aggiornamento_segno(hp):
    h = 0.5 * hp.h_tetto
    h1, _ = hm.update_humus(h, 1.0, hp)
    assert h1 < h, "senza apporti la mineralizzazione riduce lo stock"
    h2, _ = hm.update_humus(h, 1.0, hp, h_res=hm.residue_humus("mais", 10.0, hp))
    assert h2 > h1, "i residui aumentano lo stock"
    h3, _ = hm.update_humus(h, 1.0, hp, h_cov=hm.cover_humus(hp))
    assert h3 > h1


def test_stock_non_negativo_in_simulazione_lunga(hp, yields):
    h = hm.initial_humus(hp)
    for i in range(100):
        crop = CROPS[i % 3]
        h, voci = hm.update_humus(h, 0.4, hp, hm.residue_humus(crop, yields[crop], hp))
        h, voci = hm.update_humus(h, 0.6, hp)
        assert h >= 0.0
    h = hm.initial_humus(hp)
    for _ in range(200):          # senza apporti: decresce e resta >= 0
        h_new, _ = hm.update_humus(h, 1.0, hp)
        assert 0.0 <= h_new < h
        h = h_new


# --------------------------------------------------------------------- equilibrio
@pytest.mark.parametrize("frac", [0.1, 0.4, 0.8])
def test_equilibrio_stazionario(hp, frac):
    apporti = frac * hp.k2 * hp.h_tetto        # H_eq = frac * H_tetto, sotto il tetto
    h_eq = hm.equilibrium(apporti, hp)
    assert h_eq == pytest.approx(frac * hp.h_tetto)
    assert h_eq == pytest.approx(apporti / hp.k2)
    h1, voci = hm.update_humus(h_eq, 1.0, hp, h_res=apporti)
    assert h1 == pytest.approx(h_eq, rel=1e-9, abs=1e-9)
    assert voci["d_h"] == pytest.approx(0.0, abs=1e-9)
    # il passo vale anche spezzato in sotto-intervalli (k2 e tempo lineari)
    h = h_eq
    for _ in range(4):
        h, _ = hm.update_humus(h, 0.25, hp, h_res=apporti / 4.0)
    assert h == pytest.approx(h_eq, rel=1e-9)


def test_equilibrio_attrattore(hp):
    apporti = 0.5 * hp.k2 * hp.h_tetto
    h_eq = hm.equilibrium(apporti, hp)
    for h0 in (0.1 * h_eq, 1.9 * h_eq):
        h = h0
        for _ in range(int(40 / hp.k2)):
            h, _ = hm.update_humus(h, 1.0, hp, h_res=apporti)
        assert h == pytest.approx(h_eq, rel=1e-3)


def test_equilibrio_apporti_nulli(hp):
    assert hm.equilibrium(0.0, hp) == 0.0
    assert math.isfinite(hm.equilibrium(1.0, hp))
