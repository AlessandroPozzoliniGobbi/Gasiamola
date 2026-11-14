"""Test di `fieldwise.economics`: margine su concime e acqua con prezzi finti (nessun meteo)."""
from __future__ import annotations

import pytest

from fieldwise import economics as eco
from fieldwise import params as _params


def voce(valore):
    return {"valore": valore, "unita": "-", "nota": "", "verificato": False, "assunzione": True, "motivazione": "test"}


P = {"economia": {"prezzi_eur_t": {"mais": voce(250.0), "soia": voce(500.0), "frumento": voce(270.0)},
                  "azoto_eur_kg_n": voce(1.5), "irrigazione_eur_mm": voce(0.8)}}


def uscita(colture, concime, irrigazione, anni=3):
    return {"colture": [{"coltura": c, "resa": r} for c, r in colture], "durata_anni": anni,
            "indicatori": {"concime_anno": concime, "irrigazione_anno": irrigazione}}


def test_margine_a_mano():
    # ricavo/anno = (15*250 + 4*500 + 8*270) / 3 ; costi = 100*1,5 + 200*0,8
    out = uscita([("mais", 15.0), ("soia", 4.0), ("frumento", 8.0)], concime=100.0, irrigazione=200.0)
    ricavo = (15 * 250 + 4 * 500 + 8 * 270) / 3
    assert eco.ricavo_anno(P, out["colture"], 3) == pytest.approx(ricavo)
    assert eco.margine_anno(P, out) == pytest.approx(ricavo - 150.0 - 160.0)


def test_senza_concime_e_senza_irrigazione_il_margine_e_il_ricavo():
    out = uscita([("soia", 4.0)], concime=0.0, irrigazione=0.0, anni=1)
    assert eco.margine_anno(P, out) == pytest.approx(2000.0)


def test_colture_ripetute_contano_una_volta_per_segmento():
    out = uscita([("mais", 10.0), ("mais", 10.0), ("mais", 10.0)], concime=0.0, irrigazione=0.0)
    assert eco.margine_anno(P, out) == pytest.approx(2500.0)


def test_margine_puo_essere_negativo():
    out = uscita([("mais", 1.0)], concime=300.0, irrigazione=400.0, anni=1)
    assert eco.margine_anno(P, out) < 0


def test_durata_non_valida():
    with pytest.raises(ValueError):
        eco.ricavo_anno(P, [{"coltura": "mais", "resa": 10.0}], 0)


def test_prezzo_di_coltura_senza_parametro_da_errore_chiaro():
    with pytest.raises(KeyError, match="soia"):
        eco.prezzo_coltura({"economia": {"prezzi_eur_t": {"mais": voce(250.0)}}}, "soia")


def test_parametri_reali_hanno_i_valori_attesi_e_sono_positivi():
    p = _params.load_params()
    for c in ("mais", "soia", "frumento"):
        assert eco.prezzo_coltura(p, c) > 0
    assert _params.get(p, "economia.azoto_eur_kg_n") > 0
    assert _params.get(p, "economia.irrigazione_eur_mm") > 0
