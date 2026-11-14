"""Ensemble delle rotazioni: tutte le rotazioni x tutte le annate di partenza x gli scenari d'acqua.

Le annate storiche sono l'insieme di scenari climatici con cui si stima il rischio: ogni
simulazione (rotazione, annata di partenza, scenario) e' una realizzazione del motore
(`fieldwise.rotation.simulate`). Qui non c'e' nessun peso dell'agricoltore e nessun punteggio:
solo l'aggregazione statistica (`ranking.py` ordina e confronta).

Uscite di `run_ensemble`:

* ``dettaglio``: una riga per simulazione riuscita (indicatori per anno della rotazione).
* ``sintesi``: una riga per (classe ciclica, scenario), mediana su tutti i membri della classe e su
  tutte le annate. Le simulazioni con esito diverso da ``ok`` non entrano negli indicatori ma
  sono contate (``n_scartate``, ``motivo_scarto_prevalente``).

Colonne della sintesi (le usa `ranking.py`):
``resa_rel_mediana``, ``resa_rel_min`` (resa media della rotazione nell'annata peggiore), ``resa_rel_p10``
(percentile calcolato PER CLASSE su tutte le simulazioni dei suoi membri),
``irrigazione_mm``, ``concime_kg_n``, ``n_lisciviato_kg_n``, ``humus_t_ha`` (variazione annua),
``giorni_caldo``, ``ruscellamento_mm``, ``percolazione_mm``, ``deficit_n_kg_n``,
``margine_lordo_eur_ha`` (ricavo meno costo di concime e acqua, EUR/ha all'anno, MEDIA sulle annate
perche' e' il valore atteso; vedi ``economics.py`` e ``params/economia.yaml``),
``f_acqua``, ``f_caldo``, ``f_rotazione`` (medie), ``fattore_limitante``,
``quota_oltre_limite_n``, ``quota_cover_non_praticata``, ``cover_richieste`` (intervalli con cover
richiesta nel ciclo), ``cover_realizzata_quota`` (quota di quegli intervalli in cui la cover e' stata
realmente praticata; NaN se nessuna cover e' richiesta), ``equivalente_a`` (classe identica senza le
cover mai praticate, altrimenti ``nessuno``: `ranking` la esclude di default), ``conformita`` (la piu' sfavorevole tra i
regimi dei disciplinari), ``conformita_<regime>`` (uno per regime; non dipendono dallo scenario), ``attuale``,
``resa_t_ha_<coltura>`` (una per coltura principale: resa mediana in t/ha di quella coltura nella classe,
media dei suoi cicli nell'annata; NaN se la coltura non e' nella rotazione; nel dettaglio e' la resa di
quella simulazione). La resa relativa (frazione del potenziale) resta in ``resa_rel_*``.

Uso da riga di comando: ``python -m fieldwise.ensemble [--lat --lon] [--attuale "mais"]``.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import re
import time

import numpy as np
import pandas as pd

from . import config as _config
from . import economics as _eco
from . import params as _params
from . import rotation as rt
from .data import cache as _cache

FILE_DETTAGLIO = "ensemble_dettaglio.csv"
FILE_SINTESI = "ensemble_sintesi.csv"
FILE_META = "ensemble_meta.json"
NON_VALUTABILE = "non_valutabile"     # conformita' non tabulata (es. rotazione di lunghezza 1)
NESSUNO = "nessuno"                   # nessuna annata scartata
FATTORI = ("acqua", "caldo", "rotazione")
PREFISSO_RESA_T_HA = "resa_t_ha_"      # + coltura: resa in t/ha (colonne di dettaglio e sintesi)
PERCENTILE_RISCHIO = 10               # percentile basso della resa relativa
COL_MARGINE = "margine_lordo_eur_ha"  # margine su concime e acqua (EUR/ha all'anno); media, non mediana

# (colonna del dettaglio, chiave in simulate()['indicatori']) -- stesso nome del motore, unita' esplicita
_INDICATORI = (
    ("resa_rel_media", "resa_relativa_media"), ("resa_rel_minima", "resa_relativa_minima"),
    ("irrigazione_mm", "irrigazione_anno"), ("concime_kg_n", "concime_anno"),
    ("n_lisciviato_kg_n", "n_lisciviato_anno"), ("humus_t_ha", "humus_variazione_anno"),
    ("giorni_caldo", "giorni_caldo_anno"), ("ruscellamento_mm", "ruscellamento_anno"),
    ("percolazione_mm", "percolazione_anno"),
    ("f_acqua", "f_acqua_medio"), ("f_caldo", "f_caldo_medio"), ("f_rotazione", "f_rotazione_medio"),
    ("n_colture_oltre_mas", "n_colture_oltre_mas"), ("deficit_n_kg_n", "deficit_n_anno"))
# colonne del dettaglio aggregate con la mediana nella sintesi
_MEDIANE = ("irrigazione_mm", "concime_kg_n", "n_lisciviato_kg_n", "humus_t_ha", "giorni_caldo",
            "ruscellamento_mm", "percolazione_mm", "deficit_n_kg_n")


# =============================================================================
# Normalizzazione degli ingressi
# =============================================================================
def parse_rotazione(x) -> rt.Rotation:
    """Rotazione da un oggetto ``Rotation``, da un'etichetta ('mais > soia+cover > frumento',
    'mais') o da una sequenza di voci ('mais', 'soia+cover', ...) di lunghezza qualsiasi."""
    if isinstance(x, rt.Rotation):
        return x
    if isinstance(x, str):
        return rt.Rotation.from_label(x)
    voci = [str(v) for v in x]
    if not voci:
        raise ValueError("rotazione vuota")
    return rt.Rotation.from_label(rt.SEP.join(voci))


def _conformita(p: dict, rot: rt.Rotation) -> dict:
    """Conformita' per regime. Una rotazione che ripete una sequenza piu' corta di cui la lunghezza
    3 e' multipla (es. 'mais' = mais > mais > mais) usa la riga di quella sequenza ripetuta."""
    c = rt.compliance(p, rot.crops)
    if all(v is None for v in c.values()) and rot.n < 3 and 3 % rot.n == 0:
        c = rt.compliance(p, rot.crops * (3 // rot.n))
    return {r: (NON_VALUTABILE if v is None else v) for r, v in c.items()}


_ORDINE_CONF = ("conforme", "conforme_solo_in_deroga", "non_conforme")


def _peggiore(conf: dict) -> str:
    """Stato di conformita' piu' sfavorevole tra i regimi (``non_valutabile`` se nessuno e' valutabile)."""
    st = [s for s in conf.values() if s in _ORDINE_CONF]
    return max(st, key=_ORDINE_CONF.index) if st else NON_VALUTABILE


def _voce(p: dict, rot: rt.Rotation) -> dict:
    return {"rotation": rot, "label": rot.label, "classe": rot.canonical().label,
            "conformita": _conformita(p, rot)}


def _verifica_colture(p: dict, rot: rt.Rotation) -> rt.Rotation:
    """Errore chiaro se una coltura non e' tra quelle principali di crops.yaml (o e' vuota)."""
    ammesse = rt.main_crops(p)
    for c in rot.crops:
        if c not in ammesse:
            raise ValueError(f"coltura sconosciuta o vuota: {c!r} nella rotazione {rot.label!r}; "
                             f"colture ammesse: {', '.join(ammesse)}")
    return rot


def _rotazione_attuale(rotazione, p: dict | None = None) -> tuple:
    """``(rotazione, nota)``: la rotazione attuale con le ripetizioni di una classe triennale
    espanse ('mais' = 'mais > mais > mais'); ``nota`` e' None se l'etichetta resta quella indicata.
    Con ``p`` verifica che le colture siano tra quelle principali."""
    att = parse_rotazione(rotazione)
    if p is not None:
        att = _verifica_colture(p, att)
    indicata, nota = att.label, None
    if att.n < 3 and 3 % att.n == 0:
        att = rt.Rotation(att.crops * (3 // att.n), att.cover * (3 // att.n))
        if att.label != indicata:
            nota = (f"la rotazione attuale '{indicata}' e' la ripetizione di '{att.canonical().label}': "
                    f"marcata su quella classe")
    return att, nota


def classe_rotazione_attuale(rotazione, p: dict | None = None) -> str:
    """Etichetta canonica della classe ciclica a cui e' ricondotta la rotazione attuale in
    ``run_ensemble`` (etichetta, ``Rotation`` o sequenza di voci). Una ripetizione di una classe
    triennale ('mais') vale come la classe ('mais > mais > mais'). Con ``p`` verifica le colture
    (``ValueError`` se sconosciute), senza ``p`` no."""
    return _rotazione_attuale(rotazione, p)[0].canonical().label


def _membri(rot: rt.Rotation) -> list:
    """Membri distinti della classe ciclica di ``rot`` (le sue permutazioni cicliche)."""
    visti, out = set(), []
    for k in range(rot.n):
        r = rot.shifted(k)
        if r.label not in visti:
            visti.add(r.label)
            out.append(r)
    return out


def _motivo_breve(esito: str, motivo: str) -> str:
    """Motivo di scarto senza date e numeri, cosi' che motivi uguali si contino insieme."""
    m = re.sub(r"\d{4}-\d{2}-\d{2}", "<data>", str(motivo))
    m = re.sub(r"\d+(\.\d+)?", "<n>", m)
    return f"{esito}: {m}".strip(": ")


# =============================================================================
# Ensemble
# =============================================================================
def run_ensemble(ctx=None, lat=None, lon=None, rotazioni=None, scenari=None, n_avviamento=1,
                 rotazione_attuale=None, p=None, metodo_caldo="deryng", **opzioni_simulate):
    """Esegue l'ensemble e restituisce ``(dettaglio, sintesi)``.

    ``ctx``: contesto di ``rotation.build_context`` (costruito qui, una sola volta, se None;
    ``p`` = albero di parametri alternativo, ``lat``/``lon`` = punto). ``rotazioni``: elenco di
    ``Rotation``, etichette o voci di ``enumerate_rotations`` (default: le 216 rotazioni triennali).
    ``scenari``: sottoinsieme di ``rotation.SCENARI`` (default: tutti). ``rotazione_attuale``:
    etichetta, ``Rotation`` o sequenza di lunghezza qualsiasi (coltura sconosciuta = ``ValueError``);
    una ripetizione di una classe triennale (es. 'mais' = 'mais > mais > mais') e' ricondotta a quella
    classe; se la classe e' tra quelle simulate la si marca, altrimenti i suoi membri si simulano in
    piu' (es. lunghezza 2; nota in ``meta['note']``) e la si aggiunge alla sintesi (marcata ``attuale``).
    ``metodo_caldo``: funzione del caldo (``yield_model.METODI_CALDO``, default 'deryng'), passata a
    ``rotation.simulate``. ``opzioni_simulate`` (``metodo_et``, ``riparto``, ``in_conflitto``)
    passano a ``rotation.simulate``. Una simulazione non riuscita (esito diverso da ``ok``, anche per
    parametri degeneri) non interrompe l'ensemble: si conta tra le scartate. I metadati del calcolo stanno in ``.attrs['meta']`` di entrambe
    le tabelle."""
    t0 = time.perf_counter()
    if ctx is None:
        ctx = rt.build_context(p, lat=lat, lon=lon)
    elif p is not None:
        raise ValueError("passare o ctx o p (il contesto contiene gia' i parametri)")
    p = ctx.p
    scenari = tuple(rt.SCENARI if scenari is None else scenari)
    for s in scenari:
        if s not in ctx.scenarios:
            raise ValueError(f"scenario sconosciuto: {s} (ammessi {tuple(ctx.scenarios)})")
    if rotazioni is None:
        voci = [{"rotation": e["rotation"], "label": e["label"], "classe": e["classe"],
                 "conformita": {r: (NON_VALUTABILE if v is None else v)
                                for r, v in e["conformita"].items()}}
                for e in rt.enumerate_rotations(p)]
    else:
        voci = [_voce(p, _verifica_colture(p, parse_rotazione(r["rotation"] if isinstance(r, dict) else r)))
                for r in rotazioni]
    classi_simulate = {v["classe"] for v in voci}
    attuale, note = None, []
    if rotazione_attuale is not None:
        att, nota = _rotazione_attuale(rotazione_attuale, p)
        if nota:
            note.append(nota)
        attuale = att.canonical().label
        if attuale not in classi_simulate:
            voci += [_voce(p, m) for m in _membri(att)]
            if att.n != 3:
                note.append(f"la rotazione attuale ha {att.n} colture: il confronto con le triennali usa "
                            f"annate valutate diverse (cicli di durata diversa)")
    regimi = sorted({r for v in voci for r in v["conformita"]})
    n_membri = collections.Counter(v["classe"] for v in voci)

    anni = range(int(ctx.year[0]), int(ctx.year[ctx.last_idx]) + 1)
    colture_principali = rt.main_crops(p)
    righe = []
    scarti = collections.defaultdict(collections.Counter)    # (classe, scenario) -> motivo -> n
    cover_vista = {}       # etichetta -> [intervallo i: cover praticata almeno una volta (qualsiasi anno, scenario)]
    for v in voci:
        rot = v["rotation"]
        conf = {f"conformita_{r}": v["conformita"].get(r, NON_VALUTABILE) for r in regimi}
        vista = cover_vista.setdefault(v["label"], [False] * rot.n)
        for anno in anni:
            rc = rt.build_calendar(ctx, rot, anno, n_avviamento,
                                   opzioni_simulate.get("in_conflitto", "rinvia"))
            if not rc.ok:
                m = _motivo_breve(rc.esito, rc.motivo)
                for sc in scenari:
                    scarti[(v["classe"], sc)][m] += 1
                continue
            for sc in scenari:
                out = rt.simulate(ctx, rot, anno, sc, n_avviamento=n_avviamento,
                                  calendario=rc, metodo_caldo=metodo_caldo, **opzioni_simulate)
                if out["esito"] != rt.ESITO_OK:        # non dovrebbe accadere con calendario ok
                    scarti[(v["classe"], sc)][_motivo_breve(out["esito"], out["motivo"])] += 1
                    continue
                ind = out["indicatori"]
                for i, iv in enumerate(out["intervalli"]):      # intervallo i = dopo la coltura i
                    if iv["tipo"] == "cover":
                        vista[i] = True
                nudi = sum(1 for iv in out["intervalli"] if iv["cover_richiesta"] and iv["tipo"] != "cover")
                riga = {"etichetta": v["label"], "classe": v["classe"], "anno_partenza": int(anno),
                        "anno_valutato": out["anno_valutato"], "scenario": sc, **conf}
                riga.update({col: ind[k] for col, k in _INDICATORI})
                riga[COL_MARGINE] = _eco.margine_anno(p, out)
                riga.update(
                    cover_richieste=sum(1 for iv in out["intervalli"] if iv["cover_richiesta"]),
                    cover_non_praticate=nudi,
                    res_acqua_mm=out["residui"]["acqua_mm"],
                    res_azoto_max_segmento_kg=out["residui"]["azoto_max_segmento_kg"],
                    res_azoto_rotazione_kg=out["residui"]["azoto_rotazione_kg"],
                    attuale=v["classe"] == attuale)
                rese = collections.defaultdict(list)
                for c in out["colture"]:
                    rese[c["coltura"]].append(c["resa"])
                riga.update({f"{PREFISSO_RESA_T_HA}{c}": (float(np.mean(rese[c])) if c in rese else float("nan"))
                             for c in colture_principali})
                righe.append(riga)
    dettaglio = pd.DataFrame(righe)
    sintesi = _sintesi(dettaglio, voci, scenari, regimi, ctx, scarti, n_membri, attuale,
                       _equivalenze(voci, cover_vista, dettaglio))
    n_ok = len(dettaglio)
    n_scartate = int(sum(sum(c.values()) for c in scarti.values()))
    meta = {"calcolato_il": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "lat": _config.PILOT_LAT if lat is None else lat,
            "lon": _config.PILOT_LON if lon is None else lon, "n_simulazioni": n_ok, "n_scartate": n_scartate,
            "tempo_s": round(time.perf_counter() - t0, 3),
            "n_classi": int(sintesi["classe"].nunique()), "scenari": list(scenari),
            "n_avviamento": n_avviamento, "rotazione_attuale": attuale,
            "opzioni_simulate": {k: str(x) for k, x in
                                 {**opzioni_simulate,
                                  **({"metodo_caldo": metodo_caldo} if metodo_caldo != "deryng" else {})}.items()},
            "hash_parametri": _hash_albero(p), "hash_file_parametri": _hash_file_parametri(),
            "annate_partenza": [int(anni[0]), int(anni[-1])],          # tentate
            "note": note,
            "colonne_note": {"resa_rel_p10": "percentile per classe, calcolato su tutte le simulazioni dei "
                             "membri della classe: classi equivalenti con un diverso numero di membri "
                             "possono differire"}}
    if n_ok:
        meta["annate_partenza_con_risultati"] = [int(dettaglio["anno_partenza"].min()),
                                                 int(dettaglio["anno_partenza"].max())]
        meta["anni_valutati"] = [int(dettaglio["anno_valutato"].min()), int(dettaglio["anno_valutato"].max())]
    dettaglio.attrs["meta"] = meta
    sintesi.attrs["meta"] = meta
    return dettaglio, sintesi


def _equivalenze(voci, cover_vista, dettaglio) -> dict:
    """classe -> classe identica senza le cover mai praticate. Un intervallo con cover richiesta e mai
    realizzata (in nessuna annata ne' scenario) e' a suolo nudo come se la cover non fosse richiesta:
    la classe con quelle cover tolte ha lo stesso risultato. Si indica solo se tutti i membri della
    classe danno la stessa classe ridotta e questa e' tra quelle simulate; altrimenti ``NESSUNO``."""
    simulate_ = set(dettaglio["classe"]) if len(dettaglio) else set()
    ridotte = {}
    for v in voci:
        rot = v["rotation"]
        vista = cover_vista.get(v["label"], [False] * rot.n)
        senza = tuple(c and vista[i] for i, c in enumerate(rot.cover))
        if not any(rot.cover) or senza == rot.cover:
            ridotte.setdefault(v["classe"], set()).add(NESSUNO)
        else:
            ridotte.setdefault(v["classe"], set()).add(rt.Rotation(rot.crops, senza).canonical().label)
    out = {}
    for cl, ins in ridotte.items():
        (x,) = ins if len(ins) == 1 else (NESSUNO,)
        out[cl] = x if x != cl and x in simulate_ else NESSUNO
    return out


def _sintesi(dettaglio, voci, scenari, regimi, ctx, scarti, n_membri, attuale, equivalenze):
    """Una riga per (classe ciclica, scenario) in ordine di classe e di scenario."""
    classi = list(dict.fromkeys(v["classe"] for v in voci))
    rapp = {}
    for v in voci:
        rapp.setdefault(v["classe"], v)
    gruppi = ({k: g for k, g in dettaglio.groupby(["classe", "scenario"], sort=False)}
              if len(dettaglio) else {})
    righe = []
    for cl in sorted(classi):
        v = rapp[cl]
        rot_cl = rt.Rotation.from_label(cl)
        for sc in scenari:
            g = gruppi.get((cl, sc))
            n = 0 if g is None else len(g)
            sc_scarti = scarti.get((cl, sc), collections.Counter())
            r = {"classe": cl, "scenario": sc, "n_membri": n_membri[cl], "n_simulazioni": n,
                 "n_scartate": int(sum(sc_scarti.values())),
                 "motivo_scarto_prevalente": sc_scarti.most_common(1)[0][0] if sc_scarti else NESSUNO,
                 "attuale": cl == attuale,
                 "conformita": _peggiore(v["conformita"])}
            for reg in regimi:
                r[f"conformita_{reg}"] = v["conformita"].get(reg, NON_VALUTABILE)
            nan = float("nan")
            if n:
                rr = g["resa_rel_media"].to_numpy(float)
                r.update(resa_rel_mediana=float(np.median(rr)), resa_rel_min=float(rr.min()),
                         resa_rel_p10=float(np.percentile(rr, PERCENTILE_RISCHIO)),
                         resa_rel_minima_coltura=float(np.median(g["resa_rel_minima"])))
                for c in _MEDIANE:
                    r[c] = float(np.median(g[c].to_numpy(float)))
                r[COL_MARGINE] = float(g[COL_MARGINE].mean())     # valore atteso sulle annate
                for f in FATTORI:
                    r[f"f_{f}"] = float(g[f"f_{f}"].mean())
                r["quota_oltre_limite_n"] = float((g["n_colture_oltre_mas"] > 0).mean())
                ric = float(g["cover_richieste"].sum())
                r["quota_cover_non_praticata"] = float(g["cover_non_praticate"].sum() / ric) if ric else 0.0
                r["res_acqua_max_mm"] = float(g["res_acqua_mm"].abs().max())
                r["res_azoto_max_kg"] = float(max(g["res_azoto_max_segmento_kg"].abs().max(),
                                                  g["res_azoto_rotazione_kg"].abs().max()))
            else:
                for c in ("resa_rel_mediana", "resa_rel_min", "resa_rel_p10", "resa_rel_minima_coltura",
                          *_MEDIANE, COL_MARGINE, "f_acqua", "f_caldo", "f_rotazione", "quota_oltre_limite_n",
                          "quota_cover_non_praticata", "res_acqua_max_mm", "res_azoto_max_kg"):
                    r[c] = nan
            medie = [r[f"f_{f}"] for f in FATTORI]
            r["fattore_limitante"] = FATTORI[int(np.argmin(medie))] if n else NESSUNO
            r["cover_richieste"] = int(sum(rot_cl.cover))
            r["cover_realizzata_quota"] = (1.0 - r["quota_cover_non_praticata"]
                                           if n and r["cover_richieste"] else nan)
            r["equivalente_a"] = equivalenze.get(cl, NESSUNO) if n else NESSUNO
            for c in rt.main_crops(ctx.p):
                col = f"{PREFISSO_RESA_T_HA}{c}"
                r[col] = float(np.nanmedian(g[col].to_numpy(float))) if n and c in rot_cl.crops else nan
            righe.append(r)
    return pd.DataFrame(righe)


# =============================================================================
# Impronte dei parametri
# =============================================================================
def _hash_albero(p) -> str:
    """Impronta del contenuto dell'albero di parametri effettivamente usato."""
    s = json.dumps(p, sort_keys=True, default=str, ensure_ascii=True)
    return hashlib.sha256(s.encode()).hexdigest()


def _hash_file_parametri() -> dict:
    """sha256 di ciascun ``params/*.yaml`` e di ``SCHEMA.md`` su disco."""
    out = {}
    for f in sorted(_config.PARAMS_DIR.glob("*.yaml")):
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


# =============================================================================
# Cache dei risultati (demo offline)
# =============================================================================
def save_ensemble(dettaglio, sintesi, lat=None, lon=None):
    """Scrive ``ensemble_dettaglio.csv``, ``ensemble_sintesi.csv`` e ``ensemble_meta.json`` nella
    cartella degli elaborati del punto. Restituisce la cartella."""
    lat = _config.PILOT_LAT if lat is None else lat
    lon = _config.PILOT_LON if lon is None else lon
    d = _cache.processed_dir(lat, lon)
    meta = dict(sintesi.attrs.get("meta") or dettaglio.attrs.get("meta") or {})
    meta.update(lat=lat, lon=lon, n_simulazioni=int(len(dettaglio)))
    dettaglio.to_csv(d / FILE_DETTAGLIO, index=False)
    sintesi.to_csv(d / FILE_SINTESI, index=False)
    (d / FILE_META).write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str) + "\n")
    return d


def load_ensemble(lat=None, lon=None):
    """Rilegge ``(dettaglio, sintesi)`` salvati da ``save_ensemble`` (i metadati in ``.attrs['meta']``).
    Solleva ``CacheMiss`` se manca un file."""
    lat = _config.PILOT_LAT if lat is None else lat
    lon = _config.PILOT_LON if lon is None else lon
    d = _cache.processed_dir(lat, lon, create=False)
    for f in (FILE_DETTAGLIO, FILE_SINTESI, FILE_META):
        if not (d / f).exists():
            raise _cache.CacheMiss(f"ensemble non in cache: {d / f}")
    dettaglio = pd.read_csv(d / FILE_DETTAGLIO)
    sintesi = pd.read_csv(d / FILE_SINTESI)
    meta = json.loads((d / FILE_META).read_text())
    dettaglio.attrs["meta"] = meta
    sintesi.attrs["meta"] = meta
    return dettaglio, sintesi


# =============================================================================
# Riga di comando
# =============================================================================
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fieldwise.ensemble", description=__doc__.split("\n")[0])
    ap.add_argument("--lat", type=float, default=_config.PILOT_LAT)
    ap.add_argument("--lon", type=float, default=_config.PILOT_LON)
    ap.add_argument("--attuale", default=None, help='rotazione attuale, es. "mais" o "mais > soia > frumento"')
    ns = ap.parse_args(argv)
    det, sin = run_ensemble(lat=ns.lat, lon=ns.lon, rotazione_attuale=ns.attuale)
    d = save_ensemble(det, sin, ns.lat, ns.lon)
    m = sin.attrs["meta"]
    print(f"ensemble ({ns.lat}, {ns.lon}): {m['n_simulazioni']} simulazioni riuscite, "
          f"{m['n_scartate']} scartate, {m['tempo_s']:.1f} s")
    print(f"dettaglio {det.shape[0]} righe x {det.shape[1]} colonne; "
          f"sintesi {sin.shape[0]} righe ({m['n_classi']} classi x {len(m['scenari'])} scenari)")
    if ns.attuale:
        print(f"rotazione attuale: {m['rotazione_attuale']}")
    for n in m.get("note", []):
        print(f"nota: {n}")
    print(f"annate di partenza tentate {m['annate_partenza']}, con risultati "
          f"{m.get('annate_partenza_con_risultati')}, anni valutati {m.get('anni_valutati')}")
    print(f"salvato in {d}")
    return 0


if __name__ == "__main__":      # pragma: no cover
    raise SystemExit(main())

__all__ = ["run_ensemble", "classe_rotazione_attuale", "save_ensemble", "load_ensemble", "parse_rotazione", "main",
           "FATTORI", "NON_VALUTABILE", "NESSUNO"]
