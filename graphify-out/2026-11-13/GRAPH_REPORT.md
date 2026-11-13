# Graph Report - nasa  (2026-11-13)

## Corpus Check
- 164 files · ~144,654 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1545 nodes · 2881 edges · 91 communities (67 shown, 24 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `10b571f5`
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
- humus.py
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
- water.py
- crop_daily_curves_gdd
- Revisione indipendente dei parametri FIELDWISE
- test_rotation.py
- soil.py
- yield_model.py
- RotationContext
- test_water_dual.py
- test_water.py
- simulate
- TestSupporto
- test_nitrogen.py
- weather.py
- Verifica scientifica indipendente del motore (fasi 3 e 4)
- run_daily
- test_ranking.py
- test_phenology.py
- test_yield_model.py
- test_humus.py
- Rotation
- njit
- _make_smap
- fake_net
- _make_imerg_subset
- pandas
- compliance
- validation.py
- _make_imerg_full
- ranking.py
- fixture
- _Auth
- _fake_row
- _granule
- _frame
- TestEsempio18Uccle
- CycleCalendar
- _anni
- TestTabellaPilota
- _tutte
- test_semina_del_ciclo_dopo_raccolta_dell_ultima_coltura
- test_stato_ereditato_conta
- test_cover_senza_tempo_suolo_nudo_con_motivo
- test_cover_possibile_e_cover_negata_sono_coerenti
- test_cover_oltre_semina_max_motivo
- test_cover_cambia_il_bilancio_dell_azoto
- test_300_simulazioni_in_meno_di_5_secondi
- ensemble.py
- build_context
- test_ensemble.py
- WaterResult
- numpy
- Validazione del motore (fase 6)
- test_mais_traspirazione_potenziale_normalizzata_segue_il_kcb
- TestComportamento
- TestEsempio20Lione
- _sintesi
- humus_balance_residual
- sowing_index
- load_ensemble
- .breakpoints

## God Nodes (most connected - your core abstractions)
1. `run()` - 32 edges
2. `by_name()` - 31 edges
3. `run_checks()` - 26 edges
4. `water()` - 26 edges
5. `make_power()` - 25 edges
6. `build_context()` - 22 edges
7. `_a()` - 20 edges
8. `_out()` - 20 edges
9. `Rotation` - 19 edges
10. `simulate()` - 18 edges

## Surprising Connections (you probably didn't know these)
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `run_segment()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `update_soil()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves)` --implements--> `hargreaves_et0()`  [EXTRACTED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Kc crop coefficient (four phases) and ETc = Kc x ET0` --implements--> `kc_and_roots()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Daily water step (8 passes: surface demand, root water, irrigation 40 mm, stress, consumption, balance, rain runoff >60 mm)` --implements--> `run_segment()`  [EXTRACTED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Four problems of the dynamic-vectors approach** — legacy_fieldwise_proposta_modello_weighted_score_no_units, legacy_fieldwise_proposta_modello_soil_crop_coupling, legacy_fieldwise_proposta_modello_nonlinear_plant_response, legacy_fieldwise_proposta_modello_dynamic_vectors_problem [EXTRACTED 1.00]
- **Engine nested computation: daily water step, end-of-segment N/humus, rotation chain, ensemble** — legacy_fieldwise_proposta_modello_daily_water_step, legacy_fieldwise_proposta_modello_nitrogen_humus_accounting, legacy_fieldwise_proposta_modello_segment, legacy_fieldwise_proposta_modello_exhaustive_enumeration [EXTRACTED 1.00]
- **FAO water-stress to yield chain (ET0, Kc, TAW/RAW, Ks, Ky)** — legacy_fieldwise_proposta_modello_et0, legacy_fieldwise_proposta_modello_kc_crop_coefficient, legacy_fieldwise_proposta_modello_taw_raw, legacy_fieldwise_proposta_modello_ks_stress, legacy_fieldwise_proposta_modello_ky_yield_response [EXTRACTED 1.00]

## Communities (91 total, 24 thin omitted)

### Community 0 - "run_segment"
Cohesion: 0.17
Nodes (15): kc_and_roots(), Quanto chiede la pianta e fin dove arriva, al giorno d dalla semina. Kc segue…, Fa avanzare l'acqua del suolo dal giorno i0 al giorno i1 (escluso). Un…, run_segment(), Crop parameter table (maize, soybean, wheat), ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves), FAO-33 yield response to water (Doorenbos and Kassam, 1979), FAO-56 crop water use (Allen et al., 1998) (+7 more)

### Community 1 - "test_data_modis.py"
Cohesion: 0.11
Nodes (15): FakeService, pixel_values(), fixture, Test del client MODIS: nessuna rete (requests.get sostituito), cartelle…, (ndvi grezzo, affidabilita', vi_quality) dei 9 pixel di una data. Data 0: tutti…, _Resp, run_fetch(), test_block_without_meta_is_redownloaded() (+7 more)

### Community 2 - "et0.py"
Cohesion: 0.11
Nodes (44): _a(), actual_vapour_pressure(), atmospheric_pressure(), clear_sky_radiation(), daylight_hours(), et0_from_power(), et0_hargreaves(), et0_penman_monteith() (+36 more)

### Community 3 - "fieldwise_engine.py"
Cohesion: 0.16
Nodes (13): datetime, itertools, Crop, fetch_power(), load_weather(), FIELDWISE - motore di simulazione delle rotazioni colturali…, Scarica il meteo giornaliero da NASA POWER. Non serve nessun login.…, Meteo FINTO con stagioni tipo Pianura Padana. Serve SOLO a collaudare il codice… (+5 more)

### Community 5 - "params.py"
Cohesion: 0.10
Nodes (40): os, offline(), Percorsi e costanti condivise da tutto il progetto. Nessun parametro agronomico…, True se la rete e' vietata (demo): i client devono usare solo la cache., build_table(), _cell(), get(), _in_sensitivity() (+32 more)

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
Nodes (21): calendar_from_cum(), crop_pheno_params(), cumulative_gdd(), cycle_calendar(), cycle_calendars(), daily_gdd(), event_table(), _gdd_series() (+13 more)

### Community 20 - "humus.py"
Cohesion: 0.10
Nodes (28): cover_humus(), equilibrium(), grain_moisture(), humus_params(), HumusParams, initial_humus(), k2_from_params(), mineralization() (+20 more)

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

### Community 31 - "water.py"
Cohesion: 0.10
Nodes (26): dataclasses, math, FIELDWISE - confronto di rotazioni colturali con bilanci di massa giornalieri., _credit(), initial_n_min(), _mas(), nitrogen_params(), Bilancio di massa dell'azoto del suolo a passo giornaliero (FIELDWISE).… (+18 more)

### Community 32 - "crop_daily_curves_gdd"
Cohesion: 0.14
Nodes (18): crop_daily_curves_gdd(), Serie (kc, zr, p_tab) del ciclo, lunghe ``cal.n_days``, con la frazione di…, cover_daily_curves(), crop_daily_curves(), kc_climate_correction(), kc_curve(), kc_end_climate_correction(), plant_height() (+10 more)

### Community 33 - "Revisione indipendente dei parametri FIELDWISE"
Cohesion: 0.33
Nodes (5): 1. Verifiche sulle fonti (29 voci), 2. Onestà dei campi, 3. Coerenza tra file (conti a mano), 4. Correzioni prima di scrivere il motore (in ordine di importanza), Revisione indipendente dei parametri FIELDWISE

### Community 35 - "soil.py"
Cohesion: 0.13
Nodes (17): aquacrop_tau(), engine_layers(), horizons_from_aggregated(), hydrologic_soil_group(), profile_properties(), ndarray, Proprieta' idrauliche del suolo con le funzioni di pedotrasferimento di Saxton…, Classe tessiturale USDA (nomi inglesi) da percentuali di sabbia, argilla, limo.… (+9 more)

### Community 36 - "yield_model.py"
Cohesion: 0.11
Nodes (26): Resa relativa per la sola risposta all'acqua (Doorenbos e Kassam 1979, FAO-33;…, relative_yield_fao33(), _aquacrop_daily(), _clip01(), crop_yield(), heat_factor(), HeatResult, _irrigated() (+18 more)

### Community 37 - "RotationContext"
Cohesion: 0.11
Nodes (16): build_calendar(), _cover_window(), _next_sowing(), Tutto cio' che non dipende dalla rotazione: meteo come array, parametri letti…, Riga del meteo per year-mmdd (puo' essere fuori serie: <0 o > ultima riga)., Calendario, curve (kc, zr, p) e fattore di caldo del ciclo (crop, sow), in…, Kcb del ciclo (FAO-56 Tab. 17): stessa curva a quattro tratti e stessi punti di…, Tratto omogeneo della simulazione (indici di riga del meteo, estremi compresi). (+8 more)

### Community 38 - "test_water_dual.py"
Cohesion: 0.06
Nodes (47): _arr(), assert_closed(), _check_physics(), _g(), kcmax_default(), maize_inputs(), mk(), multi_inputs() (+39 more)

### Community 39 - "test_water.py"
Cohesion: 0.06
Nodes (29): dry_rotation_inputs(), forcing(), maize_inputs(), _maize_season(), _mk(), _one_day(), pars(), fixture (+21 more)

### Community 40 - "simulate"
Cohesion: 0.11
Nodes (18): n_balance_residual(), Scarto di chiusura [kg N/ha]: (ENTRATE - USCITE) - (dN_min + dN_res + dN_cov +…, _caps(), _daily_inputs(), ndarray, Esito di ``build_calendar``. Con esito diverso da 'ok' i segmenti sono vuoti., Serie giornaliere della simulazione (in cache nel calendario)., Simula la rotazione dal 1 gennaio di ``anno`` nello ``scenario`` d'acqua (uno… (+10 more)

### Community 42 - "test_nitrogen.py"
Cohesion: 0.10
Nodes (48): assert_closure(), assert_non_negative(), initial_states(), npar(), pars(), fixture, parametrize, Test di ``fieldwise.nitrogen`` (bilancio dell'azoto e dell'humus a fine… (+40 more)

### Community 43 - "weather.py"
Cohesion: 0.29
Nodes (14): _apply_rain(), _apply_temp(), available_years(), load_forcing(), _load_power(), _point_dir(), DataFrame, Series (+6 more)

### Community 44 - "Verifica scientifica indipendente del motore (fasi 3 e 4)"
Cohesion: 0.15
Nodes (12): A. Equazioni rispetto alle fonti, B. Numeri nel codice, C. Criteri di accettazione delle fasi 3 e 4 (riprodotti), D. Plausibilità per la bassa pianura lombarda (mediana su 17 annate; pioggia 789 mm/anno, ET0 888 mm/anno), E. Questioni aperte, Elenco finale per gravità, ERRORI da correggere prima dell'ensemble, F. Sensibilità dei test (mutazioni) (+4 more)

### Community 45 - "run_daily"
Cohesion: 0.10
Nodes (24): anni_seg = giorni / 365 (nitrogen._meta.convenzioni.tempo)., years(), _bil(), DailyResult, initial_state(), leaching_fraction(), mas_limit(), NitrogenParams (+16 more)

### Community 46 - "test_ranking.py"
Cohesion: 0.10
Nodes (30): _con_equivalenti(), _nd(), fixture, Test di `fieldwise.ranking` con piccole sintesi finte costruite a mano (nessun…, Tre rotazioni: A costosa e produttiva, B economica e meno produttiva, C…, riga(), _scenario_con_attuale(), sint() (+22 more)

### Community 47 - "test_phenology.py"
Cohesion: 0.12
Nodes (32): assert_ordered(), check_curves(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize (+24 more)

### Community 48 - "test_yield_model.py"
Cohesion: 0.10
Nodes (31): calendar(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize, Test di ``fieldwise.yield_model`` (resa = potenziale x f_acqua x f_caldo x… (+23 more)

### Community 49 - "test_humus.py"
Cohesion: 0.12
Nodes (10): hp(), pars(), fixture, parametrize, Test di ``fieldwise.humus`` (bilancio dell'humus di Henin-Dupuis a fine…, test_chiusura_update_humus(), test_equilibrio_stazionario(), test_residui_crescenti_con_la_resa() (+2 more)

### Community 50 - "Rotation"
Cohesion: 0.16
Nodes (8): _conformita(), Conformita' per regime. Una rotazione che ripete una sequenza piu' corta di cui…, _voce(), Etichetta leggibile, es. 'mais > soia+cover > frumento'., Permutazione ciclica che parte dalla coltura k., Rappresentante della classe di permutazioni cicliche (minimo lessicografico)., Sequenza di colture principali e, per ogni coltura, se nell'intervallo che la…, Rotation

### Community 51 - "njit"
Cohesion: 0.14
Nodes (20): _humify_fresh(), _kernel(), Rilascio uniforme di ``amount`` nei giorni start..start+ndays-1., N_umif = H_add n_humus 1000 preso dall'N fresco dei residui; il deficit da…, _schedule(), _cn_of_day(), _de_bounds_dual(), _de_consistent() (+12 more)

### Community 52 - "_make_smap"
Cohesion: 0.33
Nodes (6): _make_smap(), parametrize, _smap_datasets(), test_smap_extract_fill_values_become_nan(), test_smap_extract_full_and_subset(), test_smap_extract_wrong_pixel_index_raises()

### Community 53 - "fake_net"
Cohesion: 0.40
Nodes (5): fake_net(), fixture, Cache temporanea; online di default; nessuna chiamata di rete ammessa., Login e ricerca CMR finti; registra le chiamate. Le estrazioni le fornisce il…, tmp_cache()

### Community 54 - "_make_imerg_subset"
Cohesion: 0.50
Nodes (4): _centers(), _make_imerg_subset(), Sottoinsieme OPeNDAP finto: precipitation(1, 2, 2) in ordine (time, lon, lat)., test_imerg_extract_from_opendap_subset_and_center_check()

### Community 55 - "pandas"
Cohesion: 0.17
Nodes (4): pandas, Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998). I…, TestCapitolo3, TestEsempio17Bangkok

### Community 56 - "compliance"
Cohesion: 0.33
Nodes (6): compliance(), enumerate_rotations(), main_crops(), Colture principali di crops.yaml: le voci con un ciclo fenologico…, Stato di conformita' ai disciplinari della sequenza ``crops`` (cover ignorate,…, Tutte le rotazioni di ``length`` colture (colture da crops.yaml se ``crops`` e'…

### Community 57 - "validation.py"
Cohesion: 0.10
Nodes (43): _block_boot(), _clean(), contexts(), corr_stats(), crop_years(), detrend(), fig_case(), fig_istat() (+35 more)

### Community 58 - "_make_imerg_full"
Cohesion: 0.50
Nodes (4): _make_imerg_full(), Granulo IMERG finto con la struttura vera: precipitation(time=1, lon=3600,…, test_imerg_extract_fill_value_becomes_nan(), test_imerg_extract_from_full_granule()

### Community 59 - "ranking.py"
Cohesion: 0.13
Nodes (30): _attuale(), _colonna_conformita(), confronta(), _dict_riga(), _differenze(), _evidenze_e_peggioramenti(), insieme(), _marca_non_dominate() (+22 more)

### Community 60 - "fixture"
Cohesion: 0.17
Nodes (12): anno_centrale(), ctx(), elenco(), elenco_cover(), _mais_in_rotazione(), mais_libero(), msf(), pars() (+4 more)

### Community 62 - "_fake_row"
Cohesion: 0.67
Nodes (3): _fake_row(), test_imerg_old_single_cell_raw_is_rejected_and_redownloaded(), test_imerg_resume_from_partial_year()

### Community 66 - "CycleCalendar"
Cohesion: 0.22
Nodes (5): CycleCalendar, Calendario di un ciclo. Indici = righe del meteo (assoluti); -1 se non…, Durata del ciclo in giorni, semina e maturita' comprese (0 se fuori serie)., Raccolta = maturita' fisiologica., Eventi come date (NaT se non raggiunti); ``dates`` = colonna date del meteo.

### Community 67 - "_anni"
Cohesion: 0.25
Nodes (9): _anni(), parametrize, test_frumento_mai_irrigato(), test_irrigazione_non_oltre_il_tetto(), test_irrigazione_nulla_in_solo_pioggia(), test_residuo_idrico_della_rotazione(), test_simulazione_base(), _wbal() (+1 more)

### Community 69 - "_tutte"
Cohesion: 0.50
Nodes (4): test_regressione_durata_mais_soia_frumento(), test_regressione_frumento_continuo_lisciviazione(), test_regressione_mais_continuo_irrigazione_libera(), _tutte()

### Community 77 - "ensemble.py"
Cohesion: 0.15
Nodes (18): _equivalenze(), _hash_albero(), _hash_file_parametri(), main(), _membri(), _motivo_breve(), parse_rotazione(), Ensemble delle rotazioni: tutte le rotazioni x tutte le annate di partenza x… (+10 more)

### Community 78 - "build_context"
Cohesion: 0.17
Nodes (12): DataFrame, Tmedia giornaliera secondo crops.yaml _meta.metodo_gdd: T2M (``tmean``), oppure…, tmean_of(), build_context(), _cap_value(), Prepara il contesto una volta sola (parametri, meteo del punto, GDD cumulati,…, cn_class(), cn_class_index() (+4 more)

### Community 79 - "test_ensemble.py"
Cohesion: 0.10
Nodes (7): ctx(), fixture, slow, Test di `fieldwise.ensemble` sul meteo reale del punto pilota (saltati se la…, ris(), ris_mais(), test_ensemble_completo()

### Community 80 - "WaterResult"
Cohesion: 0.22
Nodes (10): aggregate_segments(), _cap_array(), ndarray, Scarto di chiusura [mm] su tutta la serie: (S_fine - S_inizio) - (P + I - RO -…, Scarto giornaliero [mm] dello stesso bilancio (deve essere ~0 ogni giorno)., Somme per segmento: days, rain, eta, etc, irr, runoff, dp, tr, ev [mm] e…, Uscite giornaliere [mm o -] e stato iniziale/finale. etc, eta, ks, kr, irr,…, water_balance_daily_residual() (+2 more)

### Community 81 - "numpy"
Cohesion: 0.25
Nodes (6): numpy, forcing(), _offline(), fixture, Test di ``fieldwise.weather`` (tabella meteo del motore, letta solo dalla…, Tabella del punto pilota; salta se la cache e' incompleta.

### Community 82 - "Validazione del motore (fase 6)"
Cohesion: 0.22
Nodes (8): A. Umidità superficiale SMAP, B. NDVI MODIS contro stress idrico simulato del mais (2001–2022), C. Rese ISTAT provinciali (2006–2022), Cosa NON è stato validato, D. Robustezza (mais, monosuccessione, residui dal trend), Regole seguite, Sintesi, Validazione del motore (fase 6)

### Community 86 - "_sintesi"
Cohesion: 0.50
Nodes (4): _peggiore(), Una riga per (classe ciclica, scenario) in ordine di classe e di scenario., Stato di conformita' piu' sfavorevole tra i regimi (``non_valutabile`` se…, _sintesi()

### Community 87 - "humus_balance_residual"
Cohesion: 0.50
Nodes (4): humus_balance_residual(), Scarto di chiusura [t SO/ha]: (H1 - H0) - (H_res + H_cov - H_min)., humus_balance_residual(), Scarto di chiusura dell'humus [t SO/ha] (vedi `humus.humus_balance_residual`).

### Community 88 - "sowing_index"
Cohesion: 0.50
Nodes (4): Riga del meteo con data ``year-mmdd`` ("MM-GG"); KeyError se manca., Riga della semina tipica (crops.<crop>.semina) nell'anno ``year`` (per il…, sowing_index(), typical_sowing_index()

## Knowledge Gaps
- **59 isolated node(s):** `fieldwise`, `graphify`, `graphify`, `Principi non negoziabili`, `Decisioni prese` (+54 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 654 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_segment()` connect `run_segment` to `fieldwise_engine.py`, `simulate_rotation`, `Dynamic vectors approach F(t), C(t) and its four problems`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `TestSupporto` connect `TestSupporto` to `test_water.py`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `Ks water stress coefficient and ETa = Ks x ETc` connect `run_segment` to `simulate_rotation`, `Dynamic vectors approach F(t), C(t) and its four problems`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **What connects `fieldwise`, `graphify`, `graphify` to the rest of the system?**
  _59 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_data_modis.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11076923076923077 - nodes in this community are weakly interconnected._
- **Should `et0.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10505050505050505 - nodes in this community are weakly interconnected._
- **Should `test_data_earthdata.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._