"""Test di `fieldwise.sensitivity`.

Senza rete e senza cache: limiti delle perturbazioni (intervallo, frazioni <= 1, soglie ordinate),
tau di Kendall su classifiche note, correlazione di rango parziale, campionamento a ipercubo
latino riproducibile con seme fisso. Con la cache del punto pilota (saltati se manca, marcati
`slow`): un giro minimo di `run` con pochi parametri e poche rotazioni che termina e produce la
struttura attesa. Il giro minimo non scrive nulla nel repository (`scrivi` non viene chiamato)."""
from __future__ import annotations

import math
import os

import numpy as np
import pandas as pd
import pytest
from scipy.stats import qmc

from fieldwise import config
from fieldwise import params as P
from fieldwise import rotation as rt
from fieldwise import sensitivity as sens


@pytest.fixture(scope="module")
def p():
    return P.load_params()


@pytest.fixture(scope="module")
def incerte(p):
    return sens.voci_incerte(p)


# ----------------------------------------------------------------------------- limiti
def test_ci_sono_molte_voci_perturbabili_e_le_escluse_hanno_un_motivo(incerte):
    voci, escluse = incerte
    assert len(voci) > 100
    assert set(voci.columns) >= {"percorso", "base", "basso", "alto", "intero", "limiti", "etichetta"}
    assert escluse and all(e["motivo"] for e in escluse)
    # gli interruttori 0/1 e i valori nulli non si perturbano
    perc_escluse = {e["percorso"] for e in escluse}
    assert any(k.endswith(".irrigabile") for k in perc_escluse)
    assert not set(voci["percorso"]) & perc_escluse


def test_basso_non_supera_alto_e_la_base_sta_dentro(incerte):
    voci, _ = incerte
    assert (voci["basso"] <= voci["alto"]).all()
    # la base sta nell'intervallo, salvo i casi in cui il limite del parametro la lascia fuori
    # da un lato (basso/alto ristretti all'intervallo della voce): lo si dichiara in `limiti`
    fuori = voci[(voci["base"] < voci["basso"] - 1e-12) | (voci["base"] > voci["alto"] + 1e-12)]
    assert fuori.empty or fuori["limiti"].str.contains("intervallo|frazione").all()


def test_la_perturbazione_e_al_piu_il_30_per_cento_della_base(incerte):
    voci, _ = incerte
    v = sens.VARIAZIONE
    assert v == pytest.approx(0.3)
    lo = np.minimum(voci["base"] * (1 - v), voci["base"] * (1 + v))
    hi = np.maximum(voci["base"] * (1 - v), voci["base"] * (1 + v))
    assert (voci["basso"] >= lo - 1e-9).all()
    assert (voci["alto"] <= hi + 1e-9).all()


def test_rispetta_l_intervallo_dichiarato_dalla_voce(p, incerte):
    voci, _ = incerte
    n = 0
    for k, v in P.sensitivity_entries(p):
        iv = v.get("intervallo")
        if not (isinstance(iv, (list, tuple)) and len(iv) == 2 and all(isinstance(t, (int, float)) for t in iv)):
            continue
        r = voci[voci["percorso"] == k]
        if r.empty:
            continue
        lo, hi = sorted(map(float, iv))
        assert r["basso"].iloc[0] >= lo - 1e-12 and r["alto"].iloc[0] <= hi + 1e-12, k
        n += 1
    assert n > 20      # molte voci hanno un intervallo: il controllo non deve essere vuoto


def test_le_frazioni_non_superano_uno(incerte):
    voci, _ = incerte
    frazioni = voci[voci["percorso"].apply(lambda k: any(w in k for w in sens.PAROLE_FRAZIONE))
                    & (voci["base"] > 0) & (voci["base"] <= 1)]
    assert len(frazioni) > 10
    assert (frazioni["alto"] <= 1.0 + 1e-12).all()


def test_i_valori_interi_restano_interi_nella_perturbazione(incerte):
    voci, _ = incerte
    interi = voci[voci["intero"]]
    for r in interi.itertuples():
        assert float(round(r.basso)) == pytest.approx(round(r.basso))
        assert round(r.basso) <= round(r.alto)


# ----------------------------------------------------------------------------- soglie ordinate
def test_catene_contengono_gdd_e_soglie_di_caldo(p):
    ch = sens.catene(p)
    piatte = {k for c in ch for k in c}
    for c in ("mais", "soia", "frumento"):
        assert f"crops.{c}.gdd_maturita" in piatte
        assert f"heat.colture.{c}.t_critica" in piatte and f"heat.colture.{c}.t_limite" in piatte
    assert all(len(c) >= 2 for c in ch)


def test_applica_catene_limita_la_voce_perturbata_senza_toccare_le_altre():
    base = {"a": 10.0, "b": 20.0, "c": 30.0}
    chains = [["a", "b", "c"]]
    m = sens.MARGINE_ORDINE
    # a sale oltre b (non perturbata): a viene riportata sotto b, b resta alla base
    mod, corretto = sens.applica_catene({"a": 25.0}, base, chains)
    assert corretto and "b" not in mod
    assert mod["a"] == pytest.approx(20.0 / (1 + m))
    # b scende sotto a (non perturbata): b viene alzata a a x (1 + margine)
    mod, corretto = sens.applica_catene({"b": 5.0}, base, chains)
    assert corretto
    assert mod["b"] == pytest.approx(10.0 * (1 + m))
    # due voci perturbate in disordine: si alza la successiva
    mod, corretto = sens.applica_catene({"a": 25.0, "b": 22.0}, base, chains)
    assert corretto and mod["b"] == pytest.approx(25.0 * (1 + m))
    # nessuna violazione: stesso risultato e nessuna correzione segnalata
    mod, corretto = sens.applica_catene({"a": 11.0}, base, chains)
    assert not corretto and mod == {"a": 11.0}


def test_applica_catene_non_modifica_il_dizionario_di_ingresso():
    base = {"a": 1.0, "b": 2.0}
    ingresso = {"a": 5.0}
    sens.applica_catene(ingresso, base, [["a", "b"]])
    assert ingresso == {"a": 5.0}


def test_estremi_delle_perturbazioni_restano_ordinati_dopo_le_catene(p, incerte):
    voci, _ = incerte
    base = sens.valori_base(p)
    righe = voci.set_index("percorso")
    n_catene = 0
    for ch in sens.catene(p):
        ch = [k for k in ch if k in base]
        if len(ch) < 2:
            continue
        n_catene += 1
        # caso peggiore: tutte le voci della catena al valore piu' alto (e il successivo al piu' basso)
        mod = {k: float(righe.loc[k, "alto"]) for k in ch if k in righe.index}
        mod, _ = sens.applica_catene(mod, base, [ch])
        for a, b in zip(ch, ch[1:]):
            assert mod.get(b, base[b]) >= mod.get(a, base[a]) * (1 + sens.MARGINE_ORDINE) - 1e-9, (a, b)
        mod = {k: float(righe.loc[k, "basso"]) for k in ch if k in righe.index}
        mod, _ = sens.applica_catene(mod, base, [ch])
        for a, b in zip(ch, ch[1:]):
            assert mod.get(b, base[b]) >= mod.get(a, base[a]) * (1 + sens.MARGINE_ORDINE) - 1e-9, (a, b)
    assert n_catene >= 15


# ----------------------------------------------------------------------------- tau di Kendall
def _esito(classi, punteggi=None, attuale=None, alternative=None):
    punteggi = punteggi or [1.0 - 0.1 * i for i in range(len(classi))]
    return {"esito": "ok",
            "scenari": {sc: {"classi": list(classi), "punteggi": list(punteggi),
                             "attuale": attuale or classi[-1], "alternative": alternative or list(classi[:2])}
                        for sc in rt.SCENARI}}


CLASSI = ["A", "B", "C", "D", "E"]


def test_tau_di_classifiche_identiche_e_uno():
    b = _esito(CLASSI)
    m = sens.confronto(b, _esito(CLASSI), "tetto_irriguo")
    assert m["tau"] == pytest.approx(1.0)
    assert m["identico"] and not m["prima_cambia"] and not m["top3_cambia"]
    assert m["d_prima"] == pytest.approx(0.0)


def test_tau_di_classifiche_opposte_e_meno_uno():
    b = _esito(CLASSI)
    q = _esito(CLASSI[::-1])
    m = sens.confronto(b, q, "tetto_irriguo")
    assert m["tau"] == pytest.approx(-1.0)
    assert m["prima_cambia"] and m["top3_cambia"]
    assert m["prima"] == "E"


def test_tau_con_una_sola_coppia_scambiata_vale_uno_meno_due_discordanze_su_coppie():
    # 5 elementi = 10 coppie; scambiando due vicini ne diventa discordante una: tau = (9 - 1)/10 = 0,8
    b = _esito(CLASSI)
    q = _esito(["A", "B", "D", "C", "E"])
    m = sens.confronto(b, q, "tetto_irriguo")
    assert m["tau"] == pytest.approx(0.8)
    assert not m["prima_cambia"]
    assert m["top3_cambia"]          # C esce dalle prime tre, entra D


def test_tau_di_due_scambi_indipendenti():
    # (A B)(C D) scambiati su 4 elementi: 6 coppie, 2 discordanti: tau = (4 - 2)/6
    b = _esito(["A", "B", "C", "D"])
    q = _esito(["B", "A", "D", "C"])
    assert sens.confronto(b, q, "solo_pioggia")["tau"] == pytest.approx(2.0 / 6.0)


def test_tau_usa_solo_le_classi_comuni():
    b = _esito(["A", "B", "C", "D"])
    q = _esito(["A", "B", "C", "X"])                                     # D non e' piu' nell'insieme
    assert sens.confronto(b, q, "tetto_irriguo")["tau"] == pytest.approx(1.0)


def test_confronto_misura_la_variazione_di_punteggio_della_prima_e_dell_attuale():
    b = _esito(CLASSI, [0.9, 0.7, 0.5, 0.3, 0.1], attuale="E")
    q = _esito(CLASSI, [0.8, 0.7, 0.5, 0.3, 0.2], attuale="E")
    m = sens.confronto(b, q, "tetto_irriguo")
    assert m["d_prima"] == pytest.approx(-0.1)
    assert m["d_attuale"] == pytest.approx(0.1)
    assert m["attuale_ultimo_quarto"] is True


def test_confronto_con_calcolo_fallito_segnala_errore():
    assert sens.confronto(_esito(CLASSI), {"esito": "errore", "errore": "x"}, "tetto_irriguo") == {"errore": True}


# ----------------------------------------------------------------------------- PRCC
def test_prcc_riconosce_il_parametro_che_conta():
    rng = np.random.default_rng(7)
    X = rng.uniform(size=(300, 4))
    y = np.exp(3.0 * X[:, 0]) - 2.0 * X[:, 1] + 0.05 * rng.normal(size=300)      # monotona in x0, x1
    pr = sens.prcc(X, y)
    assert pr.shape == (4,)
    assert pr[0] > 0.9 and pr[1] < -0.5
    assert abs(pr[2]) < 0.2 and abs(pr[3]) < 0.2


# ----------------------------------------------------------------------------- ipercubo latino
def _campione(voci, n, seme):
    lhs = qmc.LatinHypercube(d=len(voci), seed=seme).random(n)
    return voci["basso"].to_numpy() + lhs * (voci["alto"] - voci["basso"]).to_numpy()


def test_ipercubo_latino_riproducibile_con_seme_fisso(incerte):
    voci, _ = incerte
    a = _campione(voci, 32, sens.SEME)
    b = _campione(voci, 32, sens.SEME)
    c = _campione(voci, 32, sens.SEME + 1)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_ipercubo_latino_rispetta_i_limiti_e_stratifica(incerte):
    voci, _ = incerte
    n = 64
    X = _campione(voci, n, sens.SEME)
    assert X.shape == (n, len(voci))
    assert (X >= voci["basso"].to_numpy() - 1e-12).all() and (X <= voci["alto"].to_numpy() + 1e-12).all()
    # una sola osservazione per ognuno degli n strati di ogni parametro con intervallo non nullo
    larghi = (voci["alto"] - voci["basso"]).to_numpy() > 0
    u = (X - voci["basso"].to_numpy()) / np.where(larghi, (voci["alto"] - voci["basso"]).to_numpy(), 1.0)
    for j in np.flatnonzero(larghi)[:25]:
        strati = np.floor(np.clip(u[:, j], 0, 1 - 1e-12) * n).astype(int)
        assert len(set(strati)) == n


def test_i_campioni_rispettano_le_soglie_dopo_le_catene(p, incerte):
    voci, _ = incerte
    base = sens.valori_base(p)
    chains = sens.catene(p)
    X = _campione(voci, 24, sens.SEME)
    for i in range(X.shape[0]):
        mod = dict(zip(voci["percorso"], map(float, X[i])))
        mod, _ = sens.applica_catene(mod, base, chains)
        for ch in chains:
            ch = [k for k in ch if k in base]
            for a, b in zip(ch, ch[1:]):
                assert mod.get(b, base[b]) >= mod.get(a, base[a]) * (1 + sens.MARGINE_ORDINE) - 1e-9


# ----------------------------------------------------------------------------- costanti
def test_costanti_di_metodo():
    assert sens.SCENARIO_PRINCIPALE in rt.SCENARI
    assert sum(sens.PESI_UGUALI.values()) == pytest.approx(len(sens.PESI_UGUALI))
    assert 0 < sens.DELTA_NON_CONTA < 0.1 and 0.9 <= sens.TAU_NON_CONTA < 1.0
    assert sens.etichetta("crops.mais.kcb.mid").startswith("Colture")


# ----------------------------------------------------------------------------- giro minimo (cache)
@pytest.fixture(scope="module")
def giro_minimo():
    old = os.environ.get("FIELDWISE_OFFLINE")
    os.environ["FIELDWISE_OFFLINE"] = "1"
    mp = pytest.MonkeyPatch()
    try:
        P_ = P.load_params()
        voci, escluse = sens.voci_incerte(P_)
        scelte = ["crops.mais.kcb.mid", "crops.soia.kcb.mid", "nitrogen.mais.n_assorbito"]
        piccole = voci[voci["percorso"].isin(scelte)].reset_index(drop=True)
        assert len(piccole) == 3
        rotazioni = ["mais > mais > mais", "mais > soia > frumento", "frumento > soia+cover > mais",
                     "frumento > frumento > frumento", "soia > soia > soia"]
        mp.setattr(sens, "voci_incerte", lambda p_: (piccole, escluse))
        mp.setattr(sens, "sottoinsieme", lambda p_, sin_: rotazioni)
        mp.setattr(sens, "STRUTTURALI", {"caldo_aquacrop": sens.STRUTTURALI["caldo_aquacrop"]})
        try:
            R = sens.run(n_mc=8, workers=1, seme=5)
        except FileNotFoundError as e:
            pytest.skip(f"cache del punto pilota assente: {e}")
        yield R, piccole
    finally:
        mp.undo()
        if old is None:
            os.environ.pop("FIELDWISE_OFFLINE", None)
        else:
            os.environ["FIELDWISE_OFFLINE"] = old


@pytest.mark.slow
def test_giro_minimo_termina_con_la_struttura_attesa(giro_minimo):
    R, piccole = giro_minimo
    assert {"base", "oat", "strutturali", "mc", "prcc", "pesi", "tempi", "seme", "versione"} <= set(R)
    assert R["seme"] == 5 and R["n_mc"] == 8
    assert len(R["oat"]) == 3 and set(R["oat"]["percorso"]) == set(piccole["percorso"])
    assert len(R["strutturali"]) == 1 and R["strutturali"][0]["esito"] == "ok"
    for sc in rt.SCENARI:
        assert R["base"]["scenari"][sc]["classi"]
        m = R["mc"][sc]
        assert m["n_validi"] >= 1
        assert -1.0 <= m["tau_mediana"] <= 1.0
        for k in ("prima_resta", "top3_restano", "attuale_ultimo_quarto", "alternative_restano"):
            assert 0.0 <= m[k] <= 1.0


@pytest.mark.slow
def test_giro_minimo_oat_ha_tau_in_dominio_e_flag_booleani(giro_minimo):
    R, _ = giro_minimo
    oat = R["oat"]
    for c in ("tau_meno", "tau_piu"):
        assert oat[c].dropna().between(-1.0, 1.0).all()
    assert oat["conta"].dtype == bool
    assert (oat["effetto"].dropna() >= 0).all()
    assert (oat["valore_meno"] <= oat["valore_piu"] + 1e-12).all()


@pytest.mark.slow
def test_giro_minimo_conclusione_e_testo(giro_minimo):
    R, _ = giro_minimo
    testo = sens.conclusione(R)
    assert isinstance(testo, str) and "parametri" in testo
    assert not math.isnan(R["tempi"]["totale_s"])
