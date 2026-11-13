# Graph Report - nasa  (2026-11-13)

## Corpus Check
- 285 files · ~168,448 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1816 nodes · 3430 edges · 104 communities (82 shown, 22 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 41 edges (avg confidence: 0.84)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `2f8776df`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- run_segment
- test_data_modis.py
- et0.py
- fieldwise_engine.py
- test_data_earthdata.py
- params.py
- test_data_arpa.py
- test_data_istat.py
- test_data_power.py
- test_data_soilgrids.py
- test_params.py
- Fonti di `params/crops.yaml`
- Fonti di `params/nitrogen.yaml`
- FIELDWISE — piano di lavoro
- AGENTS.md
- CLAUDE.md
- SCHEMA.md
- fieldwise
- test_qc.py
- phenology.py
- math
- simulate_rotation
- Dynamic vectors approach F(t), C(t) and its four problems
- hargreaves_et0
- Tabella dei parametri
- Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml
- Soil
- test_soil.py
- ensemble
- test_nitrogen_daily.py
- SoilWaterParams
- get
- crop_daily_curves
- Revisione indipendente dei parametri FIELDWISE
- test_rotation.py
- numpy
- ValueError
- rotation.py
- test_water_dual.py
- test_water.py
- _daily_inputs
- TestSupporto
- test_nitrogen.py
- fw_dati.py
- Verifica scientifica indipendente del motore (fasi 3 e 4)
- nitrogen.py
- test_ranking.py
- test_phenology.py
- test_yield_model.py
- test_humus.py
- .canonical
- water.py
- _make_smap
- fake_net
- _make_imerg_subset
- test_sensitivity.py
- test_validation.py
- validation.py
- _make_imerg_full
- ranking.py
- fixture
- _Auth
- _fake_row
- _granule
- _frame
- test_et0.py
- Verifica indipendente fase 5 (ensemble + classifica)
- parametrize
- fw_confronto.py
- _tutte
- test_semina_del_ciclo_dopo_raccolta_dell_ultima_coltura
- test_stato_ereditato_conta
- test_cover_senza_tempo_suolo_nudo_con_motivo
- test_cover_possibile_e_cover_negata_sono_coerenti
- test_cover_oltre_semina_max_motivo
- test_cover_cambia_il_bilancio_dell_azoto
- test_300_simulazioni_in_meno_di_5_secondi
- ensemble.py
- sensitivity.py
- test_ensemble.py
- fw_util.py
- test_app.py
- Validazione del motore (fase 6)
- test_mais_traspirazione_potenziale_normalizzata_segue_il_kcb
- TestComportamento
- TestEsempio20Lione
- yield_model.py
- CycleCalendar
- heat_factor
- Analisi di sensibilita' (fase 7)
- sowing_index
- TestTabellaPilota
- fw_testi.py
- __init__.py
- streamlit_app.py
- _rischi
- voci_incerte
- fw_dettaglio.py
- score
- _Resp
- config.py
- PhenoParams
- valuta
- _ctx_con

## God Nodes (most connected - your core abstractions)
1. `run()` - 32 edges
2. `by_name()` - 31 edges
3. `run_checks()` - 26 edges
4. `water()` - 26 edges
5. `make_power()` - 25 edges
6. `build_context()` - 24 edges
7. `run_ensemble()` - 22 edges
8. `Rotation` - 21 edges
9. `_a()` - 20 edges
10. `_out()` - 20 edges

## Surprising Connections (you probably didn't know these)
- `test_avvertenza_frumento_solo_con_frumento()` --calls--> `rese_t_ha_testo()`  [INFERRED]
  tests/test_app.py → app/fw_util.py
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `run_segment()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `update_soil()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves)` --implements--> `hargreaves_et0()`  [EXTRACTED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Kc crop coefficient (four phases) and ETc = Kc x ET0` --implements--> `kc_and_roots()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four problems of the dynamic-vectors approach** — legacy_fieldwise_proposta_modello_weighted_score_no_units, legacy_fieldwise_proposta_modello_soil_crop_coupling, legacy_fieldwise_proposta_modello_nonlinear_plant_response, legacy_fieldwise_proposta_modello_dynamic_vectors_problem [EXTRACTED 1.00]
- **Engine nested computation: daily water step, end-of-segment N/humus, rotation chain, ensemble** — legacy_fieldwise_proposta_modello_daily_water_step, legacy_fieldwise_proposta_modello_nitrogen_humus_accounting, legacy_fieldwise_proposta_modello_segment, legacy_fieldwise_proposta_modello_exhaustive_enumeration [EXTRACTED 1.00]
- **FAO water-stress to yield chain (ET0, Kc, TAW/RAW, Ks, Ky)** — legacy_fieldwise_proposta_modello_et0, legacy_fieldwise_proposta_modello_kc_crop_coefficient, legacy_fieldwise_proposta_modello_taw_raw, legacy_fieldwise_proposta_modello_ks_stress, legacy_fieldwise_proposta_modello_ky_yield_response [EXTRACTED 1.00]

## Communities (104 total, 22 thin omitted)

### Community 0 - "run_segment"
Cohesion: 0.17
Nodes (15): kc_and_roots(), Quanto chiede la pianta e fin dove arriva, al giorno d dalla semina. Kc segue…, Fa avanzare l'acqua del suolo dal giorno i0 al giorno i1 (escluso). Un…, run_segment(), Crop parameter table (maize, soybean, wheat), ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves), FAO-33 yield response to water (Doorenbos and Kassam, 1979), FAO-56 crop water use (Allen et al., 1998) (+7 more)

### Community 1 - "test_data_modis.py"
Cohesion: 0.16
Nodes (12): FakeService, fixture, Test del client MODIS: nessuna rete (requests.get sostituito), cartelle…, run_fetch(), test_block_without_meta_is_redownloaded(), test_date_window_filter(), test_fetch_scale_fill_and_files(), test_load_works_offline_after_fetch() (+4 more)

### Community 2 - "et0.py"
Cohesion: 0.08
Nodes (58): _a(), actual_vapour_pressure(), atmospheric_pressure(), clear_sky_radiation(), daylight_hours(), et0_from_power(), et0_hargreaves(), et0_penman_monteith() (+50 more)

### Community 3 - "fieldwise_engine.py"
Cohesion: 0.16
Nodes (13): datetime, itertools, Crop, fetch_power(), load_weather(), FIELDWISE - motore di simulazione delle rotazioni colturali…, Scarica il meteo giornaliero da NASA POWER. Non serve nessun login.…, Meteo FINTO con stagioni tipo Pianura Padana. Serve SOLO a collaudare il codice… (+5 more)

### Community 5 - "params.py"
Cohesion: 0.18
Nodes (23): build_table(), _cell(), _in_sensitivity(), _is_number(), iter_entries(), _join(), main(), _nonempty_str() (+15 more)

### Community 6 - "test_data_arpa.py"
Cohesion: 0.06
Nodes (24): _catalog(), fake_net(), fake_net_both(), fixture, Test del client pioggia ARPA Lombardia, senza rete e senza toccare la cache…, Rete finta per pioggia e temperatura: instrada in base all'URL e ai parametri., _Resp, _row() (+16 more)

### Community 7 - "test_data_istat.py"
Cohesion: 0.11
Nodes (16): clock(), FakeClock, FakeResponse, FakeSession, _limiter(), fixture, Test del client ISTAT: nessuna rete, solo cartelle temporanee., _row() (+8 more)

### Community 8 - "test_data_power.py"
Cohesion: 0.14
Nodes (5): fake_net(), fixture, Test del client NASA POWER, senza rete e senza toccare la cache vera., _Resp, tmp_cache()

### Community 9 - "test_data_soilgrids.py"
Cohesion: 0.09
Nodes (14): fake_wcs_http(), FakeResp, make_tiff(), mapped(), fixture, ndarray, Test del client SoilGrids: nessuna rete, cartelle temporanee, risposte finte., rest_ok() (+6 more)

### Community 10 - "test_params.py"
Cohesion: 0.16
Nodes (23): assumed(), make_tree(), one_error(), Path, Test del caricatore/validatore dei parametri (contratto: params/SCHEMA.md)., sourced(), test_error_reports_dotted_path(), test_interval_rule() (+15 more)

### Community 11 - "Fonti di `params/crops.yaml`"
Cohesion: 0.22
Nodes (8): Aggiornamento 2026-11-12 – doppio coefficiente nel motore, Altro (dichiarato, non ufficiale), Articoli peer-reviewed e atti, Dati usati solo per conversioni e controlli, Enti pubblici italiani, Fonti cercate ma non leggibili, Fonti di `params/crops.yaml`, Manuali FAO

### Community 12 - "Fonti di `params/nitrogen.yaml`"
Cohesion: 0.22
Nodes (8): 1. Regione Emilia-Romagna — Disciplinari di produzione integrata 2023, Norme generali, 2. Regione Lombardia — Programma d'azione nitrati 2024-2027 (zone vulnerabili), 3. Salvagiotti et al. (2008), 4. Mémento Sols et Matières Organiques (Agro-Transfert, 2007), 5. SWAT — documentazione teorica e di input, Aggiornamento 2026-11-12 (correzioni dopo `reports/params_review.md`), Fonti cercate e non usate, Fonti di `params/nitrogen.yaml`

### Community 13 - "FIELDWISE — piano di lavoro"
Cohesion: 0.29
Nodes (6): Blocchi aperti, Decisioni prese, FIELDWISE — piano di lavoro, Principi non negoziabili, Registro, Stato delle fasi

### Community 18 - "test_qc.py"
Cohesion: 0.05
Nodes (117): build_auto_block(), _cell(), Check, check_arpa_completeness(), check_et0(), check_imerg(), check_istat(), check_modis() (+109 more)

### Community 19 - "phenology.py"
Cohesion: 0.17
Nodes (22): calendar_from_cum(), crop_pheno_params(), cumulative_gdd(), cycle_calendar(), cycle_calendars(), daily_gdd(), event_table(), _gdd_series() (+14 more)

### Community 20 - "math"
Cohesion: 0.09
Nodes (31): math, cover_humus(), equilibrium(), grain_moisture(), humus_balance_residual(), humus_params(), HumusParams, initial_humus() (+23 more)

### Community 21 - "simulate_rotation"
Cohesion: 0.16
Nodes (14): next_date(), Aggiorna st["N"] e st["H"] alla fine di un segmento, usando i totali calcolati…, Prima data (mese, giorno) uguale o successiva a 'after'. Esempio: dopo il 20…, Simula una rotazione completa partendo da un certo anno. seq lista di Crop, per…, simulate_rotation(), update_soil(), FIELDWISE - Proposta di modello (document), Bare soil (Kc 0.25, Zr 0.30 m) and cover crop (Kc 0.60, Zr 0.60 m) parameters (+6 more)

### Community 22 - "Dynamic vectors approach F(t), C(t) and its four problems"
Cohesion: 0.25
Nodes (9): Dynamic vectors approach F(t), C(t) and its four problems, Engine code structure (blocks 0-4: params, weather, water, N/humus, rotation, ensemble), Exhaustive enumeration of 216 rotations (3 crops in 3 positions) instead of gradient, Ranking of rotations with farmer-chosen weights, Nonlinear differential equation system solved with 1-day Euler steps, Nonlinear plant response (stress threshold, leaching excess), Physical mass balances of water, nitrogen and organic matter, Soil and crop are coupled (crop consumes soil water) (+1 more)

### Community 23 - "hargreaves_et0"
Cohesion: 0.29
Nodes (5): hargreaves_et0(), Serie meteo giornaliera pronta per il motore. Converte la tabella in array…, Converte una data nella posizione corrispondente negli array., ET0 (mm/giorno) con la formula di Hargreaves, FAO-56 equazione 52. ET0 e'…, Weather

### Community 24 - "Tabella dei parametri"
Cohesion: 0.29
Nodes (6): cover_crop, crops, heat, nitrogen, rotation_rules, Tabella dei parametri

### Community 25 - "Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml"
Cohesion: 0.29
Nodes (6): Aggiornamento 2026-11-12 (correzioni dopo `reports/params_review.md`), Caldo in fioritura, Cover crop, Disciplinari e norme regionali, Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml, Letteratura su rese e rotazione

### Community 26 - "Soil"
Cohesion: 0.33
Nodes (4): Proprieta' fisse del suolo. Valori di default: suolo franco tipico. Per un…, TAW, acqua totale disponibile nell'intero profilo, in mm. (fc - wp) e' l'acqua…, Humus iniziale dei primi 30 cm, in t/ha. % sostanza organica x densita' (t/m3)…, Soil

### Community 27 - "test_soil.py"
Cohesion: 0.13
Nodes (11): _horizons_from_yaml(), parametrize, Test di fieldwise.soil (Saxton e Rawls 2006) e coerenza con params/soil.yaml.…, test_nrcs_class_means(), test_physical_order(), test_texture_class_examples_om25(), test_yaml_inputs_match_soilgrids_cache(), test_yaml_om_alternative_effect() (+3 more)

### Community 28 - "ensemble"
Cohesion: 0.50
Nodes (4): ensemble(), label(), Nome leggibile della rotazione, es. 'mais > soia+cover > frumento'., Prova TUTTE le rotazioni su TUTTE le annate di partenza. Rotazioni: 3 colture…

### Community 29 - "test_nitrogen_daily.py"
Cohesion: 0.18
Nodes (24): build(), npar(), pars(), fixture, parametrize, Test del nucleo giornaliero dell'azoto `nitrogen.run_daily`. Serie sintetiche…, Un solo giorno di pioggia in posizione fissa: l cresce con la sua intensita'., Stessa percolazione precoce: l'ordine uniforme < tardivo e precoce <= uniforme. (+16 more)

### Community 30 - "SoilWaterParams"
Cohesion: 0.10
Nodes (10): initial_water_state(), Parametri idrici del profilo a due strati (da soil.yaml e…, TAW dello strato 1 [mm], FAO-56 eq. 82., TAW dello strato 2 [mm], FAO-56 eq. 82., Limite inferiore dell'acqua nello strato 1 [mm]: i primi Ze m a 0,5 theta_WP…, Acqua a saturazione dell'intero profilo [mm] (serve alla lisciviazione)., Stato idrico del suolo (mai azzerato tra i segmenti). w1, w2 [mm]: acqua negli…, Stato iniziale: theta = wp + frazione (fc - wp) in ciascuno strato (soil.yaml… (+2 more)

### Community 31 - "get"
Cohesion: 0.16
Nodes (15): _credit(), (credito con residui interrati, con residui asportati) da…, recupero_apparente della coltura; la soia usa quello del frumento (_meta passo…, _recovery(), get(), is_entry(), _lookup(), override() (+7 more)

### Community 32 - "crop_daily_curves"
Cohesion: 0.13
Nodes (16): cover_daily_curves(), crop_daily_curves(), kc_climate_correction(), kc_curve(), kc_end_climate_correction(), plant_height(), Frazioni di sviluppo a fine fase iniziale, sviluppo e piena stagione, dalle…, Kc a quattro tratti in funzione della frazione di sviluppo `frac` in [0, 1].… (+8 more)

### Community 33 - "Revisione indipendente dei parametri FIELDWISE"
Cohesion: 0.33
Nodes (5): 1. Verifiche sulle fonti (29 voci), 2. Onestà dei campi, 3. Coerenza tra file (conti a mano), 4. Correzioni prima di scrivere il motore (in ordine di importanza), Revisione indipendente dei parametri FIELDWISE

### Community 35 - "numpy"
Cohesion: 0.12
Nodes (18): numpy, aquacrop_tau(), engine_layers(), horizons_from_aggregated(), hydrologic_soil_group(), profile_properties(), ndarray, Proprieta' idrauliche del suolo con le funzioni di pedotrasferimento di Saxton… (+10 more)

### Community 36 - "ValueError"
Cohesion: 0.13
Nodes (20): nitrogen_params(), Legge una volta tutti i parametri dell'azoto e dell'humus. classe: classe ER di…, load_params(), Carica tutti i `*.yaml` della cartella in `{nome_file_senza_estensione:…, build_context(), _cap_value(), Prepara il contesto una volta sola (parametri, meteo del punto, GDD cumulati,…, cn_amc_aquacrop() (+12 more)

### Community 37 - "rotation.py"
Cohesion: 0.09
Nodes (27): dataclasses, build_calendar(), _caps(), compliance(), _cover_window(), _next_sowing(), ndarray, Catena di rotazione (fase 4): calendario, bilancio idrico unico, azoto/humus,… (+19 more)

### Community 38 - "test_water_dual.py"
Cohesion: 0.06
Nodes (47): _arr(), assert_closed(), _check_physics(), _g(), kcmax_default(), maize_inputs(), mk(), multi_inputs() (+39 more)

### Community 39 - "test_water.py"
Cohesion: 0.06
Nodes (29): dry_rotation_inputs(), forcing(), maize_inputs(), _maize_season(), _mk(), _one_day(), pars(), fixture (+21 more)

### Community 40 - "_daily_inputs"
Cohesion: 0.29
Nodes (6): _daily_inputs(), Serie giornaliere della simulazione (in cache nel calendario)., DailyInputs, kc_max_eq72(), Limite superiore di Kc dopo una bagnatura. FAO-56 eq. 72: Kc max = max({1.2 +…, Serie giornaliere della rotazione (tutte lunghe n). et0, rain [mm/g]; kc [-]…

### Community 42 - "test_nitrogen.py"
Cohesion: 0.10
Nodes (48): assert_closure(), assert_non_negative(), initial_states(), npar(), pars(), fixture, parametrize, Test di ``fieldwise.nitrogen`` (bilancio dell'azoto e dell'humus a fine… (+40 more)

### Community 43 - "fw_dati.py"
Cohesion: 0.11
Nodes (31): anni_affidabili(), chiave(), classe_attuale(), colture_principali(), contesto(), dati_mancanti(), ensemble(), ensemble_in_cache() (+23 more)

### Community 44 - "Verifica scientifica indipendente del motore (fasi 3 e 4)"
Cohesion: 0.15
Nodes (12): A. Equazioni rispetto alle fonti, B. Numeri nel codice, C. Criteri di accettazione delle fasi 3 e 4 (riprodotti), D. Plausibilità per la bassa pianura lombarda (mediana su 17 annate; pioggia 789 mm/anno, ET0 888 mm/anno), E. Questioni aperte, Elenco finale per gravità, ERRORI da correggere prima dell'ensemble, F. Sensibilità dei test (mutazioni) (+4 more)

### Community 45 - "nitrogen.py"
Cohesion: 0.07
Nodes (40): anni_seg = giorni / 365 (nitrogen._meta.convenzioni.tempo)., years(), _bil(), DailyResult, _humify_fresh(), humus_balance_residual(), initial_n_min(), initial_state() (+32 more)

### Community 46 - "test_ranking.py"
Cohesion: 0.09
Nodes (35): _con_equivalenti(), _nd(), fixture, Test di `fieldwise.ranking` con piccole sintesi finte costruite a mano (nessun…, Tre rotazioni: A costosa e produttiva, B economica e meno produttiva, C…, riga(), _scenario_con_attuale(), sint() (+27 more)

### Community 47 - "test_phenology.py"
Cohesion: 0.12
Nodes (32): assert_ordered(), check_curves(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize (+24 more)

### Community 48 - "test_yield_model.py"
Cohesion: 0.10
Nodes (31): calendar(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize, Test di ``fieldwise.yield_model`` (resa = potenziale x f_acqua x f_caldo x… (+23 more)

### Community 49 - "test_humus.py"
Cohesion: 0.12
Nodes (10): hp(), pars(), fixture, parametrize, Test di ``fieldwise.humus`` (bilancio dell'humus di Henin-Dupuis a fine…, test_chiusura_update_humus(), test_equilibrio_stazionario(), test_residui_crescenti_con_la_resa() (+2 more)

### Community 51 - "water.py"
Cohesion: 0.10
Nodes (32): aggregate_segments(), _cap_array(), _cn_of_day(), cover_fraction_eq76(), _de_bounds_dual(), _de_consistent(), _kernel(), _kernel_dual() (+24 more)

### Community 52 - "_make_smap"
Cohesion: 0.33
Nodes (6): _make_smap(), parametrize, _smap_datasets(), test_smap_extract_fill_values_become_nan(), test_smap_extract_full_and_subset(), test_smap_extract_wrong_pixel_index_raises()

### Community 53 - "fake_net"
Cohesion: 0.40
Nodes (5): fake_net(), fixture, Cache temporanea; online di default; nessuna chiamata di rete ammessa., Login e ricerca CMR finti; registra le chiamate. Le estrazioni le fornisce il…, tmp_cache()

### Community 54 - "_make_imerg_subset"
Cohesion: 0.50
Nodes (4): _centers(), _make_imerg_subset(), Sottoinsieme OPeNDAP finto: precipitation(1, 2, 2) in ordine (time, lon, lat)., test_imerg_extract_from_opendap_subset_and_center_check()

### Community 55 - "test_sensitivity.py"
Cohesion: 0.08
Nodes (21): _campione(), _esito(), giro_minimo(), incerte(), p(), fixture, slow, Test di `fieldwise.sensitivity`. Senza rete e senza cache: limiti delle… (+13 more)

### Community 56 - "test_validation.py"
Cohesion: 0.08
Nodes (14): _giornaliero(), fixture, slow, Test di `fieldwise.validation`: funzioni statistiche su dati sintetici dal…, Serie giornaliera sintetica: valore = climatologia del mese + anomalia…, `run_all` offline su una copia di data/processed (i file del repository restano…, riepilogo(), test_anomalie_mensili_recuperano_anomalie_note() (+6 more)

### Community 57 - "validation.py"
Cohesion: 0.10
Nodes (43): _block_boot(), _clean(), contexts(), corr_stats(), crop_years(), detrend(), fig_case(), fig_istat() (+35 more)

### Community 58 - "_make_imerg_full"
Cohesion: 0.50
Nodes (4): _make_imerg_full(), Granulo IMERG finto con la struttura vera: precipitation(time=1, lon=3600,…, test_imerg_extract_fill_value_becomes_nan(), test_imerg_extract_from_full_granule()

### Community 59 - "ranking.py"
Cohesion: 0.21
Nodes (19): _attuale(), _colonna_conformita(), confronta(), _dict_riga(), _differenze(), insieme(), _marca_non_dominate(), numeri_in_frase() (+11 more)

### Community 60 - "fixture"
Cohesion: 0.17
Nodes (12): anno_centrale(), ctx(), elenco(), elenco_cover(), _mais_in_rotazione(), mais_libero(), msf(), pars() (+4 more)

### Community 62 - "_fake_row"
Cohesion: 0.67
Nodes (3): _fake_row(), test_imerg_old_single_cell_raw_is_rejected_and_redownloaded(), test_imerg_resume_from_partial_year()

### Community 65 - "test_et0.py"
Cohesion: 0.11
Nodes (4): Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998). I…, TestCapitolo3, TestEsempio17Bangkok, TestEsempio18Uccle

### Community 66 - "Verifica indipendente fase 5 (ensemble + classifica)"
Cohesion: 0.40
Nodes (4): Criteri, Difetti in ordine di gravita', Giudizio, Verifica indipendente fase 5 (ensemble + classifica)

### Community 67 - "parametrize"
Cohesion: 0.22
Nodes (10): _anni(), parametrize, test_frumento_mai_irrigato(), test_irrigazione_non_oltre_il_tetto(), test_irrigazione_nulla_in_solo_pioggia(), test_metodo_caldo_uguale_alla_sostituzione_di_heat_factor(), test_residuo_idrico_della_rotazione(), test_simulazione_base() (+2 more)

### Community 68 - "fw_confronto.py"
Cohesion: 0.28
Nodes (15): calcola(), _compromesso(), _distribuzione(), _etichetta_voce(), _fattori(), mostra(), Pagina "Confronto": rotazione attuale contro le alternative (tutta la logica e'…, Esegue il confronto. Restituisce un dizionario con ensemble, confronto e… (+7 more)

### Community 69 - "_tutte"
Cohesion: 0.50
Nodes (4): test_regressione_durata_mais_soia_frumento(), test_regressione_frumento_continuo_lisciviazione(), test_regressione_mais_continuo_irrigazione_libera(), _tutte()

### Community 77 - "ensemble.py"
Cohesion: 0.07
Nodes (40): classe_rotazione_attuale(), _conformita(), _equivalenze(), _hash_albero(), _hash_file_parametri(), load_ensemble(), main(), _membri() (+32 more)

### Community 78 - "sensitivity.py"
Cohesion: 0.15
Nodes (22): applica_catene(), catene(), conclusione(), confronto(), esegui(), _f(), _g(), _init() (+14 more)

### Community 79 - "test_ensemble.py"
Cohesion: 0.07
Nodes (9): ctx(), fixture, slow, Test di `fieldwise.ensemble` sul meteo reale del punto pilota (saltati se la…, mais' e' la ripetizione di 'mais > mais > mais': qui non e' nel sottoinsieme,…, ris(), ris_mais(), test_ensemble_completo() (+1 more)

### Community 80 - "fw_util.py"
Cohesion: 0.20
Nodes (13): DataFrame, _tabella(), differenza(), Piccole funzioni di presentazione condivise dalle pagine (nessuna logica di…, {coltura: resa mediana in t/ha} dalle colonne ``resa_t_ha_<coltura>`` di una…, mais 14,4 t/ha · soia 3,5 t/ha' (stringa vuota se la sintesi non ha le rese per…, Valore di un indicatore della sintesi nelle sue unita' (la resa e' in % del…, Differenza rispetto all'attuale: punti percentuali per le rese, unita'… (+5 more)

### Community 81 - "test_app.py"
Cohesion: 0.14
Nodes (22): at(), contenuto(), fixture, parametrize, Test dell'app Streamlit con ``streamlit.testing.v1.AppTest`` (offline, solo…, Tutto il testo mostrato (markdown, messaggi, titoli, didascalie)., test_almeno_due_alternative_con_evidenze_e_rischi(), test_avviso_sempre_visibile() (+14 more)

### Community 82 - "Validazione del motore (fase 6)"
Cohesion: 0.22
Nodes (8): A. Umidità superficiale SMAP, B. NDVI MODIS contro stress idrico simulato del mais (2001–2022), C. Rese ISTAT provinciali (2006–2022), Cosa NON è stato validato, D. Robustezza (mais, monosuccessione, residui dal trend), Regole seguite, Sintesi, Validazione del motore (fase 6)

### Community 86 - "yield_model.py"
Cohesion: 0.17
Nodes (15): Resa relativa per la sola risposta all'acqua (Doorenbos e Kassam 1979, FAO-33;…, relative_yield_fao33(), _clip01(), crop_yield(), _irrigated(), potential_yield(), Modello di resa (fase 4): Y = Y_pot x f_acqua x f_caldo x f_rotazione. Ogni…, f_rotazione di ``crop`` date le due colture principali precedenti (None =… (+7 more)

### Community 87 - "CycleCalendar"
Cohesion: 0.18
Nodes (7): crop_daily_curves_gdd(), CycleCalendar, Calendario di un ciclo. Indici = righe del meteo (assoluti); -1 se non…, Durata del ciclo in giorni, semina e maturita' comprese (0 se fuori serie)., Raccolta = maturita' fisiologica., Eventi come date (NaT se non raggiunti); ``dates`` = colonna date del meteo., Serie (kc, zr, p_tab) del ciclo, lunghe ``cal.n_days``, con la frazione di…

### Community 88 - "heat_factor"
Cohesion: 0.18
Nodes (13): _aquacrop_daily(), FinestraVuota, heat_factor(), HeatResult, _linear_daily(), ndarray, f_caldo del ciclo ``cal`` (da ``phenology.cycle_calendar``). metodo: 'deryng'…, La finestra sensibile al caldo non contiene giorni: caso degenere dei parametri. (+5 more)

### Community 89 - "Analisi di sensibilita' (fase 7)"
Cohesion: 0.20
Nodes (9): Analisi di sensibilita' (fase 7), Caso di base, Conclusione in una frase, I 20 parametri piu' influenti (una alla volta, tetto irriguo), Incertezza strutturale (una alla volta), Metodo, Monte Carlo (incertezza congiunta dei parametri), Parametri che NON contano (+1 more)

### Community 90 - "sowing_index"
Cohesion: 0.50
Nodes (4): Riga del meteo con data ``year-mmdd`` ("MM-GG"); KeyError se manca., Riga della semina tipica (crops.<crop>.semina) nell'anno ``year`` (per il…, sowing_index(), typical_sowing_index()

### Community 92 - "fw_testi.py"
Cohesion: 0.29
Nodes (10): capire(), _istat(), limiti(), DataFrame, _r(), Pagine di spiegazione: "Capire i dati", "Validazione", "Limiti e fonti". Ogni…, Sezione sulla sensibilita': mostra la conclusione se il riepilogo esiste…, _sensibilita() (+2 more)

### Community 93 - "__init__.py"
Cohesion: 0.20
Nodes (7): pandas, FIELDWISE - confronto di rotazioni colturali con bilanci di massa giornalieri., forcing(), _offline(), fixture, Test di ``fieldwise.weather`` (tabella meteo del motore, letta solo dalla…, Tabella del punto pilota; salta se la cache e' incompleta.

### Community 94 - "streamlit_app.py"
Cohesion: 0.36
Nodes (8): avviso_cache(), barra_laterale(), main(), mappa(), _punto_iniziale(), FIELDWISE - confronto di rotazioni colturali (app Streamlit). Avvio:…, Mappa per scegliere il campo con un clic. Se non si carica (niente rete)…, _torna_al_pilota()

### Community 95 - "_rischi"
Cohesion: 0.22
Nodes (9): _evidenze_e_peggioramenti(), _evidenze_extra(), _num(), _pct(), Frasi sui miglioramenti (evidenze) e sui peggioramenti (rischi) rispetto…, Miglioramenti rispetto all'attuale che non sono differenze numeriche degli…, Rischi della rotazione. Un miglioramento rispetto all'attuale non e' mai un…, _rischi() (+1 more)

### Community 96 - "voci_incerte"
Cohesion: 0.22
Nodes (9): etichetta(), DataFrame, Voci perturbabili con limiti (x0,7 / x1,3 ristretti) e voci escluse con il…, Prima rotazione al variare dei pesi (con i parametri di base)., Tutti i membri delle classi non equivalenti nell'ensemble di base., Etichetta leggibile in italiano dal percorso della voce., sensibilita_pesi(), sottoinsieme() (+1 more)

### Community 97 - "fw_dettaglio.py"
Cohesion: 0.46
Nodes (7): _azoto(), _calendario(), _gg(), _grafici(), mostra(), DataFrame, Pagina "Dettaglio di una annata": calendario, acqua, azoto giorno per giorno.

### Community 98 - "score"
Cohesion: 0.29
Nodes (7): _normalizza(), ndarray, 0..1 con 1 = migliore; costante -> ``PUNTEGGIO_NEUTRO``., Sintesi dello ``scenario`` ordinata per punteggio decrescente. Ogni indicatore…, score(), _verifica_pesi(), verifica_sottoinsieme()

### Community 99 - "_Resp"
Cohesion: 0.29
Nodes (3): pixel_values(), (ndvi grezzo, affidabilita', vi_quality) dei 9 pixel di una data. Data 0: tutti…, _Resp

### Community 100 - "config.py"
Cohesion: 0.40
Nodes (4): os, offline(), Percorsi e costanti condivise da tutto il progetto. Nessun parametro agronomico…, True se la rete e' vietata (demo): i client devono usare solo la cache.

### Community 101 - "PhenoParams"
Cohesion: 0.40
Nodes (3): PhenoParams, Parametri fenologici di una coltura letti da crops.yaml., (f_ini, f_dev, f_mid) per ``water.kc_curve`` e ``water.root_depth``: soglie di…

### Community 102 - "valuta"
Cohesion: 0.40
Nodes (5): _forcing(), Per scenario: classi in ordine, punteggi, attuale e alternative di…, Un calcolo dell'ensemble ridotto. ``caso``: id, modifiche, opzioni,…, riassumi(), valuta()

### Community 103 - "_ctx_con"
Cohesion: 0.50
Nodes (4): _ctx_con(), test_heat_factor_con_finestra_vuota_solleva_finestra_vuota(), test_simulate_fase_di_piena_stagione_vuota_senza_avvisi_numpy(), test_simulate_finestra_del_caldo_vuota_non_riuscita_con_motivo()

## Knowledge Gaps
- **70 isolated node(s):** `fieldwise`, `graphify`, `graphify`, `Principi non negoziabili`, `Decisioni prese` (+65 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 760 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Rotation` connect `ensemble.py` to `validation.py`, `.canonical`, `rotation.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Why does `run_segment()` connect `run_segment` to `fieldwise_engine.py`, `simulate_rotation`, `Dynamic vectors approach F(t), C(t) and its four problems`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Why does `run_ensemble()` connect `ensemble.py` to `valuta`, `ValueError`, `rotation.py`, `sensitivity.py`?**
  _High betweenness centrality (0.015) - this node is a cross-community bridge._
- **Are the 30 inferred relationships involving `ValueError` (e.g. with `parse_rotazione()` and `run_ensemble()`) actually correct?**
  _`ValueError` has 30 INFERRED edges - model-reasoned connections that need verification._
- **What connects `fieldwise`, `graphify`, `graphify` to the rest of the system?**
  _70 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `et0.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07740112994350283 - nodes in this community are weakly interconnected._
- **Should `test_data_earthdata.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._