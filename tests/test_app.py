"""Test dell'app Streamlit con ``streamlit.testing.v1.AppTest`` (offline, solo dati in cache)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from fieldwise import config  # noqa: E402

APP_DIR = Path(__file__).resolve().parents[1] / "app"
APP = APP_DIR / "streamlit_app.py"
PAGINE = ("Confronto", "Dettaglio di una annata", "Capire i dati", "Validazione", "Limiti e fonti")


@pytest.fixture()
def at(monkeypatch):
    monkeypatch.setenv("FIELDWISE_OFFLINE", "1")
    return AppTest.from_file(str(APP), default_timeout=180).run()


def contenuto(at) -> str:
    """Tutto il testo mostrato (markdown, messaggi, titoli, didascalie)."""
    parti = []
    for tipo in ("markdown", "error", "warning", "info", "success", "caption", "title", "header", "subheader"):
        parti += [str(e.value) for e in at.get(tipo)]
    return "\n".join(parti)


def vai(at, pagina):
    at.sidebar.radio(key="pagina").set_value(pagina).run()
    return at


def test_si_avvia_senza_eccezioni(at):
    assert not at.exception
    assert "Confronto delle rotazioni" in contenuto(at)


@pytest.mark.parametrize("pagina", PAGINE)
def test_ogni_pagina_si_apre(at, pagina):
    vai(at, pagina)
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.get("title")) >= 1


def test_avviso_sempre_visibile(at):
    for p in PAGINE:
        vai(at, p)
        assert any("non una prescrizione agronomica" in w.value for w in at.sidebar.warning)


def test_almeno_due_alternative_con_evidenze_e_rischi(at):
    alt = [m for m in at.markdown if str(m.value).startswith("**Alternativa") or str(m.value).startswith("**Altra alternativa")]
    assert len(alt) >= 2
    t = contenuto(at)
    assert "A favore" in t and ("Rischi e svantaggi" in t or "Punti deboli" in t)
    assert "Perché una rotazione perde resa" in t
    assert len(at.get("plotly_chart")) >= 3      # fattori, compromesso, distribuzione
    assert len(at.dataframe) >= 1


def test_la_nota_sui_pesi_e_visibile(at):
    assert any("servono solo a ordinare" in c.value for c in at.sidebar.caption)


def test_cambio_scenario_e_pesi(at):
    for sc in ("solo_pioggia", "tetto_irriguo", "irrigazione_libera"):
        at.sidebar.selectbox(key="scenario").set_value(sc).run()
        assert not at.exception, (sc, [e.value for e in at.exception])
    at.sidebar.slider(key="peso_resa").set_value(10).run()
    at.sidebar.slider(key="peso_acqua").set_value(0).run()
    assert not at.exception


def test_pesi_che_non_distinguono_mostrano_l_avviso(at):
    at.sidebar.selectbox(key="scenario").set_value("solo_pioggia").run()
    for k in ("resa", "concime", "suolo", "rischio"):
        at.sidebar.slider(key=f"peso_{k}").set_value(0)
    at.run()
    assert not at.exception
    assert "non si distinguono" in contenuto(at)


def test_tutti_i_pesi_a_zero_non_da_errore(at):
    for k in ("acqua", "resa", "concime", "suolo", "rischio"):
        at.sidebar.slider(key=f"peso_{k}").set_value(0)
    at.run()
    assert not at.exception
    assert "Non posso fare il confronto" in contenuto(at)


def test_solo_conformi_mostra_lo_stato_in_parole(at):
    at.sidebar.checkbox(key="solo_conformi").set_value(True).run()
    assert not at.exception
    t = contenuto(at)
    assert "conforme" in t and "disciplinare" in t
    alt = [m for m in at.markdown if str(m.value).startswith("**Alternativa") or str(m.value).startswith("**Altra alternativa")]
    assert len(alt) >= 1


def test_cambio_rotazione_attuale_ricalcola_senza_errori(at):
    at.sidebar.radio(key="n_colture").set_value(2).run()
    at.sidebar.selectbox(key="coltura_1").set_value("soia")
    at.sidebar.checkbox(key="cover_0").set_value(True)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "mais + cover crop → soia" in contenuto(at)
    vai(at, "Dettaglio di una annata")
    assert not at.exception


def test_dettaglio_ha_calendario_e_grafici(at):
    vai(at, "Dettaglio di una annata")
    assert not at.exception
    assert len(at.get("plotly_chart")) == 1
    assert len(at.dataframe) >= 2                    # calendario e azoto
    anni = at.selectbox[1].options
    at.selectbox[1].set_value(anni[0]).run()          # un'altra annata
    assert not at.exception


def test_punto_senza_cache_da_messaggio_e_non_va_in_errore(at):
    at.sidebar.number_input(key="lat").set_value(41.0)
    at.sidebar.number_input(key="lon").set_value(-3.0).run()
    assert not at.exception, [e.value for e in at.exception]
    errori = " ".join(e.value for e in at.error)
    assert "non sono nella cache" in errori
    assert "punto pilota" in errori
    comandi = " ".join(c.value for c in at.get("code"))
    assert "fieldwise.data.power --lat 41.0 --lon -3.0" in comandi
    assert "Confronto delle rotazioni" in contenuto(at)   # intanto mostra il punto pilota
    assert not (config.PROCESSED_DIR / "lat41.000_lon-3.000").exists()   # nessuna cartella creata
    for p in PAGINE[1:]:
        vai(at, p)
        assert not at.exception, (p, [e.value for e in at.exception])


def test_sorgenti_senza_riferimenti_a_loghi():
    sorgenti = "\n".join(p.read_text(encoding="utf-8") for p in sorted(APP_DIR.glob("*.py")))
    assert not re.search(r"\blogo\b", sorgenti, re.IGNORECASE)
    assert not re.search(r"\.(png|jpe?g|svg|gif|ico|webp)\b", sorgenti, re.IGNORECASE)
    assert "st.logo" not in sorgenti


def test_la_validazione_dice_cosa_non_e_confermato(at):
    vai(at, "Validazione")
    t = contenuto(at)
    for parola in ("Cosa è confermato", "Cosa NON è confermato", "Cosa è negativo", "Cosa non è stato validato",
                   "Frumento", "Soia", "Resa del mais"):
        assert parola in t, parola


def test_limiti_e_fonti_elenca_le_fonti(at):
    vai(at, "Limiti e fonti")
    t = contenuto(at)
    for parola in ("Falda superficiale", "Effluenti zootecnici", "Cover crop", "Eccessi d'acqua", "Stress da caldo"):
        assert parola in t, parola
    fonti = " ".join(" ".join(map(str, d.value.values.ravel())) for d in at.dataframe)
    for nome in ("NASA POWER", "GPM IMERG", "SMAP", "MODIS", "SoilGrids", "ISTAT", "ARPA Lombardia"):
        assert nome in fonti, nome


def test_capire_i_dati_ha_gli_esempi_numerici(at):
    vai(at, "Capire i dati")
    t = contenuto(at)
    for parola in ("ET0", "SMAP", "NDVI", "pluviometro", "escluse"):
        assert parola in t, parola
    assert len(at.info) >= 4 and all(re.search(r"\d", i.value) for i in at.info[:4])


def test_validazione_mostra_la_sensibilita_se_esiste(at):
    from fieldwise.data import cache
    esiste = (config.PROCESSED_DIR / cache.point_key(config.PILOT_LAT, config.PILOT_LON)
              / "sensitivity_summary.json").exists()
    vai(at, "Validazione")
    assert not at.exception, [e.value for e in at.exception]
    t = contenuto(at) + " ".join(i.value for i in at.info)
    assert ("Quanto cambiano i risultati" in t) == esiste
    if esiste:
        assert "resta prima nel" in " ".join(i.value for i in at.info)


def test_confronto_mostra_t_ha_punteggio_e_avvertenze(at):
    t = contenuto(at) + " ".join(str(d.value) for d in at.dataframe if hasattr(d, "value"))
    assert "t/ha" in t                                          # resa per coltura accanto alla resa relativa
    assert "relativo alle rotazioni confrontate" in t and "serve solo a ordinarle" in t
    assert "effluenti zootecnici" in t                          # avvertenza vicino all'humus
    frumento = [w for w in at.warning if "perdite degli anni umidi" in str(w.value)]
    if "frumento" in t.lower():
        assert frumento                                         # un'alternativa col frumento: avvertenza
    vai(at, "Dettaglio di una annata")
    assert not at.exception, [e.value for e in at.exception]
    assert "effluenti zootecnici" in contenuto(at)


def test_avvertenza_frumento_solo_con_frumento():
    import sys
    sys.path.insert(0, str(APP_DIR))
    from fw_util import AVVISO_FRUMENTO, rese_t_ha_testo
    assert "ottimistica" in AVVISO_FRUMENTO and "anni umidi" in AVVISO_FRUMENTO
    assert rese_t_ha_testo({"resa_t_ha_mais": 14.44, "resa_t_ha_soia": float("nan")}) == "mais 14,4 t/ha"
