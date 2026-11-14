"""Test di `fieldwise.economics`: margine con prezzi e costi finti (nessun meteo)."""
from __future__ import annotations

import pandas as pd
import pytest

from fieldwise import economics as eco
from fieldwise import params as _params


def voce(valore):
    return {"valore": valore, "unita": "-", "nota": "", "verificato": False, "assunzione": True, "motivazione": "test"}


P = {"economia": {"prezzi_eur_t": {"mais": voce(250.0), "soia": voce(500.0), "frumento": voce(270.0)},
                  "azoto_eur_kg_n": voce(1.5), "irrigazione_eur_mm": voce(0.8),
                  "altri_costi_eur_ha": {"mais": voce(2000.0), "soia": voce(1500.0), "frumento": voce(900.0)}}}


def uscita(colture, concime, irrigazione, anni=3):
    return {"colture": [{"coltura": c, "resa": r} for c, r in colture], "durata_anni": anni,
            "indicatori": {"concime_anno": concime, "irrigazione_anno": irrigazione}}


def test_margine_a_mano():
    out = uscita([("mais", 15.0), ("soia", 4.0), ("frumento", 8.0)], concime=100.0, irrigazione=200.0)
    ricavo = (15 * 250 + 4 * 500 + 8 * 270) / 3
    altri = (2000 + 1500 + 900) / 3
    c = eco.componenti(P, out, ("mais", "soia", "frumento"))
    assert c[eco.COL_RICAVO] == pytest.approx(ricavo)
    assert c[eco.COL_ALTRI] == pytest.approx(altri)
    assert c[eco.COL_MARGINE] == pytest.approx(ricavo - 150.0 - 160.0 - altri)
    assert eco.margine_anno(P, out) == pytest.approx(c[eco.COL_MARGINE])
    assert c["colture_anno_mais"] == pytest.approx(1 / 3)


def test_colture_ripetute_contano_una_volta_per_segmento():
    out = uscita([("mais", 10.0)] * 3, concime=0.0, irrigazione=0.0)
    c = eco.componenti(P, out, ("mais", "soia"))
    assert c[eco.COL_MARGINE] == pytest.approx(2500.0 - 2000.0)
    assert c["colture_anno_mais"] == pytest.approx(1.0)
    assert c["colture_anno_soia"] == 0.0


def test_margine_puo_essere_negativo():
    assert eco.margine_anno(P, uscita([("mais", 5.0)], 300.0, 400.0, anni=1)) < 0


def test_durata_non_valida():
    with pytest.raises(ValueError):
        eco.ricavo_anno(P, [{"coltura": "mais", "resa": 10.0}], 0)


def test_prezzo_di_coltura_senza_parametro_da_errore_chiaro():
    with pytest.raises(KeyError, match="soia"):
        eco.prezzo_coltura({"economia": {"prezzi_eur_t": {"mais": voce(250.0)}}}, "soia")


def test_ricalcola_margine_con_i_costi_dell_agricoltore():
    s = pd.DataFrame({eco.COL_RICAVO: [3000.0, 2000.0], eco.COL_CONCIME: [300.0, 100.0],
                      eco.COL_IRRIGAZIONE: [100.0, 0.0], "colture_anno_mais": [1.0, 1 / 3],
                      "colture_anno_soia": [0.0, 2 / 3]})
    r = eco.ricalcola_margine(s, {"mais": 1800.0, "soia": 1200.0})
    assert list(r[eco.COL_ALTRI]) == pytest.approx([1800.0, 600.0 + 800.0])
    assert list(r[eco.COL_MARGINE]) == pytest.approx([800.0, 2000.0 - 100.0 - 1400.0])
    assert eco.COL_MARGINE not in s.columns           # l'originale non cambia
    with pytest.raises(KeyError):
        eco.ricalcola_margine(s, {"frumento": 900.0})


def test_parametri_reali_positivi():
    p = _params.load_params()
    for c in ("mais", "soia", "frumento"):
        assert eco.prezzo_coltura(p, c) > 0
        assert eco.altri_costi_coltura(p, c) > 0
    assert _params.get(p, "economia.azoto_eur_kg_n") > 0
    assert _params.get(p, "economia.irrigazione_eur_mm") > 0
