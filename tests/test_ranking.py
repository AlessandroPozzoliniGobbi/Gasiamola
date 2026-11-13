"""Test di `fieldwise.ranking` con piccole sintesi finte costruite a mano (nessun meteo)."""
from __future__ import annotations

import pandas as pd
import pytest

from fieldwise import ranking as rk

REGIME = rk.REGIME_PREDEFINITO
COL_REGIME = f"conformita_{REGIME}"
TUTTI_PESI = {k: 1 for k in rk.PRIORITA}


def riga(classe, scenario="solo_pioggia", resa=0.8, minimo=0.6, irr=100.0, conc=150.0, hum=-0.2,
         liv=10.0, conf="conforme", attuale=False, fl="acqua", n=20, oltre=0.0, cover=0.0,
         f_acqua=0.8, f_caldo=0.99, f_rot=1.0, real=1.0, eq="nessuno"):
    return {"classe": classe, "scenario": scenario, "n_simulazioni": n, "attuale": attuale,
            "conformita": conf, COL_REGIME: conf, "fattore_limitante": fl,
            "resa_rel_mediana": resa, "resa_rel_min": minimo, "irrigazione_mm": irr,
            "concime_kg_n": conc, "humus_t_ha": hum, "n_lisciviato_kg_n": liv,
            "f_acqua": f_acqua, "f_caldo": f_caldo, "f_rotazione": f_rot,
            "quota_oltre_limite_n": oltre, "quota_cover_non_praticata": cover,
            "cover_realizzata_quota": real, "equivalente_a": eq}


def sint(*righe):
    return pd.DataFrame(list(righe))


@pytest.fixture
def tre():
    """Tre rotazioni: A costosa e produttiva, B economica e meno produttiva, C peggiore su tutto."""
    return sint(
        riga("A", resa=0.9, minimo=0.7, irr=200, conc=200, hum=0.0, liv=20),
        riga("B", resa=0.7, minimo=0.5, irr=0, conc=100, hum=-0.4, liv=5),
        riga("C", resa=0.6, minimo=0.4, irr=250, conc=250, hum=-0.5, liv=25))


# =============================================================================
# score
# =============================================================================
def test_normalizzazione_e_verso(tre):
    s = rk.score(tre, {"resa": 1}, "solo_pioggia").set_index("classe")
    assert s.loc["A", "punt_resa"] == pytest.approx(1.0)     # massimo = migliore
    assert s.loc["C", "punt_resa"] == pytest.approx(0.0)
    assert s.loc["B", "punt_resa"] == pytest.approx((0.7 - 0.6) / (0.9 - 0.6))
    a = rk.score(tre, {"acqua": 1}, "solo_pioggia").set_index("classe")
    assert a.loc["B", "punt_acqua"] == pytest.approx(1.0)    # meno irrigazione = migliore
    assert a.loc["C", "punt_acqua"] == pytest.approx(0.0)
    c = rk.score(tre, {"concime": 1}, "solo_pioggia").set_index("classe")
    assert c.loc["B", "punt_concime"] == pytest.approx(1.0)
    r = rk.score(tre, {"rischio": 1}, "solo_pioggia").set_index("classe")
    assert r.loc["A", "punt_rischio"] == pytest.approx(1.0)
    assert ((s[[f"punt_{k}" for k in rk.PRIORITA]] >= 0) & (s[[f"punt_{k}" for k in rk.PRIORITA]] <= 1)).all().all()


def test_suolo_media_di_humus_e_lisciviazione(tre):
    s = rk.score(tre, {"suolo": 1}, "solo_pioggia").set_index("classe")
    # A: humus migliore (1) ma lisciviazione 0.25 -> (1 + (1-(20-5)/20))/2 ; B: humus (0.8 alle) ecc.
    humus = lambda c: (tre.set_index("classe").loc[c, "humus_t_ha"] + 0.5) / 0.5            # noqa: E731
    liv = lambda c: 1 - (tre.set_index("classe").loc[c, "n_lisciviato_kg_n"] - 5) / 20       # noqa: E731
    for c in "ABC":
        assert s.loc[c, "punt_suolo"] == pytest.approx((humus(c) + liv(c)) / 2)


def test_punteggio_somma_pesata_e_ordine(tre):
    pesi = {"resa": 3, "acqua": 1}
    s = rk.score(tre, pesi, "solo_pioggia")
    p = s.set_index("classe")
    for c in "ABC":
        atteso = (3 * p.loc[c, "punt_resa"] + 1 * p.loc[c, "punt_acqua"]) / 4
        assert p.loc[c, "punteggio"] == pytest.approx(atteso)
    assert list(s["punteggio"]) == sorted(s["punteggio"], reverse=True)
    assert list(s["posizione"]) == [1, 2, 3]


def test_i_pesi_cambiano_l_ordine(tre):
    solo_resa = rk.score(tre, {"resa": 1}, "solo_pioggia")["classe"].tolist()
    solo_acqua = rk.score(tre, {"acqua": 1}, "solo_pioggia")["classe"].tolist()
    assert solo_resa[0] == "A" and solo_acqua[0] == "B"
    # scala dei pesi irrilevante
    a = rk.score(tre, {"resa": 1, "acqua": 2}, "solo_pioggia")["punteggio"].tolist()
    b = rk.score(tre, {"resa": 10, "acqua": 20}, "solo_pioggia")["punteggio"].tolist()
    assert a == pytest.approx(b)


def test_pesi_nulli_errore_chiaro(tre):
    with pytest.raises(ValueError, match="nulli"):
        rk.score(tre, {k: 0 for k in rk.PRIORITA}, "solo_pioggia")
    with pytest.raises(ValueError, match="nulli"):
        rk.score(tre, {}, "solo_pioggia")


def test_pesi_non_validi(tre):
    with pytest.raises(ValueError, match="sconosciute"):
        rk.score(tre, {"gusto": 1}, "solo_pioggia")
    with pytest.raises(ValueError, match="non negativi"):
        rk.score(tre, {"resa": -1, "acqua": 2}, "solo_pioggia")


def test_indicatore_costante_punteggio_neutro():
    df = sint(riga("A", irr=0), riga("B", irr=0, resa=0.5), riga("C", irr=0, resa=0.7))
    s = rk.score(df, {"acqua": 1, "resa": 1}, "solo_pioggia")
    assert (s["punt_acqua"] == rk.PUNTEGGIO_NEUTRO).all()
    assert s["punteggio"].notna().all()
    solo_acqua = rk.score(df, {"acqua": 1}, "solo_pioggia")
    assert (solo_acqua["punteggio"] == rk.PUNTEGGIO_NEUTRO).all()


def test_scenario_scelto_e_sconosciuto(tre):
    altro = tre.copy()
    altro["scenario"] = "tetto_irriguo"
    altro["resa_rel_mediana"] = [0.1, 0.2, 0.3]
    both = pd.concat([tre, altro], ignore_index=True)
    s = rk.score(both, {"resa": 1}, "tetto_irriguo")
    assert set(s["scenario"]) == {"tetto_irriguo"} and s.iloc[0]["classe"] == "C"
    with pytest.raises(ValueError, match="scenario"):
        rk.score(both, {"resa": 1}, "inesistente")


def test_filtro_di_conformita():
    df = sint(riga("A", resa=0.95, conf="non_conforme"),
              riga("B", resa=0.80, conf="conforme"),
              riga("D", resa=0.85, conf="conforme_solo_in_deroga"),
              riga("X", resa=0.70, conf="non_conforme", attuale=True))
    senza = rk.score(df, {"resa": 1}, "solo_pioggia")
    assert senza.iloc[0]["classe"] == "A" and len(senza) == 4
    solo = rk.score(df, {"resa": 1}, "solo_pioggia", solo_conformi=True)
    assert set(solo["classe"]) == {"B", "X"}          # l'attuale resta per il confronto
    con_deroga = rk.score(df, {"resa": 1}, "solo_pioggia", solo_conformi=True, ammetti_deroga=True)
    assert set(con_deroga["classe"]) == {"B", "D", "X"}
    # il punteggio e' relativo all'insieme: senza A il massimo e' D (0.85)
    assert con_deroga.set_index("classe").loc["D", "punt_resa"] == pytest.approx(1.0)
    # regime diverso dal predefinito
    df2 = df.copy()
    df2["conformita_altro"] = ["conforme", "non_conforme", "non_conforme", "non_conforme"]
    alt = rk.score(df2, {"resa": 1}, "solo_pioggia", solo_conformi=True, regime="altro")
    assert set(alt["classe"]) == {"A", "X"}
    with pytest.raises(ValueError, match="regime"):
        rk.score(df, {"resa": 1}, "solo_pioggia", solo_conformi=True, regime="boh")


def test_classi_senza_simulazioni_escluse():
    df = sint(riga("A"), riga("B", resa=float("nan"), n=0))
    s = rk.score(df, {"resa": 1}, "solo_pioggia")
    assert list(s["classe"]) == ["A"]


# =============================================================================
# pareto_front
# =============================================================================
def _nd(df, scenario="solo_pioggia", **kw):
    p = rk.pareto_front(df, scenario, **kw)
    return dict(zip(p["classe"], p["non_dominata"]))


def test_pareto_dominanza(tre):
    # C e' peggiore di B su tutto tranne... B: meno irr, meno conc, meno liv, ma humus -0.4 > -0.5, resa 0.7>0.6
    nd = _nd(tre)
    assert nd == {"A": True, "B": True, "C": False}      # C dominata da B (e da A su alcuni ma non tutti)


def test_pareto_parita_non_domina():
    df = sint(riga("A"), riga("B"))          # identiche: nessuna domina l'altra
    assert _nd(df) == {"A": True, "B": True}
    df = sint(riga("A"), riga("B", resa=0.81))      # B strettamente meglio su un indicatore, pari sugli altri
    assert _nd(df) == {"A": False, "B": True}


def test_pareto_compromesso_non_si_domina():
    df = sint(riga("A", resa=0.9, irr=200), riga("B", resa=0.8, irr=0))
    assert _nd(df) == {"A": True, "B": True}


def test_pareto_tolleranza():
    df = sint(riga("A"), riga("B", resa=0.8 + 1e-12), riga("C", resa=0.8 + 1e-3))
    # differenza 1e-12 << tol x scala (1e-6 x 0.8): parita'; 1e-3 e' una differenza reale
    nd = _nd(df)
    assert nd["C"] and not nd["A"] and not nd["B"]
    nd2 = _nd(sint(riga("A"), riga("B", resa=0.8 + 1e-12)))
    assert nd2 == {"A": True, "B": True}
    nd3 = _nd(sint(riga("A"), riga("B", resa=0.8 + 1e-3)), tol=0.0)
    assert nd3 == {"A": False, "B": True}


def test_pareto_sottoinsieme_di_indicatori(tre):
    # solo sulla resa: A domina tutti
    assert _nd(tre, indicatori=["resa_rel_mediana"]) == {"A": True, "B": False, "C": False}
    # solo sull'irrigazione (verso: meno e' meglio): B domina
    assert _nd(tre, indicatori=["irrigazione_mm"]) == {"A": False, "B": True, "C": False}
    with pytest.raises(ValueError):
        rk.pareto_front(tre, "solo_pioggia", indicatori=["colore"])


def test_pareto_filtra_lo_scenario(tre):
    altro = tre.copy()
    altro["scenario"] = "tetto_irriguo"
    p = rk.pareto_front(pd.concat([tre, altro]), "tetto_irriguo")
    assert len(p) == 3


# =============================================================================
# confronta
# =============================================================================
def _scenario_con_attuale():
    return sint(
        riga("ATT", resa=0.80, minimo=0.50, irr=200.0, conc=200.0, hum=-0.40, liv=20.0, conf="non_conforme",
             attuale=True, fl="acqua", f_acqua=0.7, oltre=0.5, cover=0.0),
        riga("ALT1", resa=0.85, minimo=0.60, irr=124.0, conc=150.0, hum=-0.10, liv=12.0, conf="conforme",
             fl="acqua", f_acqua=0.8, oltre=0.0, real=0.75),
        riga("ALT2", resa=0.78, minimo=0.75, irr=300.0, conc=240.0, hum=-0.30, liv=18.0,
             conf="conforme_solo_in_deroga", fl="rotazione", f_acqua=0.99, f_rot=0.9, oltre=0.1),
        riga("PEG", resa=0.60, minimo=0.30, irr=310.0, conc=260.0, hum=-0.60, liv=30.0, conf="non_conforme"))


def test_confronta_con_attuale():
    df = _scenario_con_attuale()
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia")
    assert c["attuale"]["classe"] == "ATT"
    alt = c["alternative"]
    assert len(alt) >= 2
    classi = [a["classe"] for a in alt]
    assert "ATT" not in classi and len(set(classi)) == len(classi)
    assert alt[0]["classe"] == "ALT1" and alt[0]["ruolo"].startswith("migliore_punteggio")
    assert alt[0]["non_dominata"]
    assert alt[1]["classe"] == "ALT2" and alt[1]["ruolo"] == "migliore_rischio"   # resa_rel_min piu' alta
    assert c["n_confrontate"] == 4 and c["n_non_dominate"] == 2   # ATT e PEG dominate da ALT1


def test_confronta_differenze_numeriche():
    c = rk.confronta(_scenario_con_attuale(), TUTTI_PESI, "solo_pioggia")
    d = c["alternative"][0]["differenze"]
    assert d["irrigazione_mm"]["assoluta"] == pytest.approx(124 - 200)
    assert d["irrigazione_mm"]["percentuale"] == pytest.approx(-38.0)
    assert d["resa_rel_mediana"]["percentuale"] == pytest.approx(100 * 0.05 / 0.8)
    assert d["humus_t_ha"]["assoluta"] == pytest.approx(0.30)


def test_confronta_evidenze_e_rischi_coerenti_con_i_numeri():
    c = rk.confronta(_scenario_con_attuale(), TUTTI_PESI, "solo_pioggia")
    a1 = c["alternative"][0]
    testo_ev = " | ".join(a1["evidenze"])
    assert "−38% di irrigazione" in testo_ev                     # esempio del progetto
    assert "124" in testo_ev and "200" in testo_ev
    assert any("azoto lisciviato" in e for e in a1["evidenze"])      # 20 -> 12 = -40%
    assert any("humus" in e for e in a1["evidenze"])
    assert any("il fattore che limita la resa e' l'acqua" in e for e in a1["evidenze"])
    rischi = " | ".join(a1["rischi"])
    assert "0.60" in rischi and "0.50" in rischi                      # anno peggiore, alternativa e attuale
    assert "75%" in rischi and "la cover e' praticabile" in rischi   # cover non sempre praticabile
    assert "azoto" not in rischi.replace("limite normativo", "") or "limite normativo" in rischi
    assert "limite normativo di azoto" not in rischi                  # ALT1: quota 0 -> nessuna frase
    a2 = c["alternative"][1]
    r2 = " | ".join(a2["rischi"])
    assert "10% delle annate" in r2 and "limite normativo di azoto" in r2
    assert "solo in deroga" in r2
    assert any("la successione colturale" in e for e in a2["evidenze"])
    # i peggioramenti rispetto all'attuale finiscono nei rischi, non nelle evidenze
    assert any(r.startswith("rispetto all'attuale:") and "irrigazione" in r for r in a2["rischi"])
    assert not any("irrigazione" in e and "→ 300" in e for e in a2["evidenze"])
    # rischi dell'attuale
    ra = " | ".join(c["attuale"]["rischi"])
    assert "50% delle annate" in ra and "non conforme" in ra


def test_confronta_numeri_delle_frasi_vengono_dalla_sintesi():
    df = _scenario_con_attuale()
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia")
    ammessi = set()
    for col in list(rk.VERSI) + ["quota_oltre_limite_n", "cover_realizzata_quota"]:
        for v in df[col]:
            ammessi |= {round(abs(v), 2), round(abs(v) * 100), round(abs(v), 0)}
    for a in c["alternative"]:
        for col, d in a["differenze"].items():
            if d.get("percentuale") is not None:
                ammessi.add(round(abs(d["percentuale"])))
            ammessi.add(round(abs(d["assoluta"]), 2))
        for frase in a["evidenze"] + a["rischi"]:
            for n in rk.numeri_in_frase(frase):
                assert round(n, 2) in ammessi or round(n) in ammessi, (frase, n)


def test_confronta_senza_attuale():
    df = _scenario_con_attuale()
    df["attuale"] = False
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia")
    assert c["attuale"] is None
    assert len(c["alternative"]) >= 2
    assert any("assoluto" in n for n in c["note"])
    assert all(a["differenze"]["irrigazione_mm"].get("assoluta") is None for a in c["alternative"])
    assert all(a["evidenze"] and a["rischi"] for a in c["alternative"])


def test_confronta_seconda_diversa_dalla_prima_se_coincidono():
    # ALT1 e' sia la migliore per punteggio sia la migliore sul rischio -> la seconda e' la successiva
    df = sint(
        riga("ATT", resa=0.7, minimo=0.4, irr=200, conc=200, attuale=True),
        riga("ALT1", resa=0.9, minimo=0.8, irr=50, conc=100),
        riga("ALT2", resa=0.8, minimo=0.6, irr=100, conc=150),
        riga("ALT3", resa=0.75, minimo=0.5, irr=120, conc=170))
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia")
    classi = [a["classe"] for a in c["alternative"]]
    assert classi[0] == "ALT1" and classi[1] != "ALT1" and classi[1] != "ATT"
    assert classi[1] == "ALT2"          # seconda per punteggio
    assert len(classi) == 2


def test_confronta_n_alternative_e_poche_rotazioni():
    c = rk.confronta(_scenario_con_attuale(), TUTTI_PESI, "solo_pioggia", n_alternative=3)
    assert len(c["alternative"]) == 3
    solo_due = sint(riga("ATT", attuale=True), riga("X", resa=0.9))
    c = rk.confronta(solo_due, TUTTI_PESI, "solo_pioggia")
    assert [a["classe"] for a in c["alternative"]] == ["X"]


def test_confronta_solo_conformi_esclude_alternative_non_conformi():
    c = rk.confronta(_scenario_con_attuale(), TUTTI_PESI, "solo_pioggia", solo_conformi=True)
    assert c["attuale"]["classe"] == "ATT"            # l'attuale resta anche se non conforme
    assert [a["classe"] for a in c["alternative"]] == ["ALT1"]
    c2 = rk.confronta(_scenario_con_attuale(), TUTTI_PESI, "solo_pioggia", solo_conformi=True,
                      ammetti_deroga=True)
    assert {a["classe"] for a in c2["alternative"]} == {"ALT1", "ALT2"}


def test_confronta_attuale_dominante_nota():
    df = sint(riga("ATT", resa=0.95, minimo=0.9, irr=0, conc=50, hum=0.1, liv=1, attuale=True),
              riga("X", resa=0.5, minimo=0.2, irr=100, conc=150, hum=-0.3, liv=20),
              riga("Y", resa=0.6, minimo=0.3, irr=90, conc=140, hum=-0.2, liv=15))
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia")
    assert c["attuale"]["non_dominata"]
    assert not c["alternative"][0]["non_dominata"]
    assert any("non dominata" in n for n in c["note"])


def test_confronta_pesi_nulli_errore(tre):
    with pytest.raises(ValueError, match="nulli"):
        rk.confronta(tre, {}, "solo_pioggia")


def test_confronta_attuale_senza_irrigazione_nessuna_percentuale():
    df = sint(riga("ATT", irr=0.0, attuale=True), riga("ALT", irr=80.0, resa=0.9),
              riga("ALT2", irr=0.0, resa=0.85))
    c = rk.confronta(df, {"resa": 1}, "solo_pioggia")
    alt = {a["classe"]: a for a in c["alternative"]}
    d = alt["ALT"]["differenze"]["irrigazione_mm"]
    assert d["percentuale"] is None and d["assoluta"] == pytest.approx(80.0)
    assert any("invece di 0 mm" in p for p in alt["ALT"]["rischi"])


# =============================================================================
# classi equivalenti (cover mai praticate)
# =============================================================================
def _con_equivalenti():
    return sint(
        riga("ATT", resa=0.70, minimo=0.4, irr=200, conc=200, attuale=True),
        riga("X", resa=0.90, minimo=0.7, irr=50, conc=100),
        riga("X+cover", resa=0.90, minimo=0.7, irr=50, conc=100, real=0.0, eq="X"),
        riga("Y", resa=0.80, minimo=0.8, irr=100, conc=150))


def test_equivalenti_escluse_di_default():
    df = _con_equivalenti()
    assert "X+cover" not in set(rk.score(df, TUTTI_PESI, "solo_pioggia")["classe"])
    assert "X+cover" in set(rk.score(df, TUTTI_PESI, "solo_pioggia", includi_equivalenti=True)["classe"])
    p = rk.pareto_front(df, "solo_pioggia")
    assert "X+cover" not in set(p["classe"])
    p2 = rk.pareto_front(df, "solo_pioggia", includi_equivalenti=True)
    assert dict(zip(p2["classe"], p2["non_dominata"]))["X+cover"]       # il pari merito non e' dominato
    # nessun pari merito arbitrario nel punteggio
    s = rk.score(df, TUTTI_PESI, "solo_pioggia")
    assert s["punteggio"].is_unique


def test_equivalenti_in_confronta_e_attuale_mai_esclusa():
    df = _con_equivalenti()
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia", n_alternative=3)
    assert "X+cover" not in [a["classe"] for a in c["alternative"]]
    assert c["n_confrontate"] == 3
    c2 = rk.confronta(df, TUTTI_PESI, "solo_pioggia", n_alternative=3, includi_equivalenti=True)
    assert c2["n_confrontate"] == 4
    # l'attuale ha un'equivalente: resta, e la sua equivalente non viene proposta come alternativa
    df = _con_equivalenti()
    df.loc[df["classe"] == "ATT", "equivalente_a"] = "X"
    s = rk.score(df, TUTTI_PESI, "solo_pioggia")
    assert "ATT" in set(s["classe"])
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia", n_alternative=3)
    assert "X" not in [a["classe"] for a in c["alternative"]]


def test_sintesi_senza_colonna_equivalente_a_funziona(tre):
    assert len(rk.score(tre.drop(columns="equivalente_a"), {"resa": 1}, "solo_pioggia")) == 3


def test_frase_cover_usa_la_quota_realizzata():
    df = sint(riga("ATT", attuale=True), riga("A", resa=0.9, real=0.4), riga("B", resa=0.85, real=1.0),
              riga("N", resa=0.8, real=float("nan")))
    c = rk.confronta(df, TUTTI_PESI, "solo_pioggia", n_alternative=3)
    per = {a["classe"]: " | ".join(a["rischi"]) for a in c["alternative"]}
    assert "la cover e' praticabile nel 40% dei casi" in per["A"]
    assert "cover" not in per["B"] and "cover" not in per["N"]
