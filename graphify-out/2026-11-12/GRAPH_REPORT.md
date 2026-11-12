# Graph Report - nasa  (2026-11-12)

## Corpus Check
- 154 files · ~113,810 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1149 nodes · 2122 edges · 65 communities (51 shown, 14 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `5ee57b84`
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
- numpy
- simulate_rotation
- Dynamic vectors approach F(t), C(t) and its four problems
- hargreaves_et0
- Tabella dei parametri
- Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml
- Soil
- test_soil.py
- ensemble
- water.py
- SoilWaterParams
- __init__.py
- crop_daily_curves
- Revisione indipendente dei parametri FIELDWISE
- WaterState
- humus.py
- yield_model.py
- rotation.py
- weather.py
- test_water.py
- soil.py
- TestSupporto
- test_nitrogen.py
- humus_balance_residual
- TestEsempio18Uccle
- TestComportamento
- TestEsempio20Lione
- test_phenology.py
- test_yield_model.py
- test_humus.py
- Rotation
- WaterResult
- _make_smap
- fake_net
- _make_imerg_subset
- run_water_balance
- root_depth
- soil_from_params
- _make_imerg_full
- _Resp
- TestCapitolo3
- _Auth
- _fake_row
- _granule
- _frame

## God Nodes (most connected - your core abstractions)
1. `by_name()` - 31 edges
2. `run_checks()` - 26 edges
3. `water()` - 26 edges
4. `make_power()` - 25 edges
5. `_a()` - 20 edges
6. `_out()` - 20 edges
7. `simulate()` - 19 edges
8. `build_context()` - 18 edges
9. `state_with()` - 18 edges
10. `get()` - 16 edges

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

## Communities (65 total, 14 thin omitted)

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
Cohesion: 0.12
Nodes (36): build_table(), _cell(), get(), _in_sensitivity(), is_entry(), _is_number(), iter_entries(), _join() (+28 more)

### Community 6 - "test_data_arpa.py"
Cohesion: 0.06
Nodes (24): _catalog(), fake_net(), fake_net_both(), fixture, Test del client pioggia ARPA Lombardia, senza rete e senza toccare la cache…, Rete finta per pioggia e temperatura: instrada in base all'URL e ai parametri., _Resp, _row() (+16 more)

### Community 7 - "test_data_istat.py"
Cohesion: 0.11
Nodes (16): clock(), FakeClock, FakeResponse, FakeSession, _limiter(), fixture, Test del client ISTAT: nessuna rete, solo cartelle temporanee., _row() (+8 more)

### Community 8 - "test_data_power.py"
Cohesion: 0.20
Nodes (4): fake_net(), fixture, Test del client NASA POWER, senza rete e senza toccare la cache vera., tmp_cache()

### Community 9 - "test_data_soilgrids.py"
Cohesion: 0.09
Nodes (14): fake_wcs_http(), FakeResp, make_tiff(), mapped(), fixture, ndarray, Test del client SoilGrids: nessuna rete, cartelle temporanee, risposte finte., rest_ok() (+6 more)

### Community 10 - "test_params.py"
Cohesion: 0.12
Nodes (27): os, offline(), Percorsi e costanti condivise da tutto il progetto. Nessun parametro agronomico…, True se la rete e' vietata (demo): i client devono usare solo la cache., assumed(), make_tree(), one_error(), Path (+19 more)

### Community 11 - "Fonti di `params/crops.yaml`"
Cohesion: 0.25
Nodes (7): Altro (dichiarato, non ufficiale), Articoli peer-reviewed e atti, Dati usati solo per conversioni e controlli, Enti pubblici italiani, Fonti cercate ma non leggibili, Fonti di `params/crops.yaml`, Manuali FAO

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
Cohesion: 0.07
Nodes (40): calendar_from_cum(), crop_daily_curves_gdd(), crop_pheno_params(), cumulative_gdd(), cycle_calendar(), cycle_calendars(), CycleCalendar, daily_gdd() (+32 more)

### Community 20 - "numpy"
Cohesion: 0.25
Nodes (3): numpy, Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998). I…, TestEsempio17Bangkok

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

### Community 29 - "water.py"
Cohesion: 0.24
Nodes (11): _de_consistent(), _kernel(), njit(), p_adjusted(), Bilancio idrico giornaliero a due strati (FAO-56, Allen et al. 1998, cap. 7 e…, RHmin [%] stimata con Tdew ~ Tmin. FAO-56 eq. 63: RHmin = 100…, Frazione di esaurimento corretta con l'ETc del giorno [mm/g]. FAO-56 tab. 22,…, Ruscellamento SCS [mm]. NRCS NEH 630 cap. 10: S = 25400/CN - 254 (eq. 10-11),… (+3 more)

### Community 30 - "SoilWaterParams"
Cohesion: 0.13
Nodes (6): Parametri idrici del profilo a due strati (da soil.yaml e…, TAW dello strato 1 [mm], FAO-56 eq. 82., TAW dello strato 2 [mm], FAO-56 eq. 82., Limite inferiore dell'acqua nello strato 1 [mm]: i primi Ze m a 0,5 theta_WP…, Acqua a saturazione dell'intero profilo [mm] (serve alla lisciviazione)., SoilWaterParams

### Community 31 - "__init__.py"
Cohesion: 0.09
Nodes (30): FIELDWISE - confronto di rotazioni colturali con bilanci di massa giornalieri., _credit(), _humify(), initial_n_min(), initial_state(), leaching_fraction(), _mas(), mas_limit() (+22 more)

### Community 32 - "crop_daily_curves"
Cohesion: 0.22
Nodes (10): crop_daily_curves(), kc_climate_correction(), kc_curve(), kc_end_climate_correction(), Frazioni di sviluppo a fine fase iniziale, sviluppo e piena stagione, dalle…, Kc a quattro tratti in funzione della frazione di sviluppo `frac` in [0, 1].…, Kc mid corretto per il clima. FAO-56 eq. 62: Kc = Kc(tab) + [0.04 (u2 - 2) -…, Kc end corretto per il clima. FAO-56 eq. 65 (stessa forma di eq. 62), che si… (+2 more)

### Community 33 - "Revisione indipendente dei parametri FIELDWISE"
Cohesion: 0.33
Nodes (5): 1. Verifiche sulle fonti (29 voci), 2. Onestà dei campi, 3. Coerenza tra file (conti a mano), 4. Correzioni prima di scrivere il motore (in ordine di importanza), Revisione indipendente dei parametri FIELDWISE

### Community 34 - "WaterState"
Cohesion: 0.33
Nodes (4): initial_water_state(), Stato idrico del suolo (mai azzerato tra i segmenti). w1, w2 [mm]: acqua negli…, Stato iniziale: theta = wp + frazione (fc - wp) in ciascuno strato (soil.yaml…, WaterState

### Community 35 - "humus.py"
Cohesion: 0.09
Nodes (31): math, cover_humus(), equilibrium(), grain_moisture(), humus_params(), HumusParams, initial_humus(), k2_from_params() (+23 more)

### Community 36 - "yield_model.py"
Cohesion: 0.11
Nodes (27): dataclasses, Resa relativa per la sola risposta all'acqua (Doorenbos e Kassam 1979, FAO-33;…, relative_yield_fao33(), _aquacrop_daily(), _clip01(), crop_yield(), heat_factor(), HeatResult (+19 more)

### Community 37 - "rotation.py"
Cohesion: 0.09
Nodes (29): n_balance_residual(), Aggregati idrici del segmento k da `water.aggregate_segments` come scalari., Scarto di chiusura [kg N/ha]: (ENTRATE - USCITE) - (dN_min + dN_res + dN_cov +…, segment_water(), build_calendar(), _cap_value(), _caps(), _cover_window() (+21 more)

### Community 38 - "weather.py"
Cohesion: 0.08
Nodes (22): pandas, _apply_rain(), _apply_temp(), available_years(), load_forcing(), _load_power(), _point_dir(), DataFrame (+14 more)

### Community 39 - "test_water.py"
Cohesion: 0.06
Nodes (28): slow, dry_rotation_inputs(), forcing(), maize_inputs(), _maize_season(), _mk(), _one_day(), pars() (+20 more)

### Community 40 - "soil.py"
Cohesion: 0.13
Nodes (17): aquacrop_tau(), engine_layers(), horizons_from_aggregated(), hydrologic_soil_group(), profile_properties(), ndarray, Proprieta' idrauliche del suolo con le funzioni di pedotrasferimento di Saxton…, Classe tessiturale USDA (nomi inglesi) da percentuali di sabbia, argilla, limo.… (+9 more)

### Community 42 - "test_nitrogen.py"
Cohesion: 0.10
Nodes (48): assert_closure(), assert_non_negative(), initial_states(), npar(), pars(), fixture, parametrize, Test di ``fieldwise.nitrogen`` (bilancio dell'azoto e dell'humus a fine… (+40 more)

### Community 43 - "humus_balance_residual"
Cohesion: 0.50
Nodes (4): humus_balance_residual(), Scarto di chiusura [t SO/ha]: (H1 - H0) - (H_res + H_cov - H_min)., humus_balance_residual(), Scarto di chiusura dell'humus [t SO/ha] (vedi `humus.humus_balance_residual`).

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
Cohesion: 0.12
Nodes (11): compliance(), enumerate_rotations(), main_crops(), Etichetta leggibile, es. 'mais > soia+cover > frumento'., Permutazione ciclica che parte dalla coltura k., Rappresentante della classe di permutazioni cicliche (minimo lessicografico)., Colture principali di crops.yaml: le voci con un ciclo fenologico…, Stato di conformita' ai disciplinari della sequenza ``crops`` (cover ignorate,… (+3 more)

### Community 51 - "WaterResult"
Cohesion: 0.22
Nodes (10): aggregate_segments(), _cap_array(), ndarray, Uscite giornaliere [mm o -] e stato iniziale/finale. etc, eta, ks, kr, irr,…, Scarto di chiusura [mm] su tutta la serie: (S_fine - S_inizio) - (P + I - RO -…, Scarto giornaliero [mm] dello stesso bilancio (deve essere ~0 ogni giorno)., Somme per segmento: days, rain, eta, etc, irr, runoff, dp [mm] e storage_end…, water_balance_daily_residual() (+2 more)

### Community 52 - "_make_smap"
Cohesion: 0.33
Nodes (6): _make_smap(), parametrize, _smap_datasets(), test_smap_extract_fill_values_become_nan(), test_smap_extract_full_and_subset(), test_smap_extract_wrong_pixel_index_raises()

### Community 53 - "fake_net"
Cohesion: 0.40
Nodes (5): fake_net(), fixture, Cache temporanea; online di default; nessuna chiamata di rete ammessa., Login e ricerca CMR finti; registra le chiamate. Le estrazioni le fornisce il…, tmp_cache()

### Community 54 - "_make_imerg_subset"
Cohesion: 0.50
Nodes (4): _centers(), _make_imerg_subset(), Sottoinsieme OPeNDAP finto: precipitation(1, 2, 2) in ordine (time, lon, lat)., test_imerg_extract_from_opendap_subset_and_center_check()

### Community 55 - "run_water_balance"
Cohesion: 0.40
Nodes (4): DailyInputs, Serie giornaliere della rotazione (tutte lunghe n). et0, rain [mm/g]; kc [-]…, Bilancio idrico giornaliero su tutta la serie, in un unico ciclo. irr_cap:…, run_water_balance()

### Community 56 - "root_depth"
Cohesion: 0.50
Nodes (4): cover_daily_curves(), Profondita' radicale [m]: lineare da zr_ini alla semina a zr_max a fine fase di…, Serie (kc, zr, p_tab) della cover crop (cover_crop.yaml acqua.*): Kc costante;…, root_depth()

### Community 57 - "soil_from_params"
Cohesion: 0.50
Nodes (4): Acqua totale evaporabile [mm]. FAO-56 eq. 73: TEW = 1000 (theta_FC - 0.5…, Costruisce i parametri idrici dal dizionario di…, soil_from_params(), tew_fao56()

### Community 58 - "_make_imerg_full"
Cohesion: 0.50
Nodes (4): _make_imerg_full(), Granulo IMERG finto con la struttura vera: precipitation(time=1, lon=3600,…, test_imerg_extract_fill_value_becomes_nan(), test_imerg_extract_from_full_granule()

### Community 62 - "_fake_row"
Cohesion: 0.67
Nodes (3): _fake_row(), test_imerg_old_single_cell_raw_is_rejected_and_redownloaded(), test_imerg_resume_from_partial_year()

## Knowledge Gaps
- **41 isolated node(s):** `fieldwise`, `graphify`, `graphify`, `Principi non negoziabili`, `Decisioni prese` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 500 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SoilWaterParams` connect `SoilWaterParams` to `WaterState`, `run_water_balance`, `soil_from_params`, `water.py`, `__init__.py`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `Rotation` connect `Rotation` to `rotation.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **What connects `fieldwise`, `graphify`, `graphify` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_data_modis.py` be split into smaller, more focused modules?**
  _Cohesion score 0.11076923076923077 - nodes in this community are weakly interconnected._
- **Should `et0.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10505050505050505 - nodes in this community are weakly interconnected._
- **Should `test_data_earthdata.py` be split into smaller, more focused modules?**
  _Cohesion score 0.08 - nodes in this community are weakly interconnected._
- **Should `params.py` be split into smaller, more focused modules?**
  _Cohesion score 0.12012012012012012 - nodes in this community are weakly interconnected._