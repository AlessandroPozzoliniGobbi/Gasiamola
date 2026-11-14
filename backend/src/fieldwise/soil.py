"""Proprieta' idrauliche del suolo con le funzioni di pedotrasferimento di Saxton e Rawls (2006).

Fonte delle equazioni
---------------------
Saxton K.E., Rawls W.J. (2006). Soil water characteristic estimates by texture and
organic matter for hydrologic solutions. Soil Sci. Soc. Am. J. 70:1569-1578,
doi:10.2136/sssaj2005.0117 (Tabella 1, eq. 1-16).

L'articolo e' a pagamento e non e' stato letto direttamente. I coefficienti sono stati
trascritti da due riproduzioni ufficiali USDA, lette il 2026-11-11:

* USDA-ARS, modello WEPP, routine ``saxpar.for`` (S. Dun, verificata da J. Wu, 2008), che
  riporta accanto a ogni formula il numero di equazione dell'articolo (eq. 1, 2, 3, 5, 14,
  15, 16): https://infosys.ars.usda.gov/svn/code/weps1/branches/weps.src.wepp/src/lib_wepp/saxpar.for
* USDA Ag Data Commons, "Soil - Plant - Atmosphere - Water Field & Pond Hydrology"
  (doi:10.15482/USDA.ADC/1529226), foglio "Soil Water Characteristics-Equations.xls" di
  K. Saxton (rev. 2007). Contiene le soluzioni numeriche passo per passo per le 12 classi
  tessiturali con OM = 2,5 % (gli stessi esempi della tabella per classi dell'articolo) e
  un esempio con fattore di densita' 1,2. Con questo foglio sono state verificate
  numericamente le equazioni di densita' (sotto) e tutte le altre (tests/test_soil.py).

Unita': sabbia ``S`` e argilla ``C`` in frazione in peso (0-1) della terra fine;
sostanza organica ``OM`` in % in peso; contenuti idrici in m3/m3; Ksat in mm/h.

Campo di validita'
------------------
Le regressioni sono state ricavate da campioni di orizzonti A del database USDA/NRCS.
Il manuale SPAW (Saxton e Willey, USDA) le dichiara valide per argilla circa 0-60 % e
sabbia 0-95 %; la sostanza organica dei dati di calibrazione arriva a circa 8 % (limite
OM <= 8 % riportato dalla letteratura che riprende l'articolo, non letto nell'originale).
Fuori da questi limiti le funzioni NON tagliano gli ingressi: calcolano comunque e
segnalano con ``warnings.warn`` e con la chiave ``fuori_validita`` del risultato.
Il risultato deve rispettare wp < fc < sat; se cio' non accade (ingressi estremi) la
funzione solleva ``ValueError`` invece di restituire numeri non fisici.

Correzioni
----------
* Densita' (eq. di Tabella 1 per la compattazione, verificate sul foglio USDA): la densita'
  "normale" della matrice e' rho_N = (1 - theta_S) * 2,65; con un fattore DF = rho_misurata /
  rho_N si ha rho_DF = rho_N * DF, theta_S_DF = 1 - rho_DF / 2,65,
  theta_33_DF = theta_33 - 0,2 (theta_S - theta_S_DF); theta_1500 non cambia; Ksat si
  ricalcola con i valori corretti. DF ha senso tra 0,9 e 1,3 (intervallo del programma
  SPAW). Scelta di progetto: per default DF = 1 (nessuna correzione), perche' la densita'
  di SoilGrids e' una stima modellistica (non una misura) con intervallo q05-q95 di
  0,98-1,81 g/cm3, piu' ampio dell'intero intervallo di DF; la correzione e' disponibile per
  l'analisi di sensibilita' (``df``).
* Frammenti grossolani: la matrice fine trattiene l'acqua, lo scheletro no. Con frazione
  volumetrica di scheletro Rv (SoilGrids ``cfvo`` e' gia' in % del volume), i contenuti
  riferiti al volume totale di suolo sono theta_bulk = theta_matrice * (1 - Rv): e' la
  forma con cui il foglio USDA riduce l'acqua disponibile (con Rv = 1 l'acqua disponibile e
  Ksat diventano 0). La correzione di Ksat per lo scheletro (in funzione della frazione in
  peso) non e' stata letta in forma generale e NON e' applicata: Ksat resta quello della
  terra fine. Scelta di progetto: per default Rv = 0, perche' la carta ERSAF descrive i
  suoli della bassa pianura cremonese come "senza scheletro" e ``cfvo`` e' la proprieta'
  meno accurata di SoilGrids (MEC 0,31, Poggio et al. 2021, tab. 4).

Il modulo usa solo numpy e non dipende dal resto del motore.
"""
from __future__ import annotations

import math
import warnings
from typing import Iterable, Mapping, Sequence

import numpy as np

__all__ = [
    "saxton_rawls",
    "usda_texture_class",
    "horizons_from_aggregated",
    "profile_properties",
    "engine_layers",
    "aquacrop_tau",
    "hydrologic_soil_group",
    "VALIDITY",
]

# Campo di validita' dichiarato (vedi docstring del modulo).
VALIDITY = {"clay_max": 0.60, "sand_max": 0.95, "om_max": 8.0}

PARTICLE_DENSITY = 2.65  # g/cm3, densita' delle particelle minerali usata da Saxton e Rawls (eq. di densita')


def _validity_flags(S, C, OM):
    return (C > VALIDITY["clay_max"]) | (S > VALIDITY["sand_max"]) | (OM > VALIDITY["om_max"]) | (OM < 0) | (S < 0) | (C < 0)


def saxton_rawls(sand, clay, om, df: float | np.ndarray = 1.0, gravel_vol: float | np.ndarray = 0.0) -> dict:
    """Caratteristiche idrauliche di Saxton e Rawls (2006).

    Parametri
    ---------
    sand, clay : frazioni in peso della terra fine (0-1), scalari o array.
    om : sostanza organica, % in peso.
    df : fattore di densita' (rho_misurata / rho_normale); 1 = nessuna correzione.
    gravel_vol : frazione volumetrica di scheletro Rv (0-1); 0 = nessuna correzione.

    Restituisce un dizionario con array numpy (o float se gli ingressi sono scalari):
    ``wp`` (1500 kPa), ``fc`` (33 kPa), ``sat`` (0 kPa) in m3/m3 riferiti alla terra fine;
    ``wp_bulk``, ``fc_bulk``, ``sat_bulk`` riferiti al volume totale (con lo scheletro);
    ``ksat`` in mm/h (terra fine); ``rho_n`` densita' normale (g/cm3), ``rho_df`` densita'
    dopo la correzione; ``B``, ``A``, ``lam``; ``fuori_validita`` (bool).
    """
    S = np.asarray(sand, dtype=float)
    C = np.asarray(clay, dtype=float)
    OM = np.asarray(om, dtype=float)
    DF = np.asarray(df, dtype=float)
    RV = np.asarray(gravel_vol, dtype=float)
    scalar = all(np.ndim(x) == 0 for x in (sand, clay, om, df, gravel_vol))

    out_of_range = _validity_flags(S, C, OM)
    if np.any(out_of_range):
        warnings.warn(
            "Saxton-Rawls: ingressi fuori dal campo di validita' (argilla <= 60 %, sabbia <= 95 %, "
            "OM <= 8 %); i risultati sono estrapolati", stacklevel=2)
    if np.any((DF < 0.9) | (DF > 1.3)):
        warnings.warn("Saxton-Rawls: fattore di densita' fuori da 0,9-1,3", stacklevel=2)
    if np.any((RV < 0) | (RV >= 1)):
        raise ValueError("gravel_vol deve stare in [0, 1)")

    # Eq. 1: umidita' a 1500 kPa (punto di appassimento)
    t1500t = (-0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM
              + 0.068 * S * C + 0.031)
    wp = t1500t + (0.14 * t1500t - 0.02)
    # Eq. 2: umidita' a 33 kPa (capacita' di campo)
    t33t = (-0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM
            + 0.452 * S * C + 0.299)
    fc = t33t + (1.283 * t33t ** 2 - 0.374 * t33t - 0.015)
    # Eq. 3: umidita' tra saturazione e 33 kPa
    ts33t = (0.278 * S + 0.034 * C + 0.022 * OM - 0.018 * S * OM - 0.027 * C * OM
             - 0.584 * S * C + 0.078)
    ts33 = ts33t + (0.636 * ts33t - 0.107)
    # Eq. 5: saturazione (con la correzione per la sabbia)
    sat = fc + ts33 - 0.097 * S + 0.043
    # Eq. 6: densita' normale della matrice
    rho_n = (1.0 - sat) * PARTICLE_DENSITY

    # Correzione per la densita' (eq. di Tabella 1 per la compattazione; forme verificate sul foglio USDA)
    rho_df = rho_n * DF
    sat_df = 1.0 - rho_df / PARTICLE_DENSITY
    fc_df = fc - 0.2 * (sat - sat_df)
    wp_df = wp  # theta_1500 non e' corretto per la densita'

    if np.any(~((wp_df > 0) & (wp_df < fc_df) & (fc_df < sat_df))):
        raise ValueError("Saxton-Rawls: risultato non fisico (serve 0 < wp < fc < sat); ingressi estremi")

    # Eq. 15 e 14: parametri della curva tensione-umidita' tra 33 e 1500 kPa
    B = (math.log(1500.0) - math.log(33.0)) / (np.log(fc_df) - np.log(wp_df))
    A = np.exp(math.log(33.0) + B * np.log(fc_df))
    lam = 1.0 / B  # pendenza della curva log(tensione)-log(umidita'), Tabella 1
    # Eq. 16: conducibilita' idraulica satura, mm/h
    ksat = 1930.0 * (sat_df - fc_df) ** (3.0 - lam)

    keep = 1.0 - RV
    res = {
        "wp": wp_df, "fc": fc_df, "sat": sat_df, "ksat": ksat,
        "wp_bulk": wp_df * keep, "fc_bulk": fc_df * keep, "sat_bulk": sat_df * keep,
        "rho_n": rho_n, "rho_df": rho_df, "B": B, "A": A, "lam": lam,
        "fuori_validita": out_of_range,
    }
    if scalar:
        res = {k: (bool(v) if k == "fuori_validita" else float(v)) for k, v in res.items()}
    return res


# ------------------------------------------------------------------ classe tessiturale

def usda_texture_class(sand_pct: float, clay_pct: float, silt_pct: float | None = None) -> str:
    """Classe tessiturale USDA (nomi inglesi) da percentuali di sabbia, argilla, limo.

    Limiti dal glossario SSSA (Glossary of Soil Science Terms, voce "soil texture"), che
    riproduce il Soil Survey Manual USDA (Handbook 18, 1993). Se il limo non e' dato si usa
    100 - sabbia - argilla; le tre frazioni vengono rinormalizzate a 100.
    """
    if silt_pct is None:
        silt_pct = 100.0 - sand_pct - clay_pct
    tot = sand_pct + clay_pct + silt_pct
    if tot <= 0:
        raise ValueError("frazioni granulometriche non valide")
    sa, cl, si = (100.0 * x / tot for x in (sand_pct, clay_pct, silt_pct))

    if cl >= 40 and si >= 40:
        return "silty clay"
    if cl >= 35 and sa >= 45:
        return "sandy clay"
    if cl >= 40:
        return "clay"
    if 27 <= cl < 40 and sa < 20:
        return "silty clay loam"
    if 27 <= cl < 40 and sa <= 45:
        return "clay loam"
    if 20 <= cl < 35 and si < 28 and sa > 45:
        return "sandy clay loam"
    if sa >= 85 and si + 1.5 * cl <= 15:
        return "sand"
    if 70 <= sa <= 91 and si + 1.5 * cl >= 15 and si + 2 * cl < 30:
        return "loamy sand"
    if (7 <= cl < 20 and sa > 52 and si + 2 * cl >= 30) or (cl < 7 and si < 50 and si + 2 * cl >= 30):
        return "sandy loam"
    if si >= 80 and cl < 12:
        return "silt"
    if (si >= 50 and 12 <= cl < 27) or (50 <= si < 80 and cl < 12):
        return "silt loam"
    if 7 <= cl < 27 and 28 <= si < 50 and sa <= 52:
        return "loam"
    # residui sui bordi (es. argilla 27-35 % con sabbia > 45 % e limo >= 28 %)
    if cl >= 27:
        return "clay loam"
    return "loam"


# ------------------------------------------------------------------ profilo

def horizons_from_aggregated(table) -> list[dict]:
    """Orizzonti dal CSV aggregato di SoilGrids (``fieldwise.data.soilgrids.load_aggregated``).

    Accetta un DataFrame pandas (o un oggetto con ``to_dict('records')``) o una lista di
    righe con colonne ``property, layer, top_cm, bottom_cm, mean, q05, q95``. Restituisce
    una lista ordinata per profondita' di dizionari con sand/clay/silt (%), om (%),
    bdod (g/cm3), cfvo (% vol) e i rispettivi ``*_q05``, ``*_q95``.
    """
    rows = table.to_dict("records") if hasattr(table, "to_dict") else list(table)
    by_layer: dict = {}
    for r in rows:
        key = (int(r["top_cm"]), int(r["bottom_cm"]))
        d = by_layer.setdefault(key, {"top_cm": key[0], "bottom_cm": key[1], "layer": r["layer"]})
        d[r["property"]] = float(r["mean"])
        d[r["property"] + "_q05"] = float(r["q05"])
        d[r["property"] + "_q95"] = float(r["q95"])
    return [by_layer[k] for k in sorted(by_layer)]


def profile_properties(horizons: Sequence[Mapping], z_max_cm: float | None = None,
                       om_override: Mapping[int, float] | None = None,
                       apply_density: bool = False, apply_gravel: bool = False) -> list[dict]:
    """Proprieta' per orizzonte: fc, wp, sat (m3/m3), ksat (mm/h), acqua disponibile (mm).

    ``horizons``: lista di dizionari con top_cm, bottom_cm, sand, clay (%), om (%) e,
    se si applicano le correzioni, bdod (g/cm3) e cfvo (% vol).
    ``z_max_cm``: profondita' massima; gli orizzonti sotto sono tagliati.
    ``om_override``: {indice_orizzonte: OM %} per l'analisi di sensibilita'.
    L'acqua disponibile e' 10 * (fc - wp) * spessore_cm (mm), riferita al volume totale se
    ``apply_gravel`` (contenuti * (1 - Rv)), altrimenti alla terra fine.
    """
    out = []
    cum = 0.0
    for i, h in enumerate(horizons):
        top, bot = float(h["top_cm"]), float(h["bottom_cm"])
        if z_max_cm is not None:
            if top >= z_max_cm:
                break
            bot = min(bot, z_max_cm)
        om = om_override[i] if om_override and i in om_override else float(h["om"])
        sr0 = saxton_rawls(h["sand"] / 100.0, h["clay"] / 100.0, om)
        df = float(h["bdod"]) / sr0["rho_n"] if apply_density else 1.0
        rv = float(h["cfvo"]) / 100.0 if apply_gravel else 0.0
        sr = saxton_rawls(h["sand"] / 100.0, h["clay"] / 100.0, om, df=df, gravel_vol=rv)
        fc, wp, sat = (sr["fc_bulk"], sr["wp_bulk"], sr["sat_bulk"]) if apply_gravel else (sr["fc"], sr["wp"], sr["sat"])
        aw = 10.0 * (fc - wp) * (bot - top)
        cum += aw
        out.append({
            "top_cm": top, "bottom_cm": bot, "sand": h["sand"], "clay": h["clay"], "om": om,
            "texture": usda_texture_class(h["sand"], h["clay"], h.get("silt")),
            "fc": fc, "wp": wp, "sat": sat, "ksat": sr["ksat"], "rho_n": sr["rho_n"],
            "df": df, "gravel_vol": rv, "aw_mm": aw, "aw_cum_mm": cum,
            "fuori_validita": sr["fuori_validita"],
        })
    return out


def engine_layers(props: Sequence[Mapping], boundaries_cm: Iterable[float] = (0, 30, 150)) -> list[dict]:
    """Aggrega le proprieta' per orizzonte negli strati del motore (default 0-30, 30-150 cm).

    fc, wp, sat: media pesata sullo spessore (conserva l'acqua in mm). ksat: media armonica
    pesata (flusso verticale in serie). aw_mm: somma.
    """
    b = list(boundaries_cm)
    layers = []
    for top, bot in zip(b[:-1], b[1:]):
        w, fc, wp, sat, inv_k = 0.0, 0.0, 0.0, 0.0, 0.0
        for p in props:
            o = max(0.0, min(bot, p["bottom_cm"]) - max(top, p["top_cm"]))
            if o <= 0:
                continue
            w += o
            fc += o * p["fc"]
            wp += o * p["wp"]
            sat += o * p["sat"]
            inv_k += o / p["ksat"]
        if w < (bot - top) - 1e-9:
            raise ValueError(f"orizzonti insufficienti a coprire {top}-{bot} cm")
        layers.append({"top_cm": top, "bottom_cm": bot, "fc": fc / w, "wp": wp / w, "sat": sat / w,
                       "ksat": w / inv_k, "aw_mm": 10.0 * (fc - wp)})
    return layers


# ------------------------------------------------------------------ derivati

def aquacrop_tau(ksat_mm_h):
    """Coefficiente di drenaggio tau di AquaCrop (Reference Manual v7.3, cap. 3, eq. 3.7b).

    tau = 0,0866 * Ksat^0,35 con Ksat in mm/giorno, limitato a [0, 1].
    """
    k_day = np.asarray(ksat_mm_h, dtype=float) * 24.0
    tau = np.clip(0.0866 * k_day ** 0.35, 0.0, 1.0)
    return float(tau) if np.ndim(ksat_mm_h) == 0 else tau


def hydrologic_soil_group(ksat_um_s_0_50: float, ksat_um_s_0_100: float,
                          water_table_cm: float, impermeable_cm: float = math.inf) -> str:
    """Gruppo idrologico NRCS (NEH Part 630, cap. 7, tabella 7-1, gennaio 2009).

    ``ksat_um_s_0_50`` / ``ksat_um_s_0_100``: Ksat dello strato meno permeabile tra 0-50 e
    0-100 cm (micrometri/s). ``water_table_cm``: profondita' della falda alta stagionale.
    Per falda < 60 cm restituisce il gruppo duale non drenato (es. "C/D").
    """
    if impermeable_cm < 50:
        return "D"

    def shallow(k):  # soglie per Ksat di 0-50 cm (0-60 cm con falda < 60 cm)
        return "A" if k > 40 else "B" if k > 10 else "C" if k > 1 else "D"

    def deep(k):  # soglie per Ksat di 0-100 cm
        return "A" if k > 10 else "B" if k > 4 else "C" if k > 0.4 else "D"

    if impermeable_cm <= 100:
        g = shallow(ksat_um_s_0_50)
    elif 60 <= water_table_cm <= 100:
        g = shallow(ksat_um_s_0_50)
    else:  # falda < 60 cm oppure > 100 cm, strato impermeabile > 100 cm
        g = deep(ksat_um_s_0_100)
    if water_table_cm < 60 and g != "D":
        return f"{g}/D"
    return g
