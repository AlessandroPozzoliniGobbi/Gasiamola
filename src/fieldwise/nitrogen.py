"""Bilancio di massa dell'azoto del suolo a passo giornaliero (FIELDWISE).

Specifica: params/nitrogen.yaml, _meta.equazioni (stati, azoto_bilancio_segmento,
humus_henin_dupuis) e params/cover_crop.yaml (biomassa_e_azoto, humus). Un segmento e'
una coltura dalla semina alla raccolta, un intervallo di suolo nudo o una cover crop;
lo stato passa da un segmento al successivo e non si azzera mai (PLAN.md, D6).

Stato (`NState`, kg N/ha salvo H):
  n_min  azoto minerale nel profilo radicale
  n_res  azoto organico dei residui freschi (colture e cover) non ancora mineralizzati
  n_cov  azoto nella cover viva (0 a ogni confine di segmento: la cover e' terminata a
         fine del suo segmento)
  h      humus [t SO/ha] nello strato dell'humus (fieldwise.humus); N_hum = h n_humus 1000
  cred   credito di precessione in attesa [kg N/ha], fissato alla raccolta e applicato al
         primo segmento colturale successivo (Tab. 4 ER)

Nucleo giornaliero (`run_daily`, numba; _meta.equazioni.azoto_bilancio_segmento, versione a
passo giornaliero): ogni giorno mineralizzazione dell'humus e deposizione (tasso annuo / 365),
rilascio programmato di N_res (uniforme in suolo.residui.giorni_rilascio giorni da ogni apporto),
assorbimento della coltura u_d = U q_d (U = resa n_assorbito, q_d = ETa/ET0 normalizzato sul
ciclo), concime che copre il deficit del giorno (mais, frumento) o fissazione fino a
quota_max U (soia), assorbimento della cover, lisciviazione SWAT con la percolazione del
giorno; alla raccolta EXP, residui e umificazione; alla terminazione della cover Npd e
umificazione. Stato in piu' durante il ciclo: N_pl (azoto nella coltura). Chiusura giornaliera:
DEP + FERT + FIX - (EXP + L + DISP + PERD_F) = d(N_min + N_res + N_cov + N_pl + N_hum).
`update_segment` resta come involucro: un segmento con D e assorbimento uniformi.

Nessun numero agronomico vive qui: tutto da params/*.yaml (letti una volta in
`NitrogenParams`). Restano solo conversioni di unita' (1000 kg/t).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from typing import Iterable, Mapping

from . import humus as _humus
from . import params as _params
from . import water as _water

SEG_CROP = "coltura"
SEG_BARE = "nudo"
SEG_COVER = "cover"
LEGUME = "soia"
OXYGEN = {"scarso": 0, "moderato": 1, "buono": 2}  # colonne di fattore_dispersione
_KG_T = 1000.0


@dataclass(frozen=True, slots=True)
class NState:
    """Stato azoto-humus (vedi docstring del modulo). Immutabile: gli aggiornamenti
    restituiscono un nuovo stato."""
    n_min: float
    n_res: float
    n_cov: float
    h: float
    cred: float = 0.0

    def n_hum(self, n_humus: float) -> float:
        """Azoto contenuto nell'humus [kg N/ha] = H n_humus 1000 (_meta.equazioni.stati)."""
        return self.h * n_humus * _KG_T


@dataclass(frozen=True)
class NitrogenParams:
    """Parametri dell'azoto letti una volta sola (`nitrogen_params`).

    Per coltura (dizionari): n_ass, n_asp [kg N/t]; rec (recupero apparente) [-];
    cred_int, cred_asp [kg N/ha] (credito di precessione con residui interrati/asportati);
    mas_base [kg N/ha], mas_rif [t/ha], mas_corr [kg N/t].
    Soia: fix_quota [-]. Suolo: disp [-], dep
    [kg N/ha/anno], anion_excl [-], sat_mm [mm], eff_norm [-]. Cover: cov_n_ass
    [kg N/ha], cov_npd [kg N/t s.s.], cov_eff [-], cov_rid_lisc [min, max].
    n_min0 [kg N/ha] azoto minerale iniziale; rel_days [g normalizzati] durata del rilascio
    dell'N dei residui e delle immobilizzazioni. hp: parametri dell'humus. q10 [-]: fattore
    di temperatura di mineralizzazione e rilascio (`temperature_factor`; 1 = nessun effetto).
    """
    n_ass: dict
    n_asp: dict
    rec: dict
    cred_int: dict
    cred_asp: dict
    mas_base: dict
    mas_rif: dict
    mas_corr: dict
    fix_quota: float
    disp: float
    dep: float
    anion_excl: float
    sat_mm: float
    eff_norm: float
    cov_n_ass: float
    cov_npd: float
    cov_eff: float
    cov_rid_lisc: tuple
    n_min0: float
    rel_days: int
    hp: _humus.HumusParams
    q10: float = 1.0

    @property
    def n_per_t_humus(self) -> float:
        """kg N per t SO = n_humus x 1000."""
        return self.hp.n_humus * _KG_T


def _credit(p: dict, crop: str) -> tuple[float, float]:
    """(credito con residui interrati, con residui asportati) da nitrogen.<crop>.credito_precessione
    (Tab. 4 ER). Un valore unico (soia) vale per entrambe le gestioni."""
    node = _params.get(p, f"nitrogen.{crop}.credito_precessione")
    if not isinstance(node, dict):
        return float(node), float(node)
    k_int = next(k for k in node if "interrat" in k)
    k_asp = next(k for k in node if "asportat" in k)
    return float(node[k_int]), float(node[k_asp])


def _recovery(p: dict, crop: str) -> float:
    """recupero_apparente della coltura; la soia usa quello del frumento (_meta passo 2)."""
    key = "frumento" if crop == LEGUME else crop
    return float(_params.get(p, f"nitrogen.efficienza_concime.recupero_apparente.{key}"))


def _mas(p: dict, crop: str) -> tuple[float, float, float]:
    """(MAS base, resa di riferimento, fattore correttivo) da nitrogen.vincoli.mas; per la
    soia (nessuna resa di riferimento) MAS fisso."""
    g = _params.get
    base = float(g(p, f"nitrogen.vincoli.mas.{crop}"))
    try:
        rif = float(g(p, f"nitrogen.vincoli.mas.{crop}_resa_riferimento"))
        corr = float(g(p, f"nitrogen.vincoli.mas.{crop}_fattore_correttivo"))
    except KeyError:
        rif, corr = math.inf, 0.0
    return base, rif, corr


def initial_n_min(p: dict, classe: str) -> float:
    """N_min iniziale = n_pronto[classe] x N_totale [g/kg] (nitrogen.suolo.n_pronto, Tab. 2 ER).

    N_totale: soil.strati_soilgrids.s0_30.azoto_totale se esiste; altrimenti (parametro
    mancante, segnalato) derivato dalla SO: N_tot [g/kg] = SO% x 10 x n_humus."""
    g = _params.get
    try:
        ntot = float(g(p, "soil.strati_soilgrids.s0_30.azoto_totale"))
    except KeyError:
        ntot = float(g(p, "soil.strati_soilgrids.s0_30.sostanza_organica")) * 10.0 \
            * float(g(p, "nitrogen.suolo.n_humus"))
    return float(g(p, f"nitrogen.suolo.n_pronto.{classe}")) * ntot


def nitrogen_params(p: dict | None = None, soil: _water.SoilWaterParams | None = None,
                    classe: str | None = None, ossigeno: str = "buono",
                    cn: float | None = None) -> NitrogenParams:
    """Legge una volta tutti i parametri dell'azoto e dell'humus.

    classe: classe ER di tessitura (default da soil.yaml, `humus.texture_class`);
    ossigeno: 'scarso' | 'moderato' | 'buono' (default 'buono', come prescrive la nota di
    nitrogen.suolo.fattore_dispersione in mancanza di cartografia); cn: C/N del suolo
    (default `humus.soil_cn`); soil: parametri idrici per SAT_mm (default da params).
    """
    p = _params.load_params() if p is None else p
    g = _params.get
    classe = _humus.texture_class(p) if classe is None else classe
    soil = _water.soil_from_params(p) if soil is None else soil
    crops = _humus.CROPS
    creds = {c: _credit(p, c) for c in crops}
    mas = {c: _mas(p, c) for c in crops}
    fx = "nitrogen.soia.fissazione"
    rid = g(p, "cover_crop.biomassa_e_azoto.riduzione_lisciviazione")
    node = p["cover_crop"]["biomassa_e_azoto"]["riduzione_lisciviazione"]
    rid_int = tuple(float(x) for x in node.get("intervallo", [rid, rid]))
    return NitrogenParams(
        n_ass={c: float(g(p, f"nitrogen.{c}.n_assorbito")) for c in crops},
        n_asp={c: float(g(p, f"nitrogen.{c}.n_asportato")) for c in crops},
        rec={c: _recovery(p, c) for c in crops},
        cred_int={c: creds[c][0] for c in crops},
        cred_asp={c: creds[c][1] for c in crops},
        mas_base={c: mas[c][0] for c in crops},
        mas_rif={c: mas[c][1] for c in crops},
        mas_corr={c: mas[c][2] for c in crops},
        fix_quota=float(g(p, f"{fx}.quota_fissazione_max")),
        disp=float(g(p, f"nitrogen.suolo.fattore_dispersione.{classe}")[OXYGEN[ossigeno]]),
        dep=float(g(p, "nitrogen.deposizione_atmosferica")),
        anion_excl=float(g(p, "nitrogen.lisciviazione.anion_excl")),
        sat_mm=float(soil.sat_mm),
        eff_norm=float(g(p, "nitrogen.efficienza_concime.minerale_convenzione_normativa")),
        cov_n_ass=float(g(p, "cover_crop.biomassa_e_azoto.n_assorbito")),
        cov_npd=float(g(p, "cover_crop.biomassa_e_azoto.npd_per_t_ss")),
        cov_eff=float(g(p, "cover_crop.biomassa_e_azoto.efficienza_campo")),
        cov_rid_lisc=rid_int,
        n_min0=initial_n_min(p, classe),
        rel_days=int(g(p, "nitrogen.suolo.residui.giorni_rilascio")),
        hp=_humus.humus_params(p, classe, cn),
        q10=float(g(p, "nitrogen.suolo.temperatura.q10")),
    )


def temperature_factor(tmean, q10: float) -> np.ndarray:
    """f_T = q10^((T - T_media)/10) normalizzato a media 1 sulla serie (nitrogen.suolo.temperatura):
    sposta nell'anno mineralizzazione e rilascio senza cambiarne il totale. Giorni senza dato: 1."""
    t = np.asarray(tmean, dtype=np.float64)
    ok = np.isfinite(t)
    f = np.ones_like(t)
    if q10 == 1.0 or not ok.any():
        return f
    f[ok] = q10 ** ((t[ok] - t[ok].mean()) / 10.0)
    f[ok] /= f[ok].mean()
    return f


def initial_state(npar: NitrogenParams) -> NState:
    """Stato iniziale: N_min da n_pronto (Tab. 2 ER), N_res = N_cov = 0, H = H0, nessun credito."""
    return NState(n_min=npar.n_min0, n_res=0.0, n_cov=0.0,
                  h=_humus.initial_humus(npar.hp), cred=0.0)


def mas_limit(crop: str, resa: float, npar: NitrogenParams) -> float:
    """MAS [kg N efficiente/ha] = base + max(resa - resa_rif, 0) x fattore_correttivo
    (D.g.r. Lombardia XII/4284, All. 2 Tab. 1 e nota 112: superabile solo con rese maggiori)."""
    return npar.mas_base[crop] + max(resa - npar.mas_rif[crop], 0.0) * npar.mas_corr[crop]


def leaching_fraction(dp_mm: float, npar: NitrogenParams) -> float:
    """1 - exp(-D / ((1 - anion_excl) SAT_mm)) (SWAT 2009, eq. 4:2.1.2 e 4:2.1.8)."""
    if dp_mm <= 0.0:
        return 0.0
    return 1.0 - math.exp(-dp_mm / ((1.0 - npar.anion_excl) * npar.sat_mm))


# ------------------------------------------------------------- nucleo giornaliero
# colonne della matrice delle somme per segmento del nucleo
(_C_MIN, _C_DISP, _C_DEP, _C_HMIN, _C_REL, _C_U, _C_USOIL, _C_FIX, _C_DEFN, _C_DEF, _C_FERT,
 _C_PERD, _C_UCOV, _C_L, _C_EXP, _C_RN, _C_UEFF, _C_NUMIF, _C_IMMUMIF, _C_HRES, _C_HCOV,
 _C_CRED, _C_CREDEFF, _C_IMMCRED, _C_IMMCOV, _C_RILNPD, _C_COVBIO, _C_NUMIFCOV,
 _C_NMIN0, _C_NRES0, _C_NCOV0, _C_H0, _C_NMIN1, _C_NRES1, _C_NCOV1, _C_H1) = range(36)
_NCOL = 36
KIND_CODE = {SEG_CROP: 0, SEG_COVER: 1, SEG_BARE: 2}


@_water.njit(cache=True)
def _schedule(rate, amount, start, ndays, ft):
    """Rilascio di ``amount`` in ``ndays`` giorni normalizzati da ``start``: quota del giorno j =
    amount ft[j] / ndays finche' la somma di ft arriva a ndays (con ft = 1: uniforme in ndays
    giorni di calendario). Conserva la massa entro la fine di ``rate``."""
    if amount <= 0.0:
        return
    acc = 0.0
    j = start
    m = rate.shape[0]
    while acc < ndays and j < m:
        w = ft[j]
        if acc + w > ndays:
            w = ndays - acc
        rate[j] += amount * w / ndays
        acc += w
        j += 1


@_water.njit(cache=True)
def _humify_fresh(fresh, n_min, h_add, nph):
    """N_umif = H_add n_humus 1000 preso dall'N fresco dei residui; il deficit da N_min
    (immobilizzazione per umificazione); se non basta H_add si riduce. -> (fresh, n_min,
    h_add, n_umif, imm)."""
    n_umif = h_add * nph
    imm = 0.0
    if fresh >= n_umif:
        fresh -= n_umif
    else:
        short = n_umif - fresh
        fresh = 0.0
        imm = min(short, max(n_min, 0.0))
        n_min -= imm
        short -= imm
        if short > 0.0:
            n_umif -= short
            h_add = n_umif / nph if nph > 0.0 else 0.0
    return fresh, n_min, h_add, n_umif, imm


@_water.njit(cache=True)
def _kernel(seg, kind, dp, share, u_tot, legume, rec, resa, n_asp, hres_pot, cred_next,
            asport, k2, h_tetto, nph, disp_f, dep_day, lf_den, fix_quota, cov_bio_ref,
            cov_nref, cov_npd, cov_eff, cov_h_per_t, ndays_rel, inv_days, ft,
            n_min, n_res, n_cov, h, cred, o_l, o_nmin, o_res, S):
    n = seg.shape[0]
    rate = np.zeros(n + ndays_rel + 2)      # ft ha la stessa lunghezza (1 oltre la serie)
    _schedule(rate, n_res, 0, ndays_rel, ft)
    n_pl = 0.0
    fix_cum = 0.0
    for i in range(n):
        k = seg[i]
        knd = kind[k]
        start = i == 0 or seg[i - 1] != k
        end = i == n - 1 or seg[i + 1] != k
        t0 = n_min + n_res + n_cov + n_pl + h * nph
        e_in = 0.0
        e_out = 0.0
        if start:
            S[k, _C_NMIN0] = n_min
            S[k, _C_NRES0] = n_res
            S[k, _C_NCOV0] = n_cov
            S[k, _C_H0] = h
            if knd == 0:
                fix_cum = 0.0
                n_pl = 0.0
                c = cred
                cred = 0.0
                S[k, _C_CRED] = c
                if c < 0.0:          # immobilizzazione del credito negativo, poi rilascio
                    x = min(-c, max(n_min, 0.0))
                    n_min -= x
                    n_res += x
                    _schedule(rate, x, i, ndays_rel, ft)
                    S[k, _C_IMMCRED] += x
                    S[k, _C_CREDEFF] = -x
                elif c > 0.0 and n_res > 0.0:   # credito positivo: anticipo del rilascio
                    x = min(c, n_res)
                    f = 1.0 - x / n_res
                    for j in range(i, rate.shape[0]):
                        rate[j] *= f
                    n_res -= x
                    n_min += x
                    S[k, _C_CREDEFF] = x
        # 1) mineralizzazione dell'humus, dispersione, deposizione (tassi annui / 365)
        hm = k2 * min(h, h_tetto) * inv_days * ft[i]
        mn = hm * nph
        ds = disp_f * mn
        h -= hm
        n_min += mn - ds + dep_day
        e_in += dep_day
        e_out += ds
        S[k, _C_HMIN] += hm
        S[k, _C_MIN] += mn
        S[k, _C_DISP] += ds
        S[k, _C_DEP] += dep_day
        # 1bis) rilascio dei residui e delle immobilizzazioni programmato
        r = rate[i]
        if r > n_res:
            r = n_res
        if r > 0.0:
            n_res -= r
            n_min += r
            S[k, _C_REL] += r
        # 2) assorbimento
        if knd == 0:
            u = u_tot[k] * share[i]
            us = min(u, max(n_min, 0.0))
            n_min -= us
            n_pl += us
            S[k, _C_U] += u
            S[k, _C_USOIL] += us
            if legume[k] != 0:
                fx = min(u - us, fix_quota * u_tot[k] - fix_cum)
                if fx < 0.0:
                    fx = 0.0
                fix_cum += fx
                n_pl += fx
                e_in += fx
                S[k, _C_FIX] += fx
                S[k, _C_DEFN] += u - us - fx
            else:
                d = u - us
                fert = d / rec[k]
                perd = fert - d
                n_pl += d                     # la pianta preleva d dal concime
                e_in += fert
                e_out += perd
                S[k, _C_DEF] += d
                S[k, _C_FERT] += fert
                S[k, _C_PERD] += perd
        elif knd == 1:
            uc = min(cov_nref * share[i], max(n_min, 0.0))
            n_min -= uc
            n_cov += uc
            S[k, _C_UCOV] += uc
        # 3) lisciviazione del giorno (SWAT eq. 4:2.1.2 al passo giornaliero)
        lch = 0.0
        if dp[i] > 0.0 and n_min > 0.0:
            lch = n_min * (1.0 - math.exp(-dp[i] / lf_den))
            n_min -= lch
        e_out += lch
        S[k, _C_L] += lch
        o_l[i] = lch
        # 4) raccolta o terminazione
        if end:
            if knd == 0:
                u_eff = n_pl
                ex = resa[k] * n_asp[k] * (u_eff / u_tot[k]) if u_tot[k] > 0.0 else 0.0
                rn = u_eff - ex
                h_add = hres_pot[k]
                if asport[k] != 0:
                    ex += rn
                    rn = 0.0
                    h_add = 0.0
                n_pl = 0.0
                e_out += ex
                fresh, n_min, h_add, nu, im = _humify_fresh(rn, n_min, h_add, nph)
                h += h_add
                n_res += fresh
                _schedule(rate, fresh, i + 1, ndays_rel, ft)
                cred = cred_next[k]
                S[k, _C_UEFF] = u_eff
                S[k, _C_EXP] += ex
                S[k, _C_RN] += rn
                S[k, _C_NUMIF] += nu
                S[k, _C_IMMUMIF] += im
                S[k, _C_HRES] += h_add
            elif knd == 1:
                ss = cov_bio_ref * S[k, _C_UCOV] / cov_nref if cov_nref > 0.0 else 0.0
                fresh = n_cov
                n_cov = 0.0
                imm = cov_npd * ss
                if imm < 0.0:              # immobilizzazione da N_min alla terminazione
                    x = min(-imm, max(n_min, 0.0))
                    n_min -= x
                    fresh += x
                    S[k, _C_IMMCOV] += x
                else:                      # cover leguminose: rilascio immediato
                    x = min(cov_eff * imm, fresh)
                    fresh -= x
                    n_min += x
                    S[k, _C_RILNPD] += x
                fresh, n_min, h_add, nu, im = _humify_fresh(fresh, n_min, cov_h_per_t * ss, nph)
                h += h_add
                n_res += fresh
                _schedule(rate, fresh, i + 1, ndays_rel, ft)
                S[k, _C_COVBIO] = ss
                S[k, _C_NUMIFCOV] += nu
                S[k, _C_IMMUMIF] += im
                S[k, _C_HCOV] += h_add
            S[k, _C_NMIN1] = n_min
            S[k, _C_NRES1] = n_res
            S[k, _C_NCOV1] = n_cov + n_pl
            S[k, _C_H1] = h
        t1 = n_min + n_res + n_cov + n_pl + h * nph
        o_res[i] = (t1 - t0) - (e_in - e_out)
        o_nmin[i] = n_min
    return n_min, n_res, n_cov, h, cred, n_pl


@dataclass
class DailyResult:
    """Uscite giornaliere del nucleo: lisciviazione l, N_min a fine giorno, scarto di chiusura
    giornaliero [kg N/ha] (deve essere ~0)."""
    l: np.ndarray
    n_min: np.ndarray
    residuo: np.ndarray


def run_daily(state: NState, segment, kinds, crops, rese, dp, share, npar: NitrogenParams,
              residui_asportati=False, f_temp=None) -> tuple[NState, list, DailyResult]:
    """Bilancio dell'azoto e dell'humus a passo giornaliero su tutta la serie (una chiamata
    per rotazione, dopo il bilancio idrico; _meta.equazioni.azoto_bilancio_giornaliero).

    segment: indice del segmento per giorno (0..nseg-1, contigui); kinds: SEG_* per segmento;
    crops: coltura per segmento (None fuori dalle colture); rese: resa [t/ha] per segmento
    (ignorata fuori dalle colture); dp: percolazione profonda giornaliera [mm]; share: quota
    giornaliera dell'assorbimento del segmento (somma 1 su ogni segmento colturale e di cover,
    es. ETa/ET0 normalizzato); residui_asportati: bool o sequenza per segmento; f_temp:
    fattore di temperatura giornaliero f_T (`temperature_factor`, normalizzato sull'intera serie
    meteo) per mineralizzazione e rilascio; None = nessun effetto della temperatura (f_T = 1).
    Restituisce (stato finale, voci del bilancio per segmento, serie giornaliere)."""
    hp = npar.hp
    nph = npar.n_per_t_humus
    seg = np.ascontiguousarray(segment, dtype=np.int64)
    nseg = len(kinds)
    kind = np.array([KIND_CODE[k] for k in kinds], dtype=np.int64)
    asp = np.broadcast_to(np.asarray(residui_asportati, dtype=np.int64), (nseg,)).copy()
    u_tot, leg, rec, resa_a, nasp, hres, credn = (np.zeros(nseg) for _ in range(7))
    leg = leg.astype(np.int64)
    rec[:] = 1.0
    for k, (kd, c) in enumerate(zip(kinds, crops)):
        if kd == SEG_CROP:
            r = float(rese[k])
            u_tot[k] = r * npar.n_ass[c]
            leg[k] = 1 if c == LEGUME else 0
            rec[k] = npar.rec[c]
            resa_a[k] = r
            nasp[k] = npar.n_asp[c]
            hres[k] = _humus.residue_humus(c, r, hp)
            credn[k] = npar.cred_asp[c] if asp[k] else npar.cred_int[c]
    n = seg.shape[0]
    ft = np.ones(n + int(npar.rel_days) + 2)          # stessa lunghezza del calendario dei rilasci
    if f_temp is not None:
        f_temp = np.asarray(f_temp, dtype=np.float64)
        if f_temp.shape != (n,):
            raise ValueError(f"f_temp: attesi {n} giorni, ricevuti {f_temp.shape}")
        ft[:n] = f_temp
    o_l, o_nmin, o_res = np.zeros(n), np.zeros(n), np.zeros(n)
    S = np.zeros((nseg, _NCOL))
    n_min, n_res, n_cov, h, cred, n_pl = _kernel(
        seg, kind, np.ascontiguousarray(dp, dtype=np.float64),
        np.ascontiguousarray(share, dtype=np.float64), u_tot, leg, rec, resa_a, nasp, hres,
        credn, asp, hp.k2, hp.h_tetto, nph, npar.disp, npar.dep * _humus.years(1.0),
        (1.0 - npar.anion_excl) * npar.sat_mm, npar.fix_quota, hp.cov_biomassa,
        npar.cov_n_ass, npar.cov_npd, npar.cov_eff, _humus.cover_humus(hp, 1.0),
        int(npar.rel_days), _humus.years(1.0), ft, float(state.n_min), float(state.n_res),
        float(state.n_cov), float(state.h), float(state.cred), o_l, o_nmin, o_res, S)
    new = NState(n_min=n_min, n_res=n_res, n_cov=n_cov + n_pl, h=h, cred=cred)
    days = np.bincount(seg, minlength=nseg)
    dps = np.bincount(seg, weights=np.asarray(dp, float), minlength=nseg)
    bils = [_bil(S[k], kinds[k], crops[k], float(rese[k]) if kinds[k] == SEG_CROP else 0.0,
                 float(days[k]), float(dps[k]), npar) for k in range(nseg)]
    return new, bils, DailyResult(o_l, o_nmin, o_res)


def _bil(s, kind, crop, resa, days, dp, npar) -> dict:
    """Voci del bilancio di un segmento (stesse chiavi della versione a fine segmento)."""
    nph = npar.n_per_t_humus
    fert = s[_C_FERT]
    mas = fert_eff = eccedenza = 0.0
    supera = False
    if kind == SEG_CROP:
        mas = mas_limit(crop, resa, npar)
        fert_eff = fert * npar.eff_norm
        eccedenza = max(fert_eff - mas, 0.0)
        supera = fert_eff > mas
    d_h = s[_C_H1] - s[_C_H0]
    imm_cov = s[_C_IMMCOV]
    entrate = s[_C_DEP] + fert + s[_C_FIX]
    uscite = s[_C_EXP] + s[_C_L] + s[_C_DISP] + s[_C_PERD]
    out = {
        "kind": kind, "crop": crop, "anni": _humus.years(days), "dp": dp, "resa": resa,
        "min": s[_C_MIN], "disp": s[_C_DISP], "dep": s[_C_DEP], "cred": s[_C_CRED],
        "cred_eff": s[_C_CREDEFF],
        "n_disp": s[_C_NMIN0] + s[_C_MIN] - s[_C_DISP] + s[_C_DEP] + s[_C_REL],
        "u": s[_C_U], "u_eff": s[_C_UEFF], "u_suolo": s[_C_USOIL], "fix": s[_C_FIX],
        "def": s[_C_DEF], "deficit_n": s[_C_DEFN], "deficit_n_presente": s[_C_DEFN] > 1e-9,
        "cov_biomassa": s[_C_COVBIO], "fert": fert, "perd_f": s[_C_PERD],
        "fert_efficiente": fert_eff, "mas": mas, "supera_mas": supera, "eccedenza_mas": eccedenza,
        "u_cov": s[_C_UCOV], "l": s[_C_L],
        "frazione_lisciviata": leaching_fraction(dp, npar),
        "riduzione_lisc_vs_nudo": math.nan, "riduzione_lisc_fuori_intervallo": False,
        "exp": s[_C_EXP], "r_n": s[_C_RN], "n_umif": s[_C_NUMIF],
        "n_umif_cov": s[_C_NUMIFCOV], "imm_cred": s[_C_IMMCRED], "imm_cov": imm_cov,
        "rilascio_cov_npd": s[_C_RILNPD], "imm_umif": s[_C_IMMUMIF], "rilascio_res": s[_C_REL],
        "imm": s[_C_IMMCRED] + imm_cov + s[_C_IMMUMIF],
        "h_min": s[_C_HMIN], "h_res": s[_C_HRES], "h_cov": s[_C_HCOV], "d_h": d_h,
        "d_n_min": s[_C_NMIN1] - s[_C_NMIN0], "d_n_res": s[_C_NRES1] - s[_C_NRES0],
        "d_n_cov": s[_C_NCOV1] - s[_C_NCOV0], "d_n_hum": d_h * nph,
        "entrate": entrate, "uscite": uscite,
    }
    return {k: (float(v) if isinstance(v, np.floating) else v) for k, v in out.items()}


def segment_water(agg: Mapping, k: int) -> dict:
    """Aggregati idrici del segmento k da `water.aggregate_segments` come scalari."""
    return {key: float(v[k]) for key, v in agg.items()}


def update_segment(state: NState, kind: str, crop: str | None, acqua: Mapping, resa: float,
                   npar: NitrogenParams, residui_asportati: bool = False) -> tuple[NState, dict]:
    """Involucro di compatibilita': un segmento con il nucleo giornaliero (`run_daily`),
    percolazione e assorbimento distribuiti uniformemente sui giorni (non si conoscono le
    serie giornaliere). acqua: almeno 'days' [g] e 'dp' [mm]. L'N_res dello stato iniziale
    viene rilasciato uniformemente nei giorni_rilascio successivi all'inizio del segmento
    (la programmazione dei rilasci non passa tra chiamate separate: per una rotazione usare
    `run_daily` in un'unica chiamata). Restituisce (nuovo stato, voci del bilancio)."""
    nd = max(int(round(float(acqua["days"]))), 1)
    dp = np.full(nd, float(acqua["dp"]) / nd)
    share = np.full(nd, 1.0 / nd)
    new, bils, _ = run_daily(state, np.zeros(nd, np.int64), [kind], [crop], [resa], dp, share,
                             npar, residui_asportati)
    return new, bils[0]


def n_balance_residual(bil: Mapping) -> float:
    """Scarto di chiusura [kg N/ha]: (ENTRATE - USCITE) - (dN_min + dN_res + dN_cov + dN_hum),
    ENTRATE = DEP + FERT + FIX, USCITE = EXP + L + DISP + PERD_F (_meta.equazioni)."""
    delta = bil["d_n_min"] + bil["d_n_res"] + bil["d_n_cov"] + bil["d_n_hum"]
    return (bil["entrate"] - bil["uscite"]) - delta


def humus_balance_residual(state0: NState, state1: NState, bil: Mapping) -> float:
    """Scarto di chiusura dell'humus [t SO/ha] (vedi `humus.humus_balance_residual`)."""
    return _humus.humus_balance_residual(state0.h, state1.h, bil)


def run_segments(state: NState, segmenti: Iterable[tuple], npar: NitrogenParams):
    """Applica `update_segment` in sequenza. segmenti: tuple (kind, crop, acqua, resa[,
    residui_asportati]). Restituisce (stato finale, lista delle voci)."""
    out = []
    for seg in segmenti:
        state, bil = update_segment(state, *seg[:4], npar,
                                    *(seg[4:5] if len(seg) > 4 else ()))
        out.append(bil)
    return state, out


__all__ = ["NState", "NitrogenParams", "nitrogen_params", "initial_state", "update_segment",
           "n_balance_residual", "humus_balance_residual", "run_segments", "segment_water",
           "mas_limit", "leaching_fraction", "run_daily", "DailyResult", "initial_n_min",
           "temperature_factor", "SEG_CROP", "SEG_BARE",
           "SEG_COVER"]
