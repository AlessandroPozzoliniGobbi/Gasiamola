"""Evapotraspirazione di riferimento giornaliera (coltura di riferimento a erba).

Metodo principale: FAO Penman-Monteith; confronto: Hargreaves.

Fonte unica: Allen R.G., Pereira L.S., Raes D., Smith M. (1998). *Crop
evapotranspiration - Guidelines for computing crop water requirements*. FAO
Irrigation and Drainage Paper 56, Roma. Capitolo 3 (dati meteorologici) e
capitolo 4 (calcolo di ET0). Testo HTML: https://www.fao.org/4/x0490e/x0490e00.htm
Ogni formula riporta accanto il numero di equazione di FAO-56 ("eq. N").
Le costanti numeriche sono quelle interne alle equazioni del manuale; qui non
c'e' alcun parametro agronomico.

Convenzioni
- Tutte le funzioni accettano scalari o array numpy (broadcasting) e restituiscono
  ``float``/``ndarray``; un NaN in ingresso produce NaN in uscita senza errori.
- Unita': temperature in degC, radiazione in MJ m-2 giorno-1, vento in m s-1,
  pressioni in kPa, quota in m, latitudine in gradi decimali (Sud negativa),
  ``doy`` = giorno dell'anno J (1..365/366).
- Temperatura media: per periodi di 24 ore FAO-56 (cap. 3, "Air temperature";
  eq. 9) definisce Tmean = (Tmax + Tmin)/2, non la media delle letture orarie.
  Questa e' la definizione usata di default.
- Passo giornaliero: flusso di calore nel suolo G = 0 (FAO-56 eq. 42).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "atmospheric_pressure",
    "psychrometric_constant",
    "saturation_vapour_pressure",
    "mean_saturation_vapour_pressure",
    "slope_vapour_pressure_curve",
    "actual_vapour_pressure",
    "inverse_relative_distance",
    "solar_declination",
    "sunset_hour_angle",
    "extraterrestrial_radiation",
    "daylight_hours",
    "solar_radiation_from_sunshine",
    "clear_sky_radiation",
    "net_shortwave_radiation",
    "net_longwave_radiation",
    "net_radiation",
    "wind_speed_2m",
    "et0_penman_monteith",
    "et0_hargreaves",
    "et0_from_power",
]

# --- costanti interne alle equazioni FAO-56 -----------------------------------
GSC = 0.0820            # costante solare, MJ m-2 min-1 (eq. 21)
SIGMA = 4.903e-9        # costante di Stefan-Boltzmann, MJ K-4 m-2 giorno-1 (eq. 39)
MJ_TO_MM = 0.408        # 1/lambda, lambda = 2.45 MJ kg-1: MJ m-2 g-1 -> mm g-1 (eq. 20)


def _a(x):
    return np.asarray(x, dtype=float)


def _out(x):
    x = np.asarray(x, dtype=float)
    return float(x) if x.ndim == 0 else x


# --- parametri atmosferici (cap. 3) -------------------------------------------
def atmospheric_pressure(elev_m):
    """Pressione atmosferica P [kPa] dalla quota z [m].

    FAO-56 eq. 7: P = 101.3 * ((293 - 0.0065 z) / 293) ** 5.26
    """
    z = _a(elev_m)
    return _out(101.3 * ((293.0 - 0.0065 * z) / 293.0) ** 5.26)


def psychrometric_constant(pressure_kpa):
    """Costante psicrometrica gamma [kPa degC-1].

    FAO-56 eq. 8: gamma = cp P / (eps lambda) = 0.665e-3 P
    (cp = 1.013e-3 MJ kg-1 degC-1, eps = 0.622, lambda = 2.45 MJ kg-1).
    """
    return _out(0.665e-3 * _a(pressure_kpa))


def saturation_vapour_pressure(t):
    """Pressione di vapore saturo e0(T) [kPa] alla temperatura T [degC].

    FAO-56 eq. 11: e0(T) = 0.6108 exp(17.27 T / (T + 237.3))
    """
    t = _a(t)
    return _out(0.6108 * np.exp(17.27 * t / (t + 237.3)))


def mean_saturation_vapour_pressure(tmax, tmin):
    """Pressione di vapore saturo media es [kPa].

    FAO-56 eq. 12: es = (e0(Tmax) + e0(Tmin)) / 2
    """
    return _out((_a(saturation_vapour_pressure(tmax)) + _a(saturation_vapour_pressure(tmin))) / 2.0)


def slope_vapour_pressure_curve(t):
    """Pendenza della curva di pressione di vapore saturo Delta [kPa degC-1].

    FAO-56 eq. 13: Delta = 4098 * 0.6108 exp(17.27 T/(T+237.3)) / (T + 237.3)**2
    """
    t = _a(t)
    return _out(4098.0 * (0.6108 * np.exp(17.27 * t / (t + 237.3))) / (t + 237.3) ** 2)


def actual_vapour_pressure(tmax, tmin, *, ea=None, tdew=None, rh_max=None, rh_min=None,
                           rh_mean=None):
    """Pressione di vapore effettiva ea [kPa], in ordine di preferenza FAO-56.

    1. ``ea`` misurata: usata cosi' com'e'.
    2. ``tdew`` (temperatura di rugiada): eq. 14, ea = e0(Tdew).
    3. ``rh_max`` e ``rh_min`` [%]: eq. 17,
       ea = (e0(Tmin) RHmax/100 + e0(Tmax) RHmin/100) / 2.
    4. solo ``rh_max`` [%]: eq. 18, ea = e0(Tmin) RHmax/100.
    5. ``rh_mean`` [%]: eq. 19, ea = RHmean/100 * (e0(Tmax) + e0(Tmin))/2
       (il manuale la indica come la meno preferibile tra le stime da RH).
    Senza alcun dato di umidita' solleva ValueError (FAO-56 eq. 48 suggerisce
    Tdew ~ Tmin, ma la scelta va fatta esplicitamente dal chiamante con ``tdew``).
    """
    if ea is not None:
        return _out(ea)
    if tdew is not None:
        return saturation_vapour_pressure(tdew)                      # eq. 14
    e_tmin = _a(saturation_vapour_pressure(tmin))
    e_tmax = _a(saturation_vapour_pressure(tmax))
    if rh_max is not None and rh_min is not None:                   # eq. 17
        return _out((e_tmin * _a(rh_max) / 100.0 + e_tmax * _a(rh_min) / 100.0) / 2.0)
    if rh_max is not None:                                          # eq. 18
        return _out(e_tmin * _a(rh_max) / 100.0)
    if rh_mean is not None:                                         # eq. 19
        return _out(_a(rh_mean) / 100.0 * (e_tmax + e_tmin) / 2.0)
    raise ValueError("serve uno tra ea, tdew, rh_max(+rh_min), rh_mean")


# --- radiazione (cap. 3) ------------------------------------------------------
def inverse_relative_distance(doy):
    """Inverso della distanza relativa Terra-Sole dr. FAO-56 eq. 23."""
    return _out(1.0 + 0.033 * np.cos(2.0 * np.pi * _a(doy) / 365.0))


def solar_declination(doy):
    """Declinazione solare delta [rad]. FAO-56 eq. 24."""
    return _out(0.409 * np.sin(2.0 * np.pi * _a(doy) / 365.0 - 1.39))


def sunset_hour_angle(lat_deg, doy):
    """Angolo orario al tramonto omega_s [rad].

    FAO-56 eq. 25: omega_s = arccos(-tan(phi) tan(delta)); l'argomento e'
    limitato a [-1, 1] per le latitudini polari (notte o giorno polare).
    """
    phi = np.deg2rad(_a(lat_deg))                                   # eq. 22 (gradi -> rad)
    x = -np.tan(phi) * np.tan(_a(solar_declination(doy)))
    return _out(np.arccos(np.clip(x, -1.0, 1.0)))


def extraterrestrial_radiation(doy, lat_deg):
    """Radiazione extraterrestre giornaliera Ra [MJ m-2 giorno-1].

    FAO-56 eq. 21:
    Ra = 24*60/pi * Gsc * dr * (ws sin(phi) sin(delta) + cos(phi) cos(delta) sin(ws))
    con dr (eq. 23), delta (eq. 24), ws (eq. 25), Gsc = 0.0820 MJ m-2 min-1.
    """
    phi = np.deg2rad(_a(lat_deg))
    dr = _a(inverse_relative_distance(doy))
    dec = _a(solar_declination(doy))
    ws = _a(sunset_hour_angle(lat_deg, doy))
    ra = 24.0 * 60.0 / np.pi * GSC * dr * (
        ws * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(ws))
    return _out(np.maximum(ra, 0.0))


def daylight_hours(doy, lat_deg):
    """Durata astronomica del giorno N [h]. FAO-56 eq. 34: N = 24/pi * ws."""
    return _out(24.0 / np.pi * _a(sunset_hour_angle(lat_deg, doy)))


def solar_radiation_from_sunshine(n_hours, doy, lat_deg, a_s=0.25, b_s=0.50):
    """Radiazione solare Rs [MJ m-2 giorno-1] dalle ore di sole effettive n.

    FAO-56 eq. 35 (Angstrom): Rs = (as + bs n/N) Ra; senza calibrazione locale
    il manuale raccomanda as = 0.25, bs = 0.50. N da eq. 34, Ra da eq. 21.
    """
    ra = _a(extraterrestrial_radiation(doy, lat_deg))
    big_n = _a(daylight_hours(doy, lat_deg))
    with np.errstate(invalid="ignore", divide="ignore"):
        return _out((a_s + b_s * _a(n_hours) / big_n) * ra)


def clear_sky_radiation(ra, elev_m):
    """Radiazione a cielo sereno Rso [MJ m-2 giorno-1].

    FAO-56 eq. 37: Rso = (0.75 + 2e-5 z) Ra  (as, bs non calibrati).
    """
    return _out((0.75 + 2e-5 * _a(elev_m)) * _a(ra))


def net_shortwave_radiation(rs, albedo=0.23):
    """Radiazione netta a onda corta Rns. FAO-56 eq. 38: Rns = (1 - alpha) Rs,
    alpha = 0.23 per la coltura di riferimento."""
    return _out((1.0 - albedo) * _a(rs))


def net_longwave_radiation(tmax, tmin, ea, rs, rso):
    """Radiazione netta a onda lunga uscente Rnl [MJ m-2 giorno-1].

    FAO-56 eq. 39:
    Rnl = sigma (Tmax,K^4 + Tmin,K^4)/2 * (0.34 - 0.14 sqrt(ea)) * (1.35 Rs/Rso - 0.35)
    con Rs/Rso limitato a <= 1.0 come prescritto dal manuale (testo di eq. 39).
    """
    tmax_k4 = (_a(tmax) + 273.16) ** 4
    tmin_k4 = (_a(tmin) + 273.16) ** 4
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.minimum(_a(rs) / _a(rso), 1.0)
    return _out(SIGMA * (tmax_k4 + tmin_k4) / 2.0
                * (0.34 - 0.14 * np.sqrt(_a(ea)))
                * (1.35 * ratio - 0.35))


def net_radiation(rs, tmax, tmin, ea, doy, lat_deg, elev_m, albedo=0.23):
    """Radiazione netta Rn [MJ m-2 giorno-1].

    FAO-56 eq. 40: Rn = Rns - Rnl, con Rns (eq. 38), Rnl (eq. 39),
    Rso (eq. 37), Ra (eq. 21).
    """
    ra = extraterrestrial_radiation(doy, lat_deg)
    rso = clear_sky_radiation(ra, elev_m)
    rns = _a(net_shortwave_radiation(rs, albedo))
    rnl = _a(net_longwave_radiation(tmax, tmin, ea, rs, rso))
    return _out(rns - rnl)


def wind_speed_2m(uz, z_m):
    """Vento a 2 m u2 [m s-1] dal vento uz misurato a quota z [m].

    FAO-56 eq. 47: u2 = uz * 4.87 / ln(67.8 z - 5.42)
    """
    return _out(_a(uz) * 4.87 / np.log(67.8 * _a(z_m) - 5.42))


# --- ET0 (cap. 4 e cap. 3) ----------------------------------------------------
def et0_penman_monteith(tmax, tmin, rs, u2, doy, lat_deg, elev_m, *, rh_mean=None,
                        rh_max=None, rh_min=None, tdew=None, ea=None, tmean=None,
                        albedo=0.23, g=0.0):
    """ET0 FAO Penman-Monteith [mm giorno-1].

    FAO-56 eq. 6:
    ET0 = (0.408 Delta (Rn - G) + gamma 900/(T + 273) u2 (es - ea))
          / (Delta + gamma (1 + 0.34 u2))

    - ``rs``: radiazione solare misurata/stimata [MJ m-2 g-1]; ``u2`` a 2 m
      [m s-1] (per altre quote usare ``wind_speed_2m``, eq. 47).
    - es: eq. 12 (media di e0(Tmax) ed e0(Tmin), sempre).
    - ea: in ordine di preferenza ``ea`` > ``tdew`` (eq. 14) > ``rh_max`` +
      ``rh_min`` (eq. 17) > solo ``rh_max`` (eq. 18) > ``rh_mean`` (eq. 19);
      vedi ``actual_vapour_pressure``.
    - T (in Delta, eq. 13, e nel termine 900/(T+273)): per default
      Tmean = (Tmax + Tmin)/2 (FAO-56 eq. 9). Se si passa ``tmean`` questo
      sostituisce la media di massima e minima soltanto in Delta e in
      900/(T+273); es, Rnl e le stime di ea restano basate su Tmax e Tmin.
      Scostarsi dalla definizione FAO-56 e' una scelta del chiamante.
    - Rn: eq. 40 (eq. 38, 39 con Rs/Rso <= 1, eq. 37, eq. 21), alla quota
      ``elev_m``; P (eq. 7) e gamma (eq. 8) alla stessa quota.
    - G: 0 a passo giornaliero (eq. 42). ``g`` [MJ m-2 g-1] serve solo per
      passi mensili (eq. 43/44, calcolati dal chiamante), es. Esempio 17.
    """
    tmax = _a(tmax)
    tmin = _a(tmin)
    t = (tmax + tmin) / 2.0 if tmean is None else _a(tmean)          # eq. 9
    p = atmospheric_pressure(elev_m)                                  # eq. 7
    gamma = _a(psychrometric_constant(p))                             # eq. 8
    delta = _a(slope_vapour_pressure_curve(t))                        # eq. 13
    es = _a(mean_saturation_vapour_pressure(tmax, tmin))              # eq. 12
    e_a = _a(actual_vapour_pressure(tmax, tmin, ea=ea, tdew=tdew, rh_max=rh_max,
                                    rh_min=rh_min, rh_mean=rh_mean))  # eq. 14/17/18/19
    rn = _a(net_radiation(rs, tmax, tmin, e_a, doy, lat_deg, elev_m, albedo))  # eq. 40
    u2 = _a(u2)
    num = MJ_TO_MM * delta * (rn - _a(g)) + gamma * 900.0 / (t + 273.0) * u2 * (es - e_a)
    den = delta + gamma * (1.0 + 0.34 * u2)
    return _out(num / den)                                            # eq. 6


def et0_hargreaves(tmax, tmin, doy, lat_deg):
    """ET0 di Hargreaves [mm giorno-1] (metodo di ripiego del manuale).

    FAO-56 eq. 52: ET0 = 0.0023 (Tmean + 17.8) (Tmax - Tmin)^0.5 Ra,
    con Ra espressa in mm giorno-1 (Ra [MJ] x 0.408, eq. 20) e
    Tmean = (Tmax + Tmin)/2 (eq. 9). Se Tmax < Tmin il risultato e' NaN.
    """
    tmax = _a(tmax)
    tmin = _a(tmin)
    ra_mm = MJ_TO_MM * _a(extraterrestrial_radiation(doy, lat_deg))  # eq. 21, eq. 20
    tmean = (tmax + tmin) / 2.0                                      # eq. 9
    with np.errstate(invalid="ignore"):
        return _out(0.0023 * (tmean + 17.8) * np.sqrt(tmax - tmin) * ra_mm)  # eq. 52


def et0_from_power(df: pd.DataFrame, lat_deg: float, elev_m: float) -> pd.DataFrame:
    """ET0 giornaliera dalla tabella meteo del progetto (NASA POWER).

    Ingresso: colonne ``date, tmax, tmin, tmean, rain, srad, rh, wind``
    (degC, degC, degC, mm/g, MJ m-2 g-1, UR media %, vento a 2 m in m/s).
    Uscita: DataFrame ``date, et0_pm, et0_hargreaves`` [mm giorno-1].

    Scelte: ea da UR media (eq. 19, l'unica umidita' disponibile in POWER);
    T = (Tmax + Tmin)/2 come da FAO-56 (eq. 9), la colonna ``tmean`` di POWER
    (media oraria T2M) non e' usata; G = 0. Valori mancanti -> NaN, nessun
    riempimento.
    """
    dates = pd.to_datetime(df["date"])
    doy = dates.dt.day_of_year.to_numpy()
    pm = et0_penman_monteith(df["tmax"].to_numpy(float), df["tmin"].to_numpy(float),
                             df["srad"].to_numpy(float), df["wind"].to_numpy(float),
                             doy, lat_deg, elev_m, rh_mean=df["rh"].to_numpy(float))
    hg = et0_hargreaves(df["tmax"].to_numpy(float), df["tmin"].to_numpy(float), doy, lat_deg)
    return pd.DataFrame({"date": df["date"].to_numpy(),
                         "et0_pm": np.atleast_1d(pm),
                         "et0_hargreaves": np.atleast_1d(hg)})
