"""Test di ``fieldwise.yield_model`` (resa = potenziale x f_acqua x f_caldo x f_rotazione).

Fattori in [0, 1], f_acqua senza deficit, f_caldo con meteo fresco e caldo, metodi e
finestre, f_rotazione contro ``params/rotation_rules.yaml``, ``crop_yield`` e riferimenti
sul meteo reale del punto pilota (saltati se la cache manca). Nessuna rete.
"""
import itertools

import numpy as np
import pandas as pd
import pytest

from fieldwise import params as fparams
from fieldwise import phenology as ph
from fieldwise import weather
from fieldwise import yield_model as ym
from fieldwise.data.cache import CacheMiss

CROPS = ("mais", "soia", "frumento")
METODI = ("deryng", "aquacrop", "teixeira")
FINESTRE = (None, "giorni_emergenza_maturita", "gdd_semina_maturita")
SCENARI = ("irriguo", "asciutto")


# =============================================================================
# Ingressi
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


def make_forcing(tmean, tmax=None, start="2000-01-01"):
    tm = np.asarray(tmean, float)
    tx = tm if tmax is None else np.asarray(tmax, float)
    return pd.DataFrame({"date": pd.date_range(start, periods=len(tm), freq="D"),
                         "tmean": tm, "tmax": tx, "tmin": tm - 6.0})


def constant(temp, n_days=1500):
    """Temperatura costante: tmean = tmax = temp (quindi Teff = Tmax = temp)."""
    return make_forcing(np.full(n_days, float(temp)))


def calendar(pars, crop, forcing, sow=60):
    cal = ph.cycle_calendar(pars, crop, forcing, sow)
    assert cal.ok
    return cal


# =============================================================================
# f_acqua
# =============================================================================

def test_f_acqua_uno_senza_deficit(pars):
    for ky in (0.0, 0.8, 1.25, 3.0):
        assert ym.water_factor(300.0, 300.0, ky) == 1.0
        assert ym.water_factor(350.0, 300.0, ky) == 1.0      # ETa > ETc: limitata a 1
    for crop in CROPS:
        ky = float(fparams.get(pars, f"crops.{crop}.ky"))
        assert ym.water_factor(450.0, 450.0, ky) == 1.0


def test_f_acqua_formula_fao33(pars):
    ky = float(fparams.get(pars, "crops.mais.ky"))
    assert ym.water_factor(240.0, 300.0, ky) == pytest.approx(1.0 - ky * 0.2)
    assert ym.water_factor(150.0, 300.0, 0.5) == pytest.approx(0.75)


def test_f_acqua_decresce_con_il_deficit(pars):
    ky = float(fparams.get(pars, "crops.mais.ky"))
    f = [ym.water_factor(e, 400.0, ky) for e in (400.0, 360.0, 300.0, 200.0, 100.0, 0.0)]
    assert all(b <= a + 1e-12 for a, b in zip(f, f[1:]))
    assert f[0] == 1.0 and f[-1] < 1.0


@pytest.mark.parametrize("eta,etc,ky", list(itertools.product(
    (-50.0, 0.0, 1e-9, 100.0, 1e6), (-10.0, 0.0, 1e-9, 100.0, 1e6), (0.0, 0.5, 1.25, 10.0, 1e6))))
def test_f_acqua_in_0_1_ingressi_estremi(eta, etc, ky):
    f = ym.water_factor(eta, etc, ky)
    assert 0.0 <= f <= 1.0


# =============================================================================
# f_caldo
# =============================================================================

def test_f_caldo_uno_con_meteo_fresco(pars):
    f = constant(18.0)             # Teff = Tmax = 18 degC, sotto ogni soglia critica
    for crop in CROPS:
        cal = calendar(pars, crop, f)
        for metodo, fin, tt in itertools.product(METODI, FINESTRE, ("teff", "tmax")):
            r = ym.heat_factor(pars, crop, f, cal, metodo=metodo, finestra=fin, teixeira_temp=tt)
            assert r.f_caldo == 1.0, (crop, metodo, fin, tt)
            assert r.n_hot_days == 0
            assert 0 < r.n_window_days <= cal.n_days
            assert r.metodo == metodo


@pytest.mark.parametrize("metodo", METODI)
@pytest.mark.parametrize("crop", CROPS)
def test_f_caldo_non_cresce_scaldando(pars, crop, metodo):
    temps = np.arange(15.0, 52.0, 2.0)
    fc = []
    for t in temps:
        f = constant(t)
        cal = calendar(pars, crop, f)
        r = ym.heat_factor(pars, crop, f, cal, metodo=metodo)
        assert 0.0 <= r.f_caldo <= 1.0
        fc.append(r.f_caldo)
    assert fc[0] == 1.0
    assert all(b <= a + 1e-12 for a, b in zip(fc, fc[1:])), fc
    assert fc[-1] < 1.0
    assert fc[-1] == pytest.approx(0.0, abs=1e-9), "a 51 degC ogni metodo azzera il fattore"


@pytest.mark.parametrize("crop", CROPS)
def test_f_caldo_deryng_lineare_tra_le_soglie(pars, crop):
    tcr = float(fparams.get(pars, f"heat.colture.{crop}.t_critica"))
    tlim = float(fparams.get(pars, f"heat.colture.{crop}.t_limite"))
    t = 0.5 * (tcr + tlim)
    f = constant(t)
    r = ym.heat_factor(pars, crop, f, calendar(pars, crop, f))
    assert r.f_caldo == pytest.approx(0.5)
    assert r.t_soglia == tcr
    assert r.n_hot_days == r.n_window_days, "tutti i giorni della finestra sopra la soglia"
    assert ym.heat_factor(pars, crop, constant(tlim + 2), calendar(pars, crop, constant(tlim + 2))
                          ).f_caldo == 0.0


def test_f_caldo_giorni_caldi_conteggiati(pars):
    """Ondata di calore breve nel mezzo del ciclo: f_caldo cala di poco, i giorni caldi
    sono quelli sopra la soglia dentro la finestra."""
    tcr = float(fparams.get(pars, "heat.colture.mais.t_critica"))
    tlim = float(fparams.get(pars, "heat.colture.mais.t_limite"))
    base = np.full(1500, 22.0)
    cal0 = calendar(pars, "mais", make_forcing(base))
    r0 = ym.heat_factor(pars, "mais", make_forcing(base), cal0)
    assert r0.f_caldo == 1.0 and r0.n_hot_days == 0
    ws, we = r0.window_start, r0.window_end
    hot = base.copy()
    hot[ws:ws + 5] = tcr + 0.25 * (tlim - tcr)
    f = make_forcing(hot)
    cal = ph.cycle_calendar(pars, "mais", f, 60)
    r = ym.heat_factor(pars, "mais", f, cal)
    assert r.n_hot_days == 5
    assert r.n_hot_days <= r.n_window_days
    # 5 giorni a f = 0.75 (un quarto del tratto lineare), gli altri a 1 (Deryng eq. A.6-A.7)
    assert r.f_caldo == pytest.approx(1.0 - 0.25 * 5 / r.n_window_days)


def test_f_caldo_risultato_coerente(pars):
    f = constant(24.0)
    for crop in CROPS:
        cal = calendar(pars, crop, f)
        r = ym.heat_factor(pars, crop, f, cal)
        assert r.window_start <= r.window_end
        assert cal.sow <= r.window_start and r.window_end <= cal.maturity
        assert r.n_window_days <= r.window_end - r.window_start + 1
        assert isinstance(r.flowering_in_window, bool)
        assert len(r.f_daily) == cal.n_days
        assert ((r.f_daily >= 0) & (r.f_daily <= 1)).all()


def test_finestre_default_da_parametri(pars):
    f = constant(20.0)
    for crop in CROPS:
        cal = calendar(pars, crop, f)
        atteso = str(fparams.get(pars, f"heat.colture.{crop}.finestra_definizione"))
        assert ym.heat_factor(pars, crop, f, cal).finestra == atteso
        for fin in ym.FINESTRE:
            assert ym.heat_factor(pars, crop, f, cal, finestra=fin).finestra == fin


def test_metodo_sconosciuto_errore_chiaro(pars):
    f = constant(20.0)
    cal = calendar(pars, "mais", f)
    with pytest.raises(ValueError, match="metodo sconosciuto"):
        ym.heat_factor(pars, "mais", f, cal, metodo="inventato")
    with pytest.raises(ValueError, match="finestra sconosciuta"):
        ym.heat_factor(pars, "mais", f, cal, finestra="inventata")
    with pytest.raises(ValueError, match="teixeira_temp"):
        ym.heat_factor(pars, "mais", f, cal, metodo="teixeira", teixeira_temp="tmin")


def test_f_caldo_ciclo_fuori_serie_rifiutato(pars):
    pp = ph.crop_pheno_params(pars, "mais")
    f = constant(pp.t_base + 1.0, n_days=150)
    cal = ph.cycle_calendar(pars, "mais", f, 10)
    assert cal.status == ph.STATO_FUORI_SERIE
    with pytest.raises(ValueError):
        ym.heat_factor(pars, "mais", f, cal)


# =============================================================================
# f_rotazione
# =============================================================================

def yaml_rot(pars, path):
    return float(fparams.get(pars, f"rotation_rules.f_rotazione.{path}"))


@pytest.mark.parametrize("scenario", SCENARI)
def test_senza_ristoppio_uno(pars, scenario):
    for crop, prev1, prev2 in itertools.product(CROPS, (None,) + CROPS, (None,) + CROPS):
        if prev1 == crop:
            continue
        f, caso = ym.rotation_factor(pars, crop, prev1, prev2, scenario)
        assert f == 1.0 and caso == "nessun_ristoppio", (crop, prev1, prev2)
    # mais-soia-frumento: tutti 1
    out = ym.rotation_factors(pars, ["mais", "soia", "frumento"], scenario, n_years=9)
    assert [f for f, _ in out] == [1.0] * 9
    assert {c for _, c in out} == {"nessun_ristoppio"}


@pytest.mark.parametrize("scenario", SCENARI)
@pytest.mark.parametrize("crop", CROPS)
def test_ristoppio_penalizza_e_continua_non_migliore(pars, crop, scenario):
    altro = next(c for c in CROPS if c != crop)
    primo, caso1 = ym.rotation_factor(pars, crop, crop, altro, scenario)
    cont, caso2 = ym.rotation_factor(pars, crop, crop, crop, scenario)
    assert caso1 == "primo_ristoppio" and caso2 == "monosuccessione_continua"
    assert 0.0 < primo < 1.0
    assert 0.0 < cont <= primo
    # prev2 sconosciuta: trattata come diversa -> primo ristoppio
    assert ym.rotation_factor(pars, crop, crop, None, scenario) == (primo, "primo_ristoppio")


def test_valori_coincidono_con_rotation_rules(pars):
    # mais: irriguo (irrigabile) un solo valore; asciutto distingue primo e continuo
    assert ym.rotation_factor(pars, "mais", "mais", "soia", "irriguo")[0] == yaml_rot(
        pars, "mais_dopo_mais.irriguo")
    assert ym.rotation_factor(pars, "mais", "mais", "mais", "irriguo")[0] == yaml_rot(
        pars, "mais_dopo_mais.irriguo")
    assert ym.rotation_factor(pars, "mais", "mais", "soia", "asciutto")[0] == yaml_rot(
        pars, "mais_dopo_mais.asciutto.primo_ristoppio")
    assert ym.rotation_factor(pars, "mais", "mais", "mais", "asciutto")[0] == yaml_rot(
        pars, "mais_dopo_mais.asciutto.monosuccessione_continua")
    # soia: stesso valore nei due scenari
    for sc in SCENARI:
        for p2 in ("mais", "soia"):
            assert ym.rotation_factor(pars, "soia", "soia", p2, sc)[0] == yaml_rot(
                pars, "soia_dopo_soia")
    # frumento
    for sc in SCENARI:
        assert ym.rotation_factor(pars, "frumento", "frumento", "mais", sc)[0] == yaml_rot(
            pars, "frumento_dopo_frumento.primo_ristoppio")
        assert ym.rotation_factor(pars, "frumento", "frumento", "frumento", sc)[0] == yaml_rot(
            pars, "frumento_dopo_frumento.monosuccessione_continua")


def test_nessun_fattore_oltre_uno_precessione_favorevole_non_applicata(pars):
    """Nessuna combinazione di coltura, precessioni e scenario supera 1."""
    prev = (None,) + CROPS
    for crop, p1, p2, sc in itertools.product(CROPS, prev, prev, SCENARI):
        f, _ = ym.rotation_factor(pars, crop, p1, p2, sc)
        assert 0.0 <= f <= 1.0
    for seq in (["mais"], ["soia", "mais"], ["mais", "soia", "frumento"], ["frumento"] * 3,
                ["mais", "mais", "soia", "soia", "frumento", "frumento"]):
        for sc in SCENARI:
            for prec in (None, [], ["mais"], ["soia", "soia"]):
                for f, _ in ym.rotation_factors(pars, seq, sc, n_years=2 * len(seq) + 1,
                                                precedenti=prec):
                    assert 0.0 <= f <= 1.0


def test_rotation_factors_monosuccessione(pars):
    primo = yaml_rot(pars, "frumento_dopo_frumento.primo_ristoppio")
    cont = yaml_rot(pars, "frumento_dopo_frumento.monosuccessione_continua")
    # nessuna coltura nota prima: 1o anno libero, 2o primo ristoppio, poi continua
    out = ym.rotation_factors(pars, ["frumento"], "asciutto", n_years=4, precedenti=[])
    assert [c for _, c in out] == ["nessun_ristoppio", "primo_ristoppio",
                                   "monosuccessione_continua", "monosuccessione_continua"]
    assert [f for f, _ in out] == [1.0, primo, cont, cont]
    # a regime (default): la monosuccessione e' gia' continua dal primo anno
    reg = ym.rotation_factors(pars, ["frumento"], "asciutto", n_years=3)
    assert [f for f, _ in reg] == [cont, cont, cont]
    # storia esplicita
    s = ym.rotation_factors(pars, ["frumento", "mais"], "asciutto", n_years=2,
                            precedenti=["mais", "frumento"])
    assert s[0][1] == "primo_ristoppio" and s[0][0] == primo
    assert s[1] == (1.0, "nessun_ristoppio")
    # lunghezza predefinita = lunghezza della rotazione
    assert len(ym.rotation_factors(pars, ["mais", "soia", "frumento"], "irriguo")) == 3


def test_scenario_sconosciuto_errore(pars):
    with pytest.raises(ValueError, match="scenario"):
        ym.rotation_factor(pars, "mais", "mais", "mais", "inventato")
    with pytest.raises(ValueError, match="scenario"):
        ym.rotation_factors(pars, ["mais", "mais"], "inventato")


# =============================================================================
# crop_yield
# =============================================================================

@pytest.mark.parametrize("crop", CROPS)
def test_crop_yield_prodotto_e_fattori_separati(pars, crop):
    ypot = float(fparams.get(pars, f"crops.{crop}.resa_potenziale"))
    fa, fc, fr = 0.9, 0.95, 0.875
    r = ym.crop_yield(pars, crop, fa, fc, fr)
    assert r["resa_potenziale"] == pytest.approx(ypot)
    assert r["resa"] == pytest.approx(ypot * fa * fc * fr)
    assert (r["f_acqua"], r["f_caldo"], r["f_rotazione"]) == (fa, fc, fr)
    assert r["f_totale"] == pytest.approx(fa * fc * fr)
    assert r["resa"] == pytest.approx(r["resa_potenziale"] * r["f_totale"])
    assert ym.crop_yield(pars, crop, 1.0, 1.0, 1.0)["resa"] == pytest.approx(ypot)
    assert ym.crop_yield(pars, crop, 0.0, 1.0, 1.0)["resa"] == 0.0


@pytest.mark.parametrize("fa,fc,fr", list(itertools.product(
    (-1.0, 0.0, 0.5, 1.0, 7.0), repeat=3)))
def test_crop_yield_fattori_in_0_1_ingressi_estremi(pars, fa, fc, fr):
    r = ym.crop_yield(pars, "mais", fa, fc, fr)
    for k in ("f_acqua", "f_caldo", "f_rotazione", "f_totale"):
        assert 0.0 <= r[k] <= 1.0
    assert 0.0 <= r["resa"] <= r["resa_potenziale"] + 1e-12


def test_resa_composta_dai_moduli(pars):
    f = constant(18.0)
    cal = calendar(pars, "mais", f)
    fc = ym.heat_factor(pars, "mais", f, cal).f_caldo
    fa = ym.water_factor(300.0, 400.0, float(fparams.get(pars, "crops.mais.ky")))
    fr, _ = ym.rotation_factor(pars, "mais", "mais", "soia", "asciutto")
    r = ym.crop_yield(pars, "mais", fa, fc, fr)
    assert r["resa"] == pytest.approx(ym.potential_yield(pars, "mais") * fa * fc * fr)
    assert 0.0 < r["resa"] < r["resa_potenziale"]


# =============================================================================
# Meteo reale del punto pilota
# =============================================================================

@pytest.fixture(scope="module")
def forcing():
    try:
        return weather.load_forcing(45.2, 10.0)
    except (CacheMiss, FileNotFoundError):
        pytest.skip("cache meteo del punto pilota assente")


def test_frumento_fioritura_dentro_la_finestra_default(pars, forcing):
    visti = 0
    for year in range(2000, 2025):
        sow = ph.typical_sowing_index(pars, "frumento", forcing, year)
        cal = ph.cycle_calendar(pars, "frumento", forcing, sow)
        if not cal.ok:
            continue
        r = ym.heat_factor(pars, "frumento", forcing, cal)
        assert r.flowering_in_window, year
        assert 0.0 <= r.f_caldo <= 1.0
        visti += 1
    assert visti >= 20


@pytest.mark.parametrize("anno,atteso", [(2015, 0.930), (2022, 0.958), (2014, 1.000)])
def test_mais_f_caldo_riferimento_regressione(pars, forcing, anno, atteso):
    sow = ph.typical_sowing_index(pars, "mais", forcing, anno)
    cal = ph.cycle_calendar(pars, "mais", forcing, sow)
    assert cal.ok
    r = ym.heat_factor(pars, "mais", forcing, cal)
    assert r.f_caldo == pytest.approx(atteso, abs=0.01)
    assert r.metodo == "deryng" and r.finestra == "giorni_emergenza_maturita"


@pytest.mark.parametrize("crop", CROPS)
def test_fattori_in_0_1_su_tutti_gli_anni_reali(pars, forcing, crop):
    n = 0
    for year in range(2000, 2025):
        cal = ph.cycle_calendar(pars, crop, forcing, ph.typical_sowing_index(pars, crop, forcing, year))
        if not cal.ok:
            continue
        for metodo in METODI:
            r = ym.heat_factor(pars, crop, forcing, cal, metodo=metodo)
            assert 0.0 <= r.f_caldo <= 1.0
            assert 0 <= r.n_hot_days <= r.n_window_days
        n += 1
    assert n > 0
