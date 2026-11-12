# Graph Report - nasa  (2026-11-12)

## Corpus Check
- 154 files · ~114,852 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1160 nodes · 2144 edges · 64 communities (55 shown, 9 thin omitted)
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
- __init__.py
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
- water.py
- SoilWaterParams
- nitrogen.py
- crop_daily_curves_gdd
- Revisione indipendente dei parametri FIELDWISE
- WaterState
- HumusParams
- yield_model.py
- rotation.py
- weather.py
- test_water.py
- simulate
- TestSupporto
- test_nitrogen.py
- NState
- heat_factor
- NitrogenParams
- run_daily
- test_phenology.py
- test_yield_model.py
- test_humus.py
- Rotation
- WaterResult
- _make_smap
- fake_net
- _make_imerg_subset
- run_water_balance
- compliance
- soil_from_params
- _make_imerg_full
- initial_state
- _Auth
- _fake_row
- _granule
- _frame

## God Nodes (most connected - your core abstractions)
1. `by_name()` - 31 edges
2. `run_checks()` - 26 edges
3. `water()` - 26 edges
4. `make_power()` - 25 edges
5. `build_context()` - 21 edges
6. `_a()` - 20 edges
7. `_out()` - 20 edges
8. `state_with()` - 18 edges
9. `simulate()` - 17 edges
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

## Communities (64 total, 9 thin omitted)

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

### Community 8 - "__init__.py"
Cohesion: 0.04
Nodes (13): numpy, FIELDWISE - confronto di rotazioni colturali con bilanci di massa giornalieri., fake_net(), fixture, Test del client NASA POWER, senza rete e senza toccare la cache vera., _Resp, tmp_cache(), Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998). I… (+5 more)

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
Cohesion: 0.08
Nodes (36): calendar_from_cum(), crop_pheno_params(), cumulative_gdd(), cycle_calendar(), cycle_calendars(), CycleCalendar, daily_gdd(), event_table() (+28 more)

### Community 20 - "humus.py"
Cohesion: 0.21
Nodes (12): dataclasses, grain_moisture(), humus_params(), k2_from_params(), Bilancio dell'humus (sostanza organica stabile) a fine segmento, modello Henin-…, Costruisce `HumusParams` da `fieldwise.params.load_params()` (albero grezzo)., Classe ER (k2, n_pronto, fattore_dispersione) dalla classe USDA di soil.yaml., C/N dell'humus implicito in n_humus e fattore_so_c: C/N = (1/fattore_so_c) /… (+4 more)

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
Cohesion: 0.14
Nodes (17): cn_class(), cn_class_index(), _de_consistent(), _kernel(), njit(), p_adjusted(), Bilancio idrico giornaliero a due strati (FAO-56, Allen et al. 1998, cap. 7 e…, RHmin [%] stimata con Tdew ~ Tmin. FAO-56 eq. 63: RHmin = 100… (+9 more)

### Community 30 - "SoilWaterParams"
Cohesion: 0.13
Nodes (6): Parametri idrici del profilo a due strati (da soil.yaml e…, TAW dello strato 1 [mm], FAO-56 eq. 82., TAW dello strato 2 [mm], FAO-56 eq. 82., Limite inferiore dell'acqua nello strato 1 [mm]: i primi Ze m a 0,5 theta_WP…, Acqua a saturazione dell'intero profilo [mm] (serve alla lisciviazione)., SoilWaterParams

### Community 31 - "nitrogen.py"
Cohesion: 0.14
Nodes (18): _credit(), _humify_fresh(), initial_n_min(), _kernel(), _mas(), nitrogen_params(), Bilancio di massa dell'azoto del suolo a passo giornaliero (FIELDWISE).…, (credito con residui interrati, con residui asportati) da… (+10 more)

### Community 32 - "crop_daily_curves_gdd"
Cohesion: 0.16
Nodes (16): crop_daily_curves_gdd(), Serie (kc, zr, p_tab) del ciclo, lunghe ``cal.n_days``, con la frazione di…, cover_daily_curves(), crop_daily_curves(), kc_climate_correction(), kc_curve(), kc_end_climate_correction(), Frazioni di sviluppo a fine fase iniziale, sviluppo e piena stagione, dalle… (+8 more)

### Community 33 - "Revisione indipendente dei parametri FIELDWISE"
Cohesion: 0.33
Nodes (5): 1. Verifiche sulle fonti (29 voci), 2. Onestà dei campi, 3. Coerenza tra file (conti a mano), 4. Correzioni prima di scrivere il motore (in ordine di importanza), Revisione indipendente dei parametri FIELDWISE

### Community 34 - "WaterState"
Cohesion: 0.33
Nodes (4): initial_water_state(), Stato idrico del suolo (mai azzerato tra i segmenti). w1, w2 [mm]: acqua negli…, Stato iniziale: theta = wp + frazione (fc - wp) in ciascuno strato (soil.yaml…, WaterState

### Community 35 - "HumusParams"
Cohesion: 0.16
Nodes (13): equilibrium(), HumusParams, mineralization(), Stock oltre il quale la mineralizzazione resta costante [t SO/ha] (Tab. 1 ER)., H_min = k2 x min(H, H_tetto) x anni_seg [t SO/ha] (Henin-Dupuis; tetto Tab. 1…, SS_res [t s.s./ha] dei residui aerei: granella secca = resa x (1 - umidita);…, H_res = k1_residui x SS_res x c_residui x fattore_so_c [t SO/ha] (Henin-Dupuis,…, Un segmento: H(fine) = H - H_min + H_res + H_cov. Restituisce (H_fine, voci)… (+5 more)

### Community 36 - "yield_model.py"
Cohesion: 0.21
Nodes (13): _clip01(), crop_yield(), _irrigated(), potential_yield(), Modello di resa (fase 4): Y = Y_pot x f_acqua x f_caldo x f_rotazione. Ogni…, f_rotazione di ``crop`` date le due colture principali precedenti (None =…, f_rotazione anno per anno di una rotazione ``sequence`` ripetuta ciclicamente…, Resa potenziale [t/ha] (crops.<crop>.resa_potenziale, umidita' nell'unita'… (+5 more)

### Community 37 - "rotation.py"
Cohesion: 0.13
Nodes (17): build_calendar(), _cap_value(), _cover_window(), _next_sowing(), Catena di rotazione (fase 4): calendario, bilancio idrico unico, azoto/humus,…, Tutto cio' che non dipende dalla rotazione: meteo come array, parametri letti…, Riga del meteo per year-mmdd (puo' essere fuori serie: <0 o > ultima riga)., Calendario, curve (kc, zr, p) e fattore di caldo del ciclo (crop, sow), in… (+9 more)

### Community 38 - "weather.py"
Cohesion: 0.08
Nodes (22): pandas, _apply_rain(), _apply_temp(), available_years(), load_forcing(), _load_power(), _point_dir(), DataFrame (+14 more)

### Community 39 - "test_water.py"
Cohesion: 0.06
Nodes (28): slow, dry_rotation_inputs(), forcing(), maize_inputs(), _maize_season(), _mk(), _one_day(), pars() (+20 more)

### Community 40 - "simulate"
Cohesion: 0.20
Nodes (10): n_balance_residual(), Scarto di chiusura [kg N/ha]: (ENTRATE - USCITE) - (dN_min + dN_res + dN_cov +…, _caps(), _daily_inputs(), ndarray, Esito di ``build_calendar``. Con esito diverso da 'ok' i segmenti sono vuoti., Serie giornaliere della simulazione (in cache nel calendario)., Simula la rotazione dal 1 gennaio di ``anno`` nello ``scenario`` d'acqua (uno… (+2 more)

### Community 42 - "test_nitrogen.py"
Cohesion: 0.10
Nodes (48): assert_closure(), assert_non_negative(), initial_states(), npar(), pars(), fixture, parametrize, Test di ``fieldwise.nitrogen`` (bilancio dell'azoto e dell'humus a fine… (+40 more)

### Community 43 - "NState"
Cohesion: 0.18
Nodes (11): humus_balance_residual(), Scarto di chiusura [t SO/ha]: (H1 - H0) - (H_res + H_cov - H_min)., humus_balance_residual(), NState, Involucro di compatibilita': un segmento con il nucleo giornaliero…, Stato azoto-humus (vedi docstring del modulo). Immutabile: gli aggiornamenti…, Scarto di chiusura dell'humus [t SO/ha] (vedi `humus.humus_balance_residual`)., Applica `update_segment` in sequenza. segmenti: tuple (kind, crop, acqua,… (+3 more)

### Community 44 - "heat_factor"
Cohesion: 0.22
Nodes (11): _aquacrop_daily(), heat_factor(), HeatResult, _linear_daily(), ndarray, f_caldo del ciclo ``cal`` (da ``phenology.cycle_calendar``). metodo: 'deryng'…, Esito di ``heat_factor``. Indici = righe del meteo., Maschera sui giorni del ciclo (sow..maturity) della finestra sensibile (TSP). (+3 more)

### Community 45 - "NitrogenParams"
Cohesion: 0.22
Nodes (9): _bil(), leaching_fraction(), mas_limit(), NitrogenParams, kg N per t SO = n_humus x 1000., MAS [kg N efficiente/ha] = base + max(resa - resa_rif, 0) x fattore_correttivo…, 1 - exp(-D / ((1 - anion_excl) SAT_mm)) (SWAT 2009, eq. 4:2.1.2 e 4:2.1.8)., Voci del bilancio di un segmento (stesse chiavi della versione a fine segmento). (+1 more)

### Community 46 - "run_daily"
Cohesion: 0.25
Nodes (8): cover_humus(), anni_seg = giorni / 365 (nitrogen._meta.convenzioni.tempo)., H_cov = coefficiente_isoumico x biomassa x frazione_C x fattore_so_c [t SO/ha]…, years(), DailyResult, Uscite giornaliere del nucleo: lisciviazione l, N_min a fine giorno, scarto di…, Bilancio dell'azoto e dell'humus a passo giornaliero su tutta la serie (una…, run_daily()

### Community 47 - "test_phenology.py"
Cohesion: 0.12
Nodes (32): assert_ordered(), check_curves(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize (+24 more)

### Community 48 - "test_yield_model.py"
Cohesion: 0.10
Nodes (31): calendar(), constant(), forcing(), make_forcing(), pars(), fixture, parametrize, Test di ``fieldwise.yield_model`` (resa = potenziale x f_acqua x f_caldo x… (+23 more)

### Community 49 - "test_humus.py"
Cohesion: 0.06
Nodes (28): math, aquacrop_tau(), engine_layers(), horizons_from_aggregated(), hydrologic_soil_group(), profile_properties(), ndarray, Proprieta' idrauliche del suolo con le funzioni di pedotrasferimento di Saxton… (+20 more)

### Community 50 - "Rotation"
Cohesion: 0.20
Nodes (5): Etichetta leggibile, es. 'mais > soia+cover > frumento'., Permutazione ciclica che parte dalla coltura k., Rappresentante della classe di permutazioni cicliche (minimo lessicografico)., Sequenza di colture principali e, per ogni coltura, se nell'intervallo che la…, Rotation

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

### Community 56 - "compliance"
Cohesion: 0.33
Nodes (6): compliance(), enumerate_rotations(), main_crops(), Colture principali di crops.yaml: le voci con un ciclo fenologico…, Stato di conformita' ai disciplinari della sequenza ``crops`` (cover ignorate,…, Tutte le rotazioni di ``length`` colture (colture da crops.yaml se ``crops`` e'…

### Community 57 - "soil_from_params"
Cohesion: 0.50
Nodes (4): Acqua totale evaporabile [mm]. FAO-56 eq. 73: TEW = 1000 (theta_FC - 0.5…, Costruisce i parametri idrici dal dizionario di…, soil_from_params(), tew_fao56()

### Community 58 - "_make_imerg_full"
Cohesion: 0.50
Nodes (4): _make_imerg_full(), Granulo IMERG finto con la struttura vera: precipitation(time=1, lon=3600,…, test_imerg_extract_fill_value_becomes_nan(), test_imerg_extract_from_full_granule()

### Community 59 - "initial_state"
Cohesion: 0.50
Nodes (4): initial_humus(), H0 [t SO/ha] = SO% / 100 x prof x 10000 x densita…, initial_state(), Stato iniziale: N_min da n_pronto (Tab. 2 ER), N_res = N_cov = 0, H = H0,…

### Community 62 - "_fake_row"
Cohesion: 0.67
Nodes (3): _fake_row(), test_imerg_old_single_cell_raw_is_rejected_and_redownloaded(), test_imerg_resume_from_partial_year()

## Knowledge Gaps
- **41 isolated node(s):** `fieldwise`, `graphify`, `graphify`, `Principi non negoziabili`, `Decisioni prese` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 505 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_segment()` connect `run_segment` to `fieldwise_engine.py`, `simulate_rotation`, `Dynamic vectors approach F(t), C(t) and its four problems`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Why does `RotationContext` connect `rotation.py` to `simulate`, `phenology.py`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
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