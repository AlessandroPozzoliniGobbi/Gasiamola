# Graph Report - nasa  (2026-11-11)

## Corpus Check
- Corpus is ~3,929 words - fits in a single context window. You may not need a graph.

## Summary
- 74 nodes · 107 edges · 9 communities (4 shown, 5 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.82)
- Token cost: 79,396 input · 0 output

## Community Hubs (Navigation)
- Bilancio idrico FAO-56
- Catena di rotazione e azoto-humus
- Motivazioni del modello a bilanci
- Meteo e ET0 Hargreaves
- Download NASA POWER
- Parametri coltura (Crop)
- Suolo (TAW, humus)
- Ensemble delle rotazioni
- Meteo sintetico di test

## God Nodes (most connected - your core abstractions)
1. `simulate_rotation()` - 10 edges
2. `run_segment()` - 8 edges
3. `ensemble()` - 7 edges
4. `hargreaves_et0()` - 6 edges
5. `Ks water stress coefficient and ETa = Ks x ETc` - 6 edges
6. `fetch_power()` - 5 edges
7. `synthetic_weather()` - 5 edges
8. `update_soil()` - 5 edges
9. `load_weather()` - 5 edges
10. `Dynamic vectors approach F(t), C(t) and its four problems` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `run_segment()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Nonlinear differential equation system solved with 1-day Euler steps` --conceptually_related_to--> `update_soil()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves)` --implements--> `hargreaves_et0()`  [EXTRACTED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `NASA POWER real weather 2000-2025` --implements--> `fetch_power()`  [EXTRACTED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py
- `Kc crop coefficient (four phases) and ETc = Kc x ET0` --implements--> `kc_and_roots()`  [INFERRED]
  legacy/FIELDWISE_proposta_modello.pdf → legacy/fieldwise_engine.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **FAO water-stress to yield chain (ET0, Kc, TAW/RAW, Ks, Ky)** — legacy_fieldwise_proposta_modello_et0, legacy_fieldwise_proposta_modello_kc_crop_coefficient, legacy_fieldwise_proposta_modello_taw_raw, legacy_fieldwise_proposta_modello_ks_stress, legacy_fieldwise_proposta_modello_ky_yield_response [EXTRACTED 1.00]
- **Engine nested computation: daily water step, end-of-segment N/humus, rotation chain, ensemble** — legacy_fieldwise_proposta_modello_daily_water_step, legacy_fieldwise_proposta_modello_nitrogen_humus_accounting, legacy_fieldwise_proposta_modello_segment, legacy_fieldwise_proposta_modello_exhaustive_enumeration [EXTRACTED 1.00]
- **Four problems of the dynamic-vectors approach** — legacy_fieldwise_proposta_modello_weighted_score_no_units, legacy_fieldwise_proposta_modello_soil_crop_coupling, legacy_fieldwise_proposta_modello_nonlinear_plant_response, legacy_fieldwise_proposta_modello_dynamic_vectors_problem [EXTRACTED 1.00]

## Communities (9 total, 5 thin omitted)

### Community 0 - "Bilancio idrico FAO-56"
Cohesion: 0.15
Nodes (15): kc_and_roots(), run_segment(), Bare soil (Kc 0.25, Zr 0.30 m) and cover crop (Kc 0.60, Zr 0.60 m) parameters, Crop parameter table (maize, soybean, wheat), Daily water step (8 passes: surface demand, root water, irrigation 40 mm, stress, consumption, balance, rain runoff >60 mm), ET0 reference evapotranspiration (Penman-Monteith vs Hargreaves), FAO-33 yield response to water (Doorenbos and Kassam, 1979), FAO-56 crop water use (Allen et al., 1998) (+7 more)

### Community 1 - "Catena di rotazione e azoto-humus"
Cohesion: 0.20
Nodes (7): next_date(), simulate_rotation(), update_soil(), FIELDWISE - Proposta di modello (document), NASA Space Apps Challenge 'Field Shift: Adapting Farms with NASA Data', Simple nitrogen and humus accounting (inputs and outputs, leaching, mineralization), Soil state replacing F(t): D (water deficit mm), N (kg/ha mineral nitrogen), H (t/ha humus)

### Community 2 - "Motivazioni del modello a bilanci"
Cohesion: 0.22
Nodes (7): Dynamic vectors approach F(t), C(t) and its four problems, Engine code structure (blocks 0-4: params, weather, water, N/humus, rotation, ensemble), Exhaustive enumeration of 216 rotations (3 crops in 3 positions) instead of gradient, Ranking of rotations with farmer-chosen weights, Nonlinear differential equation system solved with 1-day Euler steps, Physical mass balances of water, nitrogen and organic matter, Segment (crop sowing-to-harvest or fallow/cover-crop interval)

### Community 4 - "Download NASA POWER"
Cohesion: 0.33
Nodes (3): fetch_power(), load_weather(), NASA POWER real weather 2000-2025

## Knowledge Gaps
- **5 isolated node(s):** `NASA Space Apps Challenge 'Field Shift: Adapting Farms with NASA Data'`, `FAO-33 yield response to water (Doorenbos and Kassam, 1979)`, `Maize (mais): sown 10 April, 150 days, Ky 1.25`, `Soybean (soia): sown 5 May, 140 days, Ky 0.85`, `Wheat (frumento): sown 25 October, 240 days, Ky 1.05`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 27 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_segment()` connect `Bilancio idrico FAO-56` to `Catena di rotazione e azoto-humus`, `Motivazioni del modello a bilanci`, `Parametri coltura (Crop)`?**
  _High betweenness centrality (0.226) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `run_segment()` (e.g. with `Ks water stress coefficient and ETa = Ks x ETc` and `Ky yield response factor: 1 - Y/Ymax = Ky x (1 - ETa/ETc)`) actually correct?**
  _`run_segment()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **What connects `NASA Space Apps Challenge 'Field Shift: Adapting Farms with NASA Data'`, `FAO-33 yield response to water (Doorenbos and Kassam, 1979)`, `Maize (mais): sown 10 April, 150 days, Ky 1.25` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Why does `simulate_rotation()` connect `Catena di rotazione e azoto-humus` to `Bilancio idrico FAO-56`, `Motivazioni del modello a bilanci`, `Parametri coltura (Crop)`, `Ensemble delle rotazioni`, `Meteo sintetico di test`?**
  _High betweenness centrality (0.188) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `Ks water stress coefficient and ETa = Ks x ETc` (e.g. with `run_segment()` and `Ky yield response factor: 1 - Y/Ymax = Ky x (1 - ETa/ETc)`) actually correct?**
  _`Ks water stress coefficient and ETa = Ks x ETc` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Why does `Soil` connect `Suolo (TAW, humus)` to `Parametri coltura (Crop)`?**
  _High betweenness centrality (0.132) - this node is a cross-community bridge._