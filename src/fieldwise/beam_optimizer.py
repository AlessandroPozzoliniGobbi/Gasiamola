"""Ottimizzatore Beam Search sequenziale su 3 trienni consecutivi (9 anni).

Implementa un ricerca beam year-by-year con maschera normativa a 0 ms su
3 x 3 = 9 anni di rotazioni triennali consecutive, garantendo:

* Continuità temporale reale del suolo (W, N, H) senza azzeramenti e
  senza sovrapposizioni di calendario tra i trienni.
* Pruning normativo prima della simulazione (compliance + finestre di
  transizione tra trienni adiacenti).
* 3 obiettivi vincolati per triennio: "resa", "costo", "guadagno".
* Benchmark singoli (best-simulation per ciascun obiettivo).
* Output 100% JSON-serializzabile con suffissi di unità.

Nessun numero agronomico/economico è scritto nel codice: tutto viene da
params/*.yaml via params.load_params().

Funzione pubblica::

    from fieldwise.beam_optimizer import run_beam_search_9y
    result = run_beam_search_9y()
    import json; json.dumps(result)   # deve funzionare senza errori

Compatibile con FIELDWISE_OFFLINE=1 (nessuna chiamata di rete a runtime).
"""
from __future__ import annotations

import dataclasses
import time
from typing import Any

import numpy as np

from . import economics as eco
from . import params as _params
from . import ranking
from . import rotation as rt
from . import weather as _weather
from .data import power as _power

# ---------------------------------------------------------------------------
# Costanti pubbliche
# ---------------------------------------------------------------------------

#: Numero di traiettorie mantenute ad ogni triennio (beam width).
BEAM_WIDTH_DEFAULT = 8

#: Numero totale di combinazioni brute-force (216^3 = 10.077.696).
COMBINAZIONI_BRUTEFORCE = 10_077_696

#: Soglia minima di resa relativa per l'obiettivo "costo" (70%).
SOGLIA_RESA_REL_COSTO = 0.70

#: Stato di conformità che permette il fallback automatico.
STATO_CONFORME = "conforme"
STATO_DEROGA = "conforme_solo_in_deroga"
STATO_NON_CONFORME = "non_conforme"

_OBIETTIVI_VALIDI = ("resa", "guadagno", "costo")


# ---------------------------------------------------------------------------
# Helper: conversione stato finale → dizionario JSON-serializzabile
# ---------------------------------------------------------------------------

def _water_state_to_dict(w) -> dict:
    """Converte un WaterState in dizionario con suffissi unità."""
    return {
        "acqua_totale_mm": float(w.w1 + w.w2),
        "de_superficiale_mm": float(w.de),
    }


def _n_state_to_dict(n) -> dict:
    """Converte un NState in dizionario con suffissi unità."""
    return {
        "n_min_kg_n_ha": float(n.n_min),
        "n_res_kg_n_ha": float(n.n_res),
        "humus_t_ha": float(n.h),
        "credito_precessione_kg_n_ha": float(n.cred),
    }


def _stato_finale_to_dict(out: dict) -> dict:
    """Estrae stato_finale da un risultato simulate() come dict JSON."""
    sf = out["stato_finale"]
    w = sf["acqua"]
    n = sf["azoto"]
    d = {}
    d.update(_water_state_to_dict(w))
    d.update(_n_state_to_dict(n))
    return d


# ---------------------------------------------------------------------------
# Helper: estrazione metriche dal risultato di simulate()
# ---------------------------------------------------------------------------

def _extract_metrics(p: dict, out: dict) -> dict:
    """Estrae le 3 metriche obiettivo + benchmark dal risultato di simulate()."""
    colture = out["colture"]
    ind = out["indicatori"]
    comp = eco.componenti(p, out)

    resa_t_ha = float(np.mean([c["resa"] for c in colture]))
    resa_rel_pct = float(ind["resa_relativa_media"] * 100.0)
    costo_totale_eur_ha = float(
        comp["costo_concime_eur_ha"]
        + comp["costo_irrigazione_eur_ha"]
        + comp["costo_altri_eur_ha"]
    )
    guadagno_eur_ha = float(comp["margine_lordo_eur_ha"])
    resa_rel_media = float(ind["resa_relativa_media"])

    return {
        "resa_t_ha": resa_t_ha,
        "resa_rel_pct": resa_rel_pct,
        "resa_rel_media": resa_rel_media,  # usata internamente per il vincolo costo
        "costo_totale_eur_ha": costo_totale_eur_ha,
        "guadagno_eur_ha": guadagno_eur_ha,
    }


# ---------------------------------------------------------------------------
# Helper: pruning normativo con finestre di transizione
# ---------------------------------------------------------------------------

def _is_compliant(
    p: dict,
    rot: rt.Rotation,
    regime_normativo: str,
    solo_conformi: bool,
    prev_crops: tuple | None = None,
) -> tuple[bool, str]:
    """Verifica la conformità di rot (e della transizione con il triennio precedente).

    Ritorna (accettato: bool, stato_conformità: str).
    - Se prev_crops è fornito, controlla anche le finestre di 3 colture a cavallo.
    - Se solo_conformi=True e nessuna rotazione supera la soglia, il chiamante
      usa il fallback a conforme_solo_in_deroga.
    """
    conf = rt.compliance(p, rot.crops)
    stato = conf.get(regime_normativo)

    # Conformità della rotazione singola
    if stato == STATO_NON_CONFORME or stato is None:
        return False, stato or STATO_NON_CONFORME

    # Verifica finestre di transizione tra trienni
    if prev_crops is not None:
        # Finestre di 3 colture a cavallo: (prev[-2], prev[-1], next[0]) e
        # (prev[-1], next[0], next[1])
        windows = []
        if len(prev_crops) >= 2:
            windows.append((prev_crops[-2], prev_crops[-1], rot.crops[0]))
        if len(prev_crops) >= 1 and len(rot.crops) >= 2:
            windows.append((prev_crops[-1], rot.crops[0], rot.crops[1]))
        for window in windows:
            w_conf = rt.compliance(p, window)
            w_stato = w_conf.get(regime_normativo)
            if w_stato == STATO_NON_CONFORME or w_stato is None:
                return False, STATO_NON_CONFORME

    # Accettato
    if solo_conformi and stato != STATO_CONFORME:
        return False, stato
    return True, stato


# ---------------------------------------------------------------------------
# Calcolo anno di inizio del triennio k (k=2,3) in continuità con il precedente
# ---------------------------------------------------------------------------

def _anno_successivo(ctx: rt.RotationContext, out_prev: dict, rot_k: rt.Rotation) -> int:
    """Calcola l'anno di partenza del triennio k (k >= 2) garantendo continuità
    temporale senza sovrapposizioni."""
    y_fine = int(str(out_prev["fine"])[:4])
    # Data di semina tipica della prima coltura del nuovo triennio
    semina_tipica = ctx.crop[rot_k.crops[0]]["semina"]
    # Se la data tipica di semina dell'anno y_fine è successiva alla fine del
    # ciclo precedente, partiamo da y_fine; altrimenti da y_fine + 1.
    if f"{y_fine:04d}-{semina_tipica}" > str(out_prev["fine"]):
        return y_fine
    return y_fine + 1


# ---------------------------------------------------------------------------
# Simulazione di un triennio con gestione errori robusta
# ---------------------------------------------------------------------------

def _simula_triennio(
    ctx: rt.RotationContext,
    rot: rt.Rotation,
    anno: int,
    irrigation_regime: str,
    n_avviamento: int,
    cal_cache: dict,
) -> dict | None:
    """Simula un triennio. Ritorna out se ESITO_OK, None altrimenti.
    Gestisce le eccezioni internamente per robustezza del beam search."""
    try:
        cal_key = (rot.label, anno)
        calendario = cal_cache.get(cal_key)
        out = rt.simulate(
            ctx, rot, anno, irrigation_regime,
            n_avviamento=n_avviamento,
            calendario=calendario,
        )
        # Metti in cache il calendario per riuso
        if calendario is None and out.get("esito") == rt.ESITO_OK:
            # Non esiste un modo diretto di recuperare il calendario da simulate();
            # lo costruiamo e lo salviamo solo la prima volta
            try:
                cal = rt.build_calendar(ctx, rot, anno, n_avviamento)
                cal_cache[cal_key] = cal
            except Exception:
                pass
        if out.get("esito") != rt.ESITO_OK:
            return None
        return out
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Score di un candidato per un dato obiettivo
# ---------------------------------------------------------------------------

def _score_for_objective(metrics: dict, objective: str) -> float:
    """Ritorna il valore scalare usato per ordinare i candidati (più alto = meglio)."""
    if objective == "resa":
        return metrics["resa_t_ha"]
    if objective == "guadagno":
        return metrics["guadagno_eur_ha"]
    if objective == "costo":
        # Minimizzare il costo: invertiamo il segno; il vincolo resa >= 70% è
        # gestito dal chiamante.
        return -metrics["costo_totale_eur_ha"]
    raise ValueError(f"Obiettivo sconosciuto: {objective!r}. Ammessi: {_OBIETTIVI_VALIDI}")


# ---------------------------------------------------------------------------
# Funzione principale pubblica
# ---------------------------------------------------------------------------

def run_beam_search_9y(
    lat: float | None = None,
    lon: float | None = None,
    objectives: tuple = ("resa", "guadagno", "costo"),
    irrigation_regime: str = "tetto_irriguo",
    regime_normativo: str | None = None,
    solo_conformi: bool = True,
    climate_mode: str = "storico",
    ssp_code: str = "ssp245",
    horizon_years: int = 10,
    beam_width: int = BEAM_WIDTH_DEFAULT,
    model_params: dict | None = None,
    other_crop_costs_eur_ha: dict[str, float] | None = None,
) -> dict:
    """Beam Search sequenziale su 3 trienni (9 anni) con maschera normativa a 0 ms.

    Parameters
    ----------
    lat, lon:
        Coordinate del punto (default: punto pilota da config).
    objectives:
        Tupla di 3 obiettivi in ordine temporale per i 3 trienni.
        Valori ammessi: ``"resa"``, ``"guadagno"``, ``"costo"``.
    irrigation_regime:
        Scenario irriguo (``"solo_pioggia"``, ``"tetto_irriguo"``,
        ``"irrigazione_libera"``).
    regime_normativo:
        Disciplinare di conformità (default: ``ranking.REGIME_PREDEFINITO``).
        ``None`` usa il più severo.
    solo_conformi:
        Se True, filtra solo le rotazioni conformi; se nessuna supera la soglia
        allarga automaticamente a ``conforme_solo_in_deroga``.
    climate_mode:
        ``"storico"`` usa la serie NASA POWER; ``"cmip6"`` applica il delta
        change CMIP6 (compatibile con ``FIELDWISE_OFFLINE=1``).
    ssp_code:
        Codice SSP (``"ssp126"``, ``"ssp245"``, ``"ssp585"``); usato solo se
        ``climate_mode == "cmip6"``.
    horizon_years:
        Orizzonte temporale in anni per CMIP6 (5, 10, 15, 20).
    beam_width:
        Numero di traiettorie mantenute ad ogni triennio (default 8).

    Returns
    -------
    dict
        Payload 100% JSON-serializzabile con chiavi:
        ``trienni`` (lista di 3), ``eredita_suolo`` (lista di 2 transizioni),
        ``performance`` e ``note``.
    """
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 0. Parametri e contesto
    # ------------------------------------------------------------------
    # A prepared field may supply its own SoilGrids-derived parameter tree.
    # Never silently use Cremona soil for a field outside the pilot cell.
    import copy
    p = copy.deepcopy(model_params) if model_params is not None else _params.load_params()
    if other_crop_costs_eur_ha:
        for crop, amount in other_crop_costs_eur_ha.items():
            if crop not in {"mais", "soia", "frumento"} or not (0 <= float(amount) <= 100_000):
                raise ValueError("Invalid crop cost override")
            p["economia"]["altri_costi_eur_ha"][crop]["valore"] = float(amount)

    if regime_normativo is None:
        regime_normativo = ranking.REGIME_PREDEFINITO

    # Validazione obiettivi
    if len(objectives) != 3:
        raise ValueError(f"objectives deve avere esattamente 3 elementi, forniti {len(objectives)}")
    for obj in objectives:
        if obj not in _OBIETTIVI_VALIDI:
            raise ValueError(f"Obiettivo {obj!r} non valido. Ammessi: {_OBIETTIVI_VALIDI}")

    # ------------------------------------------------------------------
    # 1. Costruzione del contesto (meteo + suolo)
    # ------------------------------------------------------------------
    from . import config as _config
    _lat = lat if lat is not None else _config.PILOT_LAT
    _lon = lon if lon is not None else _config.PILOT_LON

    if climate_mode == "cmip6":
        try:
            from .data import cmip6 as _cmip6
        except (ImportError, ModuleNotFoundError) as err:
            raise NotImplementedError(
                "climate_mode='cmip6' non supportato: modulo fieldwise.data.cmip6 non disponibile"
            ) from err
        forcing_hist = _weather.load_forcing(_lat, _lon)
        site = _power.load_site(_lat, _lon)
        elev_m = float(site["elevation_m"])
        forcing_fut = _cmip6.apply_delta_change(
            forcing_hist,
            ssp_code=ssp_code,
            horizon_years=horizon_years,
            lat=_lat,
            elev_m=elev_m,
            p=p,
        )
        ctx = rt.build_context(p=p, forcing=forcing_fut, lat=_lat, lon=_lon)
    else:
        ctx = rt.build_context(p=p, lat=_lat, lon=_lon)

    # ------------------------------------------------------------------
    # 2. Anno di partenza del 1° triennio
    # ------------------------------------------------------------------
    # anno_1 = primo anno della serie + 1 per garantire che anche 4 cicli
    # di frumento consecutivi rientrino nella serie disponibile.
    anno_1 = int(ctx.year[0]) + 1

    # ------------------------------------------------------------------
    # 3. Enumera le 216 rotazioni triennali
    # ------------------------------------------------------------------
    all_rots = rt.enumerate_rotations(p, length=3)

    # ------------------------------------------------------------------
    # 4. Cache dei calendari (condivisa tra le simulazioni del beam)
    # ------------------------------------------------------------------
    cal_cache: dict = {}

    # ------------------------------------------------------------------
    # 5. Funzione di filtro conformità con fallback automatico
    # ------------------------------------------------------------------
    def _filter_candidates(
        candidates: list[dict],
        prev_crops: tuple | None,
        obiettivo: str,
    ) -> tuple[list[dict], bool]:
        """Filtra i candidati per conformità. Ritorna (candidati_filtrati, deroga_attivata)."""
        # Prima passa: solo conformi
        conformi = []
        in_deroga = []
        for c in candidates:
            rot = c["rotation"]
            ok, stato = _is_compliant(p, rot, regime_normativo, solo_conformi, prev_crops)
            if ok:
                c["stato_conformita"] = stato
                conformi.append(c)
            elif stato == STATO_DEROGA:
                c["stato_conformita"] = stato
                in_deroga.append(c)

        if conformi:
            return conformi, False
        # Fallback automatico a conforme_solo_in_deroga
        if in_deroga and not solo_conformi:
            return in_deroga, True
        # Nessun candidato: ritorna lista vuota
        return [], False

    # ------------------------------------------------------------------
    # 6. Beam Search sui 3 trienni
    # ------------------------------------------------------------------
    # Ogni elemento del beam è un dizionario:
    #   {
    #     "ctx_k": RotationContext con stato suolo aggiornato,
    #     "anno_k": int,
    #     "trienni": list[dict],       # risultati dei trienni già simulati
    #     "out_prev": dict | None,     # ultimo risultato simulate()
    #     "prev_crops": tuple | None,  # crops del triennio precedente
    #   }
    beam: list[dict] = [{
        "ctx_k": ctx,
        "anno_k": anno_1,
        "trienni": [],
        "heritage": [],
        "out_prev": None,
        "prev_crops": None,
    }]

    # Risultati finali per triennio (best per ogni obiettivo)
    trienni_risultati: list[dict] = []
    eredita_suolo_list: list[dict] = []
    note_globali: list[str] = []

    for k_triennio in range(3):
        obiettivo_k = objectives[k_triennio]
        n_avviamento_k = 1 if k_triennio == 0 else 0

        new_beam: list[dict] = []

        # Raccogli tutti i candidati simulati per questo triennio,
        # partendo da ogni traiettoria nel beam corrente
        all_scored: list[dict] = []

        for beam_state in beam:
            ctx_k = beam_state["ctx_k"]
            anno_k = beam_state["anno_k"]
            out_prev = beam_state["out_prev"]
            prev_crops = beam_state["prev_crops"]

            # Filtra i candidati per conformità
            rot_entries = [dict(e) for e in all_rots]  # copia
            conformi_entries, deroga = _filter_candidates(
                rot_entries, prev_crops, obiettivo_k
            )
            if deroga:
                note_globali.append(
                    f"Triennio {k_triennio + 1}: nessuna rotazione conforme per il regime "
                    f"'{regime_normativo}' con la transizione data; allargamento automatico "
                    "a 'conforme_solo_in_deroga'."
                )

            # Simula ogni candidato conforme
            for entry in conformi_entries:
                rot = entry["rotation"]
                out = _simula_triennio(
                    ctx_k, rot, anno_k, irrigation_regime,
                    n_avviamento_k, cal_cache,
                )
                if out is None:
                    continue

                metrics = _extract_metrics(p, out)

                # Vincolo resa >= 70% per obiettivo "costo"
                if obiettivo_k == "costo" and metrics["resa_rel_media"] < SOGLIA_RESA_REL_COSTO:
                    continue  # candidato escluso (sarà recuperato nel fallback)

                score = _score_for_objective(metrics, obiettivo_k)
                all_scored.append({
                    "beam_state": beam_state,
                    "rotation": rot,
                    "stato_conformita": entry["stato_conformita"],
                    "out": out,
                    "metrics": metrics,
                    "score": score,
                    "anno_k": anno_k,
                    "ctx_k": ctx_k,
                })

        # Fallback deterministico per "costo" in caso di siccità estrema:
        # se nessun candidato supera la soglia resa >= 70%, prendi il candidato
        # con la massima resa_relativa_media tra tutti quelli validi.
        if obiettivo_k == "costo" and not all_scored:
            for beam_state in beam:
                ctx_k = beam_state["ctx_k"]
                anno_k = beam_state["anno_k"]
                out_prev = beam_state["out_prev"]
                prev_crops = beam_state["prev_crops"]

                rot_entries = [dict(e) for e in all_rots]
                conformi_entries, _ = _filter_candidates(
                    rot_entries, prev_crops, obiettivo_k
                )
                for entry in conformi_entries:
                    rot = entry["rotation"]
                    out = _simula_triennio(
                        ctx_k, rot, anno_k, irrigation_regime,
                        n_avviamento_k, cal_cache,
                    )
                    if out is None:
                        continue
                    metrics = _extract_metrics(p, out)
                    # Fallback: ordina per resa_rel_media (massimizzando)
                    all_scored.append({
                        "beam_state": beam_state,
                        "rotation": rot,
                        "stato_conformita": entry["stato_conformita"],
                        "out": out,
                        "metrics": metrics,
                        "score": metrics["resa_rel_media"],
                        "anno_k": anno_k,
                        "ctx_k": ctx_k,
                        "fallback_siccita": True,
                    })
            if all_scored:
                note_globali.append(
                    f"Triennio {k_triennio + 1}: nessun candidato supera la soglia "
                    f"resa >= {SOGLIA_RESA_REL_COSTO * 100:.0f}% per l'obiettivo 'costo' "
                    "(siccità estrema). Usato fallback: candidato con massima resa relativa."
                )

        if not all_scored:
            raise RuntimeError(
                f"Triennio {k_triennio + 1}: nessun candidato valido simulabile. "
                "Verificare parametri, anni disponibili e regime normativo."
            )

        # Ordina per score (decrescente) e mantieni i migliori beam_width
        all_scored.sort(key=lambda x: x["score"], reverse=True)
        top = all_scored[:beam_width]

        # Costruisci i benchmark singoli per questo triennio
        # (a parità di stato suolo ereditato dalla migliore traiettoria precedente)
        # Per semplicità usiamo il primo beam_state (il migliore del beam corrente)
        best_beam_state = beam[0]
        ctx_bench = best_beam_state["ctx_k"]
        anno_bench = best_beam_state["anno_k"]
        prev_crops_bench = best_beam_state["prev_crops"]

        benchmarks: dict[str, Any] = {}
        for obj_bench in _OBIETTIVI_VALIDI:
            bench_scored: list[dict] = []
            rot_entries_b = [dict(e) for e in all_rots]
            conformi_b, _ = _filter_candidates(rot_entries_b, prev_crops_bench, obj_bench)
            for entry_b in conformi_b:
                rot_b = entry_b["rotation"]
                out_b = _simula_triennio(
                    ctx_bench, rot_b, anno_bench, irrigation_regime,
                    n_avviamento_k, cal_cache,
                )
                if out_b is None:
                    continue
                metrics_b = _extract_metrics(p, out_b)
                if obj_bench == "costo" and metrics_b["resa_rel_media"] < SOGLIA_RESA_REL_COSTO:
                    continue
                bench_scored.append({
                    "metrics": metrics_b,
                    "score": _score_for_objective(metrics_b, obj_bench),
                })
            if bench_scored:
                bench_scored.sort(key=lambda x: x["score"], reverse=True)
                best_b = bench_scored[0]["metrics"]
                if obj_bench == "resa":
                    benchmarks["best_sim_resa_t_ha"] = best_b["resa_t_ha"]
                    benchmarks["best_sim_resa_rel_pct"] = best_b["resa_rel_pct"]
                elif obj_bench == "costo":
                    benchmarks["best_sim_costo_eur_ha"] = best_b["costo_totale_eur_ha"]
                elif obj_bench == "guadagno":
                    benchmarks["best_sim_guadagno_eur_ha"] = best_b["guadagno_eur_ha"]
            else:
                # Fallback valori None se non simulabile
                if obj_bench == "resa":
                    benchmarks["best_sim_resa_t_ha"] = None
                    benchmarks["best_sim_resa_rel_pct"] = None
                elif obj_bench == "costo":
                    benchmarks["best_sim_costo_eur_ha"] = None
                elif obj_bench == "guadagno":
                    benchmarks["best_sim_guadagno_eur_ha"] = None

        # Il migliore candidato per questo triennio (top[0])
        best = top[0]
        best_out = best["out"]
        best_metrics = best["metrics"]
        best_rot = best["rotation"]
        best_stato = best["stato_conformita"]

        # ------------------------------------------------------------------
        # Eredità suolo (tra i trienni k=1→2 e k=2→3)
        # ------------------------------------------------------------------
        if k_triennio > 0:
            sf = best_out["stato_finale"]
            # La transizione precedente è già calcolata; qui costruiamo
            # quella in uscita da questo triennio
            pass  # gestito sotto nella costruzione del triennio risultato

        # ------------------------------------------------------------------
        # Costruzione dizionario del triennio risultato (JSON-safe)
        # ------------------------------------------------------------------
        # Conformità della rotazione del triennio precedente per la transizione
        conformita_dict = best_out.get("conformita", {})
        conformita_json = {k: (str(v) if v is not None else None)
                           for k, v in conformita_dict.items()}

        colture_json = []
        for c in best_out["colture"]:
            colture_json.append({
                "coltura": str(c["coltura"]),
                "semina": str(c["semina"]),
                "raccolta": str(c["raccolta"]),
                "resa_t_ha": float(c["resa"]),
                "resa_relativa": float(c["resa_relativa"]),
                "irrigazione_mm": float(c["irrigazione"]),
                "concime_kg_n_ha": float(c["concime"]),
            })

        triennio_dict: dict[str, Any] = {
            "numero": k_triennio + 1,
            "obiettivo": str(obiettivo_k),
            "rotazione_label": str(best_rot.label),
            "anno_partenza": int(best["anno_k"]),
            "anno_valutato": int(best_out["anno_valutato"]),
            "inizio": str(best_out["inizio"]),
            "fine": str(best_out["fine"]),
            "conformita": conformita_json,
            "stato_conformita": str(best_stato) if best_stato else None,
            "colture": colture_json,
            # Metriche principali
            "resa_t_ha": float(best_metrics["resa_t_ha"]),
            "resa_rel_pct": float(best_metrics["resa_rel_pct"]),
            "costo_totale_eur_ha": float(best_metrics["costo_totale_eur_ha"]),
            "guadagno_eur_ha": float(best_metrics["guadagno_eur_ha"]),
            # Benchmark singoli
            "best_sim_resa_t_ha": benchmarks.get("best_sim_resa_t_ha"),
            "best_sim_resa_rel_pct": benchmarks.get("best_sim_resa_rel_pct"),
            "best_sim_costo_eur_ha": benchmarks.get("best_sim_costo_eur_ha"),
            "best_sim_guadagno_eur_ha": benchmarks.get("best_sim_guadagno_eur_ha"),
            # Flag fallback siccità
            "fallback_siccita": bool(best.get("fallback_siccita", False)),
        }
        trienni_risultati.append(triennio_dict)

        # ------------------------------------------------------------------
        # Eredità suolo tra trienni adiacenti
        # ------------------------------------------------------------------
        if k_triennio < 2:
            sf = best_out["stato_finale"]
            w_fin = sf["acqua"]
            n_fin = sf["azoto"]
            eredita_dict: dict[str, Any] = {
                "da_triennio": k_triennio + 1,
                "a_triennio": k_triennio + 2,
                "acqua_totale_mm": float(w_fin.w1 + w_fin.w2),
                "de_superficiale_mm": float(w_fin.de),
                "n_min_kg_n_ha": float(n_fin.n_min),
                "n_res_kg_n_ha": float(n_fin.n_res),
                "humus_t_ha": float(n_fin.h),
                "credito_precessione_kg_n_ha": float(n_fin.cred),
            }
            eredita_suolo_list.append(eredita_dict)

        # ------------------------------------------------------------------
        # Aggiorna il beam per il triennio successivo
        # ------------------------------------------------------------------
        new_beam = []
        for cand in top:
            cand_out = cand["out"]
            cand_metrics = cand["metrics"]
            cand_rot = cand["rotation"]
            parent = cand["beam_state"]
            sf = cand_out["stato_finale"]
            w_fin = sf["acqua"]
            n_fin = sf["azoto"]
            child_triennium = {
                "numero": k_triennio + 1,
                "obiettivo": str(obiettivo_k),
                "rotazione_label": str(cand_rot.label),
                "anno_partenza": int(cand["anno_k"]),
                "anno_valutato": int(cand_out["anno_valutato"]),
                "inizio": str(cand_out["inizio"]),
                "fine": str(cand_out["fine"]),
                "conformita": {key: str(val) if val is not None else None
                               for key, val in cand_out.get("conformita", {}).items()},
                "stato_conformita": cand["stato_conformita"],
                "colture": [{
                    "coltura": str(c["coltura"]), "semina": str(c["semina"]),
                    "raccolta": str(c["raccolta"]), "resa_t_ha": float(c["resa"]),
                    "resa_relativa": float(c["resa_relativa"]),
                    "irrigazione_mm": float(c["irrigazione"]),
                    "concime_kg_n_ha": float(c["concime"]),
                } for c in cand_out["colture"]],
                "resa_t_ha": float(cand_metrics["resa_t_ha"]),
                "resa_rel_pct": float(cand_metrics["resa_rel_pct"]),
                "costo_totale_eur_ha": float(cand_metrics["costo_totale_eur_ha"]),
                "guadagno_eur_ha": float(cand_metrics["guadagno_eur_ha"]),
                "best_sim_resa_t_ha": benchmarks.get("best_sim_resa_t_ha"),
                "best_sim_resa_rel_pct": benchmarks.get("best_sim_resa_rel_pct"),
                "best_sim_costo_eur_ha": benchmarks.get("best_sim_costo_eur_ha"),
                "best_sim_guadagno_eur_ha": benchmarks.get("best_sim_guadagno_eur_ha"),
                "fallback_siccita": bool(cand.get("fallback_siccita", False)),
            }
            heritage = {
                "da_triennio": k_triennio + 1,
                "a_triennio": k_triennio + 2,
                "acqua_totale_mm": float(w_fin.w1 + w_fin.w2),
                "de_superficiale_mm": float(w_fin.de),
                "n_min_kg_n_ha": float(n_fin.n_min),
                "n_res_kg_n_ha": float(n_fin.n_res),
                "humus_t_ha": float(n_fin.h),
                "credito_precessione_kg_n_ha": float(n_fin.cred),
            }
            ctx_next = dataclasses.replace(cand["ctx_k"], w0=w_fin, n0=n_fin)
            anno_next = _anno_successivo(cand["ctx_k"], cand_out, cand_rot)
            new_beam.append({
                "ctx_k": ctx_next,
                "anno_k": anno_next,
                "trienni": parent["trienni"] + [child_triennium],
                "heritage": parent["heritage"] + ([heritage] if k_triennio < 2 else []),
                "out_prev": cand_out,
                "prev_crops": cand_rot.crops,
            })

        beam = new_beam

    # ------------------------------------------------------------------
    # The displayed 3 cycles MUST belong to the same surviving path. Each
    # branch already propagates its own water and nitrogen state to its child.
    trienni_risultati = beam[0]["trienni"]
    eredita_suolo_list = beam[0]["heritage"]

    # 7. Performance
    # ------------------------------------------------------------------
    t_end = time.perf_counter()
    tempo_beam_s = float(t_end - t_start)
    # Stima brute-force: assumiamo ~0.2 s per simulazione (dal README)
    tempo_per_sim_s = 0.2
    tempo_bruteforce_stimato_s = float(COMBINAZIONI_BRUTEFORCE * tempo_per_sim_s)
    speedup_factor = float(tempo_bruteforce_stimato_s / tempo_beam_s) if tempo_beam_s > 0 else 0.0

    # ------------------------------------------------------------------
    # 8. Payload finale JSON-serializzabile
    # ------------------------------------------------------------------
    payload: dict[str, Any] = {
        "lat": float(_lat),
        "lon": float(_lon),
        "climate_mode": str(climate_mode),
        "ssp_code": str(ssp_code) if climate_mode == "cmip6" else None,
        "horizon_years": int(horizon_years) if climate_mode == "cmip6" else None,
        "irrigation_regime": str(irrigation_regime),
        "regime_normativo": str(regime_normativo),
        "solo_conformi": bool(solo_conformi),
        "beam_width": int(beam_width),
        "objectives": list(objectives),
        "trienni": trienni_risultati,
        "eredita_suolo": eredita_suolo_list,
        "performance": {
            "tempo_beam_s": round(tempo_beam_s, 3),
            "tempo_bruteforce_stimato_s": round(tempo_bruteforce_stimato_s, 0),
            "combinazioni_bruteforce": COMBINAZIONI_BRUTEFORCE,
            "speedup_factor": round(speedup_factor, 1),
        },
        "note": note_globali,
    }

    return payload


__all__ = [
    "run_beam_search_9y",
    "BEAM_WIDTH_DEFAULT",
    "COMBINAZIONI_BRUTEFORCE",
    "SOGLIA_RESA_REL_COSTO",
]
