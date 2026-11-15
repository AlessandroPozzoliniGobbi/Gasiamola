# Contratto Dati Beam Search 3-Trienni (9 anni)

**Destinatario:** Alessandro (Frontend & UI Integration)  
**Modulo Python:** `fieldwise.beam_optimizer`  
**Data aggiornamento:** 14 Novembre 2026  

---

## 1. Visione Generale

Il modulo `beam_optimizer` implementa un ottimizzatore **Beam Search sequenziale** su **3 trienni consecutivi (9 anni totali)** di rotazioni colturali triennali.

### Che problema risolve

Ottimizzare 3 trienni consecutivi richiede di valutare fino a **216³ = 10.077.696 combinazioni** possibili, impiegando circa **28 ore** con il metodo bruto (a 0,2 s/simulazione).

Il Beam Search con **maschera normativa a 0 ms** riduce questo a **< 1,2 secondi** grazie a:
- **Pruning normativo anticipato** (scarta rotazioni non conformi *prima* della simulazione)
- **Beam width B = 8** (mantiene solo le migliori 8 traiettorie ad ogni triennio)
- **Continuità reale del suolo** (stato [W, N, H] propagato senza mai azzerarsi)

---

## 2. Chiamata Python

```python
import os
os.environ["FIELDWISE_OFFLINE"] = "1"  # zero rete a runtime

from fieldwise.beam_optimizer import run_beam_search_9y

# Chiamata tipica (tutti i parametri hanno default sensati)
result = run_beam_search_9y(
    lat=45.2,
    lon=10.0,
    objectives=("resa", "guadagno", "costo"),   # obiettivo per ogni triennio
    irrigation_regime="tetto_irriguo",           # "solo_pioggia" | "tetto_irriguo" | "irrigazione_libera"
    regime_normativo=None,                       # None = usa REGIME_PREDEFINITO (Lombardia quinquennale)
    solo_conformi=True,
    climate_mode="storico",                      # "storico" | "cmip6"
    ssp_code="ssp245",                           # solo se climate_mode=="cmip6"
    horizon_years=10,                            # solo se climate_mode=="cmip6"; 5|10|15|20
    beam_width=8,
)
import json
json.dumps(result)   # sempre funziona: nessun tipo NumPy o oggetto custom
```

---

## 3. JSON Completo di Esempio

```json
{
  "lat": 45.2,
  "lon": 10.0,
  "climate_mode": "storico",
  "ssp_code": null,
  "horizon_years": null,
  "irrigation_regime": "tetto_irriguo",
  "regime_normativo": "lombardia_impegno_quinquennale",
  "solo_conformi": true,
  "beam_width": 8,
  "objectives": ["resa", "guadagno", "costo"],
  "trienni": [
    {
      "numero": 1,
      "obiettivo": "resa",
      "rotazione_label": "frumento+cover > soia+cover > mais",
      "anno_partenza": 2001,
      "anno_valutato": 2002,
      "inizio": "2002-10-01",
      "fine": "2005-09-30",
      "conformita": {
        "lombardia_impegno_quinquennale": "conforme",
        "lombardia_impegno_triennale_SRA01_2026": "conforme"
      },
      "stato_conformita": "conforme",
      "colture": [
        {
          "coltura": "frumento",
          "semina": "2002-10-15",
          "raccolta": "2003-07-10",
          "resa_t_ha": 6.2,
          "resa_relativa": 0.88,
          "irrigazione_mm": 0.0,
          "concime_kg_n_ha": 142.0
        },
        {
          "coltura": "soia",
          "semina": "2003-04-25",
          "raccolta": "2003-10-05",
          "resa_t_ha": 3.4,
          "resa_relativa": 0.91,
          "irrigazione_mm": 45.0,
          "concime_kg_n_ha": 0.0
        },
        {
          "coltura": "mais",
          "semina": "2004-04-20",
          "raccolta": "2004-09-28",
          "resa_t_ha": 10.1,
          "resa_relativa": 0.87,
          "irrigazione_mm": 155.0,
          "concime_kg_n_ha": 180.0
        }
      ],
      "resa_t_ha": 6.57,
      "resa_rel_pct": 88.7,
      "costo_totale_eur_ha": 487.3,
      "guadagno_eur_ha": 1842.5,
      "best_sim_resa_t_ha": 7.12,
      "best_sim_resa_rel_pct": 92.1,
      "best_sim_costo_eur_ha": 213.4,
      "best_sim_guadagno_eur_ha": 2105.8,
      "fallback_siccita": false
    },
    {
      "numero": 2,
      "obiettivo": "guadagno",
      "rotazione_label": "frumento+cover > soia+cover > mais",
      "anno_partenza": 2005,
      "anno_valutato": 2006,
      "inizio": "2006-10-01",
      "fine": "2009-09-30",
      "conformita": {
        "lombardia_impegno_quinquennale": "conforme"
      },
      "stato_conformita": "conforme",
      "colture": ["... stessa struttura del triennio 1 ..."],
      "resa_t_ha": 6.41,
      "resa_rel_pct": 86.3,
      "costo_totale_eur_ha": 495.1,
      "guadagno_eur_ha": 2231.7,
      "best_sim_resa_t_ha": 7.05,
      "best_sim_resa_rel_pct": 91.0,
      "best_sim_costo_eur_ha": 198.2,
      "best_sim_guadagno_eur_ha": 2231.7,
      "fallback_siccita": false
    },
    {
      "numero": 3,
      "obiettivo": "costo",
      "rotazione_label": "frumento+cover > soia+cover > frumento",
      "anno_partenza": 2009,
      "anno_valutato": 2010,
      "inizio": "2010-10-01",
      "fine": "2013-09-30",
      "conformita": {
        "lombardia_impegno_quinquennale": "conforme"
      },
      "stato_conformita": "conforme",
      "colture": ["... stessa struttura ..."],
      "resa_t_ha": 5.98,
      "resa_rel_pct": 80.2,
      "costo_totale_eur_ha": 213.4,
      "guadagno_eur_ha": 1654.2,
      "best_sim_resa_t_ha": 7.12,
      "best_sim_resa_rel_pct": 92.1,
      "best_sim_costo_eur_ha": 213.4,
      "best_sim_guadagno_eur_ha": 2105.8,
      "fallback_siccita": false
    }
  ],
  "eredita_suolo": [
    {
      "da_triennio": 1,
      "a_triennio": 2,
      "acqua_totale_mm": 187.4,
      "de_superficiale_mm": 12.3,
      "n_min_kg_n_ha": 45.2,
      "n_res_kg_n_ha": 28.7,
      "humus_t_ha": 62.1,
      "credito_precessione_kg_n_ha": 15.0
    },
    {
      "da_triennio": 2,
      "a_triennio": 3,
      "acqua_totale_mm": 193.1,
      "de_superficiale_mm": 8.7,
      "n_min_kg_n_ha": 38.4,
      "n_res_kg_n_ha": 31.2,
      "humus_t_ha": 62.3,
      "credito_precessione_kg_n_ha": 12.5
    }
  ],
  "performance": {
    "tempo_beam_s": 0.87,
    "tempo_bruteforce_stimato_s": 2015539.0,
    "combinazioni_bruteforce": 10077696,
    "speedup_factor": 2316000.0
  },
  "note": []
}
```

---

## 4. Tabella delle Chiavi — Tipi, Unità e Mappatura UI

### 4.1 Radice del payload

| Chiave | Tipo | Unità | Descrizione | Elemento UI |
|--------|------|-------|-------------|-------------|
| `lat` | `float` | ° | Latitudine del punto | *non mostrato* |
| `lon` | `float` | ° | Longitudine del punto | *non mostrato* |
| `climate_mode` | `str` | — | `"storico"` o `"cmip6"` | Selettore forzante climatica |
| `ssp_code` | `str\|null` | — | Codice SSP (solo CMIP6) | Selettore scenario CMIP6 |
| `horizon_years` | `int\|null` | anni | Orizzonte CMIP6 | Selettore orizzonte |
| `irrigation_regime` | `str` | — | Scenario irriguo | Selettore irrigazione |
| `regime_normativo` | `str` | — | Disciplinare di conformità | Selettore legale |
| `solo_conformi` | `bool` | — | Filtro conformità | Checkbox disciplinare |
| `beam_width` | `int` | — | Traiettorie mantenute | *non mostrato* |
| `objectives` | `list[str]` | — | Obiettivi per i 3 trienni | 3 box ordinati temporalmente |
| `trienni` | `list[dict]` | — | I 3 risultati triennali | 3 colonne affiancate |
| `eredita_suolo` | `list[dict]` | — | 2 transizioni di stato suolo | Badge "Eredità Suolo" tra le colonne |
| `performance` | `dict` | — | Metriche di velocità | Nota in piccolo sotto le colonne |
| `note` | `list[str]` | — | Note automatiche (fallback, deroga) | Avvisi espandibili |

### 4.2 Ogni elemento di `trienni[k]`

| Chiave | Tipo | Unità | Descrizione | Elemento UI |
|--------|------|-------|-------------|-------------|
| `numero` | `int` | — | 1, 2 o 3 | Intestazione colonna (`"1° Triennio"`) |
| `obiettivo` | `str` | — | `"resa"`, `"guadagno"` o `"costo"` | Badge obiettivo |
| `rotazione_label` | `str` | — | Etichetta della rotazione (es. `"frumento+cover > soia+cover > mais"`) | **Combinazione scelta** (riga 1 della colonna) |
| `anno_partenza` | `int` | anno | Anno di inizio della simulazione | *tooltip* |
| `anno_valutato` | `int` | anno | Anno del ciclo valutato | *tooltip* |
| `inizio` | `str` | ISO date | Data inizio del ciclo valutato | *tooltip* |
| `fine` | `str` | ISO date | Data fine del ciclo valutato | *tooltip* |
| `conformita` | `dict[str, str]` | — | Stato per ogni regime normativo | Badge `conformità` |
| `stato_conformita` | `str\|null` | — | Stato per il regime scelto: `"conforme"`, `"conforme_solo_in_deroga"`, ecc. | Badge colorato affianco alla rotazione |
| `colture` | `list[dict]` | — | Una voce per ogni coltura del ciclo | Tabella espandibile o tooltip |
| `resa_t_ha` | `float` | t/ha | Resa media sulle colture del triennio | **Resa** (riga 2) |
| `resa_rel_pct` | `float` | % | Resa relativa media (% del potenziale) | **%** affianco alla resa |
| `costo_totale_eur_ha` | `float` | €/ha/anno | Costo totale (concime + irrigazione + altri) | **Costo** (riga 3) |
| `guadagno_eur_ha` | `float` | €/ha/anno | Margine lordo (ricavo meno tutti i costi) | **Guadagno** (riga 4) |
| `best_sim_resa_t_ha` | `float\|null` | t/ha | Migliore simulazione per resa (pura) | *(migliore simulazione per resa: X t/ha — dato riferito all'ottimizzazione pura della resa)* |
| `best_sim_resa_rel_pct` | `float\|null` | % | Resa relativa del best-sim resa | parte della didascalia in corsivo |
| `best_sim_costo_eur_ha` | `float\|null` | €/ha/anno | Migliore simulazione per costo (con resa ≥ 70%) | *(migliore simulazione per costo: Y €/ha/anno — dato riferito all'ottimizzazione pura del costo con resa ≥ 70%)* |
| `best_sim_guadagno_eur_ha` | `float\|null` | €/ha/anno | Migliore simulazione per guadagno (pura) | *(migliore simulazione per guadagno: Z €/ha/anno — dato riferito all'ottimizzazione pura del guadagno)* |
| `fallback_siccita` | `bool` | — | True se attivato il fallback siccità estrema | Avviso giallo nella colonna |

### 4.3 Colture `trienni[k]["colture"][i]`

| Chiave | Tipo | Unità | Descrizione |
|--------|------|-------|-------------|
| `coltura` | `str` | — | `"mais"`, `"soia"`, `"frumento"` |
| `semina` | `str` | ISO date | Data semina |
| `raccolta` | `str` | ISO date | Data raccolta |
| `resa_t_ha` | `float` | t/ha | Resa simulata |
| `resa_relativa` | `float` | 0–1 | Resa relativa (0 = zero, 1 = potenziale) |
| `irrigazione_mm` | `float` | mm | Irrigazione del ciclo |
| `concime_kg_n_ha` | `float` | kg N/ha | Concime azotato |

### 4.4 Ogni elemento di `eredita_suolo[k]`

| Chiave | Tipo | Unità | Descrizione | Elemento UI |
|--------|------|-------|-------------|-------------|
| `da_triennio` | `int` | — | 1 o 2 | Badge "Eredità Suolo" `1° → 2°` |
| `a_triennio` | `int` | — | 2 o 3 | Badge "Eredità Suolo" `2° → 3°` |
| `acqua_totale_mm` | `float` | mm | Acqua totale nel suolo (W1 + W2) | **Acqua suolo [mm]** |
| `de_superficiale_mm` | `float` | mm | Esaurimento strato superficiale De | *tooltip avanzato* |
| `n_min_kg_n_ha` | `float` | kg N/ha | Azoto minerale nel profilo | **Azoto residuo [kg N/ha]** |
| `n_res_kg_n_ha` | `float` | kg N/ha | Azoto organico residui freschi | *tooltip avanzato* |
| `humus_t_ha` | `float` | t SO/ha | Humus nel suolo | **Humus [t SO/ha]** |
| `credito_precessione_kg_n_ha` | `float` | kg N/ha | Credito di precessione in attesa | *tooltip avanzato* |

### 4.5 `performance`

| Chiave | Tipo | Unità | Descrizione | Elemento UI |
|--------|------|-------|-------------|-------------|
| `tempo_beam_s` | `float` | s | Tempo totale del beam search | **X secondi** nella nota in piccolo |
| `tempo_bruteforce_stimato_s` | `float` | s | Tempo stimato brute-force (216³ × 0,2 s) | **Y secondi (~Z ore)** nella nota |
| `combinazioni_bruteforce` | `int` | — | 10.077.696 fisso | (**10.077.696 combinazioni**) nella nota |
| `speedup_factor` | `float` | × | Rapporto brute-force / beam | parte della nota in piccolo |

---

## 5. Elementi UI e Mappatura 1-a-1

### In alto — Selettori

```
[Regime legale ▼]  [Irrigazione ▼]  [Forzante climatica ▼]
[1° Triennio: Resa ▼]  [2° Triennio: Guadagno ▼]  [3° Triennio: Costo ▼]
```

Mappatura Python:
- `regime_normativo` → selettore legale
- `irrigation_regime` → selettore irrigazione  
- `climate_mode` / `ssp_code` / `horizon_years` → selettore forzante
- `objectives[0]` / `objectives[1]` / `objectives[2]` → 3 box triennio

### Al centro — 3 Colonne Affiancate

```
┌─────────────────┬─────────────────┬─────────────────┐
│   1° Triennio   │   2° Triennio   │   3° Triennio   │
│   obj: resa     │   obj: guadagno │   obj: costo    │
├─────────────────┼─────────────────┼─────────────────┤
│ frumento+cover  │ frumento+cover  │ frumento+cover  │
│ > soia+cover    │ > soia+cover    │ > soia+cover    │
│ > mais          │ > mais          │ > frumento      │
│ [conforme ✓]    │ [conforme ✓]    │ [conforme ✓]    │
├─────────────────┼─────────────────┼─────────────────┤
│ Resa: 6.57 t/ha │ Resa: 6.41 t/ha │ Resa: 5.98 t/ha │
│ 88.7%           │ 86.3%           │ 80.2%           │
│ *(migliore sim  │ *(migliore sim  │ *(migliore sim  │
│  resa: 7.12     │  resa: 7.05     │  resa: 7.12     │
│  t/ha — dato    │  t/ha — dato    │  t/ha — dato    │
│  ott. pura)*    │  ott. pura)*    │  ott. pura)*    │
├─────────────────┼─────────────────┼─────────────────┤
│ Costo:          │ Costo:          │ Costo:          │
│ 487 €/ha/anno   │ 495 €/ha/anno   │ 213 €/ha/anno   │
│ *(migliore sim  │                 │                 │
│  costo: 213     │                 │                 │
│  €/ha/anno ...)*│                 │                 │
├─────────────────┼─────────────────┼─────────────────┤
│ Guadagno:       │ Guadagno:       │ Guadagno:       │
│ 1843 €/ha/anno  │ 2232 €/ha/anno  │ 1654 €/ha/anno  │
│ *(migliore sim  │                 │                 │
│  guadagno: 2106 │                 │                 │
│  €/ha/anno ...)*│                 │                 │
└─────────────────┴─────────────────┴─────────────────┘
```

### Badge "Eredità Suolo" tra le colonne

```
   [1° ──────── Acqua: 187 mm | Azoto: 45 kg N/ha | Humus: 62.1 t SO/ha ──────── 2°]
   [2° ──────── Acqua: 193 mm | Azoto: 38 kg N/ha | Humus: 62.3 t SO/ha ──────── 3°]
```

Mappatura:
- `eredita_suolo[0]["acqua_totale_mm"]` → Acqua [mm] badge 1→2
- `eredita_suolo[0]["n_min_kg_n_ha"]` → Azoto residuo [kg N/ha] badge 1→2
- `eredita_suolo[0]["humus_t_ha"]` → Humus [t SO/ha] badge 1→2
- (analogo per `eredita_suolo[1]` = badge 2→3)

### Nota in piccolo sotto le colonne

```
Calcolato con il metodo di Beam Search con Maschera Normativa che ha permesso di 
caricare tutto in X secondi vs Y secondi (~Z ore) che avrebbe impiegato il metodo 
bruto (10.077.696 combinazioni).
```

Dove:
- `X` = `performance["tempo_beam_s"]`
- `Y` = `performance["tempo_bruteforce_stimato_s"]`
- `Z` = `performance["tempo_bruteforce_stimato_s"] / 3600` (ore)
- `10.077.696` = `performance["combinazioni_bruteforce"]`

---

## 6. Note Importanti per l'Integrazione

> [!IMPORTANT]
> **Il payload è sempre 100% JSON-serializzabile.** Puoi chiamare `json.dumps(result)` direttamente senza conversioni. Non ci sono oggetti NumPy, WaterState, NState o Rotation nelle chiavi.

> [!NOTE]
> **Il campo `note` può essere non vuoto** quando il beam search attiva automaticamente:
> - Il fallback da `conforme` a `conforme_solo_in_deroga` (regime troppo restrittivo)
> - Il fallback deterministico per siccità estrema nell'obiettivo `costo`
> Mostra queste note come avvisi espandibili nell'UI.

> [!TIP]
> **I valori `best_sim_*` possono essere `null`** (Python `None`) se nessuna simulazione è riuscita per quel benchmark (caso raro ma possibile in anni estremi). Gestiscilo con un fallback `"N/D"` nell'UI.

> [!WARNING]
> **L'obiettivo `"costo"` ha un vincolo implicito di resa >= 70%.** Il campo `fallback_siccita: true` indica che questo vincolo non è stato rispettato da nessun candidato (siccità estrema) e il beam ha usato invece il candidato con la massima resa relativa. Mostra un avviso giallo nella colonna corrispondente.

---

## 7. Modalità CMIP6

Per usare le proiezioni climatiche future invece dei dati storici:

```python
result = run_beam_search_9y(
    climate_mode="cmip6",
    ssp_code="ssp245",    # "ssp126" | "ssp245" | "ssp585"
    horizon_years=10,     # 5 | 10 | 15 | 20
    # ... altri parametri uguali
)
# result["climate_mode"] == "cmip6"
# result["ssp_code"] == "ssp245"
# result["horizon_years"] == 10
```

**Funziona completamente offline** con `FIELDWISE_OFFLINE=1`: usa il metodo Delta Change CMIP6 applicato alla serie storica NASA POWER in cache (vedi `CONTRATTO_DATI_FUTURO_ALESSANDRO.md`).

---

## 8. Scenari Irrigui e Regimi Normativi

### Scenari irrigui (`irrigation_regime`)

| Valore | Etichetta UI | Descrizione |
|--------|-------------|-------------|
| `"solo_pioggia"` | Solo pioggia | Nessuna irrigazione |
| `"tetto_irriguo"` | Irrigazione limitata | Tetto netto per coltura (default) |
| `"irrigazione_libera"` | Irrigazione libera | Nessun tetto |

### Regimi normativi (`regime_normativo`)

| Valore | Etichetta UI |
|--------|-------------|
| `"lombardia_impegno_quinquennale"` | Lombardia, impegno quinquennale *(default)* |
| `"lombardia_impegno_triennale_SRA01_2026"` | Lombardia, impegno triennale (SRA01) |
| `"emilia_romagna_impegno_quinquennale"` | Emilia-Romagna, impegno quinquennale |
| `"emilia_romagna_adesione_singola_coltura"` | Emilia-Romagna, adesione per singola coltura |
| `None` | Usa il più severo (default) |

### Obiettivi per triennio (`objectives`)

| Valore | Descrizione | Vincolo |
|--------|-------------|---------|
| `"resa"` | Massimizza resa media (t/ha) | nessuno |
| `"guadagno"` | Massimizza margine lordo (€/ha/anno) | nessuno |
| `"costo"` | Minimizza costo totale (€/ha/anno) | resa relativa ≥ 70% |
