"""Test del modulo di rotazione (`fieldwise.rotation`): etichette, regole, calendario,
simulazione sul meteo reale del punto pilota, scenari d'acqua, stato mai azzerato, cover,
fattore di rotazione, regressione e prestazioni.

I valori attesi che dipendono dai parametri vengono ricavati da `fieldwise.params` e dal
contesto (`ctx.scenarios`, `ctx.cover`, `ctx.crop`), non scritti come numeri fissi. I test sul
meteo reale usano un solo `build_context()` per modulo e si saltano se la cache manca.
"""
from __future__ import annotations

import dataclasses
import math
import os
import time

import numpy as np
import pytest

from fieldwise import params as fparams
from fieldwise import rotation as rt
from fieldwise import yield_model as ym

MAIS_SOIA_FRUMENTO = "mais > soia > frumento"
SCEN_PIOGGIA, SCEN_TETTO, SCEN_LIBERA = rt.SCENARI
TOL_RES_ACQUA = 1e-6    # mm
TOL_RES_N = 1e-6        # kg N/ha


# =============================================================================
# Fixture
# =============================================================================

@pytest.fixture(scope="module")
def pars():
    return fparams.load_params()


@pytest.fixture(scope="module")
def ctx(pars):
    """Contesto sul meteo reale del punto pilota, costruito una sola volta per modulo."""
    old = os.environ.get("FIELDWISE_OFFLINE")
    os.environ["FIELDWISE_OFFLINE"] = "1"
    try:
        return rt.build_context(pars)
    except FileNotFoundError as e:       # cache.CacheMiss e' un FileNotFoundError
        pytest.skip(f"cache meteo del punto pilota assente: {e}")
    finally:
        if old is None:
            os.environ.pop("FIELDWISE_OFFLINE", None)
        else:
            os.environ["FIELDWISE_OFFLINE"] = old


@pytest.fixture(scope="module")
def msf():
    return rt.Rotation.from_label(MAIS_SOIA_FRUMENTO)


@pytest.fixture(scope="module")
def anno_centrale(ctx, msf):
    """Un'annata di partenza centrale tra quelle in cui la rotazione e' simulabile."""
    ys = rt.start_years(ctx, msf)
    assert ys, "nessuna annata simulabile"
    return ys[len(ys) // 2]


# =============================================================================
# 1) Etichette e permutazioni cicliche (non richiedono il meteo)
# =============================================================================

def test_etichetta_andata_e_ritorno():
    for lab in ("mais > soia > frumento", "mais+cover > soia > frumento+cover",
                "frumento+cover > frumento+cover > frumento+cover", "mais", "soia+cover"):
        r = rt.Rotation.from_label(lab)
        assert r.label == lab
        assert rt.Rotation.from_label(r.label) == r
    r = rt.Rotation(("mais", "soia", "frumento"), (True, False, True))
    assert r.label == "mais+cover > soia > frumento+cover"
    assert rt.Rotation.from_label(r.label) == r


def test_etichetta_cover_dopo_la_coltura_giusta():
    r = rt.Rotation.from_label("mais > soia+cover > frumento")
    assert r.crops == ("mais", "soia", "frumento")
    assert r.cover == (False, True, False)


def test_rotation_validazione():
    with pytest.raises(ValueError):
        rt.Rotation(("mais", "soia"), (False,))
    with pytest.raises(ValueError):
        rt.Rotation((), ())


def test_shifted_e_canonical_coerenti():
    r = rt.Rotation(("mais", "soia", "frumento"), (True, False, False))
    assert r.shifted(0) == r
    assert r.shifted(r.n) == r
    assert r.shifted(1) == rt.Rotation(("soia", "frumento", "mais"), (False, False, True))
    # la cover resta legata alla propria coltura nello spostamento
    for k in range(r.n):
        s = r.shifted(k)
        assert sorted(zip(s.crops, s.cover)) == sorted(zip(r.crops, r.cover))
    # ricomporre i k spostamenti riporta alla rotazione di partenza
    assert r.shifted(1).shifted(2) == r
    can = r.canonical()
    for k in range(r.n):
        assert r.shifted(k).canonical() == can
    assert can.canonical() == can            # idempotente
    assert can in {r.shifted(k) for k in range(r.n)}


def test_canonical_distingue_rotazioni_non_cicliche():
    a = rt.Rotation(("mais", "soia", "frumento"), (False,) * 3)
    b = rt.Rotation(("mais", "frumento", "soia"), (False,) * 3)   # ordine inverso: classe diversa
    assert a.canonical() != b.canonical()
    c = rt.Rotation(("mais", "soia", "frumento"), (True, False, False))
    assert a.canonical() != c.canonical()                          # la cover cambia la classe


# =============================================================================
# 2) Enumerazione e conformita' (non richiedono il meteo)
# =============================================================================

@pytest.fixture(scope="module")
def elenco(pars):
    return rt.enumerate_rotations(pars, length=3)


def test_enumerate_216_rotazioni_76_classi_nessuna_esclusa(pars, elenco):
    n_colture = len(rt.main_crops(pars))
    assert len(elenco) == n_colture ** 3 * 2 ** 3 == 216
    assert len({e["label"] for e in elenco}) == 216
    assert len({e["classe"] for e in elenco}) == 76
    assert sum(e["rappresentante"] for e in elenco) == 76
    for e in elenco:
        assert e["n_equivalenti"] == sum(1 for x in elenco if x["classe"] == e["classe"])
        assert rt.Rotation.from_label(e["label"]) == e["rotation"]


def test_ogni_rotazione_ha_uno_stato_di_conformita(pars, elenco):
    regimi = set(pars["rotation_rules"]["successioni_vietate"]["mais_mais_mais"])
    for e in elenco:
        conf = e["conformita"]
        assert set(conf) == regimi, e["label"]
        assert all(isinstance(v, str) and v for v in conf.values()), (e["label"], conf)


def test_permutazioni_cicliche_stesso_stato(elenco):
    per_classe = {}
    for e in elenco:
        per_classe.setdefault(e["classe"], []).append(e["conformita"])
    for classe, stati in per_classe.items():
        assert all(s == stati[0] for s in stati), classe


def test_mais_continuo_non_conforme_quinquennale(pars):
    c = rt.compliance(pars, ("mais", "mais", "mais"))
    chiavi = [k for k in c if "quinquennale" in k]
    assert chiavi
    for k in chiavi:
        assert c[k] == "non_conforme", (k, c[k])


def test_mais_soia_frumento_conforme(pars):
    c = rt.compliance(pars, ("mais", "soia", "frumento"))
    assert c and all(v == "conforme" for v in c.values()), c
    # la conformita' ignora le cover e vale per ogni permutazione ciclica
    assert rt.compliance(pars, ("soia", "frumento", "mais")) == c
    assert rt.compliance(pars, ("frumento", "mais", "soia")) == c


def test_compliance_sequenza_non_tabulata(pars):
    c = rt.compliance(pars, ("mais", "soia"))
    assert c and all(v is None for v in c.values())


# =============================================================================
# 3) Simulazione di mais > soia > frumento da un'annata centrale, nei tre scenari
# =============================================================================

@pytest.mark.parametrize("scenario", rt.SCENARI)
def test_simulazione_base(ctx, msf, anno_centrale, scenario):
    out = rt.simulate(ctx, msf, anno_centrale, scenario)
    assert out["esito"] == rt.ESITO_OK, out.get("motivo")
    for k in ("label", "conformita", "colture", "intervalli", "indicatori", "residui",
              "durata_anni", "anno_valutato"):
        assert k in out
    assert out["label"] == MAIS_SOIA_FRUMENTO
    assert len(out["colture"]) == msf.n
    assert [c["coltura"] for c in out["colture"]] == list(msf.crops)

    for c in out["colture"]:
        for f in ("f_acqua", "f_caldo", "f_rotazione"):
            assert 0.0 <= c[f] <= 1.0, (c["coltura"], f, c[f])
        prodotto = c["f_acqua"] * c["f_caldo"] * c["f_rotazione"]
        assert c["resa"] == pytest.approx(c["resa_potenziale"] * prodotto, rel=1e-9)
        assert c["resa_relativa"] == pytest.approx(prodotto, rel=1e-9)
        assert c["resa_potenziale"] == pytest.approx(
            fparams.get(ctx.p, f"crops.{c['coltura']}.resa_potenziale"))

    # date in ordine: semina < fioritura < raccolta, e semina successiva dopo la raccolta
    cs = out["colture"]
    for c in cs:
        assert c["semina"] < c["fioritura"] < c["raccolta"], c
    for prec, succ in zip(cs, cs[1:]):
        assert succ["semina"] > prec["raccolta"], (prec["coltura"], succ["coltura"])

    r = out["residui"]
    assert abs(r["acqua_mm"]) < TOL_RES_ACQUA
    assert abs(r["azoto_max_segmento_kg"]) < TOL_RES_N
    assert abs(r["azoto_max_giorno_kg"]) < TOL_RES_N
    assert abs(r["azoto_rotazione_kg"]) < TOL_RES_N
    assert out["durata_anni"] == pytest.approx(msf.n, abs=0.5)


def test_semina_del_ciclo_dopo_raccolta_dell_ultima_coltura(ctx, msf, anno_centrale):
    """Il ciclo valutato si chiude prima della semina della prima coltura del ciclo seguente."""
    out = rt.simulate(ctx, msf, anno_centrale, SCEN_PIOGGIA)
    assert out["colture"][-1]["raccolta"] <= out["fine"]
    assert out["colture"][0]["semina"] == out["inizio"]
    assert out["anno_valutato"] == int(out["inizio"][:4])


# =============================================================================
# 4) Scenari
# =============================================================================

def _anni(ctx, rot, passo=3):
    return rt.start_years(ctx, rot)[::passo]


def test_scenari_dichiarati(ctx):
    assert set(ctx.scenarios) == set(rt.SCENARI)
    assert len(rt.SCENARI) == 3


@pytest.mark.parametrize("etichetta", [MAIS_SOIA_FRUMENTO, "mais > mais > mais"])
def test_irrigazione_nulla_in_solo_pioggia(ctx, etichetta):
    rot = rt.Rotation.from_label(etichetta)
    for y in _anni(ctx, rot):
        out = rt.simulate(ctx, rot, y, SCEN_PIOGGIA)
        assert out["esito"] == rt.ESITO_OK
        assert out["indicatori"]["irrigazione_anno"] == 0.0
        assert all(c["irrigazione"] == 0.0 for c in out["colture"])


@pytest.mark.parametrize("etichetta", [MAIS_SOIA_FRUMENTO, "mais > mais > mais", "soia > soia > soia"])
def test_irrigazione_non_oltre_il_tetto(ctx, etichetta):
    rot = rt.Rotation.from_label(etichetta)
    cap = ctx.scenarios[SCEN_TETTO]["cap"]
    visto_irrigazione = False
    for y in _anni(ctx, rot):
        out = rt.simulate(ctx, rot, y, SCEN_TETTO)
        for c in out["colture"]:
            tetto = cap.get(c["coltura"], 0.0)
            assert c["irrigazione"] <= tetto + 1e-9, (y, c["coltura"], c["irrigazione"], tetto)
            visto_irrigazione |= c["irrigazione"] > 0
    assert visto_irrigazione, "il tetto non e' mai stato esercitato: test non informativo"


def test_resa_relativa_mais_non_decrescente_tra_scenari(ctx):
    for etichetta in (MAIS_SOIA_FRUMENTO, "mais > mais > mais"):
        rot = rt.Rotation.from_label(etichetta)
        for y in rt.start_years(ctx, rot)[::2]:
            cal = rt.build_calendar(ctx, rot, y)
            rr = []
            for sc in (SCEN_PIOGGIA, SCEN_TETTO, SCEN_LIBERA):
                out = rt.simulate(ctx, rot, y, sc, calendario=cal)
                mais = [c["resa_relativa"] for c in out["colture"] if c["coltura"] == "mais"]
                rr.append(float(np.mean(mais)))
            assert rr[0] <= rr[1] + 1e-9 <= rr[2] + 2e-9, (etichetta, y, rr)


def test_frumento_mai_irrigato(ctx):
    assert int(fparams.get(ctx.p, "crops.frumento.irrigabile")) == 0
    for etichetta in (MAIS_SOIA_FRUMENTO, "frumento > frumento > frumento"):
        rot = rt.Rotation.from_label(etichetta)
        for y in _anni(ctx, rot):
            cal = rt.build_calendar(ctx, rot, y)
            for sc in rt.SCENARI:
                out = rt.simulate(ctx, rot, y, sc, calendario=cal)
                for c in out["colture"]:
                    if c["coltura"] == "frumento":
                        assert c["irrigazione"] == 0.0, (y, sc)


# =============================================================================
# 5) Stato mai azzerato e determinismo
# =============================================================================

def test_stato_ereditato_conta(ctx, msf):
    """Stesso ciclo valutato, con e senza i cicli di avviamento: l'azoto/humus differiscono."""
    y_av = next(y for y in rt.start_years(ctx, msf) if y + 3 in rt.start_years(ctx, msf))
    con = rt.simulate(ctx, msf, y_av, SCEN_TETTO, n_avviamento=1)
    # primo anno di semina della simulazione con avviamento -> stesso ciclo valutato senza avviamento
    ciclo = con["inizio"]
    y_senza = int(ciclo[:4])
    senza = rt.simulate(ctx, msf, y_senza, SCEN_TETTO, n_avviamento=0)
    assert con["esito"] == senza["esito"] == rt.ESITO_OK
    assert senza["inizio"] == ciclo, "i due calcoli non valutano lo stesso ciclo"
    a, b = con["indicatori"], senza["indicatori"]
    chiavi_n = ("n_lisciviato_anno", "concime_anno", "humus_variazione_anno", "fissazione_anno")
    diff = [k for k in chiavi_n if not math.isclose(a[k], b[k], rel_tol=1e-9, abs_tol=1e-9)]
    assert diff, f"indicatori di azoto identici con e senza avviamento: {[a[k] for k in chiavi_n]}"
    # lo stato finale del ciclo avviato parte dallo stato iniziale solo senza avviamento
    assert con["stato_finale"]["azoto"] != senza["stato_finale"]["azoto"]


def test_avviamento_literal_indicatori_diversi(ctx, msf, anno_centrale):
    con = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO, n_avviamento=1)
    senza = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO, n_avviamento=0)
    assert con["esito"] == senza["esito"] == rt.ESITO_OK
    chiavi_n = ("n_lisciviato_anno", "concime_anno", "humus_variazione_anno")
    assert any(con["indicatori"][k] != senza["indicatori"][k] for k in chiavi_n)


def test_determinismo(ctx, msf, anno_centrale):
    a = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO)
    b = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO)
    cal = rt.build_calendar(ctx, msf, anno_centrale)
    c = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO, calendario=cal)
    d = rt.simulate(ctx, msf, anno_centrale, SCEN_TETTO, calendario=cal)
    for x in (b, c, d):
        assert x["indicatori"] == a["indicatori"]
        assert x["residui"] == a["residui"]
        assert x["colture"] == a["colture"]


def test_il_calendario_non_dipende_dallo_scenario(ctx, msf, anno_centrale):
    cal = rt.build_calendar(ctx, msf, anno_centrale)
    for sc in rt.SCENARI:
        con = rt.simulate(ctx, msf, anno_centrale, sc, calendario=cal)
        senza = rt.simulate(ctx, msf, anno_centrale, sc)
        assert con["indicatori"] == senza["indicatori"]


# =============================================================================
# 6) Annata troppo tarda
# =============================================================================

def test_annata_troppo_tarda_non_simulabile(ctx, msf):
    ys = rt.start_years(ctx, msf)
    ultimo_ok = ys[-1]
    ultimo_anno_serie = int(ctx.year[ctx.last_idx])
    assert ultimo_ok < ultimo_anno_serie
    tardive = [y for y in range(ultimo_ok + 1, ultimo_anno_serie + 1)]
    assert tardive
    for y in tardive:
        out = rt.simulate(ctx, msf, y, SCEN_TETTO)
        assert out["esito"] != rt.ESITO_OK, y
        assert out["esito"] == rt.ESITO_NON_SIMULABILE
        assert out["motivo"]
        # nessun numero inventato: niente indicatori, colture, residui ne' durata
        assert not out.get("indicatori")
        assert not out.get("colture")
        assert "residui" not in out
        assert "durata_anni" not in out or math.isnan(out["durata_anni"])


def test_annata_fuori_serie(ctx, msf):
    for y in (int(ctx.year[0]) - 1, int(ctx.year[ctx.last_idx]) + 1):
        out = rt.simulate(ctx, msf, y, SCEN_PIOGGIA)
        assert out["esito"] == rt.ESITO_NON_SIMULABILE
        assert not out.get("indicatori")


def test_start_years_coerente_con_calendario(ctx, msf):
    ys = set(rt.start_years(ctx, msf))
    for y in range(int(ctx.year[0]), int(ctx.year[ctx.last_idx]) + 1):
        assert (rt.build_calendar(ctx, msf, y).ok) == (y in ys)


# =============================================================================
# 7) Cover non possibile -> suolo nudo con il motivo
# =============================================================================

def test_cover_senza_tempo_suolo_nudo_con_motivo(ctx, anno_centrale):
    """Dopo la soia (raccolta a settembre) la semina del frumento e' a fine ottobre: la cover
    non ha il tempo minimo e l'intervallo resta a suolo nudo, con il motivo dichiarato."""
    rot = rt.Rotation.from_label("soia+cover > frumento > mais")
    ys = rt.start_years(ctx, rot)
    out = rt.simulate(ctx, rot, ys[len(ys) // 2], SCEN_PIOGGIA, dettaglio=True)
    assert out["esito"] == rt.ESITO_OK
    iv = next(i for i in out["intervalli"] if i["dopo"] == "soia")
    assert iv["cover_richiesta"] is True
    assert iv["tipo"] == "nudo"
    assert iv["motivo_nudo"], "motivo del suolo nudo non dichiarato"
    assert iv["cover_semina"] == "" and iv["cover_terminazione"] == ""
    assert iv["giorni"] < ctx.cover["durata_min"], "l'intervallo avrebbe lasciato il tempo"
    assert not any(s.kind == "cover" for s in out["segmenti"]
                   if s.cycle == out["n_avviamento"] and s.pos == 0)
    # le altre posizioni, senza cover richiesta, non hanno motivo
    for i in out["intervalli"]:
        if not i["cover_richiesta"]:
            assert i["tipo"] == "nudo" and i["motivo_nudo"] == ""


def test_cover_possibile_e_cover_negata_sono_coerenti(ctx, elenco_cover):
    """Su tutte le rotazioni con cover: cover effettiva <=> nessun motivo, e viceversa."""
    n_cover = n_nudo = 0
    for rot in elenco_cover:
        ys = rt.start_years(ctx, rot)
        if not ys:
            continue
        out = rt.simulate(ctx, rot, ys[len(ys) // 2], SCEN_PIOGGIA)
        for iv in out["intervalli"]:
            if not iv["cover_richiesta"]:
                assert iv["tipo"] == "nudo"
                continue
            if iv["tipo"] == "cover":
                n_cover += 1
                assert iv["motivo_nudo"] == ""
                assert iv["cover_semina"] and iv["cover_terminazione"]
                assert iv["cover_semina"] < iv["cover_terminazione"] < iv["fine"]
                assert iv["inizio"] < iv["cover_semina"]
            else:
                n_nudo += 1
                assert iv["motivo_nudo"]
    assert n_cover and n_nudo, (n_cover, n_nudo)


@pytest.fixture(scope="module")
def elenco_cover(pars):
    return [e["rotation"] for e in rt.enumerate_rotations(pars) if e["rappresentante"]
            and any(e["rotation"].cover)]


def test_cover_oltre_semina_max_motivo(ctx, msf):
    """Con la finestra di semina della cover chiusa prima della raccolta il motivo e' dichiarato."""
    cv = dict(ctx.cover)
    cv["semina_max"] = "09-01"
    ctx2 = dataclasses.replace(ctx, cover=cv)
    rot = rt.Rotation.from_label("mais+cover > soia > frumento")
    ys = rt.start_years(ctx2, rot)
    out = rt.simulate(ctx2, rot, ys[len(ys) // 2], SCEN_PIOGGIA)
    iv = next(i for i in out["intervalli"] if i["dopo"] == "mais")
    assert iv["cover_richiesta"] and iv["tipo"] == "nudo"
    assert "semina_max" in iv["motivo_nudo"]


def test_cover_cambia_il_bilancio_dell_azoto(ctx, msf):
    """Con la cover effettiva la lisciviazione dell'intervallo non supera quella a suolo nudo."""
    senza = rt.Rotation.from_label("frumento > mais > soia")
    con = rt.Rotation.from_label("frumento+cover > mais > soia")
    ys = rt.start_years(ctx, con)
    meno = 0
    for y in ys[::2]:
        a = rt.simulate(ctx, senza, y, SCEN_PIOGGIA)
        b = rt.simulate(ctx, con, y, SCEN_PIOGGIA)
        ivb = next(i for i in b["intervalli"] if i["dopo"] == "frumento")
        if ivb["tipo"] != "cover":
            continue
        meno += b["indicatori"]["n_lisciviato_anno"] <= a["indicatori"]["n_lisciviato_anno"] + 1e-9
    assert meno >= 1


# =============================================================================
# 8) Fattore di rotazione
# =============================================================================

def test_frumento_continuo_fattore_rotazione_minore_di_uno(ctx):
    rot = rt.Rotation.from_label("frumento > frumento > frumento")
    ys = rt.start_years(ctx, rot)
    for y in ys[::4]:
        for sc in rt.SCENARI:
            out = rt.simulate(ctx, rot, y, sc)
            atteso, _ = ym.rotation_factor(ctx.p, "frumento", "frumento", "frumento",
                                           ctx.scenarios[sc]["regime"])
            assert len(out["colture"]) == 3
            for c in out["colture"]:
                assert c["f_rotazione"] < 1.0, (y, sc, c["f_rotazione"])
                assert c["f_rotazione"] == pytest.approx(atteso)


def test_mais_soia_frumento_fattore_rotazione_uno(ctx, msf):
    for y in rt.start_years(ctx, msf)[::4]:
        for sc in rt.SCENARI:
            out = rt.simulate(ctx, msf, y, sc)
            for c in out["colture"]:
                assert c["f_rotazione"] == 1.0, (y, sc, c["coltura"])
            assert out["indicatori"]["f_rotazione_medio"] == 1.0


# =============================================================================
# 9) Regressione sul meteo reale (tolleranze larghe)
# =============================================================================

def _tutte(ctx, etichetta, scenario):
    rot = rt.Rotation.from_label(etichetta)
    ys = rt.start_years(ctx, rot)
    cal = {y: rt.build_calendar(ctx, rot, y) for y in ys}
    return [rt.simulate(ctx, rot, y, scenario, calendario=cal[y]) for y in ys]


def test_regressione_mais_continuo_irrigazione_libera(ctx):
    outs = _tutte(ctx, "mais > mais > mais", SCEN_LIBERA)
    assert len(outs) >= 10
    irr = float(np.median([o["indicatori"]["irrigazione_anno"] for o in outs]))
    rr = float(np.mean([o["indicatori"]["resa_relativa_media"] for o in outs]))
    assert irr == pytest.approx(290.0, rel=0.15), irr
    assert rr >= 0.9, rr


def test_regressione_frumento_continuo_lisciviazione(ctx):
    outs = _tutte(ctx, "frumento > frumento > frumento", SCEN_PIOGGIA)
    assert len(outs) >= 10
    mediana = float(np.median([o["indicatori"]["n_lisciviato_anno"] for o in outs]))
    assert mediana > 1.0, mediana


def test_regressione_durata_mais_soia_frumento(ctx, msf):
    outs = _tutte(ctx, MAIS_SOIA_FRUMENTO, SCEN_PIOGGIA)
    assert len(outs) >= 10
    durate = [o["durata_anni"] for o in outs]
    assert float(np.median(durate)) == pytest.approx(3.0, rel=0.15)
    assert all(2.0 < d < 4.0 for d in durate)


# =============================================================================
# 10) Prestazioni
# =============================================================================

def test_300_simulazioni_in_meno_di_5_secondi(ctx, pars):
    """Dopo il riscaldamento (compilazione numba, cache dei cicli), 300 simulazioni complete
    (calendario compreso) di rotazioni, annate e scenari diversi."""
    rots = [e["rotation"] for e in rt.enumerate_rotations(pars) if e["rappresentante"]][:40]
    casi = []
    for r in rots:
        ys = rt.start_years(ctx, r)
        for i, y in enumerate(ys[:8]):
            casi.append((r, y, rt.SCENARI[i % 3]))
    assert len(casi) >= 300
    casi = casi[:300]
    for r, y, sc in casi[:10]:                         # riscaldamento
        rt.simulate(ctx, r, y, sc)
    t0 = time.perf_counter()
    esiti = [rt.simulate(ctx, r, y, sc)["esito"] for r, y, sc in casi]
    dt = time.perf_counter() - t0
    assert set(esiti) == {rt.ESITO_OK}
    print(f"\n300 simulazioni: {dt:.2f} s")
    assert dt < 5.0, f"{dt:.2f} s"


# =============================================================================
# 11) Curve di coltura dentro la catena di rotazione (mais, doppio coefficiente)
# =============================================================================
# Una curva di Kc invertita nella catena non era rilevata: qui si guarda dentro `dettaglio=True`.

def _mais_in_rotazione(ctx, rot, anno, scenario):
    """(inp, res, indici dei giorni del mais valutato) per la prima coltura 'mais' del ciclo valutato."""
    rc = rt.build_calendar(ctx, rot, anno)
    out = rt.simulate(ctx, rot, anno, scenario, calendario=rc, dettaglio=True)
    assert out["esito"] == rt.ESITO_OK, out.get("motivo")
    inp = rt._daily_inputs(ctx, rc)                         # stesse serie passate al nucleo idrico
    res = out["acqua"]
    k = next(i for i, s in enumerate(out["segmenti"])
             if s.crop == "mais" and s.cycle == rc.n_avviamento)
    idx = np.nonzero(res.segment == k)[0]
    assert idx.size > 60
    return out, inp, res, idx


@pytest.fixture(scope="module", params=["mais > soia > frumento", "mais > mais > mais"])
def mais_libero(request, ctx):
    rot = rt.Rotation.from_label(request.param)
    ys = rt.start_years(ctx, rot)
    anno = ys[len(ys) // 2]
    return _mais_in_rotazione(ctx, rot, anno, SCEN_LIBERA)


def test_mais_kcb_basso_alla_semina_massimo_in_piena_stagione_cala_alla_raccolta(ctx, mais_libero):
    _, inp, res, idx = mais_libero
    kcb = inp.kcb[idx]
    n = len(idx)
    d = max(5, n // 15)
    ini, fine = float(kcb[:d].mean()), float(kcb[-d:].mean())
    mid = float(kcb.max())
    mid_pos = int(np.argmax(kcb)) / (n - 1)
    kcb_ini = fparams.get(ctx.p, "crops.mais.kcb.ini")
    kcb_mid = fparams.get(ctx.p, "crops.mais.kcb.mid")
    kcb_end = fparams.get(ctx.p, "crops.mais.kcb.end")
    assert ini < 0.5 * mid, (ini, mid)                      # basso alla semina
    assert ini == pytest.approx(kcb_ini, abs=0.1)
    assert mid >= kcb_mid - 0.05                            # massimo in piena stagione (eq. 70: puo' salire col clima)
    assert 0.25 < mid_pos < 0.85, mid_pos                   # ... e in mezzo al ciclo, non agli estremi
    assert fine < 0.75 * mid, (fine, mid)                   # cala verso la raccolta
    assert fine == pytest.approx(kcb_end, abs=0.15)
    assert kcb[-1] < kcb[np.argmax(kcb)] and kcb[0] < kcb[np.argmax(kcb)]
    # forma: non decrescente fino al massimo, non crescente da piena stagione in poi
    i_max = int(np.argmax(kcb))
    assert np.all(np.diff(kcb[:i_max + 1]) >= -1e-9)
    j = int(np.nonzero(kcb >= kcb.max() - 1e-9)[0][-1])
    assert np.all(np.diff(kcb[j:]) <= 1e-9)


def test_mais_traspirazione_potenziale_normalizzata_segue_il_kcb(ctx, mais_libero):
    """In irrigazione libera Ks ~ 1, quindi tr / ET0 riproduce la curva del Kcb (nei giorni con ET0 > 0)."""
    _, inp, res, idx = mais_libero
    ok = inp.et0[idx] > 0.3
    tr_n = res.tr[idx][ok] / inp.et0[idx][ok]
    assert np.all(tr_n <= inp.kcb[idx][ok] + 1e-9)          # mai oltre Kcb
    assert np.mean(tr_n >= inp.kcb[idx][ok] - 1e-6) > 0.95    # quasi sempre uguale (Ks = 1)
    n = len(tr_n)
    d = max(5, n // 15)
    assert tr_n[:d].mean() < 0.5 * tr_n.max()
    assert tr_n[-d:].mean() < 0.75 * tr_n.max()
    assert 0.25 < np.argmax(tr_n) / (n - 1) < 0.85


def test_mais_profondita_radicale_cresce_nel_ciclo(ctx, mais_libero):
    _, inp, res, idx = mais_libero
    zr = inp.zr[idx]
    zr_ini = fparams.get(ctx.p, "crops.mais.zr_ini")
    zr_max = fparams.get(ctx.p, "crops.mais.zr_max")
    assert np.all(np.diff(zr) >= -1e-12)                    # non diminuisce mai
    assert zr[-1] > zr[0] + 0.5                             # cresce davvero
    assert zr[0] == pytest.approx(zr_ini, abs=0.1)
    assert zr[-1] == pytest.approx(min(zr_max, ctx.soil.depth), abs=1e-6)
    assert zr[len(zr) // 4] < zr[-1]                        # ancora in crescita a un quarto del ciclo


def test_mais_traspirazione_maggiore_dell_evaporazione_in_irrigazione_libera(ctx, mais_libero):
    out, inp, res, idx = mais_libero
    tr, ev = float(res.tr[idx].sum()), float(res.ev[idx].sum())
    assert tr > ev, (tr, ev)
    assert tr > 2.0 * ev, (tr, ev)                          # copertura piena: la traspirazione domina
    c = next(c for c in out["colture"] if c["coltura"] == "mais")
    assert c["traspirazione"] > c["evaporazione"]
    assert c["traspirazione"] + c["evaporazione"] == pytest.approx(c["eta"], rel=1e-9)


@pytest.mark.parametrize("scenario", rt.SCENARI)
def test_residuo_idrico_della_rotazione(ctx, msf, anno_centrale, scenario):
    out = rt.simulate(ctx, msf, anno_centrale, scenario, dettaglio=True)
    assert abs(out["residui"]["acqua_mm"]) <= 0.01
    res = out["acqua"]
    assert abs(_wbal(res)) <= 0.01
    assert float(np.max(np.abs(_wbal_day(res)))) <= 0.01
    assert res.metodo_et == "doppio"                        # la catena usa il doppio coefficiente


def _wbal(res):
    from fieldwise import water as _w
    return _w.water_balance_residual(res)


def _wbal_day(res):
    from fieldwise import water as _w
    return _w.water_balance_daily_residual(res)
