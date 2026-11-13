"""Test di `fieldwise.ensemble` sul meteo reale del punto pilota (saltati se la cache manca).

Quasi tutti usano un piccolo sottoinsieme di rotazioni per restare veloci; il test marcato
`slow` esegue l'ensemble completo (216 rotazioni x annate x 3 scenari)."""
from __future__ import annotations

import os
import time

import pandas as pd
import pytest

from fieldwise import config
from fieldwise import ensemble as en
from fieldwise import rotation as rt

MSF = "mais > soia > frumento"
PERMUTAZIONI = ["soia > frumento > mais", "frumento > mais > soia"]     # stessa classe ciclica di MSF
ALTRE = ["mais > frumento > soia", "mais > mais > soia+cover", "mais > soia+cover > frumento"]
SUBSET = [MSF, *PERMUTAZIONI, *ALTRE]
CLASSE_MSF = rt.Rotation.from_label(MSF).canonical().label
INDICATORI = ["resa_rel_media", "resa_rel_minima", "irrigazione_mm", "concime_kg_n", "n_lisciviato_kg_n",
              "humus_t_ha", "giorni_caldo", "ruscellamento_mm", "percolazione_mm"]


@pytest.fixture(scope="module")
def ctx():
    old = os.environ.get("FIELDWISE_OFFLINE")
    os.environ["FIELDWISE_OFFLINE"] = "1"
    try:
        return rt.build_context()
    except FileNotFoundError as e:
        pytest.skip(f"cache meteo del punto pilota assente: {e}")
    finally:
        if old is None:
            os.environ.pop("FIELDWISE_OFFLINE", None)
        else:
            os.environ["FIELDWISE_OFFLINE"] = old


@pytest.fixture(scope="module")
def ris(ctx):
    return en.run_ensemble(ctx, rotazioni=SUBSET, rotazione_attuale=MSF)


@pytest.fixture(scope="module")
def ris_mais(ctx):
    return en.run_ensemble(ctx, rotazioni=SUBSET, rotazione_attuale="mais")


def test_forma_delle_tabelle(ris):
    det, sin = ris
    for c in ["etichetta", "classe", "anno_partenza", "anno_valutato", "scenario", "conformita",
              *INDICATORI, "f_acqua", "f_caldo", "f_rotazione", "n_colture_oltre_mas", "deficit_n_kg_n",
              "res_acqua_mm", "res_azoto_rotazione_kg"]:
        if c != "conformita":      # nel dettaglio la conformita' e' per regime (conformita_<regime>)
            assert c in det.columns, c
    assert any(c.startswith("conformita_") for c in det.columns)
    for c in ["classe", "scenario", "n_simulazioni", "n_scartate", "motivo_scarto_prevalente", "attuale",
              "conformita", "resa_rel_mediana", "resa_rel_min", "resa_rel_p10", "irrigazione_mm",
              "concime_kg_n", "n_lisciviato_kg_n", "humus_t_ha", "f_acqua", "f_caldo", "f_rotazione",
              "fattore_limitante", "quota_oltre_limite_n", "quota_cover_non_praticata"]:
        assert c in sin.columns, c
    assert set(det["scenario"]) == set(rt.SCENARI)
    assert det[INDICATORI].notna().all().all()
    assert det["res_acqua_mm"].abs().max() < 1e-6          # bilanci chiusi


def test_una_riga_per_classe_e_scenario(ris):
    _, sin = ris
    assert len(sin) == sin[["classe", "scenario"]].drop_duplicates().shape[0]
    assert sin["classe"].nunique() == 4          # MSF e le sue permutazioni sono una sola classe
    assert len(sin) == 4 * 3


def test_aggregazione_per_classe_ciclica(ris):
    det, sin = ris
    sub = det[(det["classe"] == CLASSE_MSF) & (det["scenario"] == "tetto_irriguo")]
    assert set(sub["etichetta"]) == {MSF, *PERMUTAZIONI}
    riga = sin[(sin["classe"] == CLASSE_MSF) & (sin["scenario"] == "tetto_irriguo")].iloc[0]
    assert riga["n_simulazioni"] == len(sub)
    assert riga["n_membri"] == 3
    assert riga["resa_rel_mediana"] == pytest.approx(sub["resa_rel_media"].median())
    assert riga["resa_rel_min"] == pytest.approx(sub["resa_rel_media"].min())
    assert riga["resa_rel_p10"] == pytest.approx(sub["resa_rel_media"].quantile(0.10))
    assert riga["resa_rel_min"] <= riga["resa_rel_p10"] <= riga["resa_rel_mediana"]
    assert riga["irrigazione_mm"] == pytest.approx(sub["irrigazione_mm"].median())
    assert riga["f_acqua"] == pytest.approx(sub["f_acqua"].mean())
    medie = {f: riga[f"f_{f}"] for f in en.FATTORI}
    assert riga["fattore_limitante"] == min(medie, key=medie.get)
    assert riga["quota_oltre_limite_n"] == pytest.approx((sub["n_colture_oltre_mas"] > 0).mean())


def test_scartate_contate_e_non_negli_indicatori(ctx, ris):
    det, sin = ris
    anni = int(ctx.year[ctx.last_idx]) - int(ctx.year[0]) + 1
    for _, r in sin.iterrows():
        assert r["n_simulazioni"] + r["n_scartate"] == r["n_membri"] * anni
        assert (r["n_scartate"] == 0) == (r["motivo_scarto_prevalente"] == en.NESSUNO)
    assert sin["n_scartate"].sum() > 0       # le ultime annate non bastano al ciclo completo
    assert sin.attrs["meta"]["n_scartate"] == sin["n_scartate"].sum()


def test_rotazione_attuale_tra_le_enumerate(ris):
    _, sin = ris
    assert sin.loc[sin["attuale"], "classe"].unique().tolist() == [CLASSE_MSF]
    assert sin["attuale"].sum() == 3             # una riga per scenario
    assert len(sin) == 12                        # nessuna riga aggiunta


def test_rotazione_attuale_non_enumerata(ris_mais, ris):
    det, sin = ris_mais
    assert sin["classe"].nunique() == 5          # 4 del sottoinsieme + "mais"
    att = sin[sin["attuale"]]
    assert att["classe"].unique().tolist() == ["mais"] and len(att) == 3
    assert not sin.loc[sin["classe"] != "mais", "attuale"].any()
    assert (det.loc[det["classe"] == "mais", "attuale"]).all()
    # mais continuo = mais > mais > mais per la conformita' (non e' valutabile come lunghezza 1)
    assert (att["conformita"] == "non_conforme").all()
    # il resto della sintesi non cambia aggiungendo l'attuale
    a = ris[1].drop(columns="attuale").reset_index(drop=True)
    b = sin[sin["classe"] != "mais"].drop(columns="attuale").reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_attuale_come_sequenza(ctx):
    _, sin = en.run_ensemble(ctx, rotazioni=[MSF], rotazione_attuale=["mais", "soia", "frumento"])
    assert sin["attuale"].all()


def test_irrigazione_nulla_solo_pioggia(ris_mais):
    det, sin = ris_mais
    assert (det.loc[det["scenario"] == "solo_pioggia", "irrigazione_mm"] == 0).all()
    assert (sin.loc[sin["scenario"] == "solo_pioggia", "irrigazione_mm"] == 0).all()
    assert (sin.loc[sin["scenario"] == "irrigazione_libera", "irrigazione_mm"] > 0).any()


def test_scenari_e_opzioni(ctx):
    det, _ = en.run_ensemble(ctx, rotazioni=[MSF], scenari=["tetto_irriguo"], metodo_et="singolo")
    assert set(det["scenario"]) == {"tetto_irriguo"}
    base, _ = en.run_ensemble(ctx, rotazioni=[MSF], scenari=["tetto_irriguo"])
    assert not det["irrigazione_mm"].equals(base["irrigazione_mm"])   # l'opzione arriva a simulate
    with pytest.raises(ValueError, match="scenario"):
        en.run_ensemble(ctx, rotazioni=[MSF], scenari=["nessuno"])
    with pytest.raises(ValueError):
        en.run_ensemble(ctx, p={}, rotazioni=[MSF])


def test_determinismo(ctx, ris):
    _, s1 = ris
    _, s2 = en.run_ensemble(ctx, rotazioni=SUBSET, rotazione_attuale=MSF)
    pd.testing.assert_frame_equal(s1, s2)


def test_salvataggio_e_rilettura_identici(ris, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    det, sin = ris
    d = en.save_ensemble(det, sin, 44.0, 9.0)
    for f in (en.FILE_DETTAGLIO, en.FILE_SINTESI, en.FILE_META):
        assert (d / f).exists()
    det2, sin2 = en.load_ensemble(44.0, 9.0)
    pd.testing.assert_frame_equal(det, det2, check_exact=True)
    pd.testing.assert_frame_equal(sin, sin2, check_exact=True)
    meta = sin2.attrs["meta"]
    assert meta["n_simulazioni"] == len(det)
    for k in ("calcolato_il", "tempo_s", "hash_parametri", "hash_file_parametri", "opzioni_simulate"):
        assert k in meta
    assert "crops.yaml" in meta["hash_file_parametri"]


def test_load_senza_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    with pytest.raises(FileNotFoundError):
        en.load_ensemble(1.0, 2.0)


@pytest.mark.slow
def test_ensemble_completo(ctx):
    t0 = time.perf_counter()
    det, sin = en.run_ensemble(ctx)
    dt = time.perf_counter() - t0
    assert dt < 60, f"ensemble completo in {dt:.1f} s"
    assert sin["classe"].nunique() == 76
    assert len(sin) == 76 * 3
    assert len(det) == sin["n_simulazioni"].sum() > 0
    assert sin["n_membri"].sum() == 216 * 3


def test_cover_realizzata_ed_equivalenze(ctx):
    rot = ["frumento > frumento > soia+cover", "frumento > frumento > soia",
           "frumento+cover > mais > soia", "mais > mais > mais", "mais"]
    det, sin = en.run_ensemble(ctx, rotazioni=rot)
    s = sin[sin["scenario"] == "solo_pioggia"].set_index("classe")
    for c in ("cover_richieste", "cover_realizzata_quota", "equivalente_a"):
        assert c in sin.columns
    assert s.loc["frumento > frumento > soia+cover", "cover_richieste"] == 1
    assert s.loc["frumento > frumento > soia", "cover_richieste"] == 0
    assert s["cover_realizzata_quota"].dropna().between(0, 1).all()
    assert pd.isna(s.loc["frumento > frumento > soia", "cover_realizzata_quota"])
    # quota coerente con il dettaglio
    d = det[(det["classe"] == "frumento > frumento > soia+cover") & (det["scenario"] == "solo_pioggia")]
    q = 1 - d["cover_non_praticate"].sum() / d["cover_richieste"].sum()
    assert s.loc["frumento > frumento > soia+cover", "cover_realizzata_quota"] == pytest.approx(q)
    # una cover mai praticata rende la classe identica a quella senza cover
    for cl, r in s.iterrows():
        if r["equivalente_a"] != en.NESSUNO:
            assert r["cover_richieste"] > 0 and r["equivalente_a"] in s.index
            for col in ("resa_rel_mediana", "irrigazione_mm", "concime_kg_n", "humus_t_ha", "n_lisciviato_kg_n"):
                assert r[col] == pytest.approx(s.loc[r["equivalente_a"], col])
    eq = s.loc["frumento > frumento > soia+cover", "equivalente_a"]
    if s.loc["frumento > frumento > soia+cover", "cover_realizzata_quota"] == 0:
        assert eq == "frumento > frumento > soia"
    assert s.loc["frumento > frumento > soia", "equivalente_a"] == en.NESSUNO


def test_equivalente_a_solo_se_la_classe_ridotta_e_simulata(ctx):
    _, sin = en.run_ensemble(ctx, rotazioni=["frumento > frumento > soia+cover"])
    assert (sin["equivalente_a"] == en.NESSUNO).all()      # la classe senza cover non e' nell'insieme
