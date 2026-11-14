"""Test di ``fieldwise.phenology`` (fasi in gradi-giorno).

Formula dei GDD ai casi limite, ordine cronologico degli eventi, frazione di sviluppo,
risposta alla temperatura e alla data di semina, stati ``fuori_serie`` e ``oltre_limite``,
curve Kc/radici e confronto con il meteo reale del punto pilota (saltato se la cache
manca). I valori attesi si ricavano dai parametri caricati. Nessuna rete.
"""
import math

import numpy as np
import pandas as pd
import pytest

from fieldwise import params as fparams
from fieldwise import phenology as ph
from fieldwise import weather
from fieldwise.data.cache import CacheMiss

CROPS = ("mais", "soia", "frumento")
EVENT_KEY = {"emergence": "gdd_emergenza", "end_ini": "gdd_fine_ini",
             "end_dev": "gdd_fine_sviluppo", "end_mid": "gdd_fine_mid",
             "flowering": "gdd_fioritura", "maturity": "gdd_maturita"}


# =============================================================================
# Ingressi
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


def make_forcing(tmean, start="2000-01-01"):
    """Meteo sintetico: tmax = tmean + 4, tmin = tmean - 4."""
    tm = np.asarray(tmean, float)
    return pd.DataFrame({"date": pd.date_range(start, periods=len(tm), freq="D"),
                         "tmean": tm, "tmax": tm + 4.0, "tmin": tm - 4.0})


def seasonal(n_days=4 * 365, mean=13.0, amp=12.0, shift=0.0):
    doy = np.arange(n_days) % 365
    return mean + shift + amp * np.sin(2 * np.pi * (doy - 110) / 365.0)


def constant(temp, n_days=3000):
    return make_forcing(np.full(n_days, float(temp)))


def sow_of(pars, crop, forcing, year):
    return ph.typical_sowing_index(pars, crop, forcing, year)


# =============================================================================
# Gradi-giorno
# =============================================================================

def test_daily_gdd_casi_limite():
    tb, tu = 8.0, 30.0
    assert ph.daily_gdd(tb - 5.0, tb, tu) == 0.0
    assert ph.daily_gdd(-20.0, tb, tu) == 0.0
    assert ph.daily_gdd(tb, tb, tu) == 0.0
    assert ph.daily_gdd(20.0, tb, tu) == pytest.approx(12.0)
    assert ph.daily_gdd(tu, tb, tu) == pytest.approx(tu - tb)
    assert ph.daily_gdd(tu + 10.0, tb, tu) == pytest.approx(tu - tb)
    assert ph.daily_gdd(60.0, tb, tu) == pytest.approx(tu - tb)


def test_daily_gdd_vettoriale_non_negativo():
    t = np.linspace(-30, 60, 181)
    g = ph.daily_gdd(t, 5.0, 28.0)
    assert g.shape == t.shape
    assert (g >= 0).all() and (g <= 23.0 + 1e-12).all()
    assert (np.diff(g) >= -1e-12).all(), "monotona nella temperatura"
    expected = np.maximum(0.0, np.minimum(t, 28.0) - 5.0)
    np.testing.assert_allclose(g, expected)


@pytest.mark.parametrize("crop", CROPS)
def test_daily_gdd_con_parametri_della_coltura(pars, crop):
    pp = ph.crop_pheno_params(pars, crop)
    assert pp.t_base == float(fparams.get(pars, f"crops.{crop}.t_base"))
    assert pp.t_upper == float(fparams.get(pars, f"crops.{crop}.t_upper"))
    assert ph.daily_gdd(pp.t_base - 1, pp.t_base, pp.t_upper) == 0.0
    assert ph.daily_gdd(pp.t_upper + 5, pp.t_base, pp.t_upper) == pytest.approx(
        pp.t_upper - pp.t_base)


def test_cumulative_gdd():
    c = ph.cumulative_gdd([1.0, 2.0, 0.0, 3.0])
    np.testing.assert_allclose(c, [0.0, 1.0, 3.0, 3.0, 6.0])
    assert ph.cumulative_gdd([]).tolist() == [0.0]
    with pytest.raises(ValueError):
        ph.cumulative_gdd([1.0, float("nan")])


def test_threshold_days_e_non_raggiunta():
    c = ph.cumulative_gdd(np.full(10, 5.0))          # 5, 10, ..., 50
    d = ph.threshold_days(c, [0, 3], [5.0, 12.0, 30.0, 50.0])
    assert d.shape == (2, 4)
    assert d[0].tolist() == [0, 2, 5, 9]
    assert d[1, 0] == 3 and d[1, 1] == 5 and d[1, 2] == 8
    assert d[1, 3] == -1, "50 GDD dalla semina al giorno 3 non sono raggiunti"
    with pytest.raises(IndexError):
        ph.threshold_days(c, [10], [5.0])
    with pytest.raises(IndexError):
        ph.threshold_days(c, [-1], [5.0])


def test_tmean_mancante_usa_tmax_tmin():
    f = make_forcing([10.0, 20.0, 30.0])
    f.loc[1, "tmean"] = np.nan
    np.testing.assert_allclose(ph.tmean_of(f), [10.0, 20.0, 30.0])


# =============================================================================
# Parametri della coltura
# =============================================================================

@pytest.mark.parametrize("crop", CROPS)
def test_breakpoints_crescenti_in_0_1(pars, crop):
    pp = ph.crop_pheno_params(pars, crop)
    f_ini, f_dev, f_mid = pp.breakpoints
    assert 0.0 < f_ini < f_dev < f_mid < 1.0
    thr = [float(fparams.get(pars, f"crops.{crop}.{k}")) for k in
           ("gdd_fine_ini", "gdd_fine_sviluppo", "gdd_fine_mid")]
    gm = float(fparams.get(pars, f"crops.{crop}.gdd_maturita"))
    assert (f_ini, f_dev, f_mid) == pytest.approx(tuple(t / gm for t in thr))
    assert pp.gdd_maturita == pytest.approx(gm)


def test_soglie_non_ordinate_rifiutate(pars):
    import copy
    bad = copy.deepcopy(pars)
    bad["crops"]["mais"]["gdd_fine_ini"]["valore"] = 1e9
    with pytest.raises(ValueError):
        ph.crop_pheno_params(bad, "mais")


# =============================================================================
# Calendario del ciclo
# =============================================================================

def assert_ordered(cal):
    assert cal.sow <= cal.emergence <= cal.end_ini <= cal.end_dev <= cal.end_mid <= cal.maturity
    assert cal.emergence <= cal.flowering <= cal.maturity


@pytest.mark.parametrize("crop", CROPS)
def test_eventi_in_ordine_cronologico_meteo_stagionale(pars, crop):
    f = make_forcing(seasonal())
    year = 2000 if crop != "frumento" else 2000
    cal = ph.cycle_calendar(pars, crop, f, sow_of(pars, crop, f, year))
    assert cal.status == ph.STATO_OK and cal.ok
    assert_ordered(cal)
    assert cal.n_days == cal.maturity - cal.sow + 1
    assert cal.harvest == cal.maturity
    ev = cal.events()
    assert list(ev) == ["sow", "emergence", "end_ini", "end_dev", "end_mid", "flowering", "maturity"]
    d = cal.as_dates(f["date"])
    assert d["sow"] <= d["emergence"] <= d["maturity"]


@pytest.mark.parametrize("crop", CROPS)
def test_eventi_alla_prima_soglia_raggiunta(pars, crop):
    """Ogni evento cade nel primo giorno in cui i GDD cumulati dalla semina raggiungono la
    soglia dei parametri; nessun giorno inventato."""
    f = make_forcing(seasonal())
    pp = ph.crop_pheno_params(pars, crop)
    gdd = ph.daily_gdd(f["tmean"].to_numpy(), pp.t_base, pp.t_upper)
    cal = ph.cycle_calendar(pars, crop, f, sow_of(pars, crop, f, 2000))
    for ev, key in EVENT_KEY.items():
        thr = float(fparams.get(pars, f"crops.{crop}.{key}"))
        i = getattr(cal, ev)
        assert i >= 0
        assert gdd[cal.sow:i + 1].sum() >= thr - 1e-9
        assert gdd[cal.sow:i].sum() < thr


@pytest.mark.parametrize("crop", CROPS)
def test_frazione_di_sviluppo(pars, crop):
    f = make_forcing(seasonal())
    cal = ph.cycle_calendar(pars, crop, f, sow_of(pars, crop, f, 2000))
    fr = cal.frac
    assert len(fr) == cal.n_days
    assert 0.0 <= fr[0] < 0.1
    assert fr[-1] == pytest.approx(1.0)
    assert (np.diff(fr) >= -1e-12).all()
    assert ((fr >= 0.0) & (fr <= 1.0)).all()
    assert cal.gdd_cum[-1] >= cal.gdd_maturita - 1e-9
    assert cal.breakpoints == ph.crop_pheno_params(pars, crop).breakpoints


@pytest.mark.parametrize("crop", ["mais", "soia"])
def test_ciclo_con_temperatura_costante_esatto(pars, crop):
    """T costante: il numero di giorni e' ceil(soglia / GDD giornalieri)."""
    pp = ph.crop_pheno_params(pars, crop)
    t = pp.t_base + 0.4 * (pp.t_upper - pp.t_base)
    g = t - pp.t_base
    f = constant(t)
    sow = 100
    cal = ph.cycle_calendar(pars, crop, f, sow)
    for ev, key in EVENT_KEY.items():
        thr = float(fparams.get(pars, f"crops.{crop}.{key}"))
        n = math.ceil(thr / g - 1e-9)           # giorni, semina compresa
        assert getattr(cal, ev) == sow + n - 1, ev
    assert cal.n_days == math.ceil(pp.gdd_maturita / g - 1e-9)


@pytest.mark.parametrize("crop", CROPS)
def test_meteo_piu_caldo_ciclo_piu_corto_costante(pars, crop):
    pp = ph.crop_pheno_params(pars, crop)
    t_fresco = pp.t_base + 0.3 * (pp.t_upper - pp.t_base)
    t_caldo = pp.t_base + 0.7 * (pp.t_upper - pp.t_base)
    c1 = ph.cycle_calendar(pars, crop, constant(t_fresco), 50)
    c2 = ph.cycle_calendar(pars, crop, constant(t_caldo), 50)
    assert c1.ok and c2.ok
    assert c2.n_days < c1.n_days
    assert c2.maturity < c1.maturity


@pytest.mark.parametrize("crop", ["mais", "soia", "frumento"])
def test_meteo_stagionale_scaldato_ciclo_piu_corto(pars, crop):
    base = make_forcing(seasonal(shift=0.0))
    caldo = make_forcing(seasonal(shift=3.0))
    sow = sow_of(pars, crop, base, 2000)
    c0 = ph.cycle_calendar(pars, crop, base, sow)
    c1 = ph.cycle_calendar(pars, crop, caldo, sow)
    assert c0.ok and c1.ok
    assert c1.n_days < c0.n_days


@pytest.mark.parametrize("crop", ["mais", "soia"])
def test_semina_posticipata_raccolta_non_anticipa(pars, crop):
    f = make_forcing(seasonal())
    s0 = sow_of(pars, crop, f, 2000)
    sows = np.arange(s0 - 30, s0 + 61)
    cals = ph.cycle_calendars(pars, crop, f, sows)
    mats = [c.maturity for c in cals]
    assert all(c.ok for c in cals)
    assert all(b >= a for a, b in zip(mats, mats[1:])), mats
    # la versione batch coincide con quella singola
    single = ph.cycle_calendar(pars, crop, f, int(sows[17]))
    assert single.events() == cals[17].events()
    tab = ph.event_table(pars, crop, f, sows)
    assert tab[:, -1].tolist() == mats


# =============================================================================
# Casi limite: fuori serie e oltre limite
# =============================================================================

@pytest.mark.parametrize("crop", CROPS)
def test_soglia_non_raggiunta_fuori_serie(pars, crop):
    pp = ph.crop_pheno_params(pars, crop)
    f = constant(pp.t_base + 1.0, n_days=120)          # 1 GDD/giorno: maturita' irraggiungibile
    cal = ph.cycle_calendar(pars, crop, f, 10)
    assert cal.status == ph.STATO_FUORI_SERIE
    assert not cal.ok
    assert cal.maturity == -1
    assert cal.n_days == 0
    assert cal.harvest == -1
    # nessun numero inventato: solo indici reali o -1
    for k, v in cal.events().items():
        assert v == -1 or (10 <= v < 120), (k, v)
    d = cal.as_dates(f["date"])
    assert pd.isna(d["maturity"])
    assert d["sow"] == f["date"][10]
    with pytest.raises(ValueError):
        ph.crop_daily_curves_gdd(pars, crop, cal)


def test_semina_all_ultimo_giorno_fuori_serie(pars):
    f = constant(20.0, n_days=200)
    cal = ph.cycle_calendar(pars, "mais", f, 199)
    assert cal.status == ph.STATO_FUORI_SERIE and cal.maturity == -1


@pytest.mark.parametrize("crop", ["mais", "frumento"])
def test_deadline_superato_oltre_limite(pars, crop):
    pp = ph.crop_pheno_params(pars, crop)
    f = constant(pp.t_base + 0.4 * (pp.t_upper - pp.t_base))
    sow = 100
    cal = ph.cycle_calendar(pars, crop, f, sow)
    assert cal.ok
    m = cal.maturity
    assert ph.cycle_calendar(pars, crop, f, sow, deadline_idx=m).status == ph.STATO_OK
    assert ph.cycle_calendar(pars, crop, f, sow, deadline_idx=m + 50).status == ph.STATO_OK
    over = ph.cycle_calendar(pars, crop, f, sow, deadline_idx=m - 1)
    assert over.status == ph.STATO_OLTRE_LIMITE
    assert not over.ok
    assert ph.cycle_calendars(pars, crop, f, [sow], deadline_idx=m - 1)[0].status == ph.STATO_OLTRE_LIMITE
    assert ph.cycle_calendars(pars, crop, f, [sow], deadline_idx=m)[0].status == ph.STATO_OK


# =============================================================================
# Curve Kc e radici (sintetico)
# =============================================================================

@pytest.mark.parametrize("crop", CROPS)
def test_curve_kc_radici_sintetiche(pars, crop):
    f = make_forcing(seasonal())
    cal = ph.cycle_calendar(pars, crop, f, sow_of(pars, crop, f, 2000))
    kc, zr, ptab = ph.crop_daily_curves_gdd(pars, crop, cal)
    check_curves(pars, crop, cal, kc, zr, ptab)


def check_curves(pars, crop, cal, kc, zr, ptab):
    g = lambda k: float(fparams.get(pars, f"crops.{crop}.{k}"))
    kc_ini, kc_mid, kc_end = g("kc.ini"), g("kc.mid"), g("kc.end")
    zr_ini, zr_max = g("zr_ini"), g("zr_max")
    assert len(kc) == len(zr) == len(ptab) == cal.n_days
    assert (kc >= min(kc_ini, kc_end) - 1e-9).all()
    assert (kc <= max(kc_mid, kc_ini, kc_end) + 1e-9).all()
    assert kc[0] == pytest.approx(kc_ini)
    assert kc[-1] == pytest.approx(kc_end)
    assert kc.max() == pytest.approx(kc_mid)
    assert (zr >= zr_ini - 1e-9).all() and (zr <= zr_max + 1e-9).all()
    assert (np.diff(zr) >= -1e-12).all(), "radici non decrescenti"
    assert zr[0] == pytest.approx(zr_ini, abs=0.05 * zr_max)
    assert zr[-1] == pytest.approx(zr_max)
    assert (ptab == g("p")).all()


def test_curve_correzione_climatica_neutra_e_ventosa(pars):
    f = make_forcing(seasonal())
    cal = ph.cycle_calendar(pars, "mais", f, sow_of(pars, "mais", f, 2000))
    kc0, _, _ = ph.crop_daily_curves_gdd(pars, "mais", cal)
    # u2 = 2 m/s e RHmin = 45 %: correzione nulla (FAO-56 eq. 62 e 65)
    kcn, _, _ = ph.crop_daily_curves_gdd(pars, "mais", cal, u2_mid=2.0, rhmin_mid=45.0,
                                         u2_end=2.0, rhmin_end=45.0)
    np.testing.assert_allclose(kcn, kc0, atol=1e-9)
    kcw, _, _ = ph.crop_daily_curves_gdd(pars, "mais", cal, u2_mid=5.0, rhmin_mid=25.0,
                                         u2_end=5.0, rhmin_end=25.0)
    assert kcw.max() > kc0.max(), "clima secco e ventoso alza Kc mid"
    assert kcw.max() < 1.5 and kcw.min() > 0.0


# =============================================================================
# Meteo reale del punto pilota
# =============================================================================

@pytest.fixture(scope="module")
def forcing():
    try:
        return weather.load_forcing(45.2, 10.0)
    except (CacheMiss, FileNotFoundError):
        pytest.skip("cache meteo del punto pilota assente")


def test_mais_semina_tipica_durata_reale(pars, forcing):
    n = {}
    for y in (2022, 2003, 2014):
        cal = ph.cycle_calendar(pars, "mais", forcing, sow_of(pars, "mais", forcing, y))
        assert cal.ok, y
        assert_ordered(cal)
        n[y] = cal.n_days
    assert n[2022] < n[2014] and n[2003] < n[2014]
    # riferimenti di regressione: 125, 126, 164 giorni
    assert n[2022] == pytest.approx(125, abs=3)
    assert n[2003] == pytest.approx(126, abs=3)
    assert n[2014] == pytest.approx(164, abs=3)


@pytest.mark.parametrize("crop,year", [("mais", 2022), ("mais", 2014), ("soia", 2015),
                                       ("frumento", 2010)])
def test_curve_reali(pars, forcing, crop, year):
    cal = ph.cycle_calendar(pars, crop, forcing, sow_of(pars, crop, forcing, year))
    assert cal.ok
    kc, zr, ptab = ph.crop_daily_curves_gdd(pars, crop, cal)
    check_curves(pars, crop, cal, kc, zr, ptab)
    kc_min = min(float(fparams.get(pars, f"crops.{crop}.kc.{k}")) for k in ("ini", "mid", "end"))
    assert kc.min() >= kc_min - 1e-9
    assert kc.max() <= 1.5, "Kc oltre il massimo ragionevole"
    assert np.isfinite(kc).all() and np.isfinite(zr).all()


def test_frumento_autunnale_ciclo_oltre_l_anno(pars, forcing):
    cal = ph.cycle_calendar(pars, "frumento", forcing, sow_of(pars, "frumento", forcing, 2010))
    assert cal.ok
    d = cal.as_dates(forcing["date"])
    assert d["sow"].year == 2010 and d["maturity"].year == 2011
    assert_ordered(cal)
