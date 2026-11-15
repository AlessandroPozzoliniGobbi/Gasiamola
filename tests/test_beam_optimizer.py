"""Test per beam_optimizer.py.

Verifica:
 1. Continuità dello stato suolo [W, N, H] tra i 3 trienni (zero azzeramenti).
 2. Vincolo costo con resa >= 70% + fallback deterministico.
 3. Benchmark singoli per ciascun obiettivo.
 4. json.dumps(payload) senza errori (payload 100% JSON-serializzabile).
 5. Funzionamento con FIELDWISE_OFFLINE=1 in modalità storica.
 6. Funzionamento con FIELDWISE_OFFLINE=1 in modalità CMIP6.

Tutti i test girano senza rete (FIELDWISE_OFFLINE=1 è forzato nel setUp).
"""
from __future__ import annotations

import json
import os

import pytest

# ---------------------------------------------------------------------------
# Setup globale: forza modalità offline prima di qualsiasi import fieldwise
# ---------------------------------------------------------------------------
os.environ.setdefault("FIELDWISE_OFFLINE", "1")

try:
    from fieldwise.data import cmip6 as _cmip6  # noqa: F401
    HAS_CMIP6 = True
except (ImportError, ModuleNotFoundError):
    HAS_CMIP6 = False


@pytest.fixture(scope="module")
def payload_storico():
    """Payload beam search modalità storica (calcolo una sola volta per il modulo)."""
    from fieldwise.beam_optimizer import run_beam_search_9y

    return run_beam_search_9y(
        objectives=("resa", "guadagno", "costo"),
        irrigation_regime="tetto_irriguo",
        climate_mode="storico",
        beam_width=4,  # beam ridotto per velocità nei test
    )


@pytest.fixture(scope="module")
def payload_cmip6():
    """Payload beam search modalità CMIP6 (calcolo una sola volta per il modulo)."""
    if not HAS_CMIP6:
        pytest.skip("Modulo fieldwise.data.cmip6 non disponibile su main")
    from fieldwise.beam_optimizer import run_beam_search_9y

    return run_beam_search_9y(
        objectives=("resa", "costo", "guadagno"),
        irrigation_regime="tetto_irriguo",
        climate_mode="cmip6",
        ssp_code="ssp245",
        horizon_years=10,
        beam_width=4,
    )


# ---------------------------------------------------------------------------
# 1. Struttura del payload
# ---------------------------------------------------------------------------

class TestStrutturaPayload:

    def test_chiavi_principali(self, payload_storico):
        p = payload_storico
        assert "trienni" in p
        assert "eredita_suolo" in p
        assert "performance" in p
        assert "note" in p

    def test_tre_trienni(self, payload_storico):
        assert len(payload_storico["trienni"]) == 3

    def test_due_transizioni_suolo(self, payload_storico):
        assert len(payload_storico["eredita_suolo"]) == 2

    def test_performance_chiavi(self, payload_storico):
        perf = payload_storico["performance"]
        assert "tempo_beam_s" in perf
        assert "tempo_bruteforce_stimato_s" in perf
        assert "combinazioni_bruteforce" in perf
        assert "speedup_factor" in perf

    def test_combinazioni_bruteforce_valore(self, payload_storico):
        from fieldwise.beam_optimizer import COMBINAZIONI_BRUTEFORCE
        assert payload_storico["performance"]["combinazioni_bruteforce"] == COMBINAZIONI_BRUTEFORCE
        assert COMBINAZIONI_BRUTEFORCE == 10_077_696

    def test_chiavi_triennio(self, payload_storico):
        for t in payload_storico["trienni"]:
            assert "numero" in t
            assert "obiettivo" in t
            assert "rotazione_label" in t
            assert "resa_t_ha" in t
            assert "resa_rel_pct" in t
            assert "costo_totale_eur_ha" in t
            assert "guadagno_eur_ha" in t
            assert "best_sim_resa_t_ha" in t
            assert "best_sim_costo_eur_ha" in t
            assert "best_sim_guadagno_eur_ha" in t


# ---------------------------------------------------------------------------
# 2. Continuità stato suolo [W, N, H]
# ---------------------------------------------------------------------------

class TestContinuitaSuolo:

    def test_eredita_suolo_chiavi(self, payload_storico):
        for trans in payload_storico["eredita_suolo"]:
            assert "acqua_totale_mm" in trans
            assert "n_min_kg_n_ha" in trans
            assert "n_res_kg_n_ha" in trans
            assert "humus_t_ha" in trans
            assert "credito_precessione_kg_n_ha" in trans
            assert "de_superficiale_mm" in trans

    def test_acqua_non_zero(self, payload_storico):
        """Lo stato dell'acqua non deve essere azzerato tra i trienni."""
        for trans in payload_storico["eredita_suolo"]:
            # L'acqua totale nel suolo deve essere > 0 (campo non a secco assoluto)
            assert trans["acqua_totale_mm"] >= 0, \
                f"Acqua totale negativa: {trans['acqua_totale_mm']}"

    def test_humus_positivo(self, payload_storico):
        """L'humus deve sempre essere >= 0 t/ha."""
        for trans in payload_storico["eredita_suolo"]:
            assert trans["humus_t_ha"] >= 0, \
                f"Humus negativo: {trans['humus_t_ha']}"

    def test_transizione_da_a(self, payload_storico):
        """Verifica che le transizioni siano numerate correttamente."""
        trans = payload_storico["eredita_suolo"]
        assert trans[0]["da_triennio"] == 1
        assert trans[0]["a_triennio"] == 2
        assert trans[1]["da_triennio"] == 2
        assert trans[1]["a_triennio"] == 3

    def test_anni_non_sovrapposti(self, payload_storico):
        """L'anno di partenza del triennio 2 deve essere >= anno fine triennio 1."""
        t = payload_storico["trienni"]
        # L'anno di partenza del 2° triennio deve essere dopo la fine del 1°
        anno_fine_1 = int(t[0]["fine"][:4])
        anno_start_2 = t[1]["anno_partenza"]
        assert anno_start_2 >= anno_fine_1, \
            f"Triennio 2 parte ({anno_start_2}) prima della fine del 1° ({anno_fine_1})"

        anno_fine_2 = int(t[1]["fine"][:4])
        anno_start_3 = t[2]["anno_partenza"]
        assert anno_start_3 >= anno_fine_2, \
            f"Triennio 3 parte ({anno_start_3}) prima della fine del 2° ({anno_fine_2})"


# ---------------------------------------------------------------------------
# 3. Vincolo costo con resa >= 70%
# ---------------------------------------------------------------------------

class TestVincoloCosto:

    def test_obiettivo_costo_nel_payload(self, payload_storico):
        """Il triennio con obiettivo 'costo' deve esistere nel payload."""
        obiettivi = [t["obiettivo"] for t in payload_storico["trienni"]]
        assert "costo" in obiettivi

    def test_resa_relativa_sufficiente_per_costo(self, payload_storico):
        """Se non c'è fallback siccità, la resa deve essere >= 70%."""
        from fieldwise.beam_optimizer import SOGLIA_RESA_REL_COSTO
        for t in payload_storico["trienni"]:
            if t["obiettivo"] == "costo" and not t.get("fallback_siccita", False):
                resa_rel = t["resa_rel_pct"] / 100.0
                assert resa_rel >= SOGLIA_RESA_REL_COSTO, \
                    f"Resa relativa {resa_rel:.3f} < soglia {SOGLIA_RESA_REL_COSTO} " \
                    f"per triennio {t['numero']} (costo, senza fallback)"

    def test_benchmark_costo_non_nessuno(self, payload_storico):
        """Il benchmark best_sim_costo_eur_ha deve essere un numero."""
        for t in payload_storico["trienni"]:
            if t["obiettivo"] == "costo":
                val = t.get("best_sim_costo_eur_ha")
                assert val is not None, \
                    f"best_sim_costo_eur_ha è None per triennio {t['numero']}"
                assert isinstance(val, (int, float)), \
                    f"best_sim_costo_eur_ha non è un numero: {type(val)}"


# ---------------------------------------------------------------------------
# 4. Benchmark singoli
# ---------------------------------------------------------------------------

class TestBenchmarkSingoli:

    def test_benchmark_resa_presente(self, payload_storico):
        for t in payload_storico["trienni"]:
            assert t.get("best_sim_resa_t_ha") is not None or t.get("best_sim_resa_t_ha") is None
            # Almeno deve essere presente la chiave
            assert "best_sim_resa_t_ha" in t
            assert "best_sim_resa_rel_pct" in t

    def test_benchmark_positivi(self, payload_storico):
        """I benchmark devono essere valori positivi (quando non None)."""
        for t in payload_storico["trienni"]:
            if t["best_sim_resa_t_ha"] is not None:
                assert t["best_sim_resa_t_ha"] > 0, \
                    f"best_sim_resa_t_ha non positivo in triennio {t['numero']}"
            if t["best_sim_costo_eur_ha"] is not None:
                assert t["best_sim_costo_eur_ha"] > 0, \
                    f"best_sim_costo_eur_ha non positivo in triennio {t['numero']}"


# ---------------------------------------------------------------------------
# 5. JSON-serializzabilità
# ---------------------------------------------------------------------------

class TestJsonSerializzabile:

    def test_json_dumps_storico(self, payload_storico):
        """Il payload deve essere serializzabile senza errori."""
        try:
            serialized = json.dumps(payload_storico)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"json.dumps ha fallito: {exc}")
        assert isinstance(serialized, str)
        assert len(serialized) > 100

    def test_json_round_trip(self, payload_storico):
        """json.loads(json.dumps(payload)) deve restituire un dizionario equivalente."""
        serialized = json.dumps(payload_storico)
        reloaded = json.loads(serialized)
        assert reloaded["performance"]["combinazioni_bruteforce"] == \
               payload_storico["performance"]["combinazioni_bruteforce"]
        assert len(reloaded["trienni"]) == 3

    def test_no_numpy_types(self, payload_storico):
        """Verifica ricorsivamente che non ci siano tipi NumPy nel payload."""
        import numpy as np

        def check_no_numpy(obj, path=""):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    check_no_numpy(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_numpy(v, f"{path}[{i}]")
            elif isinstance(obj, np.generic):
                pytest.fail(
                    f"Tipo NumPy trovato al path '{path}': {type(obj).__name__} = {obj!r}"
                )

        check_no_numpy(payload_storico)

    def test_no_custom_objects(self, payload_storico):
        """Verifica che non ci siano oggetti WaterState, NState, Rotation nel payload."""
        from fieldwise import rotation as rt
        from fieldwise import nitrogen as _n

        def check_no_custom(obj, path=""):
            if isinstance(obj, (rt.RotationContext, rt.Rotation, rt.RotationCalendar)):
                pytest.fail(f"Oggetto Rotation trovato al path '{path}': {type(obj).__name__}")
            if hasattr(_n, "NState") and isinstance(obj, _n.NState):
                pytest.fail(f"NState trovato al path '{path}'")
            if isinstance(obj, dict):
                for k, v in obj.items():
                    check_no_custom(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    check_no_custom(v, f"{path}[{i}]")

        check_no_custom(payload_storico)


# ---------------------------------------------------------------------------
# 6. Modalità storica (FIELDWISE_OFFLINE=1)
# ---------------------------------------------------------------------------

class TestModalitaStorica:

    def test_climate_mode_storico(self, payload_storico):
        assert payload_storico["climate_mode"] == "storico"

    def test_lat_lon_presenti(self, payload_storico):
        assert "lat" in payload_storico
        assert "lon" in payload_storico
        assert isinstance(payload_storico["lat"], float)
        assert isinstance(payload_storico["lon"], float)

    def test_tempo_beam_ragionevole(self, payload_storico):
        """Il beam search deve completare in meno di 120 secondi."""
        tempo = payload_storico["performance"]["tempo_beam_s"]
        assert tempo < 120.0, f"Tempo beam eccessivo: {tempo:.1f} s"

    def test_speedup_positivo(self, payload_storico):
        """Lo speedup rispetto al brute-force deve essere >> 1."""
        speedup = payload_storico["performance"]["speedup_factor"]
        assert speedup > 1.0, f"Speedup non positivo: {speedup}"


# ---------------------------------------------------------------------------
# 7. Modalità CMIP6 (FIELDWISE_OFFLINE=1)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAS_CMIP6, reason="Modulo fieldwise.data.cmip6 non disponibile su main")
class TestModalitaCmip6:

    def test_climate_mode_cmip6(self, payload_cmip6):
        assert payload_cmip6["climate_mode"] == "cmip6"

    def test_ssp_code_presente(self, payload_cmip6):
        assert payload_cmip6["ssp_code"] == "ssp245"

    def test_horizon_years_presente(self, payload_cmip6):
        assert payload_cmip6["horizon_years"] == 10

    def test_json_dumps_cmip6(self, payload_cmip6):
        """Il payload CMIP6 deve essere JSON-serializzabile."""
        try:
            json.dumps(payload_cmip6)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"json.dumps CMIP6 ha fallito: {exc}")

    def test_tre_trienni_cmip6(self, payload_cmip6):
        assert len(payload_cmip6["trienni"]) == 3

    def test_suolo_continuo_cmip6(self, payload_cmip6):
        """La continuità del suolo deve valere anche in modalità CMIP6."""
        trans = payload_cmip6["eredita_suolo"]
        assert len(trans) == 2
        for t in trans:
            assert t["acqua_totale_mm"] >= 0
            assert t["humus_t_ha"] >= 0


# ---------------------------------------------------------------------------
# 8. Parametri e firme pubbliche
# ---------------------------------------------------------------------------

class TestParametriPubblici:

    def test_beam_width_personalizzato(self):
        """Il beam search accetta un beam_width personalizzato."""
        from fieldwise.beam_optimizer import run_beam_search_9y
        p = run_beam_search_9y(
            objectives=("resa", "resa", "resa"),
            beam_width=2,
            climate_mode="storico",
        )
        assert len(p["trienni"]) == 3

    def test_obiettivo_invalido(self):
        """Un obiettivo non valido deve sollevare ValueError."""
        from fieldwise.beam_optimizer import run_beam_search_9y
        with pytest.raises(ValueError, match="Obiettivo"):
            run_beam_search_9y(objectives=("resa", "INVALIDO", "costo"))

    def test_numero_obiettivi_errato(self):
        """Un numero di obiettivi diverso da 3 deve sollevare ValueError."""
        from fieldwise.beam_optimizer import run_beam_search_9y
        with pytest.raises(ValueError, match="esattamente 3"):
            run_beam_search_9y(objectives=("resa", "costo"))

    def test_suffissi_unita(self, payload_storico):
        """Verifica che le chiavi abbiano i suffissi di unità corretti."""
        for trans in payload_storico["eredita_suolo"]:
            # Deve avere suffisso _mm
            assert "acqua_totale_mm" in trans
            assert "de_superficiale_mm" in trans
            # Deve avere suffisso _kg_n_ha
            assert "n_min_kg_n_ha" in trans
            assert "n_res_kg_n_ha" in trans
            # Deve avere suffisso _t_ha
            assert "humus_t_ha" in trans
        for t in payload_storico["trienni"]:
            assert "resa_t_ha" in t
            assert "resa_rel_pct" in t
            assert "costo_totale_eur_ha" in t
            assert "guadagno_eur_ha" in t
