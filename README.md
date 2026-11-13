# FIELDWISE

Strumento di supporto alle decisioni per la NASA Space Apps Challenge 2026, challenge "Field Shift: Adapting Farms with NASA Data".

FIELDWISE confronta la rotazione colturale attuale di un campo con alternative che proteggono il suolo e risparmiano acqua. Le colture sono mais, soia e frumento, con o senza cover crop (segale) tra una coltura e l'altra. Il motore è fatto di bilanci di massa giornalieri di acqua, azoto e humus (formule FAO-56, FAO-33, AquaCrop), alimentati da dati NASA (meteo, pioggia, umidità, NDVI) e da dati pubblici italiani. Lo stato del suolo non si azzera mai tra una coltura e la successiva. Non prevede il tempo: ogni rotazione parte da ogni annata storica e l'incertezza è la variabilità tra le annate. Punto pilota: lat 45,2, lon 10,0 (provincia di Cremona).

Cosa esce: per ogni rotazione e per tre scenari d'acqua (solo pioggia, tetto irriguo, irrigazione libera) resa relativa mediana e nell'annata peggiore, irrigazione, concime, azoto lisciviato, variazione di humus, conformità ai disciplinari regionali, e una classifica con i pesi scelti dall'agricoltore. Il confronto si legge in un'app Streamlit (gira offline).

**Prima di usare i risultati leggi la sezione [Limiti](#limiti).** Il report per il team (`reports/FIELDWISE_report.pdf`) spiega il modello, la validazione e la sensibilità.

## Installazione

Serve Python 3.11 o successivo. Con [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt
uv pip install --python .venv/bin/python -e .      # installa il pacchetto fieldwise (cartella src/)
```

Senza uv: `python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .`

Il repository contiene già la cache dei dati del punto pilota (`data/raw/`, `data/processed/`): test, ensemble, validazione, sensibilità e app funzionano senza rete e senza credenziali.

### Test

```bash
.venv/bin/python -m pytest                      # tutta la suite (1272 test, circa 1 minuto)
.venv/bin/python -m pytest -m "not slow"        # salta i test lenti (ensemble completo, validazione, giro di sensibilità)
```

I test sui dati reali si saltano da soli se la cache manca; nessun test usa la rete.

## Uso

Tutti i comandi si lanciano dalla radice del repository. Per vietare ogni accesso alla rete (demo) imposta `FIELDWISE_OFFLINE=1`: i client dei dati sollevano un errore invece di scaricare.

### 1. Dati

Il motore ha bisogno solo di NASA POWER (meteo giornaliero) e SoilGrids (suolo) per il punto. Gli altri dati servono a controlli, validazione e alternative di sensibilità.

Senza credenziali Earthdata (nessun login):

```bash
.venv/bin/python -m fieldwise.data.power     --lat 45.2 --lon 10.0     # NASA POWER, meteo 2000-2025
.venv/bin/python -m fieldwise.data.soilgrids --lat 45.2 --lon 10.0     # SoilGrids 250 m
.venv/bin/python -m fieldwise.data.arpa      --lat 45.2 --lon 10.0 --variable rain          # ARPA Lombardia (solo Lombardia)
.venv/bin/python -m fieldwise.data.arpa      --lat 45.2 --lon 10.0 --variable temperature
.venv/bin/python -m fieldwise.data.modis     --lat 45.2 --lon 10.0     # NDVI MODIS (ORNL DAAC)
.venv/bin/python -m fieldwise.data.istat     --province Cremona        # rese ISTAT provinciali
```

Con credenziali NASA Earthdata (IMERG per la pioggia alternativa, SMAP per la validazione dell'umidità): crea un account gratuito su <https://urs.earthdata.nasa.gov> e autorizza le applicazioni "NASA GESDISC DATA ARCHIVE" (IMERG) e quella dell'NSIDC DAAC (SMAP). Poi una delle due strade:

```bash
# 1) file ~/.netrc (consigliato)
#    machine urs.earthdata.nasa.gov login <utente> password <password>
chmod 600 ~/.netrc
# 2) oppure variabili d'ambiente
export EARTHDATA_USERNAME=<utente> EARTHDATA_PASSWORD=<password>     # oppure EARTHDATA_TOKEN=<token>

.venv/bin/python -m fieldwise.data.imerg --lat 45.2 --lon 10.0
.venv/bin/python -m fieldwise.data.smap  --lat 45.2 --lon 10.0
```

Senza credenziali questi due comandi si fermano con un messaggio che spiega cosa fare; il resto del progetto funziona (la validazione SMAP e l'alternativa IMERG richiedono quei dati). Ogni file in cache ha un `.meta.json` con prodotto, versione, URL, data di download e checksum. Opzioni comuni: `--start`, `--end`, `--force` (`--help` per l'elenco).

### 2. Controllo qualità dei dati

```bash
.venv/bin/python -m fieldwise.qc --lat 45.2 --lon 10.0
```

Esegue i controlli sui dati in cache (completezza, intervalli, confronto POWER contro pluviometri ARPA e IMERG, temperature, NDVI, rese ISTAT) e **riscrive la parte automatica di `data/CHECKS.md`**. Le decisioni prese sui risultati stanno nella sezione "Decisioni" dello stesso file e non vengono toccate. Esce con codice 1 se c'è un errore.

### 3. Parametri

```bash
.venv/bin/python -m fieldwise.params --check       # riepilogo (voci, fonti, assunzioni, non verificate) ed errori
.venv/bin/python -m fieldwise.params --table       # riscrive reports/params_table.md
```

Ogni numero agronomico sta in `params/*.yaml` con valore, unità, fonte, riferimento, URL e un campo `verificato` (vero solo se il valore è stato letto dalla fonte durante il lavoro); le assunzioni sono marcate (`params/SCHEMA.md`).

### 4. Ensemble

```bash
.venv/bin/python -m fieldwise.ensemble --lat 45.2 --lon 10.0 [--attuale "mais"]
```

Tutte le 216 rotazioni di tre colture (con e senza cover) per tutte le annate di partenza e per i tre scenari d'acqua; circa 7 secondi. Scrive `ensemble_dettaglio.csv`, `ensemble_sintesi.csv` ed `ensemble_meta.json` in `data/processed/lat45.200_lon10.000/`. `--attuale` accetta una rotazione come `"mais > soia > frumento"`.

### 5. Validazione

```bash
.venv/bin/python -m fieldwise.validation [--no-figure]
```

Solo dalla cache: confronta il modello con SMAP (umidità superficiale), NDVI MODIS e rese ISTAT, con intervalli di confidenza al 95%. Scrive `validation_*.csv`, `validation_summary.json` e le figure in `reports/figure/`. Risultati in `reports/validation.md`.

### 6. Sensibilità

```bash
.venv/bin/python -m fieldwise.sensitivity [--n-mc 256] [--workers N] [--seme 20261113]
```

Perturba i parametri incerti (uno alla volta e con un Monte Carlo a ipercubo latino) e misura quanto cambia la decisione; circa 6 minuti con 8 processi. Scrive `reports/sensitivity.md`, `sensitivity_summary.json` e le figure. Va rilanciata dopo ogni nuovo ensemble.

### 7. App

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Apre l'app su <http://localhost:8501> con cinque pagine: Confronto, Dettaglio di una annata, Capire i dati, Validazione, Limiti e fonti. Non usa mai la rete. Per un altro punto servono in cache almeno POWER e SoilGrids (l'app indica il comando mancante).

### 8. Report

```bash
.venv/bin/python reports/build_report.py
```

Rigenera `reports/FIELDWISE_report.pdf` e `reports/FIELDWISE_report.md` leggendo i numeri dalla cache (richiede `reportlab`, incluso in `requirements.txt`).

## Dati usati

| Dato | Prodotto e versione | Periodo in cache | Uso |
|---|---|---|---|
| Meteo giornaliero (temperature, pioggia, radiazione, umidità, vento) | NASA POWER, Daily API v2.10.3, community AG (sorgenti MERRA-2, SRB, SYN1DEG, POWER) | 2000-01-01 → 2025-12-31 | Forzante del motore; l'ensemble usa 2000-2022 |
| Pioggia | GPM IMERG Final Daily V07 (`GPM_3IMERGDF`), interpolazione bilineare di quattro celle | 2000-06-01 → 2025-09-30 | Confronto con POWER e ARPA; forzante alternativa in sensibilità |
| Umidità superficiale del suolo | SMAP L3 enhanced 9 km, `SPL3SMP_E` V006 | 2015-03-31 → 2025-12-31 | Validazione (solo passaggi di qualità raccomandata) |
| NDVI | MODIS/Terra MOD13Q1 250 m, 16 giorni (ORNL DAAC; versione non dichiarata dal servizio) | 2000-02 → 2025-12 | Validazione |
| Suolo | SoilGrids 2.0, 250 m (ISRIC) | statico | Tessitura e densità; la sostanza organica 0-30 cm è il valore ERSAF (SoilGrids in sensibilità) |
| Pioggia e temperatura da pluviometri e termometri | ARPA Lombardia, open data `dati.lombardia.it` (stazioni, precipitazioni, temperatura) | 2000 → 2025 | Controllo qualità, alternativa `power_arpa` in sensibilità |
| Rese provinciali | ISTAT, "Superfici e produzione - dati in complesso - prov" (dataflow `101_1015_DF_DCSP_COLTIVAZIONI_2`), Cremona | 2006 → 2026 (2026 provvisorio, escluso) | Validazione sulle anomalie 2006-2022 |

Data e checksum di ogni download sono nei `.meta.json` accanto ai file in `data/raw/`.

## Struttura del repository

```
README.md, AI_USAGE.md, PLAN.md      questo file; uso dell'IA; piano, decisioni e registro del lavoro
requirements.txt, pyproject.toml     dipendenze e pacchetto (src/fieldwise)
params/                              parametri agronomici in YAML con fonte (SCHEMA.md descrive il formato)
src/fieldwise/
  data/                              client di download e cache (power, arpa, imerg, smap, modis, soilgrids, istat, earthdata, cache)
  weather.py, et0.py, soil.py        meteo, evapotraspirazione di riferimento, suolo (Saxton-Rawls)
  water.py, nitrogen.py, humus.py    bilanci di massa
  phenology.py, yield_model.py       gradi-giorno; resa = potenziale x f_acqua x f_caldo x f_rotazione
  rotation.py                        catena di rotazione (stato mai azzerato)
  ensemble.py, ranking.py            ensemble di tutte le rotazioni; classifica con i pesi dell'agricoltore
  qc.py, validation.py, sensitivity.py   controlli, validazione, sensibilità
app/                                 app Streamlit (streamlit_app.py e moduli fw_*)
tests/                               suite pytest
data/raw/, data/processed/           cache dei dati con .meta.json; CHECKS.md = controlli e decisioni sui dati
docs/fonti_*.md                      registro delle fonti dei parametri
reports/                             rapporti (validation, sensitivity, engine_review, params_review, phase5_review),
                                     report per il team (PDF + sorgente + build_report.py), figure/
legacy/                              proposta originale e primo motore, solo lettura
```

## Risultati principali

I numeri seguenti vengono dai file indicati; rigenerarli dopo ogni modifica.

- **Classifica** (`ensemble_sintesi.csv`, pesi uguali sulle cinque priorità): la prima rotazione dipende dallo scenario e include frumento e cover crop in tutti e tre; il mais continuo (rotazione di riferimento) è 45° su 45 in solo pioggia, 30° su 45 con il tetto irriguo e 43° su 45 in irrigazione libera. Il confronto completo è nel report, sezione 9.
- **Validazione** (`reports/validation.md`, scenario tetto irriguo): mais confermato (resa ISTAT, correlazione sui residui dal trend +0,70, IC 95% da +0,33 a +0,88, n = 17); soia non confermata (+0,27, da -0,24 a +0,67); frumento negativo (-0,50, da -0,79 a -0,03). Umidità superficiale SMAP: anomalie mensili r circa 0,7. NDVI estivo contro stress idrico del mais: r circa 0,6.
- **Sensibilità** (`reports/sensitivity.md`): la prima rotazione non è robusta (resta prima nel 33-62% dei campioni a seconda dello scenario); il mais continuo finisce nell'ultimo quarto della classifica nel 92-99% dei campioni perturbati (ma nel caso di base col tetto irriguo è 30° su 45).
- **Parametri** (`python -m fieldwise.params --check`): 372 voci con fonte, 26 assunzioni dichiarate, 50 non verificate sulla fonte originale.

## Limiti

Questi limiti cambiano il modo di leggere i risultati. Elenco completo in `reports/FIELDWISE_report.pdf` (sezione 12), `reports/validation.md`, `reports/engine_review.md` e `data/CHECKS.md`.

- **Frumento: validazione negativa.** La resa simulata del frumento è correlata in senso opposto alle rese ISTAT: il modello penalizza la siccità primaverile, mentre in Pianura Padana le perdite vengono dagli anni umidi (malattie, allettamento, ristagno). Il frumento compare spesso in alto nelle classifiche: va letto con prudenza.
- **Soia: validazione non confermata.** Gli intervalli di confidenza comprendono lo zero.
- **Sensibilità.** La scelta della rotazione migliore tra le prime è instabile rispetto ai parametri incerti e ai pesi; è più affidabile il giudizio su ciò che sta in fondo (mais continuo). Con le penalità di rotazione azzerate vince il frumento continuo.
- **Non validati**: azoto (concime, assorbimento, mineralizzazione, fissazione), humus, lisciviazione, percolazione, ruscellamento, volumi irrigui, effetto delle cover crop e delle penalità di rotazione. Non ci sono osservazioni.
- **Nessuna falda né risalita capillare**: lo stress del mais senza irrigazione è probabilmente sovrastimato. Il concime non passa dal pool di azoto minerale (lisciviazione probabilmente sottostimata) e l'azoto non limita la resa. Gli effluenti zootecnici non sono modellati (quasi tutte le rotazioni perdono humus).
- **Caldo in fioritura**: effetto piccolo; il criterio "fattore caldo chiaramente basso per il mais nel 2022" non è soddisfatto (0,958 con POWER). Non abbiamo tarato la funzione per ottenerlo.
- **Pioggia**: NASA POWER sovrastima la pioggia dal 2023 (e ha troppi giorni di pioviggine e pochi eventi intensi): l'ensemble usa solo 2000-2022. IMERG sovrastima i totali annui.
- **Penalità di rotazione** da studi di altri contesti (USA, UK), non padani; possono includere un effetto azoto.
- **Un punto e un suolo** (cella POWER di circa 50 km, pixel SoilGrids da 250 m). Rese ISTAT provinciali, irriguo e asciutto mescolati, n = 17. I parametri senza fonte ufficiale sono dichiarati assunzioni (`assunzione: true`).
- **Passato, non futuro**: l'ensemble usa annate storiche e può sottostimare gli estremi di un clima che cambia.
- **App**: il suo aspetto nel browser non è stato controllato da una persona.

## Licenze e attribuzioni dei dati

I dati di terzi restano di chi li produce; qui si indicano prodotto ed ente. Le condizioni d'uso dei dati NASA, ISRIC, ISTAT, ORNL DAAC non sono registrate nei metadati della cache né in `docs/fonti_*.md`: prima di ridistribuirli, verificarle sui siti degli enti.

- **NASA POWER** (Prediction Of Worldwide Energy Resources); sorgenti MERRA-2, SRB, SYN1DEG. <https://power.larc.nasa.gov>
- **GPM IMERG Final Run Daily V07**, NASA GES DISC. DOI 10.5067/GPM/IMERGDF/DAY/07.
- **SMAP Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture, V006** (`SPL3SMP_E`), NASA NSIDC DAAC. DOI 10.5067/M20OXIZHY3RJ.
- **MODIS/Terra Vegetation Indices 16-Day L3 Global 250 m (MOD13Q1)**, tramite il servizio di subset di ORNL DAAC. <https://modis.ornl.gov/rst/api/v1/>
- **SoilGrids 2.0**, ISRIC - World Soil Information. <https://soilgrids.org>
- **ARPA Lombardia**, open data di Regione Lombardia (`dati.lombardia.it`): i metadati del catalogo scaricato in `data/raw/arpa/` indicano per le serie di precipitazione, temperatura e per l'anagrafica delle stazioni la licenza "Creative Commons 1.0 Universal (Public Domain Dedication)".
- **ISTAT**, Superfici e produzione delle coltivazioni, <https://esploradati.istat.it>.
- **ERSAF Lombardia** (carta pedologica e monitoraggio dei suoli) per la sostanza organica del suolo; **FAO** (Irrigation and Drainage Paper 56 e 33, AquaCrop), disciplinari di produzione integrata di Lombardia ed Emilia-Romagna e letteratura citata in `docs/fonti_*.md` per i parametri.

Nessun logo o simbolo NASA è usato nel progetto. Uso dell'intelligenza artificiale: vedi [AI_USAGE.md](AI_USAGE.md).
