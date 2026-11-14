"""Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998).

I numeri attesi sono quelli stampati nel manuale (capitoli 3 e 4); le tolleranze sono
quelle del progetto: 1% su ET0 e sugli intermedi, 2% dove il manuale arrotonda a due
cifre significative. Nessuna rete.
"""
import numpy as np
import pandas as pd
import pytest

from fieldwise import config
from fieldwise import et0 as e


def _lat(deg, minutes=0.0):
    return deg + minutes / 60.0


# --- Esempio 18 (cap. 4): Uccle, 6 luglio, ET0 giornaliera ---------------------
class TestEsempio18Uccle:
    LAT, ELEV, DOY = _lat(50, 48), 100.0, 187
    TMAX, TMIN, RHMAX, RHMIN = 21.5, 12.3, 84.0, 63.0
    WIND_10M_MS = 10.0 / 3.6      # 10 km/h a 10 m
    SUN_H = 9.25

    def test_vento_a_2m(self):
        assert e.wind_speed_2m(self.WIND_10M_MS, 10.0) == pytest.approx(2.078, rel=0.01)

    def test_pressione(self):
        assert e.atmospheric_pressure(self.ELEV) == pytest.approx(100.1, rel=0.01)

    def test_pressione_vapore_effettiva(self):
        ea = e.actual_vapour_pressure(self.TMAX, self.TMIN, rh_max=self.RHMAX,
                                      rh_min=self.RHMIN)
        assert ea == pytest.approx(1.409, rel=0.01)

    def test_radiazione_extraterrestre_e_durata_del_giorno(self):
        assert e.extraterrestrial_radiation(self.DOY, self.LAT) == pytest.approx(41.09, rel=0.01)
        assert e.daylight_hours(self.DOY, self.LAT) == pytest.approx(16.1, rel=0.01)

    def test_radiazione_solare_e_cielo_sereno(self):
        rs = e.solar_radiation_from_sunshine(self.SUN_H, self.DOY, self.LAT)
        assert rs == pytest.approx(22.07, rel=0.01)
        ra = e.extraterrestrial_radiation(self.DOY, self.LAT)
        assert e.clear_sky_radiation(ra, self.ELEV) == pytest.approx(30.90, rel=0.01)

    def test_radiazione_netta(self):
        rs = e.solar_radiation_from_sunshine(self.SUN_H, self.DOY, self.LAT)
        ea = e.actual_vapour_pressure(self.TMAX, self.TMIN, rh_max=self.RHMAX,
                                      rh_min=self.RHMIN)
        rn = e.net_radiation(rs, self.TMAX, self.TMIN, ea, self.DOY, self.LAT, self.ELEV)
        assert rn == pytest.approx(13.28, rel=0.01)

    def test_et0_penman_monteith(self):
        rs = e.solar_radiation_from_sunshine(self.SUN_H, self.DOY, self.LAT)
        u2 = e.wind_speed_2m(self.WIND_10M_MS, 10.0)
        et0 = e.et0_penman_monteith(self.TMAX, self.TMIN, rs, u2, self.DOY, self.LAT,
                                    self.ELEV, rh_max=self.RHMAX, rh_min=self.RHMIN)
        assert et0 == pytest.approx(3.88, rel=0.01)


# --- Esempio 17 (cap. 4, mensile): Bangkok, aprile -------------------------------
class TestEsempio17Bangkok:
    LAT, ELEV, DOY = _lat(13, 44), 2.0, 105
    TMAX, TMIN, EA, U2, SUN_H, G = 34.8, 25.6, 2.85, 2.0, 8.5, 0.14

    def test_intermedi(self):
        ra = e.extraterrestrial_radiation(self.DOY, self.LAT)
        assert ra == pytest.approx(38.06, rel=0.01)
        rs = e.solar_radiation_from_sunshine(self.SUN_H, self.DOY, self.LAT)
        assert rs == pytest.approx(22.65, rel=0.01)
        rn = e.net_radiation(rs, self.TMAX, self.TMIN, self.EA, self.DOY, self.LAT, self.ELEV)
        assert rn == pytest.approx(14.33, rel=0.01)

    def test_et0_con_flusso_di_calore_nel_suolo(self):
        rs = e.solar_radiation_from_sunshine(self.SUN_H, self.DOY, self.LAT)
        et0 = e.et0_penman_monteith(self.TMAX, self.TMIN, rs, self.U2, self.DOY, self.LAT,
                                    self.ELEV, ea=self.EA, g=self.G)
        assert et0 == pytest.approx(5.72, rel=0.01)


# --- Esempio 20 (cap. 4): Lione, 15 luglio, Penman-Monteith e Hargreaves -----------
class TestEsempio20Lione:
    LAT, ELEV, DOY = 45.72, 200.0, 196
    TMAX, TMIN, U2 = 26.6, 14.8, 2.0

    def _rs(self):
        ra = e.extraterrestrial_radiation(self.DOY, self.LAT)
        return 0.16 * np.sqrt(self.TMAX - self.TMIN) * ra

    def test_ra(self):
        assert e.extraterrestrial_radiation(self.DOY, self.LAT) == pytest.approx(40.55, rel=0.01)

    def test_penman_monteith_con_tdew_uguale_tmin(self):
        et0 = e.et0_penman_monteith(self.TMAX, self.TMIN, self._rs(), self.U2, self.DOY,
                                    self.LAT, self.ELEV, tdew=self.TMIN)
        assert et0 == pytest.approx(4.56, rel=0.01)

    def test_hargreaves(self):
        # il manuale riporta 5.0 (una cifra): tolleranza 2%
        et0 = e.et0_hargreaves(self.TMAX, self.TMIN, self.DOY, self.LAT)
        assert et0 == pytest.approx(5.0, rel=0.02)


# --- Capitolo 3 -----------------------------------------------------------------
class TestCapitolo3:
    def test_esempio_2_pressione_e_costante_psicrometrica(self):
        p = e.atmospheric_pressure(1800.0)
        assert p == pytest.approx(81.8, rel=0.01)
        assert e.psychrometric_constant(p) == pytest.approx(0.054, rel=0.02)

    def test_esempio_8_ra_emisfero_sud(self):
        assert e.extraterrestrial_radiation(246, -20.0) == pytest.approx(32.2, rel=0.01)

    def test_esempio_14_vento_a_2m(self):
        assert e.wind_speed_2m(3.2, 10.0) == pytest.approx(2.4, rel=0.02)


# --- comportamento -----------------------------------------------------------------
class TestComportamento:
    def test_ingressi_array(self):
        n = 5
        doy = np.full(n, 187)
        rs = np.full(n, 22.07)
        out = e.et0_penman_monteith(np.full(n, 21.5), np.full(n, 12.3), rs, np.full(n, 2.078),
                                    doy, 50.8, 100.0, rh_max=np.full(n, 84.0),
                                    rh_min=np.full(n, 63.0))
        assert isinstance(out, np.ndarray) and out.shape == (n,)
        assert np.allclose(out, out[0])
        hg = e.et0_hargreaves(np.full(n, 26.6), np.full(n, 14.8), doy, 45.72)
        assert hg.shape == (n,)

    def test_scalare_restituisce_float(self):
        assert isinstance(e.atmospheric_pressure(100.0), float)
        assert isinstance(e.et0_hargreaves(26.6, 14.8, 196, 45.72), float)

    def test_nan_in_ingresso_nan_in_uscita(self):
        tmax = np.array([21.5, np.nan, 21.5, 21.5])
        tmin = np.array([12.3, 12.3, np.nan, 12.3])
        rs = np.array([22.0, 22.0, 22.0, np.nan])
        out = e.et0_penman_monteith(tmax, tmin, rs, 2.0, 187, 50.8, 100.0, tdew=10.0)
        assert np.isfinite(out[0])
        assert np.isnan(out[1:]).all()
        assert np.isnan(e.et0_penman_monteith(np.nan, 12.3, 22.0, 2.0, 187, 50.8, 100.0,
                                              tdew=10.0))
        assert np.isnan(e.et0_hargreaves(np.nan, 12.3, 187, 50.8))
        assert np.isnan(e.wind_speed_2m(np.nan, 10.0))

    def test_errore_senza_dati_di_umidita(self):
        with pytest.raises(ValueError):
            e.actual_vapour_pressure(21.5, 12.3)
        with pytest.raises(ValueError):
            e.et0_penman_monteith(21.5, 12.3, 22.0, 2.0, 187, 50.8, 100.0)

    def test_hargreaves_nan_se_tmax_minore_di_tmin(self):
        assert np.isnan(e.et0_hargreaves(10.0, 15.0, 187, 45.0))

    def test_et0_from_power_forma_e_nan(self):
        dates = pd.date_range("2020-07-01", periods=3)
        df = pd.DataFrame({"date": dates, "tmax": [28.0, np.nan, 30.0],
                           "tmin": [16.0, 17.0, 18.0], "tmean": [22.0, 22.0, 24.0],
                           "rain": 0.0, "srad": [24.0, 24.0, np.nan], "rh": 60.0, "wind": 1.5})
        out = e.et0_from_power(df, 45.2, 170.78)
        assert list(out.columns) == ["date", "et0_pm", "et0_hargreaves"]
        assert len(out) == 3
        assert np.isfinite(out["et0_pm"].iloc[0]) and 2.0 < out["et0_pm"].iloc[0] < 8.0
        assert np.isnan(out["et0_pm"].iloc[1]) and np.isnan(out["et0_pm"].iloc[2])
        assert np.isnan(out["et0_hargreaves"].iloc[1]) and np.isfinite(out["et0_hargreaves"].iloc[2])


# --- dati reali del punto pilota -----------------------------------------------------
def test_et0_non_negativa_su_dati_reali():
    from fieldwise.data import cache, power
    lat, lon = config.PILOT_LAT, config.PILOT_LON
    try:
        df = power.load(lat, lon)
        site = power.load_site(lat, lon)
    except cache.CacheMiss:
        pytest.skip("POWER non in cache")
    df = df[df["date"].dt.year == 2024].reset_index(drop=True)
    assert len(df) >= 365
    out = e.et0_from_power(df, lat, site["elevation_m"])
    pm = out["et0_pm"].to_numpy()
    hg = out["et0_hargreaves"].to_numpy()
    assert np.isfinite(pm).all() and (pm >= 0).all()
    assert np.isfinite(hg).all() and (hg >= 0).all()
    assert 700 < np.nansum(pm) < 1400  # ordine di grandezza annuo plausibile in pianura padana
