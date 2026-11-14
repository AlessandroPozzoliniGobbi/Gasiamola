"""Test della verifica dell'ET con ECOSTRESS (`fieldwise.validation.validate_ecostress`):
dati sintetici dal risultato calcolabile a mano, offline. Il motore e' sostituito da una serie
giornaliera finta (`mono_daily`): qui si prova la statistica, non il bilancio idrico."""
from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd
import pytest

from fieldwise import config
from fieldwise import validation as val
from fieldwise.data import ecostress


# ----------------------------------------------------------------------------- anomalie
def _mensile(valori):
    """valori: {'AAAA-MM': (obs, sim)} -> tabella mensile come `ecostress_monthly`."""
    idx = pd.PeriodIndex(list(valori), freq="M")
    return pd.DataFrame({"et_obs": [v[0] for v in valori.values()],
                         "eta_sim": [v[1] for v in valori.values()], "n_passaggi": 9}, index=idx)


def test_anomalie_rispetto_al_mese_di_calendario_a_mano():
    # luglio: 2019 (2; 3), 2020 (4; 5) -> medie 3 e 4 -> anomalie -1/+1 sia osservate sia simulate
    # agosto presente solo nel 2019: nessuna anomalia (sarebbe zero) -> escluso
    h = val.calendar_anomalies(_mensile({"2019-07": (2.0, 3.0), "2019-08": (5.0, 9.0),
                                         "2020-07": (4.0, 5.0)}))
    assert list(h.index.astype(str)) == ["2019-07", "2020-07"]
    assert h["et_obs_anom"].tolist() == pytest.approx([-1.0, 1.0])
    assert h["eta_sim_anom"].tolist() == pytest.approx([-1.0, 1.0])


def test_anomalie_tolgono_il_ciclo_stagionale():
    # ciclo stagionale forte (estate 5, inverno 1) ma nessuna differenza tra gli anni: anomalie zero
    v = {f"{a}-{m:02d}": (5.0 if m == 7 else 1.0, 6.0 if m == 7 else 2.0)
         for a in (2019, 2020, 2021) for m in (1, 7)}
    h = val.calendar_anomalies(_mensile(v))
    assert len(h) == 6 and np.allclose(h["et_obs_anom"], 0) and np.allclose(h["eta_sim_anom"], 0)


def test_medie_mensili_solo_con_almeno_5_passaggi():
    giorni = list(range(1, 6)) + list(range(1, 5))             # 5 passaggi a luglio, 4 ad agosto
    mesi = [7] * 5 + [8] * 4
    d = pd.DataFrame({"data": pd.to_datetime([f"2019-{m:02d}-{g:02d}" for m, g in zip(mesi, giorni)]),
                      "et_obs": np.arange(9.0), "eta_sim": np.arange(9.0) + 1.0})
    m = val.ecostress_monthly(d)
    assert list(m.index.astype(str)) == ["2019-07"] and m["n_passaggi"].iloc[0] == 5
    assert m["et_obs"].iloc[0] == pytest.approx(2.0)           # media di 0..4
    assert len(val.ecostress_monthly(d, min_passaggi=4)) == 2


# ----------------------------------------------------------------------------- validate_ecostress
ANNI = (2019, 2020, 2021)
MESI_STAGIONE = (6, 7, 8)


def _eta_giornaliera(date):
    """ET simulata finta: cresce col giorno dell'anno, piu' alta di anno in anno (sempre diversa)."""
    d = pd.DatetimeIndex(date)
    return 1.0 + 0.01 * d.day_of_year + 0.2 * (d.year - 2018)


@pytest.fixture
def sintetico(monkeypatch):
    idx = pd.date_range("2018-01-01", "2023-12-31", freq="D")
    day = pd.DataFrame({"eta": _eta_giornaliera(idx), "ks": 1.0, "etc": 1.0,
                        "in_stagione": idx.month.isin(MESI_STAGIONE)}, index=idx)
    chiamate = []

    def finta(ctx, crop, scenario, anno=2000):
        chiamate.append((crop, scenario))
        return day
    monkeypatch.setattr(val, "mono_daily", finta)

    righe = []

    def passaggi(punto, anno, mese, n, qualita="valido"):
        for g in range(1, n + 1):
            righe.append({"punto": punto, "data_ora_passaggio": f"{anno}-{mese:02d}-{g:02d} 10:00:00 UTC",
                          "tile": "32TNR", "data": pd.Timestamp(anno, mese, g),
                          "et_mm_giorno": float(_eta_giornaliera([pd.Timestamp(anno, mese, g)])[0]) - 1.0
                          if qualita == "valido" else np.nan, "qualita": qualita})
    for a in ANNI:
        for m in MESI_STAGIONE:
            passaggi("P01", a, m, 6)                  # scarto esatto: sim - obs = +1,0
    passaggi("P01", 2021, 9, 4)                       # settembre con 4 passaggi: fuori dalle medie mensili
    passaggi("P01", 2022, 7, 6)                       # punto-anno non in tabella: escluso
    passaggi("P02", 2020, 7, 6)                       # punto non in tabella: escluso
    passaggi("P01", 2020, 12, 6, qualita="nube")      # non valido: escluso
    passaggi("P01", 2023, 7, 6)                       # dopo il 2022: escluso
    colture = pd.DataFrame({"punto": "P01", "anno": list(ANNI), "coltura": "mais"})
    return pd.DataFrame(righe), colture, chiamate


def test_scarto_e_correlazione_di_un_caso_noto(sintetico):
    pas, col, chiamate = sintetico
    res, tab = val.validate_ecostress({"power": None}, pas, col, scenari=("tetto_irriguo",))
    assert res["passaggi_usati"] == 3 * 3 * 6 + 4 and res["punti_usati"] == 1
    assert res["coltura_dei_passaggi"] == {"mais": 58}
    assert chiamate == [("mais", "tetto_irriguo")]               # solo le colture presenti
    s = res["scenari"]["tetto_irriguo"]
    st = s["stagione"]
    assert st["n_passaggi"] == 54 and st["n_punti"] == 1
    assert st["scarto_sim_meno_obs"] == pytest.approx(1.0)
    assert st["rmse"] == pytest.approx(1.0)
    assert st["media_sim"] - st["media_obs"] == pytest.approx(1.0)
    # 9 mesi con almeno 5 passaggi; sim = obs + 1: correlazione perfetta, grezza e sulle anomalie
    assert st["mensile"]["n_mesi"] == 9 and st["mensile"]["pearson"] == pytest.approx(1.0)
    assert st["anomalie"]["n_mesi"] == 9 and st["anomalie"]["pearson"] == pytest.approx(1.0)
    assert st["anomalie"]["metodo_ic"] == "block"
    # lettura alternativa dell'unita': W m-2 -> ET osservata ~0,035 volte, scarto molto piu' grande
    assert st["scarto_lettura_wm2"] > st["scarto_sim_meno_obs"]
    # settembre (4 passaggi) e' fuori stagione e fuori dalle medie mensili
    fs = s["fuori_stagione"]
    assert fs["n_passaggi"] == 4 and fs["mensile"]["n_mesi"] == 0
    assert math.isnan(fs["mensile"]["pearson"])
    assert "tutti" in s and s["tutti"]["n_passaggi"] == 58
    assert {"stagione_mais", "stagione_soia", "stagione_frumento"} <= set(s)
    so = s["stagione_soia"]                                      # nessun passaggio: nessun numero inventato
    assert so["n_passaggi"] == 0 and "scarto_sim_meno_obs" not in so and math.isnan(so["mensile"]["pearson"])


def test_tabella_mensile_e_unita_dichiarata(sintetico):
    pas, col, _ = sintetico
    res, tab = val.validate_ecostress({"power": None}, pas, col, scenari=("solo_pioggia", "tetto_irriguo"))
    assert set(tab["scenario"]) == {"solo_pioggia", "tetto_irriguo"}
    t = tab[(tab["scenario"] == "tetto_irriguo") & (tab["sottoinsieme"] == "stagione")]
    assert len(t) == 9 and {"mese", "et_obs", "eta_sim", "n_passaggi", "et_obs_anom"} <= set(t.columns)
    assert t["n_passaggi"].eq(6).all()
    assert "mm/giorno" in res["unita"] and "W m-2" in res["unita"]
    assert res["min_passaggi_per_mese"] == 5 and res["anni"] == [2018, 2022]


def test_n_minimo_pochi_mesi_non_stimano_l_intervallo(sintetico):
    pas, col, _ = sintetico
    # 5 mesi con >= 5 passaggi (giu-ago 2019, giu-lug 2020): correlazione calcolabile, ma meno di un
    # blocco da 6 mesi -> IC non stimato; anomalie: agosto e' in un solo anno -> 4 mesi
    d = pas["data"]
    pas = pas[(d.dt.year == 2019) | ((d.dt.year == 2020) & d.dt.month.isin([6, 7]))]
    res, _ = val.validate_ecostress({"power": None}, pas, col, scenari=("tetto_irriguo",))
    st = res["scenari"]["tetto_irriguo"]["stagione"]
    assert st["mensile"]["n_mesi"] == 5
    assert st["mensile"]["pearson"] == pytest.approx(1.0)
    assert all(math.isnan(x) for x in st["mensile"]["pearson_ic95"])
    assert st["anomalie"]["n_mesi"] == 4 and st["anomalie"]["pearson"] == pytest.approx(1.0)
    assert all(math.isnan(x) for x in st["anomalie"]["pearson_ic95"])
    # tre soli mesi: nemmeno la correlazione
    solo = pas[pas["data"].dt.year == 2019]
    res, _ = val.validate_ecostress({"power": None}, solo, col, scenari=("tetto_irriguo",))
    st = res["scenari"]["tetto_irriguo"]["stagione"]
    assert st["mensile"]["n_mesi"] == 3 and math.isnan(st["mensile"]["pearson"])
    assert st["anomalie"]["n_mesi"] == 0 and math.isnan(st["anomalie"]["pearson"])


def test_meno_di_4_passaggi_non_danno_statistiche(sintetico):
    pas, col, _ = sintetico
    pas = pas[(pas["data"].dt.year == 2019) & (pas["data"].dt.month == 7)].head(3)
    res, _ = val.validate_ecostress({"power": None}, pas, col, scenari=("tetto_irriguo",))
    assert res["scenari"]["tetto_irriguo"]["stagione"]["n_passaggi"] == 3
    assert "scarto_sim_meno_obs" not in res["scenari"]["tetto_irriguo"]["stagione"]


def test_la_coltura_scelta_decide_quali_passaggi_entrano(sintetico):
    pas, col, chiamate = sintetico
    col2 = pd.concat([col, pd.DataFrame({"punto": ["P02"], "anno": [2020], "coltura": ["soia"]})])
    res, _ = val.validate_ecostress({"power": None}, pas, col2, scenari=("tetto_irriguo",))
    assert res["coltura_dei_passaggi"] == {"mais": 58, "soia": 6}
    assert sorted(chiamate) == [("mais", "tetto_irriguo"), ("soia", "tetto_irriguo")]


def test_riepilogo_serializzabile_con_run_all_clean(sintetico):
    pas, col, _ = sintetico
    res, _ = val.validate_ecostress({"power": None}, pas, col, scenari=("tetto_irriguo",))
    json.dumps(val._clean(res))                                  # niente NaN/numpy non serializzabili


# ----------------------------------------------------------------------------- dati reali (cache)
@pytest.mark.slow
def test_riproduce_la_prova_e_con_le_stesse_colture(monkeypatch):
    """Con le colture della prova (riconoscimento Sentinel-2, esterno al prodotto) il codice del
    prodotto rida i numeri della prova E: passaggi, scarto e correlazioni coincidono."""
    prove = config.PROCESSED_DIR / "esperimenti"
    f_cl, f_rif = prove / "prova_a_classi_s2.csv", prove / "prova_e_riepilogo.json"
    if not (f_cl.exists() and f_rif.exists() and ecostress.processed_path(create=False).exists()):
        pytest.skip("cache ECOSTRESS o file della prova assenti")
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    from fieldwise import rotation as R
    from fieldwise import weather
    ctx = R.build_context(forcing=weather.load_forcing(config.PILOT_LAT, config.PILOT_LON, rain_source="power"))
    cl = pd.read_csv(f_cl)[["punto", "anno", "classe"]]
    cl = cl[cl["classe"].isin(["mais", "soia", "cereale_vernino"])].replace({"cereale_vernino": "frumento"})
    res, _ = val.validate_ecostress({"power": ctx}, ecostress.load(), cl.rename(columns={"classe": "coltura"}),
                                    scenari=("tetto_irriguo",))
    rif = json.loads(f_rif.read_text())["tetto_irriguo"]["stagione"]
    s = res["scenari"]["tetto_irriguo"]["stagione"]
    assert res["passaggi_usati"] == 2436 and res["punti_usati"] == 23
    assert s["n_passaggi"] == rif["n_passaggi"] == 1258
    assert s["scarto_sim_meno_obs"] == pytest.approx(rif["scarto_sim_meno_obs"], abs=1e-9)
    assert s["mensile"]["pearson"] == pytest.approx(rif["mensile"]["pearson"], abs=1e-9)
    assert s["mensile"]["n_mesi"] == 27


# ----------------------------------------------------------------------------- regole di controllo
def test_pesi_istat_sono_le_quote_delle_tre_colture_dell_anno():
    ist = pd.DataFrame({"year": [2019] * 4, "crop": ["mais", "soia", "frumento", "orzo"],
                        "area_ha": [50.0, 30.0, 20.0, 99.0]})
    assert val._pesi_istat(ist) == {2019: pytest.approx({"mais": 0.5, "soia": 0.3, "frumento": 0.2})}


def test_controlli_tutti_e_mix_istat_a_mano(monkeypatch):
    """Tre colture con ET simulata costante (mais 6, soia 4, frumento 2) e stagioni diverse: mais e soia
    in stagione a luglio, frumento no. Il passaggio osservato vale sempre 1."""
    idx = pd.date_range("2018-01-01", "2023-12-31", freq="D")
    eta = {"mais": 6.0, "soia": 4.0, "frumento": 2.0}
    stag = {"mais": True, "soia": True, "frumento": False}

    def finta(ctx, crop, scenario, anno=2000):
        return pd.DataFrame({"eta": eta[crop], "ks": 1.0, "etc": 1.0,
                             "in_stagione": np.where(idx.month == 7, stag[crop], False)}, index=idx)
    monkeypatch.setattr(val, "mono_daily", finta)
    righe = [{"punto": "P01", "data_ora_passaggio": f"2019-{m:02d}-{g:02d} 10:00:00 UTC", "tile": "32TNR",
              "data": pd.Timestamp(2019, m, g), "et_mm_giorno": 1.0, "qualita": "valido"}
             for m in (1, 7) for g in range(1, 7)]
    righe.append({"punto": "P01", "data_ora_passaggio": "2019-07-20 10:00:00 UTC", "tile": "32TNR",
                  "data": pd.Timestamp(2019, 7, 20), "et_mm_giorno": np.nan, "qualita": "nube"})
    ist = pd.DataFrame({"year": [2019] * 3, "crop": ["mais", "soia", "frumento"], "area_ha": [50.0, 30.0, 20.0]})
    res, tab = val.validate_ecostress_controlli({"power": None}, pd.DataFrame(righe), ist, scenari=("tetto_irriguo",))
    assert res["passaggi_validi"] == 12 and set(res["scenari"]["tetto_irriguo"]) == {
        "tutti_mais", "tutti_soia", "tutti_frumento", "mix_istat"}
    s = res["scenari"]["tetto_irriguo"]
    assert s["tutti_mais"]["tutti"]["scarto_sim_meno_obs"] == pytest.approx(5.0)
    assert s["tutti_soia"]["tutti"]["scarto_sim_meno_obs"] == pytest.approx(3.0)
    assert s["tutti_frumento"]["tutti"]["scarto_sim_meno_obs"] == pytest.approx(1.0)
    assert s["tutti_frumento"]["stagione"]["n_passaggi"] == 0          # il frumento finto non e' mai in stagione
    # mix: 0,5*6 + 0,3*4 + 0,2*2 = 4,6 -> scarto 3,6; peso in stagione a luglio 0,8 >= 0,5, a gennaio 0
    assert s["mix_istat"]["tutti"]["scarto_sim_meno_obs"] == pytest.approx(3.6)
    assert s["mix_istat"]["stagione"]["n_passaggi"] == 6 and s["mix_istat"]["fuori_stagione"]["n_passaggi"] == 6
    assert set(tab["regola"]) == set(s) and {"scenario", "sottoinsieme", "mese"} <= set(tab.columns)
    json.dumps(val._clean(res))


def test_la_tabella_delle_colture_si_carica_da_sola_se_esiste(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    assert val.ecostress_colture_table() is None
    (tmp_path / "cremona").mkdir()
    pd.DataFrame({"punto": ["P01"], "anno": [2019], "coltura": ["mais"]}).to_csv(
        tmp_path / "cremona" / val.ECOSTRESS_COLTURE_FILE, index=False)
    t = val.ecostress_colture_table()
    assert t is not None and t.iloc[0].to_dict() == {"punto": "P01", "anno": 2019, "coltura": "mais"}


@pytest.mark.slow
def test_la_tabella_salvata_e_quella_della_prova_con_i_suoi_metadati():
    p = config.PROCESSED_DIR / "cremona" / val.ECOSTRESS_COLTURE_FILE
    if not p.exists():
        pytest.skip("tabella delle colture non salvata")
    t = pd.read_csv(p)
    assert list(t.columns) == ["punto", "anno", "coltura"] and set(t["coltura"]) <= {"mais", "soia", "frumento"}
    assert not t.duplicated(["punto", "anno"]).any()
    meta = json.loads((p.parent / (p.name + ".meta.json")).read_text(encoding="utf-8"))
    assert "prova_a.py" in meta["params"]["script"] and "regole_prefissate" in meta["params"]["regole"]
    assert "65%" in meta["notes"] and "80%" in meta["notes"]
