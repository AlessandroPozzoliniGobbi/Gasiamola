# Contratto Dati Simulazione Climatica Futura (CMIP6 / Delta Change)
**Destinatario:** Alessandro (Frontend & UI Integration)  
**Modulo Python:** `fieldwise.future`, `fieldwise.data.cmip6`  
**Data aggiornamento:** 14 Novembre 2026  

---

## 1. Visione Generale

Il modulo futuro di FieldWise consente all'agricoltore e al consulente agronomico di proiettare l'impatto del cambiamento climatico sulla rotazione colturale attuale e confrontarla con le migliori rotazioni alternative.

Le proiezioni utilizzano il metodo **Delta Change** mensile validato scientificamente (consenso CMIP6 per la pianura padana / Nord Italia), scalato linearmente sull'orizzonte temporale scelto e applicato alla serie storica meteorologica validata NASA POWER, **senza bisogno di chiamate di rete a runtime** (completamente compatibile con `FIELDWISE_OFFLINE=1`).

---

## 2. Orizzonti e Scenari

### Orizzonti Temporali
* **`5` anni** (breve termine)
* **`10` anni** (medio termine – default)
* **`15` anni** (medio-lungo termine)
* **`20` anni** (lungo termine, orizzonte massimo dei delta calibrati)

### Scenari Radiativi IPCC CMIP6
| Codice | Titolo UI | Descrizione per l'utente |
| :--- | :--- | :--- |
| `ssp126` | **Sostenibile (SSP1-2.6)** | Transizione ecologica rapida e taglio delle emissioni, riscaldamento contenuto sotto +2°C. |
| `ssp245` | **Tendenziale (SSP2-4.5)** | Politiche attuali lungo il trend storico recente, estati progressivamente più calde e asciutte. |
| `ssp585` | **Estremo (SSP5-8.5)** | Alte emissioni da fonti fossili, massima frequenza di ondate di calore e siccità severa. |

---

## 3. Funzioni Python per il Frontend

Tutte le funzioni sono importabili direttamente da `fieldwise.future`:

```python
from fieldwise.future import (
    load_future_payload,
    load_future_ranking,
    load_future_timeseries,
    get_future_simulation_payload,
    run_all_ssps_horizons,
)
```

### 3.1 `load_future_payload(lat=45.2, lon=10.0) -> dict`
Legge istantaneamente il file pre-calcolato `future_dashboard_summary.json` dalla cache di elaborazione del punto.
* **Input:** `lat, lon` (opzionali, default punto pilota).
* **Output:** Dizionario indicizzato per chiave `"{ssp_code}_{orizzonte}a"`, ad esempio:
  * `"ssp126_5a"`, `"ssp126_10a"`, `"ssp126_15a"`, `"ssp126_20a"`
  * `"ssp245_5a"`, `"ssp245_10a"`, `"ssp245_15a"`, `"ssp245_20a"`
  * `"ssp585_5a"`, `"ssp585_10a"`, `"ssp585_15a"`, `"ssp585_20a"`

### 3.2 `load_future_ranking(lat=45.2, lon=10.0) -> pd.DataFrame`
Carica il DataFrame della classifica completa di tutte le rotazioni simulate per scenario ed orizzonte (`future_rotations_ranking.csv`).

### 3.3 `load_future_timeseries(lat=45.2, lon=10.0) -> pd.DataFrame`
Carica il DataFrame con le serie temporali (inclusa baseline a orizzonte 0) per alimentare gli 8 grafici interattivi del pulsante `FULL ANALYSIS` (`future_full_analysis_timeseries.csv`).

### 3.4 `get_future_simulation_payload(...) -> dict`
Calcola on-demand un singolo payload piatto per una configurazione specifica se l'utente modifica pesi o scenario irriguo personalizzato:
```python
payload = get_future_simulation_payload(
    lat=45.2,
    lon=10.0,
    horizon_years=10,
    ssp_code="ssp245",
    current_rotation="mais > soia > frumento",
    irrigation_regime="tetto_irriguo",  # "solo_pioggia" | "tetto_irriguo" | "irrigazione_libera"
    weights={"resa": 1.0, "profitto": 1.0, "suolo": 1.0},
)
```

---

## 4. Specifiche dei File Pre-calcolati

I file risiedono in `data/processed/<punto>/` (es. `data/processed/lat45.200_lon10.000/`).

### 4.1 `future_dashboard_summary.json`

Ciascuna chiave (es. `"ssp245_10a"`) contiene un oggetto con le seguenti proprietà:

#### A. Metadati
* `lat`, `lon`: Coordinate del punto.
* `horizon_years`: `5`, `10`, `15` o `20`.
* `ssp_code`: `"ssp126"`, `"ssp245"` o `"ssp585"`.
* `ssp_label`: Titolo formattato (es. `"Tendenziale (SSP2-4.5)"`).
* `ssp_description`: Testo descrittivo dello scenario.
* `current_rotation`: Rotazione attuale impostata (es. `"mais > soia > frumento"`).
* `irrigation_regime`: Regime irriguo applicato (es. `"tetto_irriguo"`).
* `calcolato_il`: Timestamp ISO UTC di calcolo.

#### B. Baseline Storica (Orizzonte Storico)
* `baseline_resa_rel_pct` (%): Indice di resa relativo mediano storico (100% = resa potenziale priva di stress).
* `baseline_resa_t_ha` (t/ha): Resa media ponderata annua in tonnellate/ettaro sul ciclo colturale.
* `baseline_costo_eur_ha` (€/ha/anno): Somma dei costi variabili modellati (irrigazione + concime azotato).
* `baseline_costo_irrigazione_eur_ha` (€/ha/anno): Costo dell'acqua irrigua (`irrigazione_mm * costo_mm`).
* `baseline_costo_concime_eur_ha` (€/ha/anno): Costo del concime azotato (`concime_kg_n * prezzo_N`).
* `baseline_margine_eur_ha` (€/ha/anno): Margine lordo su acqua e concime (**Guadagno Netto** = Ricavo - Costi).
* `baseline_irrigazione_mm` (mm/anno): Volume irriguo annuo medio distribuito.
* `baseline_concime_kg_n_ha` (kg N/ha/anno): Apporto annuo medio di concime chimico azotato.
* `baseline_humus_t_ha` (t/ha): Stock di humus del suolo.
* `baseline_n_lisciviato_kg_n_ha` (kg N/ha/anno): Azoto lisciviato sotto la zona radicale.
* `baseline_et0_ann_mm` (mm/anno): Evapotraspirazione di riferimento Penman-Monteith media annua.
* `baseline_tmean_ann_c` (°C): Temperatura media annua storica.
* `baseline_gdd_base10_ann` (°C·giorno): Somma termica utile (GDD base 10°C).

#### C. Proiezione Futura – Rotazione Attuale
* `future_resa_rel_pct` (%): Resa relativa mediana proiettata nel futuro per la rotazione attuale.
* `future_resa_rel_p10_pct` (%): Resa caso-peggiore (10° percentile, stress severo).
* `future_resa_t_ha` (t/ha): Resa media annua in tonnellate/ettaro proiettata.
* `future_costo_eur_ha` (€/ha/anno): Costo totale annuo futuro modellato.
* `future_costo_irrigazione_eur_ha` (€/ha/anno): Costo irriguo futuro.
* `future_costo_concime_eur_ha` (€/ha/anno): Costo concime futuro.
* `future_margine_eur_ha` (€/ha/anno): Margine lordo / Guadagno annuo futuro.
* `future_margine_p10_eur_ha` (€/ha/anno): Margine caso-peggiore (p10).
* `future_irrigazione_mm` (mm/anno): Fabbisogno irriguo futuro.
* `future_concime_kg_n_ha` (kg N/ha/anno): Concimazione futura necessaria.
* `future_humus_t_ha` (t/ha): Stock di humus futuro.
* `future_n_lisciviato_kg_n_ha` (kg N/ha/anno): Azoto lisciviato futuro.
* `future_et0_ann_mm` (mm/anno): ET0 futura ricalcolata post delta termico e radiativo.
* `future_tmean_ann_c` (°C): Nuova temperatura media annua.
* `future_gdd_base10_ann` (°C·giorno): Nuova somma termica GDD base 10°C.
* `future_hot_days_ann` (giorni/anno): Giorni con temperatura massima superiore a 35°C (stress da calore estremo).

#### D. Delta di Confronto (Futuro vs Baseline)
* `delta_resa_rel_pct` (%): Variazione percentuale della resa (`future_resa_rel_pct - baseline_resa_rel_pct`).
* `delta_costo_eur_ha` (€/ha/anno): Variazione dei costi (`future_costo_eur_ha - baseline_costo_eur_ha`).
* `delta_margine_eur_ha` (€/ha/anno): Variazione del guadagno (`future_margine_eur_ha - baseline_margine_eur_ha`).

#### E. Miglior Rotazione Futura (Opportunità di Adattamento)
* `best_rotation`: Nome della classe ciclica consigliata (es. `"mais > mais > mais"` o `"mais > soia+cover > frumento"`).
* `best_resa_rel_pct` (%): Resa relativa della miglior rotazione nello scenario futuro.
* `best_resa_t_ha` (t/ha): Resa in tonnellate/ettaro della miglior rotazione.
* `best_costo_eur_ha` (€/ha/anno): Costo totale della miglior rotazione.
* `best_margine_eur_ha` (€/ha/anno): Guadagno/Margine della miglior rotazione.
* `best_irrigazione_mm` (mm/anno): Irrigazione richiesta dalla miglior rotazione.
* `best_concime_kg_n_ha` (kg N/ha/anno): Concime richiesto dalla miglior rotazione.
* `delta_guadagno_eur_ha` (€/ha/anno): **Guadagno aggiuntivo** adottando la rotazione consigliata rispetto a mantenere quella attuale (`best_margine - future_margine`).
* `delta_resa_best_pct` (%): Incremento di resa rispetto alla rotazione attuale nel futuro.
* `delta_costo_best_eur_ha` (€/ha/anno): Differenza di costo tra la miglior rotazione e quella attuale.
* `best_posizione`: Posizione in graduatoria multicriterio (1 = prima classificata).
* `best_non_dominata`: `True` se appartiene alla frontiera di Pareto (ottimo non dominato).
* `best_conformita`: Stato di conformità ai disciplinari regionali (`"conforme"`, `"conforme_solo_in_deroga"`, `"non_conforme"`).
* `best_rischi`: Array di stringhe con i rischi ed evidenze normative generati da `ranking.confronta` (es. non conformità al disciplinare, superamento limite azoto).

---

### 4.2 `future_rotations_ranking.csv`

Tabella per alimentare tabelle di classifica e matrici di confronto per tutte le 12 combinazioni:

| Colonna | Tipo | Descrizione |
| :--- | :--- | :--- |
| `ssp_code` | `str` | `"ssp126"`, `"ssp245"`, `"ssp585"` |
| `horizon_years` | `int` | `5`, `10`, `15`, `20` |
| `classe` | `str` | Etichetta canonica della rotazione (es. `"mais > soia > frumento"`) |
| `posizione` | `int` | Rango (1 = migliore) secondo i pesi multicriterio |
| `punteggio` | `float` | Punteggio sintetico normalizzato (0..1) |
| `resa_rel_mediana` | `float` | Resa relativa mediana (0..1) |
| `resa_rel_p10` | `float` | Resa relativa percentile 10 (caso sfavorevole) |
| `margine_lordo_eur_ha` | `float` | Margine lordo annuo (€/ha) |
| `irrigazione_mm` | `float` | Irrigazione media annua (mm) |
| `concime_kg_n_ha` | `float` | Concime azotato medio annuo (kg N/ha) |
| `n_lisciviato_kg_n_ha` | `float` | Azoto lisciviato medio annuo (kg N/ha) |
| `humus_t_ha` | `float` | Stock finale medio di humus (t/ha) |
| `non_dominata` | `bool` | `True` se la soluzione è sulla frontiera di Pareto |

---

### 4.3 `future_full_analysis_timeseries.csv`

Tabella temporale orizzontale ottimizzata per i grafici Plotly del pulsante `FULL ANALYSIS`:

| Colonna | Unità | Uso nel grafico |
| :--- | :--- | :--- |
| `ssp_code` | stringa | Filtro scenario selezionato |
| `horizon_years` | anni (`0, 5, 10, 15, 20`) | **Asse X** di tutti i grafici (0 = baseline storica) |
| `rotation` | stringa | Raggruppamento serie (rotazione attuale vs miglior rotazione) |
| `is_current` | booleano | Identifica se è la rotazione attuale dell'agricoltore |
| `tmean_ann_c` | °C | **Grafico 1: Temperatura & GDD** (temperatura media annua) |
| `tmax_ann_c` | °C | **Grafico 1: Temperatura & GDD** (temperatura massima) |
| `gdd_base10_ann` | °C·giorno | **Grafico 1: Temperatura & GDD** (gradi giorno utili, asse Y2) |
| `hot_days_ann` | giorni/anno | **Grafico 1: Temperatura & GDD** (giorni con Tmax > 35°C) |
| `et0_ann_mm` | mm/anno | **Grafico 2: Bilancio Idrico** (evapotraspirazione riferimento ET0) |
| `eta_ann_mm` | mm/anno | **Grafico 2: Bilancio Idrico** (evapotraspirazione effettiva ETa) |
| `irrigazione_mm` | mm/anno | **Grafico 2: Bilancio Idrico** (volume irriguo somministrato) |
| `rain_ann_mm` | mm/anno | **Grafico 2: Bilancio Idrico** (precipitazione annua media) |
| `deficit_stress_ks` | indice 0..1 | **Grafico 3: Deficit & Stress Ks** (stress da deficit idrico = `1 - f_acqua`) |
| `f_acqua` | indice 0..1 | **Grafico 3: Deficit & Stress Ks** (fattore idrico FAO) |
| `concime_kg_n_ha` | kg N/ha | **Grafico 4: Azoto** (concime chimico distribuito) |
| `n_lisciviato_kg_n_ha` | kg N/ha | **Grafico 4: Azoto** (lisciviazione nitrati nelle falde) |
| `deficit_n_kg_n_ha` | kg N/ha | **Grafico 4: Azoto** (fabbisogno azotato insoddisfatto) |
| `humus_t_ha` | t/ha | **Grafico 5: Humus** (evoluzione sostanza organica/humus) |
| `costo_eur_ha` | €/ha/anno | **Grafico 6: Costo** (costo totale variabile concime + acqua) |
| `costo_irrigazione_eur_ha`| €/ha/anno | **Grafico 6: Costo** (scomposizione costo irriguo) |
| `costo_concime_eur_ha` | €/ha/anno | **Grafico 6: Costo** (scomposizione costo concime) |
| `resa_rel_pct` | % | **Grafico 7: Resa** (resa relativa % potenziale) |
| `resa_t_ha` | t/ha | **Grafico 7: Resa** (resa in tonnellate/ha) |
| `margine_eur_ha` | €/ha/anno | **Grafico 8: Guadagno** (margine netto / guadagno economico) |
| `ricavo_eur_ha` | €/ha/anno | **Grafico 8: Guadagno** (ricavo lordo granella) |

---

## 5. Modello Economico Integrato (`economics.py`)

I calcoli economici riflettono la formula ufficiale di `fieldwise.economics`:

$$\text{Ricavo} = \frac{\sum_{i} \text{Resa}_i \times \text{Prezzo}_i}{\text{Anni del ciclo}}$$

$$\text{Costo Concime} = \text{Concime (kg N/ha/anno)} \times \text{Prezzo N (€/kg N)}$$

$$\text{Costo Irrigazione} = \text{Irrigazione (mm/anno)} \times \text{Costo mm (€/mm)}$$

$$\text{Costo Totale} = \text{Costo Concime} + \text{Costo Irrigazione}$$

$$\text{Guadagno (Margine Lordo)} = \text{Ricavo} - \text{Costo Totale}$$

Tutti i parametri economici unitari sono caricati automaticamente da `params/economia.yaml`.
