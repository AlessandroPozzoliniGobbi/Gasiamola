"""Analisi di sensibilita' (fase 7): quali parametri incerti cambiano la DECISIONE.

La decisione e' la classifica delle rotazioni (``ranking.score`` con pesi uguali) e le due
alternative proposte da ``ranking.confronta``. Nessuna taratura: si riporta cio' che esce.

Metodo (dichiarato anche nel rapporto):

* Sottoinsieme fisso dell'ensemble: tutti i membri (125 rotazioni) delle classi cicliche NON
  equivalenti nell'ensemble di base, tutte le annate, i tre scenari, rotazione attuale "mais".
  Le equivalenze sono fissate sul caso di base. ``verifica_sottoinsieme`` confronta una volta la
  classifica di base sul sottoinsieme con quella dell'ensemble completo (tau di Kendall).
* Indicatore principale: punteggio a pesi uguali nello scenario ``tetto_irriguo``; in subordine
  ``solo_pioggia`` e ``irrigazione_libera``.
* Una alla volta (OAT): ogni voce di ``params.sensitivity_entries`` a x0,7 e x1,3 del valore,
  limitata all'``intervallo`` della voce, a 1 per le frazioni, e alle soglie che devono restare
  ordinate (``CATENE``). Voci a valore nullo e interruttori 0/1 non si perturbano (dichiarato).
* Incertezza strutturale (``STRUTTURALI``), una alla volta. La funzione del caldo alternativa
  si seleziona con l'argomento ``metodo_caldo`` di ``ensemble.run_ensemble`` e ``rotation.simulate``.
* Monte Carlo: ipercubo latino (``scipy.stats.qmc``) su tutte le voci perturbabili, uniformi tra
  i limiti dell'OAT, seme fisso; influenza con correlazioni di rango parziali (PRCC).
* Pesi dell'utente (non incertezza del modello): 5 casi estremi + 200 pesi casuali di Dirichlet.

Uso: ``python -m fieldwise.sensitivity [--n-mc 256] [--workers 8]``: rigenera
``reports/sensitivity.md``, le figure in ``reports/figure/`` e ``sensitivity_summary.json`` nella
cartella degli elaborati del punto. Offline: legge solo la cache meteo.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import math
import os
import time

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import qmc

from . import config as _config
from . import ensemble as _ens
from . import params as _params
from . import ranking as _rk
from . import rotation as _rt
from . import weather as _w
from .data import cache as _cache

SCENARIO_PRINCIPALE = "tetto_irriguo"
PESI_UGUALI = {k: 1.0 for k in _rk.PRIORITA}
ATTUALE = "mais"
VARIAZIONE = 0.30
SEME = 20261113
N_MC = 256
N_PESI = 200
MARGINE_ORDINE = 0.01           # soglie ordinate: la successiva resta >= precedente x 1,01
TAU_NON_CONTA = 0.95            # sotto questa soglia di tau un parametro "conta"
DELTA_NON_CONTA = 0.01          # |variazione del punteggio| sotto cui non conta
FILE_JSON = "sensitivity_summary.json"
FILE_MD = _config.REPORTS_DIR / "sensitivity.md"
FIG_DIR = _config.REPORTS_DIR / "figure"

PAROLE_FRAZIONE = ("frazione", "quota", "efficienza", "f_rotazione", "anion_excl", "nhi",
                   "recupero", "riduzione")

STRUTTURALI = {
    "caldo_aquacrop": ("Funzione del caldo AquaCrop (Ks logistico su Tmax)", {"metodo_caldo": "aquacrop"}),
    "caldo_teixeira": ("Funzione del caldo con soglie di Teixeira et al. (2013)", {"metodo_caldo": "teixeira"}),
    "et_singolo": ("Evapotraspirazione a Kc singolo", {"opzioni": {"metodo_et": "singolo"}}),
    "cn_copertura": ("Curve Number per copertura (NEH) al posto di AquaCrop",
                     {"modifiche": {"soil.ruscellamento.metodo_cn": "neh_copertura"}}),
    "riparto_eta": ("Riparto dell'azoto assorbito su ETa", {"opzioni": {"riparto": "eta"}}),
    "riparto_eta_et0": ("Riparto dell'azoto assorbito su ETa/ET0", {"opzioni": {"riparto": "eta_et0"}}),
    "avviamento_0": ("Zero cicli di avviamento", {"n_avviamento": 0}),
    "pioggia_imerg": ("Pioggia IMERG al posto di NASA POWER", {"pioggia": "imerg"}),
    "rotazione_1": ("Penalita' di rotazione azzerate (tutti i fattori = 1)", {"f_rotazione_1": True}),
    "so_soilgrids": ("Sostanza organica 0-30 cm al valore SoilGrids (3,563%)",
                     {"modifiche": {"soil.strati_soilgrids.s0_30.sostanza_organica": 3.563,
                                    "soil.strati_soilgrids.s0_30.carbonio_organico": 20.67}}),
}

_NOMI_FILE = {"nitrogen": "Azoto", "crops": "Colture", "heat": "Caldo", "soil": "Suolo",
              "cover_crop": "Cover crop", "rotation_rules": "Rotazione", "scenarios": "Scenari"}


def etichetta(percorso: str) -> str:
    """Etichetta leggibile in italiano dal percorso della voce."""
    testa, _, resto = percorso.partition(".")
    resto = (resto.replace("strati_soilgrids.", "").replace("biomassa_e_azoto.", "")
             .replace("scenari.", "").replace("_", " ").replace(".", " · "))
    return f"{_NOMI_FILE.get(testa, testa)}: {resto}"


# ----------------------------------------------------------------------------------- vincoli
def catene(p: dict) -> list[list[str]]:
    """Gruppi di voci che devono restare strettamente crescenti."""
    out = []
    for c in ("mais", "soia", "frumento"):
        g = f"crops.{c}."
        out += [[g + k for k in ("gdd_emergenza", "gdd_fine_ini", "gdd_fine_sviluppo",
                                 "gdd_fine_mid", "gdd_maturita")],
                [g + "gdd_emergenza", g + "gdd_fioritura", g + "gdd_maturita"],
                [g + "zr_ini", g + "zr_max"],
                [f"heat.colture.{c}.t_critica", f"heat.colture.{c}.t_limite"],
                [f"heat.colture.{c}.finestra_inizio_frazione", f"heat.colture.{c}.finestra_fine_frazione"],
                [f"heat.alternative.teixeira_2013.t_critica_{c}", f"heat.alternative.teixeira_2013.t_limite_{c}"]]
    out.append(["cover_crop.acqua.profondita_radicale_iniziale", "cover_crop.acqua.profondita_radicale_max"])
    s = "nitrogen.lisciviazione.metodo_disciplinare.soglie_pioggia_autunno_inverno"
    out.append([f"{s}[0]", f"{s}[1]"])
    return out


def voci_incerte(p: dict) -> tuple[pd.DataFrame, list[dict]]:
    """Voci perturbabili con limiti (x0,7 / x1,3 ristretti) e voci escluse con il motivo."""
    righe, escluse = [], []
    for k, v in _params.sensitivity_entries(p):
        x = v["valore"]
        if isinstance(x, bool) or k.endswith(".irrigabile"):
            escluse.append({"percorso": k, "motivo": "interruttore 0/1, non una grandezza continua"})
            continue
        x = float(x)
        if x == 0.0:
            escluse.append({"percorso": k, "motivo": "valore nullo: +/-30% non lo cambia"})
            continue
        a, b = sorted((x * (1 - VARIAZIONE), x * (1 + VARIAZIONE)))
        note = []
        iv = v.get("intervallo")
        if isinstance(iv, (list, tuple)) and len(iv) == 2 and all(isinstance(t, (int, float)) for t in iv):
            lo, hi = sorted(map(float, iv))
            if a < lo or b > hi:
                note.append("intervallo")
            a, b = max(a, lo), min(b, hi)
        if x > 0 and any(w in k for w in PAROLE_FRAZIONE) and b > 1.0:
            b = 1.0
            note.append("frazione<=1")
        righe.append({"percorso": k, "base": x, "basso": a, "alto": b,
                      "intero": isinstance(v["valore"], int), "limiti": ",".join(note),
                      "etichetta": etichetta(k)})
    return pd.DataFrame(righe), escluse


def applica_catene(mod: dict, base: dict, chains: list[list[str]]) -> tuple[dict, bool]:
    """Corregge ``mod`` perche' ogni catena resti crescente; restituisce (mod, corretto?)."""
    mod = dict(mod)
    corretto = False
    for ch in chains:
        ch = [k for k in ch if k in base]
        for a, b in zip(ch, ch[1:]):
            va, vb = mod.get(a, base[a]), mod.get(b, base[b])
            if vb >= va * (1 + MARGINE_ORDINE):
                continue
            corretto = True
            if a in mod and b not in mod:
                mod[a] = vb / (1 + MARGINE_ORDINE)
            else:
                mod[b] = va * (1 + MARGINE_ORDINE)
    return mod, corretto


def valori_base(p: dict) -> dict:
    return {k: float(v["valore"]) for k, v in _params.sensitivity_entries(p)
            if isinstance(v["valore"], (int, float)) and not isinstance(v["valore"], bool)}


# ----------------------------------------------------------------------------------- calcolo
_W = {}


def _init(rotazioni):
    _W["p"] = _params.load_params()
    _W["rot"] = rotazioni
    _W["forcing"] = {}


def _forcing(fonte: str):
    if fonte not in _W["forcing"]:
        _W["forcing"][fonte] = (None if fonte == "default" else
                                _w.load_forcing(_config.PILOT_LAT, _config.PILOT_LON, rain_source=fonte))
    return _W["forcing"][fonte]


def riassumi(sintesi: pd.DataFrame) -> dict:
    """Per scenario: classi in ordine, punteggi, attuale e alternative di ``confronta``."""
    out = {}
    for sc in _rt.SCENARI:
        r = _rk.score(sintesi, PESI_UGUALI, sc)
        c = _rk.confronta(sintesi, PESI_UGUALI, sc)
        out[sc] = {"classi": r["classe"].tolist(), "punteggi": [float(x) for x in r["punteggio"]],
                   "attuale": c["attuale"]["classe"] if c.get("attuale") else None,
                   "alternative": [a["classe"] for a in c["alternative"]]}
    return out


def valuta(caso: dict) -> dict:
    """Un calcolo dell'ensemble ridotto. ``caso``: id, modifiche, opzioni, n_avviamento,
    metodo_caldo, pioggia, f_rotazione_1. Gli errori si registrano, non interrompono."""
    t0 = time.time()
    try:
        p = _W["p"]
        mod = dict(caso.get("modifiche") or {})
        if caso.get("f_rotazione_1"):
            mod.update({k: 1.0 for k, _ in _params.iter_entries(p) if k.startswith("rotation_rules.f_rotazione.")})
        if mod:
            p = _params.override(p, mod)
        ctx = _rt.build_context(p, forcing=_forcing(caso.get("pioggia", "default")))
        _, sin = _ens.run_ensemble(ctx=ctx, rotazioni=_W["rot"], rotazione_attuale=ATTUALE,
                                   n_avviamento=caso.get("n_avviamento", 1),
                                   metodo_caldo=caso.get("metodo_caldo") or "deryng",
                                   **(caso.get("opzioni") or {}))
        res = {"id": caso["id"], "esito": "ok", "scenari": riassumi(sin)}
    except Exception as ex:                                   # noqa: BLE001 (si registra e si prosegue)
        res = {"id": caso["id"], "esito": "errore", "errore": f"{type(ex).__name__}: {ex}"[:300]}
    res["tempo_s"] = time.time() - t0
    return res


def esegui(casi: list[dict], rotazioni: list[str], workers: int) -> dict:
    if workers <= 1:
        _init(rotazioni)
        return {c["id"]: valuta(c) for c in casi}
    with cf.ProcessPoolExecutor(workers, initializer=_init, initargs=(rotazioni,)) as ex:
        return {r["id"]: r for r in ex.map(valuta, casi, chunksize=2)}


# ----------------------------------------------------------------------------------- metriche
def confronto(base: dict, pert: dict, sc: str) -> dict:
    """Metriche della decisione nello scenario ``sc`` (perturbato contro base)."""
    if pert.get("esito") != "ok":
        return {"errore": True}
    b, q = base["scenari"][sc], pert["scenari"][sc]
    pb = dict(zip(b["classi"], b["punteggi"]))
    pq = dict(zip(q["classi"], q["punteggi"]))
    comuni = [c for c in b["classi"] if c in pq]
    tau = (stats.kendalltau([b["classi"].index(c) for c in comuni],
                            [q["classi"].index(c) for c in comuni])[0] if len(comuni) > 2 else np.nan)
    prima, att = b["classi"][0], b["attuale"]
    n = len(q["classi"])
    pos_att = q["classi"].index(q["attuale"]) + 1 if q["attuale"] in q["classi"] else np.nan
    return {"tau": float(tau),
            "d_prima": pq.get(prima, np.nan) - pb[prima],
            "d_attuale": (pq.get(att, np.nan) - pb[att]) if att in pb else np.nan,
            "prima": q["classi"][0], "prima_cambia": q["classi"][0] != prima,
            "top3_cambia": set(q["classi"][:3]) != set(b["classi"][:3]),
            "top3": q["classi"][:3],
            "alternative_cambiano": set(q["alternative"]) != set(b["alternative"]),
            "alternative": q["alternative"],
            "attuale_ultimo_quarto": bool(pos_att > 0.75 * n) if pos_att == pos_att else False,
            "identico": all(abs(pq.get(c, np.inf) - pb[c]) < 1e-12 for c in b["classi"])}


def prcc(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Coefficienti di correlazione di rango parziale (Marino et al. 2008) di ogni colonna di X."""
    R = np.column_stack([stats.rankdata(c) for c in X.T] + [stats.rankdata(y)])
    C = np.corrcoef(R, rowvar=False)
    Ci = np.linalg.pinv(C)
    j = Ci.shape[0] - 1
    return -Ci[:-1, j] / np.sqrt(np.abs(np.diag(Ci)[:-1] * Ci[j, j]))


def sensibilita_pesi(sintesi: pd.DataFrame, n: int = N_PESI, seme: int = SEME) -> dict:
    """Prima rotazione al variare dei pesi (con i parametri di base)."""
    rng = np.random.default_rng(seme)
    pr = list(_rk.PRIORITA)
    out = {}
    for sc in _rt.SCENARI:
        estremi, avvisi = {}, {}
        for k in pr:
            r = _rk.score(sintesi, {k: 1.0}, sc)
            estremi[k] = r["classe"].iloc[0]
            if r.attrs.get("avviso"):
                avvisi[k] = str(r.attrs["avviso"])
        cas = [_rk.score(sintesi, dict(zip(pr, w)), sc)["classe"].iloc[0]
               for w in rng.dirichlet(np.ones(len(pr)), n)]
        freq = pd.Series(cas).value_counts()
        out[sc] = {"estremi": estremi, "avvisi_estremi": avvisi, "n_prime_diverse_casuali": int(freq.size),
                   "n_prime_diverse_totale": len(set(cas) | set(estremi.values())),
                   "frequenza_prima_casuali": {k: int(v) for k, v in freq.items()}}
    return out


# ----------------------------------------------------------------------------------- figure
def _tornado(df: pd.DataFrame, col_lo: str, col_hi: str, titolo: str, xlab: str, path, rif=0.0):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    d = df.iloc[::-1]
    fig, ax = plt.subplots(figsize=(9, 0.38 * len(d) + 1.6))
    y = np.arange(len(d))
    ax.barh(y, d[col_lo] - rif, left=rif, color="#3b6ea5", label="valore x0,7 (o limite)")
    ax.barh(y, d[col_hi] - rif, left=rif, color="#d08c2c", alpha=0.85, label="valore x1,3 (o limite)")
    ax.axvline(rif, color="k", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(d["etichetta"], fontsize=8)
    ax.set_xlabel(xlab)
    ax.set_title(titolo, fontsize=10)
    ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _istogramma_tau(mc: dict, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    for sc, col in zip(_rt.SCENARI, ("#7a9a3a", "#3b6ea5", "#b0413e")):
        ax.hist(mc[sc]["tau_tutti"], bins=30, range=(0, 1), alpha=0.5, color=col, label=sc.replace("_", " "))
    ax.set_xlabel("tau di Kendall rispetto alla classifica di base")
    ax.set_ylabel("campioni Monte Carlo")
    ax.set_title("Stabilita' della classifica sotto incertezza congiunta dei parametri", fontsize=10)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ----------------------------------------------------------------------------------- pipeline
def sottoinsieme(p: dict, sintesi_completa: pd.DataFrame) -> list[str]:
    """Tutti i membri delle classi non equivalenti nell'ensemble di base."""
    neq = set(sintesi_completa.loc[sintesi_completa["equivalente_a"] == _ens.NESSUNO, "classe"])
    return [r["label"] for r in _rt.enumerate_rotations(p) if r["classe"] in neq]


def verifica_sottoinsieme(sintesi_completa, base: dict) -> dict:
    out = {}
    for sc in _rt.SCENARI:
        r = _rk.score(sintesi_completa, PESI_UGUALI, sc)["classe"].tolist()
        q = base["scenari"][sc]["classi"]
        comuni = [c for c in r if c in q]
        out[sc] = {"tau": float(stats.kendalltau([r.index(c) for c in comuni], [q.index(c) for c in comuni])[0]),
                   "stessa_prima": r[0] == q[0], "stesse_prime3": set(r[:3]) == set(q[:3]),
                   "n_completo": len(r), "n_sottoinsieme": len(q),
                   "solo_nel_completo": [c for c in r if c not in q]}
    return out


def run(n_mc: int = N_MC, workers: int | None = None, seme: int = SEME) -> dict:
    t_tot = time.time()
    workers = workers or max(1, min(8, (os.cpu_count() or 2) - 1))
    p = _params.load_params()
    _, sin_full = _ens.run_ensemble(rotazione_attuale=ATTUALE)
    rot = sottoinsieme(p, sin_full)
    voci, escluse = voci_incerte(p)
    base_v = valori_base(p)
    chains = catene(p)

    # OAT: limiti effettivi (con catene)
    casi, limiti = [{"id": "base"}], []
    for r in voci.itertuples():
        for lato, v in (("meno", r.basso), ("piu", r.alto)):
            v = round(v) if r.intero else v
            mod, corr = applica_catene({r.percorso: v}, base_v, chains)
            v = mod[r.percorso]
            limiti.append((r.percorso, lato, v, corr))
            if abs(v - r.base) > 1e-12:
                casi.append({"id": f"oat|{r.percorso}|{lato}", "modifiche": mod})
    for k, (_, spec) in STRUTTURALI.items():
        casi.append({"id": f"str|{k}", **spec})
    t0 = time.time()
    ris = esegui(casi, rot, workers)
    t_oat = time.time() - t0
    base = ris["base"]
    if base.get("esito") != "ok":
        raise RuntimeError(f"caso di base non eseguibile: {base.get('errore')}")

    # tabella OAT
    lim = {(k, l): (v, c) for k, l, v, c in limiti}
    righe = []
    for r in voci.itertuples():
        row = {"percorso": r.percorso, "etichetta": r.etichetta, "base": r.base, "limiti": r.limiti}
        for lato in ("meno", "piu"):
            v, corr = lim[(r.percorso, lato)]
            row[f"valore_{lato}"] = v
            if corr:
                row["limiti"] = ",".join(filter(None, [row["limiti"], f"ordine({lato})"]))
            res = ris.get(f"oat|{r.percorso}|{lato}")
            for sc in _rt.SCENARI:
                m = confronto(base, res, sc) if res else {"tau": 1.0, "d_prima": 0.0, "d_attuale": 0.0,
                                                          "prima_cambia": False, "top3_cambia": False,
                                                          "alternative_cambiano": False, "identico": True}
                s = "" if sc == SCENARIO_PRINCIPALE else f"_{sc}"
                if m.get("errore"):
                    row[f"errore_{lato}"] = res.get("errore")
                    m = {"tau": np.nan, "d_prima": np.nan, "d_attuale": np.nan, "prima_cambia": False,
                         "top3_cambia": False, "alternative_cambiano": False, "identico": False}
                for key in ("tau", "d_prima", "d_attuale", "prima_cambia", "top3_cambia",
                            "alternative_cambiano", "identico"):
                    row[f"{key}_{lato}{s}"] = m[key]
                if sc == SCENARIO_PRINCIPALE and m.get("prima"):
                    row[f"prima_{lato}"] = m["prima"]
        righe.append(row)
    oat = pd.DataFrame(righe)
    oat["effetto"] = oat[["d_prima_meno", "d_prima_piu"]].abs().max(axis=1)
    oat["tau_min"] = oat[["tau_meno", "tau_piu"]].min(axis=1)
    for s in ["", "_solo_pioggia", "_irrigazione_libera"]:
        oat[f"tau_min{s}"] = oat[[f"tau_meno{s}", f"tau_piu{s}"]].min(axis=1)
        oat[f"prima_cambia{s}"] = oat[f"prima_cambia_meno{s}"] | oat[f"prima_cambia_piu{s}"]
        oat[f"top3_cambia{s}"] = oat[f"top3_cambia_meno{s}"] | oat[f"top3_cambia_piu{s}"]
        oat[f"alt_cambiano{s}"] = oat[f"alternative_cambiano_meno{s}"] | oat[f"alternative_cambiano_piu{s}"]
    oat["inattiva"] = oat["identico_meno"] & oat["identico_piu"]
    oat["conta"] = (oat[[c for c in oat if c.startswith(("prima_cambia", "top3_cambia", "alt_cambiano"))
                         and not c.endswith(("_meno", "_piu")) and "_meno_" not in c and "_piu_" not in c]].any(axis=1)
                    | (oat["effetto"] >= DELTA_NON_CONTA)
                    | (oat[["tau_min", "tau_min_solo_pioggia", "tau_min_irrigazione_libera"]].min(axis=1) < TAU_NON_CONTA))
    oat = oat.sort_values("effetto", ascending=False, na_position="last").reset_index(drop=True)

    strutt = []
    for k, (nome, _) in STRUTTURALI.items():
        res = ris[f"str|{k}"]
        row = {"chiave": k, "descrizione": nome, "esito": res["esito"], "errore": res.get("errore")}
        for sc in _rt.SCENARI:
            m = confronto(base, res, sc)
            row[sc] = None if m.get("errore") else {
                kk: (float(vv) if isinstance(vv, (float, np.floating)) else vv) for kk, vv in m.items()}
        strutt.append(row)

    # Monte Carlo
    d = len(voci)
    lhs = qmc.LatinHypercube(d=d, seed=seme).random(n_mc)
    X = voci["basso"].to_numpy() + lhs * (voci["alto"] - voci["basso"]).to_numpy()
    casi_mc, n_corr = [], 0
    for i in range(n_mc):
        mod = {k: (round(x) if it else float(x)) for k, x, it in zip(voci["percorso"], X[i], voci["intero"])}
        mod, corr = applica_catene(mod, base_v, chains)
        n_corr += corr
        X[i] = [mod[k] for k in voci["percorso"]]
        casi_mc.append({"id": f"mc|{i}", "modifiche": mod})
    t0 = time.time()
    ris_mc = esegui(casi_mc, rot, workers)
    t_mc = time.time() - t0
    mc, ok = {}, [i for i in range(n_mc) if ris_mc[f"mc|{i}"]["esito"] == "ok"]
    infl = {}
    for sc in _rt.SCENARI:
        ms = [confronto(base, ris_mc[f"mc|{i}"], sc) for i in ok]
        tau = np.array([m["tau"] for m in ms])
        top3 = pd.Series([c for m in ms for c in m["top3"]]).value_counts() / len(ms)
        mc[sc] = {"n_validi": len(ms), "tau_mediana": float(np.median(tau)),
                  "tau_p5": float(np.percentile(tau, 5)),
                  "prima_resta": float(np.mean([not m["prima_cambia"] for m in ms])),
                  "top3_restano": float(np.mean([not m["top3_cambia"] for m in ms])),
                  "attuale_ultimo_quarto": float(np.mean([m["attuale_ultimo_quarto"] for m in ms])),
                  "alternative_restano": float(np.mean([not m["alternative_cambiano"] for m in ms])),
                  "frequenza_top3": {k: float(v) for k, v in top3.items()},
                  "prime_osservate": pd.Series([m["prima"] for m in ms]).value_counts().to_dict(),
                  "tau_tutti": tau.tolist()}
        Xo = X[ok]
        var = Xo.std(axis=0) > 0
        for nome, y in (("d_prima", np.array([m["d_prima"] for m in ms])), ("tau", tau)):
            pr = np.full(d, np.nan)
            if len(ok) > var.sum() + 2:
                pr[var] = prcc(Xo[:, var], np.nan_to_num(y, nan=np.nanmin(y)))
            infl[f"{sc}|{nome}"] = pr
    prcc_df = voci[["percorso", "etichetta"]].copy()
    for k, v in infl.items():
        prcc_df[k] = v
    prcc_df["dof"] = len(ok) - int(np.sum(X.std(axis=0) > 0)) - 2

    pesi = sensibilita_pesi(_rk_sintesi_base(rot))
    import subprocess
    try:
        git = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             cwd=_config.ROOT).stdout.strip()
        sporco = subprocess.run(["git", "status", "--porcelain", "src", "params"], capture_output=True,
                                text=True, cwd=_config.ROOT).stdout.strip()
    except OSError:
        git, sporco = "?", ""
    meta = sin_full.attrs.get("meta", {})
    versione = (f"commit {git}" + (" con modifiche locali in src/ o params/ non registrate" if sporco else "")
                + f", hash dei parametri {meta.get('hash_parametri', '?')}, ensemble calcolato il "
                f"{meta.get('calcolato_il', '?')}")
    return {"versione": versione, "n_classi_sottoinsieme": int((sin_full.loc[sin_full["equivalente_a"] == _ens.NESSUNO].groupby("scenario")["classe"].nunique()).max()),
            "base": base, "verifica": verifica_sottoinsieme(sin_full, base), "rotazioni": rot,
            "oat": oat, "escluse": escluse, "strutturali": strutt, "mc": mc, "prcc": prcc_df,
            "pesi": pesi, "n_mc": n_mc, "n_mc_falliti": n_mc - len(ok), "n_mc_ordine_corretto": n_corr,
            "errori_mc": sorted({ris_mc[f"mc|{i}"].get("errore") for i in range(n_mc) if i not in ok} - {None}),
            "tempi": {"oat_e_strutturali_s": t_oat, "monte_carlo_s": t_mc, "totale_s": time.time() - t_tot,
                      "n_calcoli_oat_strutturali": len(casi), "workers": workers},
            "seme": seme}


def _rk_sintesi_base(rot):
    _, s = _ens.run_ensemble(rotazioni=rot, rotazione_attuale=ATTUALE)
    return s


# ----------------------------------------------------------------------------------- uscite
def _f(x, n=3):
    return "-" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{n}f}"


def _g(x):
    return f"{x:.4g}"


def conclusione(R: dict) -> str:
    oat = R["oat"]
    prima = oat[oat["prima_cambia"]]
    n_no = int((~oat["conta"]).sum())
    n_inatt = int(oat["inattiva"].sum())
    st = [s["descrizione"].split(" (")[0].lower() for s in R["strutturali"] if s["esito"] == "ok"
          and any(s[sc]["prima_cambia"] for sc in _rt.SCENARI)]
    m = R["mc"][SCENARIO_PRINCIPALE]
    return (f"Cambiano la prima rotazione nel tetto irriguo {len(prima)} dei {len(oat)} parametri presi uno "
            f"alla volta (soprattutto {', '.join(f'`{p}`' for p in prima['percorso'].head(5))}) e, tra le scelte "
            f"strutturali, {'; '.join(st) or 'nessuna'}; non cambiano la decisione {n_no} parametri "
            f"({n_inatt} senza alcun effetto); con l'incertezza congiunta la prima resta prima solo nel "
            f"{m['prima_resta']:.0%} dei campioni (tau mediano {m['tau_mediana']:.2f}) ma il mais continuo resta "
            f"nell'ultimo quarto nel {m['attuale_ultimo_quarto']:.0%}: e' robusto il giudizio sulla rotazione "
            f"attuale, non la scelta fine tra le prime alternative.")


def scrivi(R: dict, lat=None, lon=None) -> dict:
    lat = _config.PILOT_LAT if lat is None else lat
    lon = _config.PILOT_LON if lon is None else lon
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    oat, base = R["oat"], R["base"]
    b = base["scenari"][SCENARIO_PRINCIPALE]
    top = oat.dropna(subset=["effetto"]).head(20)
    _tornado(top, "d_prima_meno", "d_prima_piu",
             f"Variazione del punteggio della prima rotazione ({b['classi'][0]})\n"
             "scenario tetto irriguo, pesi uguali, un parametro alla volta",
             "variazione del punteggio (scala 0-1)", FIG_DIR / "sensibilita_tornado_punteggio.png")
    tt = oat.assign(k=1 - oat["tau_min"]).sort_values("k", ascending=False).head(20)
    _tornado(tt, "tau_meno", "tau_piu", "Concordanza con la classifica di base (tau di Kendall)\n"
             "scenario tetto irriguo, un parametro alla volta", "tau di Kendall (1 = classifica invariata)",
             FIG_DIR / "sensibilita_tornado_tau.png", rif=1.0)
    _istogramma_tau(R["mc"], FIG_DIR / "sensibilita_montecarlo_tau.png")

    T = R["tempi"]
    L = ["# Analisi di sensibilita' (fase 7)", "",
         f"Generato da `python -m fieldwise.sensitivity` il {dt.date.today().isoformat()}. "
         "Domanda: quali parametri incerti cambiano la DECISIONE (classifica delle rotazioni e alternative "
         "proposte) e quali no. Nessuna taratura: si riporta cio' che esce.", "",
         "## Conclusione in una frase", "", conclusione(R), "",
         "## Metodo", "",
         f"- **Versione del codice**: {R['versione']}.",
         f"- **Sottoinsieme fisso**: tutti i membri ({len(R['rotazioni'])} rotazioni) delle {R['n_classi_sottoinsieme']} classi cicliche non "
         "equivalenti dell'ensemble di base, tutte le annate, i tre scenari d'acqua, rotazione attuale \"mais\". "
         "Le equivalenze sono fissate sul caso di base.",
         "- **Verifica del sottoinsieme** (classifica di base, pesi uguali, contro l'ensemble completo di 216 rotazioni): "
         + "; ".join(f"{sc.replace('_', ' ')} tau {v['tau']:.3f}, stessa prima {'si' if v['stessa_prima'] else 'no'}, "
                     f"stesse prime tre {'si' if v['stesse_prime3'] else 'no'}" for sc, v in R["verifica"].items())
         + ".",
         "- **Indicatore principale**: punteggio a pesi uguali di `ranking.score` nello scenario tetto irriguo; "
         "in subordine solo pioggia e irrigazione libera. Il punteggio e' relativo all'insieme confrontato (0-1).",
         f"- **Una alla volta**: {len(oat)} voci di `params.sensitivity_entries` a x0,7 e x1,3 del valore. "
         "Limiti: l'`intervallo` della voce se piu' stretto; 1 per frazioni, quote ed efficienze; soglie ordinate "
         "(GDD delle fasi, zr iniziale < massima, t critica < t limite, finestre del caldo, soglie di pioggia) con "
         f"la successiva >= precedente x{1 + MARGINE_ORDINE:.2f}. Valori interi arrotondati. Escluse "
         f"{len(R['escluse'])} voci: " + "; ".join(f"`{e['percorso']}` ({e['motivo']})" for e in R["escluse"]) + ".",
         f"- **Soglie 'non conta'**: in nessuno dei tre scenari cambia la prima, l'insieme delle prime tre o le "
         f"alternative; |variazione del punteggio della prima| < {DELTA_NON_CONTA}; tau >= {TAU_NON_CONTA}.",
         "- **Funzione del caldo alternativa**: si seleziona con l'argomento `metodo_caldo` di `ensemble.run_ensemble` "
         "e `rotation.simulate` (`yield_model.heat_factor` con `metodo` diverso).",
         f"- **Monte Carlo**: {R['n_mc']} campioni a ipercubo latino (`scipy.stats.qmc.LatinHypercube`, seme {R['seme']}) "
         f"su tutte le {len(oat)} voci, uniformi tra gli stessi limiti dell'OAT; {R['n_mc_ordine_corretto']} campioni "
         f"corretti per le soglie ordinate; {R['n_mc_falliti']} non eseguibili"
         + (" (" + "; ".join(R["errori_mc"])[:600] + ")" if R["errori_mc"] else "") + f". Con {len(oat)} parametri e "
         f"{R['n_mc']} campioni l'influenza si stima con correlazioni di rango parziali (PRCC, gradi di liberta' residui "
         f"{int(R['prcc']['dof'].iloc[0])}): indicativa, non un indice di Sobol.",
         f"- **Tempo di calcolo**: OAT + strutturali {T['oat_e_strutturali_s']:.0f} s ({T['n_calcoli_oat_strutturali']} "
         f"calcoli), Monte Carlo {T['monte_carlo_s']:.0f} s, totale {T['totale_s']:.0f} s con {T['workers']} processi.",
         "", "## Caso di base", ""]
    for sc in _rt.SCENARI:
        s = base["scenari"][sc]
        pos = s["classi"].index(s["attuale"]) + 1 if s["attuale"] in s["classi"] else "-"
        L.append(f"- {sc.replace('_', ' ')}: prime tre {', '.join(f'`{c}`' for c in s['classi'][:3])}; "
                 f"attuale `{s['attuale']}` {pos}a su {len(s['classi'])}; alternative "
                 f"{', '.join(f'`{c}`' for c in s['alternative'])}")
    L += ["", "## I 20 parametri piu' influenti (una alla volta, tetto irriguo)", "",
          "Effetto = variazione del punteggio della prima rotazione di base; tau = minimo sui due lati; "
          "'prima'/'top3'/'alt' = cambia la prima, l'insieme delle prime tre, le alternative (T = tetto irriguo, "
          "S = solo pioggia, L = irrigazione libera).", "",
          "Ord. | Parametro | Base | Valore -30% | Valore +30% | Effetto -30% | Effetto +30% | Attuale -/+ | tau | prima | top3 | alt | limiti",
          "---|---|---|---|---|---|---|---|---|---|---|---|---"]

    def flag(r, k):
        return "".join(l for l, s in (("T", ""), ("S", "_solo_pioggia"), ("L", "_irrigazione_libera")) if r[f"{k}{s}"]) or "-"
    for i, r in top.iterrows():
        L.append(f"{i + 1} | `{r.percorso}` | {_g(r.base)} | {_g(r.valore_meno)} | {_g(r.valore_piu)} | "
                 f"{_f(r.d_prima_meno)} | {_f(r.d_prima_piu)} | {_f(r.d_attuale_meno, 2)}/{_f(r.d_attuale_piu, 2)} | "
                 f"{r.tau_min:.2f} | {flag(r, 'prima_cambia')} | {flag(r, 'top3_cambia')} | {flag(r, 'alt_cambiano')} | "
                 f"{r.limiti or '-'}")
    piu_tau = oat[(oat["tau_min"] < TAU_NON_CONTA) & ~oat.index.isin(top.index)]
    if len(piu_tau):
        L += ["", "Fuori dai primi 20 per effetto ma con tau < "
              f"{TAU_NON_CONTA} nel tetto irriguo: " + ", ".join(f"`{p}` ({t:.2f})" for p, t in
                                                                 zip(piu_tau.percorso, piu_tau.tau_min)) + "."]
    err = oat[oat.filter(like="errore_").notna().any(axis=1)] if oat.filter(like="errore_").shape[1] else oat.iloc[:0]
    L += ["", "Variazioni non eseguibili: " + ("nessuna." if err.empty else "; ".join(
        f"`{r.percorso}`: {r.get('errore_meno') or r.get('errore_piu')}" for _, r in err.iterrows()))]
    L += ["", "![Tornado sul punteggio](figure/sensibilita_tornado_punteggio.png)", "",
          "![Tornado sul tau di Kendall](figure/sensibilita_tornado_tau.png)", "",
          "## Incertezza strutturale (una alla volta)", "",
          "Scelta | Esito | tau T / S / L | Effetto sulla prima (T) | Prima nel tetto irriguo | Cambia prima T/S/L | Cambiano top3 T/S/L | Cambiano alternative T/S/L",
          "---|---|---|---|---|---|---|---"]
    for s in R["strutturali"]:
        if s["esito"] != "ok":
            L.append(f"{s['descrizione']} | non eseguibile: {s['errore']} | - | - | - | - | - | -")
            continue
        m = [s[sc] for sc in _rt.SCENARI]

        def yn(k):
            return "/".join("si" if x[k] else "no" for x in m)
        taus = " / ".join(f"{x['tau']:.2f}" for x in m)
        L.append(f"{s['descrizione']} | ok | {taus} | "
                 f"{_f(s[SCENARIO_PRINCIPALE]['d_prima'])} | `{s[SCENARIO_PRINCIPALE]['prima']}` | "
                 f"{yn('prima_cambia')} | {yn('top3_cambia')} | {yn('alternative_cambiano')}")
    L += ["", "## Monte Carlo (incertezza congiunta dei parametri)", "",
          "Scenario | campioni validi | tau mediana | tau 5° perc. | prima resta prima | prime tre restano | attuale nell'ultimo quarto | alternative restano",
          "---|---|---|---|---|---|---|---"]
    for sc, m in R["mc"].items():
        L.append(f"{sc.replace('_', ' ')} | {m['n_validi']} | {m['tau_mediana']:.3f} | {m['tau_p5']:.3f} | "
                 f"{m['prima_resta']:.1%} | {m['top3_restano']:.1%} | {m['attuale_ultimo_quarto']:.1%} | "
                 f"{m['alternative_restano']:.1%}")
    L += ["", "Frequenza con cui le rotazioni compaiono tra le prime tre (le prime 6 per scenario):", ""]
    for sc, m in R["mc"].items():
        L.append(f"- {sc.replace('_', ' ')}: " + "; ".join(f"`{k}` {v:.0%}" for k, v in list(m["frequenza_top3"].items())[:6]))
    pr = R["prcc"]
    L += ["", "Parametri con le correlazioni di rango parziali piu' forti (tetto irriguo; |PRCC| piu' alto su "
          "punteggio della prima e tau):", ""]
    pr = pr.assign(m=pr[[f"{SCENARIO_PRINCIPALE}|d_prima", f"{SCENARIO_PRINCIPALE}|tau"]].abs().max(axis=1)).sort_values("m", ascending=False)
    for _, r in pr.head(10).iterrows():
        L.append(f"- `{r.percorso}`: PRCC punteggio della prima {r[f'{SCENARIO_PRINCIPALE}|d_prima']:+.2f}, "
                 f"PRCC tau {r[f'{SCENARIO_PRINCIPALE}|tau']:+.2f}")
    L += ["", "![Distribuzione del tau nel Monte Carlo](figure/sensibilita_montecarlo_tau.png)", "",
          "## Sensibilita' ai pesi dell'utente (non e' incertezza del modello)", "",
          f"Parametri di base; 5 casi estremi (tutto il peso su una priorita') e {N_PESI} pesi casuali "
          "(Dirichlet uniforme sul simplesso, stesso seme).", ""]
    for sc, w in R["pesi"].items():
        L.append(f"- {sc.replace('_', ' ')}: {w['n_prime_diverse_totale']} rotazioni diverse arrivano prime "
                 f"({w['n_prime_diverse_casuali']} con i pesi casuali). Estremi: "
                 + "; ".join(f"{k} -> `{v}`" + (" (avviso: le rotazioni non si distinguono)" if k in w["avvisi_estremi"] else "")
                             for k, v in w["estremi"].items())
                 + ". Piu' frequenti: " + "; ".join(f"`{k}` {v / N_PESI:.0%}" for k, v in list(w["frequenza_prima_casuali"].items())[:3]))
    inatt = oat[oat["inattiva"]]
    nc = oat[~oat["conta"] & ~oat["inattiva"]]
    L += ["", "## Parametri che NON contano", "",
          f"**Senza alcun effetto sul risultato** ({len(inatt)}; voci non usate dal motore nella configurazione di base, "
          "per esempio i parametri delle sole alternative strutturali): " + ", ".join(f"`{p}`" for p in inatt.percorso) + ".", "",
          f"**Con effetto ma senza conseguenze sulla decisione** ({len(nc)}; nessun cambio di prima, prime tre o "
          f"alternative in alcuno scenario, |effetto| < {DELTA_NON_CONTA}, tau >= {TAU_NON_CONTA}): "
          + ", ".join(f"`{p}`" for p in nc.percorso) + ".", ""]
    FILE_MD.write_text("\n".join(L) + "\n", encoding="utf-8")

    def pulisci(o):
        if isinstance(o, dict):
            return {k: pulisci(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [pulisci(v) for v in o]
        if isinstance(o, (np.floating, float)):
            return None if math.isnan(o) else round(float(o), 6)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        return o
    cols = ["percorso", "etichetta", "base", "valore_meno", "valore_piu", "d_prima_meno", "d_prima_piu",
            "d_attuale_meno", "d_attuale_piu", "tau_min", "tau_min_solo_pioggia", "tau_min_irrigazione_libera",
            "prima_cambia", "prima_cambia_solo_pioggia", "prima_cambia_irrigazione_libera", "top3_cambia",
            "alt_cambiano", "limiti", "inattiva", "conta"]
    J = {"generato_il": dt.datetime.now().isoformat(timespec="seconds"), "lat": lat, "lon": lon,
         "versione": R["versione"],
         "indicatore_principale": {"scenario": SCENARIO_PRINCIPALE, "pesi": PESI_UGUALI},
         "conclusione": conclusione(R), "verifica_sottoinsieme": R["verifica"],
         "n_rotazioni_sottoinsieme": len(R["rotazioni"]),
         "base": {sc: {"prime3": v["classi"][:3], "attuale": v["attuale"], "alternative": v["alternative"]}
                  for sc, v in base["scenari"].items()},
         "oat": oat[cols].to_dict("records"), "escluse": R["escluse"],
         "strutturali": R["strutturali"],
         "montecarlo": {sc: {k: v for k, v in m.items() if k != "tau_tutti"} for sc, m in R["mc"].items()},
         "montecarlo_n": R["n_mc"], "montecarlo_falliti": R["n_mc_falliti"], "montecarlo_errori": R["errori_mc"], "seme": R["seme"],
         "prcc": R["prcc"].drop(columns="dof").to_dict("records"), "pesi": R["pesi"], "tempi": R["tempi"],
         "non_contano": nc.percorso.tolist(), "inattive": inatt.percorso.tolist()}
    out = _cache.processed_dir(lat, lon) / FILE_JSON
    out.write_text(json.dumps(pulisci(J), ensure_ascii=False, indent=1), encoding="utf-8")
    return {"md": FILE_MD, "json": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fieldwise.sensitivity", description=__doc__.split("\n")[0])
    ap.add_argument("--n-mc", type=int, default=N_MC)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--seme", type=int, default=SEME)
    ns = ap.parse_args(argv)
    R = run(ns.n_mc, ns.workers, ns.seme)
    f = scrivi(R)
    print(conclusione(R))
    print(f"tempo totale {R['tempi']['totale_s']:.0f} s; scritti {f['md']} e {f['json']}")
    return 0


if __name__ == "__main__":      # pragma: no cover
    raise SystemExit(main())
