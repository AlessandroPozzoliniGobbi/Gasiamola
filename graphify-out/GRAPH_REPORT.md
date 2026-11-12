# Graph Report - nasa  (2026-11-12)

## Corpus Check
- 31 files · ~81,064 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 702 nodes · 1264 edges · 40 communities (36 shown, 4 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.82)
- Token cost: 0 input · 0 output

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
- qc.py
- test_et0.py
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
- WaterResult
- crop_daily_curves
- Revisione indipendente dei parametri FIELDWISE
- WaterState
- run_water_balance
- root_depth
- soil_from_params
- weather.py
- config.py

## God Nodes (most connected - your core abstractions)
1. `by_name()` - 31 edges
2. `run_checks()` - 26 edges
3. `make_power()` - 25 edges
4. `_a()` - 20 edges
5. `_out()` - 20 edges
6. `Check` - 15 edges
7. `_skip()` - 14 edges
8. `SoilWaterParams` - 13 edges
9. `power_checks()` - 13 edges
10. `check_power()` - 12 edges

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

## Communities (40 total, 4 thin omitted)

### Community 0 - "run_segment"
Cohesion: 0.17
Nodes (15): kc_and_roots(), Quanto chiede la pianta e fin dove arriva, al giorno d dalla semina. Kc segue…, Fa avanzare l'acqua del suolo dal giorno i0 al giorno i1 (escluso). Un…, run_segment(), Crop parameter table (maize, soybean, wheat), ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves), FAO-33 yield response to water (Doorenbos and Kassam, 1979), FAO-56 crop water use (Allen et al., 1998) (+7 more)

### Community 1 - "test_data_modis.py"
Cohesion: 0.11
Nodes (16): datetime, FakeService, pixel_values(), fixture, Test del client MODIS: nessuna rete (requests.get sostituito), cartelle…, (ndvi grezzo, affidabilita', vi_quality) dei 9 pixel di una data. Data 0: tutti…, _Resp, run_fetch() (+8 more)

### Community 2 - "et0.py"
Cohesion: 0.11
Nodes (44): _a(), actual_vapour_pressure(), atmospheric_pressure(), clear_sky_radiation(), daylight_hours(), et0_from_power(), et0_hargreaves(), et0_penman_monteith() (+36 more)

### Community 3 - "fieldwise_engine.py"
Cohesion: 0.16
Nodes (13): dataclasses, itertools, Crop, fetch_power(), load_weather(), FIELDWISE - motore di simulazione delle rotazioni colturali…, Scarica il meteo giornaliero da NASA POWER. Non serve nessun login.…, Meteo FINTO con stagioni tipo Pianura Padana. Serve SOLO a collaudare il codice… (+5 more)

### Community 4 - "test_data_earthdata.py"
Cohesion: 0.05
Nodes (22): date, _Auth, fake_net(), _granule(), _make_imerg_full(), _make_imerg_subset(), _make_smap(), fixture (+14 more)

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
Cohesion: 0.12
Nodes (6): FIELDWISE - confronto di rotazioni colturali con bilanci di massa giornalieri., fake_net(), fixture, Test del client NASA POWER, senza rete e senza toccare la cache vera., _Resp, tmp_cache()

### Community 9 - "test_data_soilgrids.py"
Cohesion: 0.09
Nodes (14): fake_wcs_http(), FakeResp, make_tiff(), mapped(), fixture, ndarray, Test del client SoilGrids: nessuna rete, cartelle temporanee, risposte finte., rest_ok() (+6 more)

### Community 10 - "test_params.py"
Cohesion: 0.16
Nodes (23): assumed(), make_tree(), one_error(), Path, Test del caricatore/validatore dei parametri (contratto: params/SCHEMA.md)., sourced(), test_error_reports_dotted_path(), test_interval_rule() (+15 more)

### Community 11 - "Fonti di `params/crops.yaml`"
Cohesion: 0.25
Nodes (7): Altro (dichiarato, non ufficiale), Articoli peer-reviewed e atti, Dati usati solo per conversioni e controlli, Enti pubblici italiani, Fonti cercate ma non leggibili, Fonti di `params/crops.yaml`, Manuali FAO

### Community 12 - "Fonti di `params/nitrogen.yaml`"
Cohesion: 0.25
Nodes (7): 1. Regione Emilia-Romagna — Disciplinari di produzione integrata 2023, Norme generali, 2. Regione Lombardia — Programma d'azione nitrati 2024-2027 (zone vulnerabili), 3. Salvagiotti et al. (2008), 4. Mémento Sols et Matières Organiques (Agro-Transfert, 2007), 5. SWAT — documentazione teorica e di input, Fonti cercate e non usate, Fonti di `params/nitrogen.yaml`

### Community 13 - "FIELDWISE — piano di lavoro"
Cohesion: 0.29
Nodes (6): Blocchi aperti, Decisioni prese, FIELDWISE — piano di lavoro, Principi non negoziabili, Registro, Stato delle fasi

### Community 18 - "test_qc.py"
Cohesion: 0.08
Nodes (68): main(), Series, rain_annual_table(), Tabella annua POWER contro riferimento + statistiche di sintesi. ``ref``:…, _ref_frame(), by_name(), env(), make_arpa() (+60 more)

### Community 19 - "qc.py"
Cohesion: 0.12
Nodes (49): build_auto_block(), _cell(), Check, check_arpa_completeness(), check_et0(), check_imerg(), check_istat(), check_modis() (+41 more)

### Community 20 - "test_et0.py"
Cohesion: 0.06
Nodes (7): pandas, Test di ``fieldwise.et0`` sugli esempi svolti di FAO-56 (Allen et al. 1998). I…, TestCapitolo3, TestComportamento, TestEsempio17Bangkok, TestEsempio18Uccle, TestEsempio20Lione

### Community 21 - "simulate_rotation"
Cohesion: 0.15
Nodes (15): next_date(), Aggiorna st["N"] e st["H"] alla fine di un segmento, usando i totali calcolati…, Prima data (mese, giorno) uguale o successiva a 'after'. Esempio: dopo il 20…, Simula una rotazione completa partendo da un certo anno. seq lista di Crop, per…, simulate_rotation(), update_soil(), FIELDWISE - Proposta di modello (document), Bare soil (Kc 0.25, Zr 0.30 m) and cover crop (Kc 0.60, Zr 0.60 m) parameters (+7 more)

### Community 22 - "Dynamic vectors approach F(t), C(t) and its four problems"
Cohesion: 0.29
Nodes (8): Dynamic vectors approach F(t), C(t) and its four problems, Exhaustive enumeration of 216 rotations (3 crops in 3 positions) instead of gradient, Ranking of rotations with farmer-chosen weights, Nonlinear differential equation system solved with 1-day Euler steps, Nonlinear plant response (stress threshold, leaching excess), Physical mass balances of water, nitrogen and organic matter, Soil and crop are coupled (crop consumes soil water), Weighted compatibility score has no unit of measure

### Community 23 - "hargreaves_et0"
Cohesion: 0.29
Nodes (5): hargreaves_et0(), Serie meteo giornaliera pronta per il motore. Converte la tabella in array…, Converte una data nella posizione corrispondente negli array., ET0 (mm/giorno) con la formula di Hargreaves, FAO-56 equazione 52. ET0 e'…, Weather

### Community 24 - "Tabella dei parametri"
Cohesion: 0.29
Nodes (6): cover_crop, crops, heat, nitrogen, rotation_rules, Tabella dei parametri

### Community 25 - "Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml"
Cohesion: 0.33
Nodes (5): Caldo in fioritura, Cover crop, Disciplinari e norme regionali, Fonti: rotation_rules.yaml, heat.yaml, cover_crop.yaml, Letteratura su rese e rotazione

### Community 26 - "Soil"
Cohesion: 0.33
Nodes (4): Proprieta' fisse del suolo. Valori di default: suolo franco tipico. Per un…, TAW, acqua totale disponibile nell'intero profilo, in mm. (fc - wp) e' l'acqua…, Humus iniziale dei primi 30 cm, in t/ha. % sostanza organica x densita' (t/m3)…, Soil

### Community 27 - "test_soil.py"
Cohesion: 0.06
Nodes (30): math, numpy, aquacrop_tau(), engine_layers(), horizons_from_aggregated(), hydrologic_soil_group(), profile_properties(), ndarray (+22 more)

### Community 28 - "ensemble"
Cohesion: 0.50
Nodes (4): ensemble(), label(), Nome leggibile della rotazione, es. 'mais > soia+cover > frumento'., Prova TUTTE le rotazioni su TUTTE le annate di partenza. Rotazioni: 3 colture…

### Community 29 - "water.py"
Cohesion: 0.18
Nodes (13): cn_class(), _kernel(), njit(), p_adjusted(), Bilancio idrico giornaliero a due strati (FAO-56, Allen et al. 1998, cap. 7 e…, RHmin [%] stimata con Tdew ~ Tmin. FAO-56 eq. 63: RHmin = 100…, Frazione di esaurimento corretta con l'ETc del giorno [mm/g]. FAO-56 tab. 22,…, Classe di Curve Number di soil.yaml per una coltura/superficie ('mais','soia'… (+5 more)

### Community 30 - "SoilWaterParams"
Cohesion: 0.15
Nodes (5): Parametri idrici del profilo a due strati (da soil.yaml e…, TAW dello strato 1 [mm], FAO-56 eq. 82., TAW dello strato 2 [mm], FAO-56 eq. 82., Acqua a saturazione dell'intero profilo [mm] (serve alla lisciviazione)., SoilWaterParams

### Community 31 - "WaterResult"
Cohesion: 0.22
Nodes (10): aggregate_segments(), _cap_array(), ndarray, Uscite giornaliere [mm o -] e stato iniziale/finale. etc, eta, ks, kr, irr,…, Scarto di chiusura [mm] su tutta la serie: (S_fine - S_inizio) - (P + I - RO -…, Scarto giornaliero [mm] dello stesso bilancio (deve essere ~0 ogni giorno)., Somme per segmento: days, rain, eta, etc, irr, runoff, dp [mm] e storage_end…, water_balance_daily_residual() (+2 more)

### Community 32 - "crop_daily_curves"
Cohesion: 0.22
Nodes (10): crop_daily_curves(), kc_climate_correction(), kc_curve(), kc_end_climate_correction(), Frazioni di sviluppo a fine fase iniziale, sviluppo e piena stagione, dalle…, Kc a quattro tratti in funzione della frazione di sviluppo `frac` in [0, 1].…, Kc mid corretto per il clima. FAO-56 eq. 62: Kc = Kc(tab) + [0.04 (u2 - 2) -…, Kc end corretto per il clima. FAO-56 eq. 65 (stessa forma di eq. 62), che si… (+2 more)

### Community 33 - "Revisione indipendente dei parametri FIELDWISE"
Cohesion: 0.33
Nodes (5): 1. Verifiche sulle fonti (29 voci), 2. Onestà dei campi, 3. Coerenza tra file (conti a mano), 4. Correzioni prima di scrivere il motore (in ordine di importanza), Revisione indipendente dei parametri FIELDWISE

### Community 34 - "WaterState"
Cohesion: 0.33
Nodes (4): initial_water_state(), Stato idrico del suolo (mai azzerato tra i segmenti). w1, w2 [mm]: acqua negli…, Stato iniziale: theta = wp + frazione (fc - wp) in ciascuno strato (soil.yaml…, WaterState

### Community 35 - "run_water_balance"
Cohesion: 0.40
Nodes (4): DailyInputs, Serie giornaliere della rotazione (tutte lunghe n). et0, rain [mm/g]; kc [-]…, Bilancio idrico giornaliero su tutta la serie, in un unico ciclo. irr_cap:…, run_water_balance()

### Community 36 - "root_depth"
Cohesion: 0.50
Nodes (4): cover_daily_curves(), Profondita' radicale [m]: lineare da zr_ini alla semina a zr_max a fine fase di…, Serie (kc, zr, p_tab) della cover crop (cover_crop.yaml acqua.*): Kc costante;…, root_depth()

### Community 37 - "soil_from_params"
Cohesion: 0.50
Nodes (4): Acqua totale evaporabile [mm]. FAO-56 eq. 73: TEW = 1000 (theta_FC - 0.5…, Costruisce i parametri idrici dal dizionario di…, soil_from_params(), tew_fao56()

### Community 38 - "weather.py"
Cohesion: 0.29
Nodes (14): _apply_rain(), _apply_temp(), available_years(), load_forcing(), _load_power(), _point_dir(), DataFrame, Series (+6 more)

### Community 39 - "config.py"
Cohesion: 0.40
Nodes (4): os, offline(), Percorsi e costanti condivise da tutto il progetto. Nessun parametro agronomico…, True se la rete e' vietata (demo): i client devono usare solo la cache.

## Knowledge Gaps
- **39 isolated node(s):** `fieldwise`, `graphify`, `graphify`, `Principi non negoziabili`, `Decisioni prese` (+34 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 317 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `SoilWaterParams` connect `SoilWaterParams` to `soil_from_params`, `WaterState`, `run_water_balance`, `water.py`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `run_segment()` connect `run_segment` to `fieldwise_engine.py`, `simulate_rotation`, `Dynamic vectors approach F(t), C(t) and its four problems`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **Why does `simulate_rotation()` connect `simulate_rotation` to `run_segment`, `fieldwise_engine.py`, `ensemble`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **What connects `fieldwise`, `graphify`, `graphify` to the rest of the system?**
  _39 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `test_data_modis.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10541310541310542 - nodes in this community are weakly interconnected._
- **Should `et0.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10505050505050505 - nodes in this community are weakly interconnected._
- **Should `test_data_earthdata.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05353535353535353 - nodes in this community are weakly interconnected._