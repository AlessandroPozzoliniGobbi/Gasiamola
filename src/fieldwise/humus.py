"""Bilancio dell'humus (sostanza organica stabile) a fine segmento, modello Henin-Dupuis.

Specifica: params/nitrogen.yaml, _meta.equazioni.humus_henin_dupuis e k2_suolo;
params/cover_crop.yaml (biomassa_e_azoto, humus). Fonti delle equazioni:
- Henin S., Dupuis M. (1945), forma a un compartimento dH/dt = k1 A - k2 H, con k1 e
  k2 Henin-Dupuis letti in Duparque et al. (2007), Memento Sols et Matieres
  Organiques, Agro-Transfert, p. 19-20 (Tab. 2 e 3);
- k2 e tetto della mineralizzazione oltre il 3% di SO: Regione Emilia-Romagna (2023),
  Disciplinari di produzione integrata, Norme generali, Allegato 2, Tab. 1 e nota, p. 53.

Grandezza di stato: H [t SO/ha] nello strato dell'humus (spessore
nitrogen.suolo.profondita_humus), con SO% e densita' di soil.yaml
(strati_soilgrids.s0_30), vedi nitrogen._meta.convenzioni.

Equazioni (passo discreto a fine segmento, anni_seg = giorni / 365):
  H0     = SO% / 100 x prof x 10000 x densita                       (convenzioni.humus)
  H_tetto= soglia_so_tetto / 100 x prof x 10000 x densita            (Tab. 1 ER)
  H_min  = k2 x min(H, H_tetto) x anni_seg                            (Henin-Dupuis, Tab. 1 ER)
  SS_res = resa x (1 - umidita) x (1/HI - 1)                          (residui aerei, s.s.)
  H_res  = k1_residui x SS_res x c_residui x fattore_so_c             (Henin-Dupuis, base C)
  H_cov  = coefficiente_isoumico x biomassa_secca x frazione_C x fattore_so_c
  H(fine)= H - H_min + H_res + H_cov

Nessun numero agronomico vive qui: tutto da params/*.yaml. Le sole costanti del
codice sono conversioni di unita' (100 per le percentuali, 10000 m2/ha, 365 g/anno).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from . import params as _params

CROPS = ("mais", "soia", "frumento")

# Classi USDA (nomi inglesi di soil.yaml classe_tessiturale) -> classe ER di k2.
# Corrispondenza scritta in nitrogen._meta.equazioni.k2_suolo (classi USDA in italiano,
# tabella SO p. 66 ER): sabbioso = S, SF, FS; franco = F, FL, FA, FSA;
# argilloso = A, AL, FLA, AS, L.
USDA_TO_ER = {
    "sand": "tendenzialmente_sabbioso", "loamy sand": "tendenzialmente_sabbioso",
    "sandy loam": "tendenzialmente_sabbioso",
    "loam": "franco", "silt loam": "franco", "clay loam": "franco",
    "sandy clay loam": "franco",
    "clay": "tendenzialmente_argilloso", "silty clay": "tendenzialmente_argilloso",
    "silty clay loam": "tendenzialmente_argilloso", "sandy clay": "tendenzialmente_argilloso",
    "silt": "tendenzialmente_argilloso",
}

_DAYS_PER_YEAR = 365.0   # convenzioni.tempo: anni_seg = giorni / 365
_HA_M2 = 10000.0
_RE_MOIST = re.compile(r"(\d+(?:[.,]\d+)?)\s*%\s*di\s*umidit")


def texture_class(p: dict) -> str:
    """Classe ER (k2, n_pronto, fattore_dispersione) dalla classe USDA di soil.yaml."""
    usda = str(_params.get(p, "soil.strati_soilgrids.s0_30.classe_tessiturale")).lower()
    return USDA_TO_ER[usda]


def soil_cn(p: dict) -> float:
    """C/N dell'humus implicito in n_humus e fattore_so_c: C/N = (1/fattore_so_c) / n_humus
    (nitrogen.suolo.n_humus, nota: 11,6). soil.yaml non ha l'azoto totale: si usa questo."""
    g = _params.get
    return (1.0 / float(g(p, "nitrogen.suolo.fattore_so_c"))) / float(g(p, "nitrogen.suolo.n_humus"))


def k2_from_params(p: dict, classe: str | None = None, cn: float | None = None) -> float:
    """k2 [1/anno] da nitrogen.suolo.k2 secondo _meta.equazioni.k2_suolo:
    C/N < 9 -> cn_basso; 9-12 -> per_tessitura; > 12 -> cn_alto (soglie del metodo ER,
    Allegato 2 Tab. 1, colonne C/N<9, 9-12, >12)."""
    classe = texture_class(p) if classe is None else classe
    cn = soil_cn(p) if cn is None else float(cn)
    tab = "cn_basso" if cn < 9.0 else ("cn_alto" if cn > 12.0 else "per_tessitura")
    return float(_params.get(p, f"nitrogen.suolo.k2.{tab}.{classe}"))


def grain_moisture(p: dict, crop: str) -> float:
    """Umidita' commerciale della granella [frazione].

    Cerca crops.<crop>.umidita_granella; se manca (parametro mancante, segnalato) la
    legge dall'unita' di crops.<crop>.resa_potenziale ('granella al 14% di umidita''),
    che nitrogen._meta.convenzioni.resa indica come la base delle rese."""
    try:
        return float(_params.get(p, f"crops.{crop}.umidita_granella"))
    except KeyError:
        pass
    node = p["crops"][crop]["resa_potenziale"]
    m = _RE_MOIST.search(str(node.get("unita", "")) if isinstance(node, dict) else "")
    if not m:
        raise KeyError(f"umidita' della granella non trovata: crops.{crop}.umidita_granella")
    return float(m.group(1).replace(",", ".")) / 100.0


@dataclass(frozen=True)
class HumusParams:
    """Parametri dell'humus letti una volta sola (vedi `humus_params`).

    prof [m], densita [t/m3], so_pct0 [%], soglia_so [%], k2 [1/anno], n_humus
    [kg N/kg SO], fattore_so_c [kg SO/kg C], c_residui [kg C/kg s.s.];
    k1, hi, umidita: dizionari per coltura; cov_*: segale di cover_crop.yaml.
    """
    prof: float
    densita: float
    so_pct0: float
    soglia_so: float
    k2: float
    n_humus: float
    fattore_so_c: float
    c_residui: float
    k1: dict
    hi: dict
    umidita: dict
    cov_biomassa: float
    cov_frazione_c: float
    cov_k1: float

    @property
    def h_tetto(self) -> float:
        """Stock oltre il quale la mineralizzazione resta costante [t SO/ha] (Tab. 1 ER)."""
        return self.soglia_so / 100.0 * self.prof * _HA_M2 * self.densita


def humus_params(p: dict | None = None, classe: str | None = None,
                 cn: float | None = None) -> HumusParams:
    """Costruisce `HumusParams` da `fieldwise.params.load_params()` (albero grezzo)."""
    p = _params.load_params() if p is None else p
    g = _params.get
    s = "soil.strati_soilgrids.s0_30"
    return HumusParams(
        prof=float(g(p, "nitrogen.suolo.profondita_humus")),
        densita=float(g(p, f"{s}.densita_apparente")),
        so_pct0=float(g(p, f"{s}.sostanza_organica")),
        soglia_so=float(g(p, "nitrogen.suolo.soglia_so_tetto")),
        k2=k2_from_params(p, classe, cn),
        n_humus=float(g(p, "nitrogen.suolo.n_humus")),
        fattore_so_c=float(g(p, "nitrogen.suolo.fattore_so_c")),
        c_residui=float(g(p, "nitrogen.suolo.residui.c_residui")),
        k1={c: float(g(p, f"nitrogen.{c}.k1_residui")) for c in CROPS},
        hi={c: float(g(p, f"crops.{c}.hi")) for c in CROPS},
        umidita={c: grain_moisture(p, c) for c in CROPS},
        cov_biomassa=float(g(p, "cover_crop.biomassa_e_azoto.biomassa_secca")),
        cov_frazione_c=float(g(p, "cover_crop.biomassa_e_azoto.frazione_carbonio_sostanza_secca")),
        cov_k1=float(g(p, "cover_crop.humus.coefficiente_isoumico")),
    )


def initial_humus(hp: HumusParams) -> float:
    """H0 [t SO/ha] = SO% / 100 x prof x 10000 x densita (nitrogen._meta.convenzioni.humus)."""
    return hp.so_pct0 / 100.0 * hp.prof * _HA_M2 * hp.densita


def years(days: float) -> float:
    """anni_seg = giorni / 365 (nitrogen._meta.convenzioni.tempo)."""
    return float(days) / _DAYS_PER_YEAR


def mineralization(h: float, anni: float, hp: HumusParams) -> float:
    """H_min = k2 x min(H, H_tetto) x anni_seg [t SO/ha] (Henin-Dupuis; tetto Tab. 1 ER)."""
    return hp.k2 * min(h, hp.h_tetto) * anni


def residue_dry_matter(crop: str, resa: float, hp: HumusParams) -> float:
    """SS_res [t s.s./ha] dei residui aerei: granella secca = resa x (1 - umidita);
    biomassa aerea = granella secca / HI; residui = biomassa - granella
    (HI su sostanza secca, come FAO-66; nitrogen._meta.equazioni.humus_henin_dupuis)."""
    gdm = resa * (1.0 - hp.umidita[crop])
    return gdm * (1.0 / hp.hi[crop] - 1.0)


def residue_humus(crop: str, resa: float, hp: HumusParams) -> float:
    """H_res = k1_residui x SS_res x c_residui x fattore_so_c [t SO/ha] (Henin-Dupuis,
    k1 su base carbonio, Memento 2007 Tab. 2)."""
    return hp.k1[crop] * residue_dry_matter(crop, resa, hp) * hp.c_residui * hp.fattore_so_c


def cover_humus(hp: HumusParams, biomassa: float | None = None) -> float:
    """H_cov = coefficiente_isoumico x biomassa x frazione_C x fattore_so_c [t SO/ha]
    (cover_crop.yaml humus; Memento 2007 Tab. 2, 'Engrais vert'). biomassa [t s.s./ha]:
    default biomassa_secca di riferimento; il modulo azoto la riduce in proporzione
    all'N assorbito (C/N costante)."""
    b = hp.cov_biomassa if biomassa is None else biomassa
    return hp.cov_k1 * b * hp.cov_frazione_c * hp.fattore_so_c


def update_humus(h: float, anni: float, hp: HumusParams, h_res: float = 0.0,
                 h_cov: float = 0.0) -> tuple[float, dict]:
    """Un segmento: H(fine) = H - H_min + H_res + H_cov. Restituisce (H_fine, voci)
    con voci h_min, h_res, h_cov, d_h [t SO/ha]."""
    h_min = mineralization(h, anni, hp)
    h1 = h - h_min + h_res + h_cov
    return h1, {"h_min": h_min, "h_res": h_res, "h_cov": h_cov, "d_h": h1 - h}


def humus_balance_residual(h0: float, h1: float, voci: dict) -> float:
    """Scarto di chiusura [t SO/ha]: (H1 - H0) - (H_res + H_cov - H_min)."""
    return (h1 - h0) - (voci["h_res"] + voci["h_cov"] - voci["h_min"])


def equilibrium(apporti_annui: float, hp: HumusParams) -> float:
    """H_eq = A / k2 con k2 costante e H sotto il tetto (humus_henin_dupuis)."""
    return apporti_annui / hp.k2 if hp.k2 > 0 else math.inf
