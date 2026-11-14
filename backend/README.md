# FIELDWISE

Motore di simulazione e backend per confrontare rotazioni colturali (mais, soia, frumento, con o senza cover crop di segale) in un campo. Progetto per la NASA Space Apps Challenge 2026, challenge "Field Shift: Adapting Farms with NASA Data". Punto pilota: lat 45,2, lon 10,0 (provincia di Cremona). In questo repository l'interfaccia è nella cartella `frontend/`; questa cartella `backend/` contiene il motore, i dati in cache e i rapporti che il motore genera. Tutti i comandi qui sotto si lanciano da dentro `backend/` (`cd backend`).

**Se devi costruire l'interfaccia, leggi in ordine: [Come usare il backend](#come-usare-il-backend-dal-frontend), [File di dati](#file-di-dati-leggibili-direttamente) e [Avvertenze](#avvertenze-che-linterfaccia-deve-mostrare).**

## Che cosa fa

- Calcola **bilanci giornalieri di acqua, azoto e humus** (formule FAO-56, FAO-33, AquaCrop) con meteo NASA POWER e suolo SoilGrids. Lo stato del suolo non si azzera tra una coltura e la successiva.
- Non prevede il tempo. Ogni rotazione parte da ogni **annata storica** (2000-2022 tentate; vedi `ensemble_meta.json` per quelle con risultati) e l'incertezza è la variabilità tra le annate.
- Simula tre **scenari d'acqua**: `solo_pioggia`, `tetto_irriguo` (irrigazione limitata, tetto per coltura), `irrigazione_libera`.
- Per ogni rotazione dà: resa (relativa e in t/ha), resa nell'annata peggiore, irrigazione, concime, azoto lisciviato, variazione di humus, giorni di caldo, conformità ai disciplinari regionali e **margine economico** (ricavo meno concime e acqua).
- Fa una **classifica con i pesi dell'agricoltore** su sei priorità (resa, rischio, acqua, concime, suolo, profitto) e il **fronte di Pareto**. Confronta la rotazione attuale con le alternative, con frasi di evidenze e rischi già pronte.
- Tutto gira offline sulla cache in `data/`.

## Installazione ed esecuzione

Serve Python 3.11 o successivo.

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .                      # installa il pacchetto fieldwise (cartella src/)
export FIELDWISE_OFFLINE=1            # vieta la rete: i client dei dati sollevano un errore invece di scaricare
```

Comandi (dalla radice del repository; `--help` mostra le opzioni):

| Comando | Che cosa fa | Tempo (da `ensemble_meta.json` e `sensitivity.md`) |
|---|---|---|
| `python -m fieldwise.ensemble --lat 45.2 --lon 10.0 [--attuale "mais > soia > frumento"]` | Ricalcola l'ensemble e **sovrascrive** `ensemble_*.csv` e `ensemble_meta.json` in `data/processed/<punto>/` | circa 7 s |
| `python -m fieldwise.validation [--lat --lon] [--no-figure]` | Confronta il modello con SMAP, NDVI MODIS, rese ISTAT, ECOSTRESS. Sovrascrive `validation_*` e le figure | solo cache |
| `python -m fieldwise.sensitivity [--n-mc 256] [--workers N] [--seme 20261113]` | Perturba i parametri incerti e misura quanto cambia la decisione. Sovrascrive `reports/sensitivity.md`, `sensitivity_summary.json` e le figure | circa 7 minuti con 8 processi |
| `python -m fieldwise.params --check` / `--table` | Controlla i parametri (voci, fonti, assunzioni) / riscrive `reports/params_table.md` | pochi secondi |
| `python -m fieldwise.qc --lat 45.2 --lon 10.0` | Controllo qualità dei dati in cache; riscrive la parte automatica di `data/CHECKS.md` | |
| `pytest` (`-m "not slow"` salta i test lenti) | Test; nessuno usa la rete | |

Tutti i punti di una analisi stanno in `data/processed/lat<LAT>_lon<LON>/` (`lat45.200_lon10.000` per il pilota). Per un altro punto servono in cache almeno POWER e SoilGrids. I download (richiedono rete): `python -m fieldwise.data.<power|soilgrids|arpa|modis|istat> --lat .. --lon ..`, `fieldwise.data.imerg`, `fieldwise.data.smap` e `fieldwise.data.ecostress` (servono credenziali NASA Earthdata in `~/.netrc` o in `EARTHDATA_USERNAME`/`EARTHDATA_PASSWORD`/`EARTHDATA_TOKEN`). Il motore ha bisogno solo di POWER e SoilGrids; gli altri dati servono a controlli e validazione.

## Come usare il backend dal frontend

Tutta la logica sta nel pacchetto `fieldwise`: l'interfaccia deve solo chiamarlo e mostrare i risultati. **Non modificare il motore dal frontend** (vedi [Contribuire](#struttura-e-regole-per-chi-contribuisce)).

### Concetti

- **Rotazione**: sequenza di colture con `+cover` se dopo quella coltura si semina la cover crop. Etichetta: `"mais > soia+cover > frumento"` (separatore `" > "`, costante `rotation.SEP`). Colture principali: `mais`, `soia`, `frumento` (`rotation.main_crops(params.load_params())`).
- **Classe**: rotazioni che differiscono solo per la partenza (permutazioni cicliche) sono la stessa classe, con etichetta canonica (`ensemble.classe_rotazione_attuale(etichetta)`). Una rotazione di una coltura o di tre colture uguali (`"mais"`) vale `"mais > mais > mais"` (monosuccessione). La sintesi ha una riga per (classe, scenario).
- **Ensemble**: tutte le 216 rotazioni triennali (con e senza cover) × annate di partenza × scenari. Lo `meta` del file in cache dà numeri e date: 76 classi, 11016 simulazioni riuscite, 3888 scartate, annate di partenza con risultati 2000-2016 (annate valutate 2003-2019).
- **Classi equivalenti**: 31 classi hanno `equivalente_a` diverso da `nessuno`: la cover richiesta non è mai praticabile, quindi il risultato è identico a quello della classe indicata. La classifica le esclude di default: restano **45 classi per scenario**.

### Nomi interni e priorità

| Scenario (`rotation.SCENARI`) | Etichetta (`ranking.ETICHETTE["scenari"]`) |
|---|---|
| `solo_pioggia` | solo pioggia |
| `tetto_irriguo` | irrigazione limitata (tetto netto di 200 mm per il mais, da `params/scenarios.yaml`) |
| `irrigazione_libera` | irrigazione libera |

| Priorità (`ranking.PRIORITA`) | Indicatori usati (verso: + più alto è meglio, − più basso) |
|---|---|
| `resa` | `resa_rel_mediana` (+) |
| `rischio` | `resa_rel_min` (+), resa media della rotazione nell'annata peggiore |
| `acqua` | `irrigazione_mm` (−) |
| `concime` | `concime_kg_n` (−) |
| `suolo` | `humus_t_ha` (+) e `n_lisciviato_kg_n` (−), media con peso uguale |
| `profitto` | `margine_lordo_eur_ha` (+) |

Regimi di conformità (`ranking.ETICHETTE["regimi"]`, default `ranking.REGIME_PREDEFINITO`): `lombardia_impegno_quinquennale`, `lombardia_impegno_triennale_SRA01_2026`, `emilia_romagna_impegno_quinquennale`, `emilia_romagna_adesione_singola_coltura`; `regime=None` usa il più severo. Stati: `conforme`, `conforme_solo_in_deroga`, `non_conforme`, `non_valutabile`.

### Funzioni principali

Nessuna scrive su disco (tranne `save_ensemble`); `run_ensemble` costa circa 7 s, le altre meno di un secondo. Gli errori di input sono `ValueError`; un file in cache mancante è `fieldwise.data.cache.CacheMiss`.

| Funzione | Argomenti | Restituisce |
|---|---|---|
| `ensemble.load_ensemble(lat=None, lon=None)` | punto (default pilota) | `(dettaglio, sintesi)`: DataFrame letti dalla cache. `.attrs["meta"]` = contenuto di `ensemble_meta.json` |
| `ensemble.run_ensemble(lat=, lon=, rotazione_attuale=None, scenari=None, n_avviamento=1)` | `rotazione_attuale`: etichetta come `"mais"` o `"mais > soia > frumento"` (colture sconosciute: `ValueError`) | `(dettaglio, sintesi)` ricalcolati in memoria, con la rotazione attuale marcata (`attuale=True`). Per salvare: `ensemble.save_ensemble(dett, sint, lat, lon)` |
| `ensemble.classe_rotazione_attuale(etichetta)` | etichetta | etichetta canonica della classe |
| `ranking.score(sintesi, pesi, scenario, solo_conformi=False, regime=REGIME_PREDEFINITO, ammetti_deroga=False)` | `pesi`: `{priorità: peso >= 0}` (mancanti = 0; tutti zero = `ValueError`); `solo_conformi`: tiene solo le rotazioni conformi per `regime` (l'attuale resta) | La sintesi dello scenario ordinata per punteggio, con colonne `punt_<priorità>` (0-1), `punteggio` (0-1) e `posizione` (1 = prima). Se nessun indicatore pesato discrimina, `risultato.attrs["avviso"]` è valorizzato e l'ordine non significa nulla |
| `ranking.pareto_front(sintesi, scenario, indicatori=None, solo_conformi=False, regime=...)` | `indicatori`: colonne tra quelle di `ranking.VERSI` (default tutte e sette le colonne di `ranking.VERSI`; con due colonne si ottiene il grafico di compromesso) | Le righe dello scenario con la colonna booleana `non_dominata` |
| `ranking.confronta(sintesi, pesi, scenario, n_alternative=2, solo_conformi=False, regime=...)` | come `score`. La sintesi deve avere la rotazione attuale marcata, altrimenti il confronto è "assoluto" (`attuale` è `None`, con una nota) | Dizionario `{scenario, attuale, alternative, n_confrontate, n_non_dominate, note}`. `attuale` e ogni alternativa sono dizionari con `ruolo`, `classe`, `punteggio`, `posizione`, `non_dominata`, `valori` (la riga della sintesi), `differenze` (per indicatore: `valore`, `attuale`, `assoluta`, `percentuale`), `evidenze` e `rischi` (liste di frasi italiane con i numeri già inseriti). Ruoli: `attuale`, `migliore_punteggio_non_dominata` (o `migliore_punteggio`), `migliore_rischio`, `per_punteggio` |
| `ranking.ETICHETTE` | | Etichette leggibili: chiavi `indicatori`, `priorita`, `scenari`, `regimi`, `stati`, `fattori`. Non mostrare mai gli identificativi tecnici all'utente |
| `rotation.build_context(lat=, lon=)` | punto | `RotationContext` (meteo, suolo, parametri). Si costruisce in circa 0,2 s: tienilo in memoria |
| `rotation.simulate(ctx, rotazione, anno, scenario, n_avviamento=1, dettaglio=False)` | `rotazione`: `rotation.Rotation.from_label(etichetta)`; `anno`: anno di partenza | Dizionario di una singola simulazione (circa 0,2 s). Con `dettaglio=True` aggiunge le serie giornaliere. Vedi sotto |
| `economics.margine_anno(p, out)` | `p = params.load_params()`, `out` = uscita di `simulate` | Margine in EUR/ha all'anno di quella simulazione |

**Rotazione attuale.** I file in cache non hanno nessuna rotazione marcata (`rotazione_attuale: null` in `ensemble_meta.json`). Per il confronto marca la classe in memoria, senza ricalcolare nulla (verificato: dà gli stessi numeri di `run_ensemble(..., rotazione_attuale=...)`):

```python
sintesi["attuale"] = sintesi["classe"] == ensemble.classe_rotazione_attuale("mais")
```

Se la rotazione attuale non è tra le 76 classi (per esempio ha due colture) serve `run_ensemble(lat=lat, lon=lon, rotazione_attuale=...)`: la rotazione viene simulata in più e confrontata con cicli di durata diversa (lo dice `meta["note"]`). Passa `n_avviamento=meta["n_avviamento"]`.

**Dettaglio di una rotazione in un'annata.** Dalla riga di `dettaglio` per (`scenario`, `classe`, `anno_valutato`) prendi `etichetta` e `anno_partenza` e chiama `simulate(ctx, Rotation.from_label(etichetta), anno_partenza, scenario, n_avviamento=meta["n_avviamento"], dettaglio=True)`. Chiavi principali del risultato:

- `esito`: `"ok"` oppure `non_simulabile`, `conflitto_calendario`, `parametri_degeneri` (con `motivo`; mostra il motivo e non i numeri).
- `anno_valutato`, `inizio`, `fine` (date ISO), `durata_anni`.
- `colture`: lista, una per coltura del ciclo, con `coltura`, `semina`, `fioritura`, `raccolta`, `resa` e `resa_potenziale` (t/ha), `resa_relativa`, `f_acqua`, `f_caldo`, `f_rotazione` (0-1: perdita di resa per acqua, caldo, successione), `irrigazione`, `pioggia` (mm), `concime`, `fissazione`, `lisciviazione` (kg N/ha), `supera_mas` (azoto sopra il limite normativo).
- `intervalli`: tra una coltura e la successiva: `dopo`, `tipo` (`cover` o `nudo`), `cover_richiesta`, `inizio`, `fine`, `cover_semina`, `cover_terminazione`, `avvertenze`.
- `indicatori`: gli stessi della sintesi per quella simulazione: `resa_relativa_media`, `irrigazione_anno` (mm), `concime_anno`, `n_lisciviato_anno` (kg N/ha), `humus_variazione_anno` (t/ha), ecc.
- Con `dettaglio=True`: `acqua` (serie giornaliere numpy: `w1`+`w2` acqua nel suolo, `tr` traspirazione, `ev` evaporazione, `rain`, `irr`, in mm), `azoto_giornaliero` (`n_min` azoto minerale, `l` lisciviato, in kg N/ha) e `segmenti`. Le date: `pd.date_range(ctx.date(out["segmenti"][0].start), periods=len(out["acqua"].tr))`.

**Margine economico.** `margine_lordo_eur_ha` è in EUR/ha all'anno, **media** sulle annate (le altre misure sono mediane): ricavo della granella meno concime azotato meno irrigazione, con i prezzi statici di `params/economia.yaml`. Per un campo di `ha` ettari: `margine * ha`. La differenza rispetto alla rotazione attuale è in `confronta(...)["alternative"][i]["differenze"]["margine_lordo_eur_ha"]["assoluta"]`. La resa in t/ha per coltura sta nelle colonne `resa_t_ha_mais`, `resa_t_ha_soia`, `resa_t_ha_frumento` (NaN se la coltura non è nella rotazione).

### Esempio (offline)

```python
import os
os.environ["FIELDWISE_OFFLINE"] = "1"
from fieldwise import ensemble, ranking

dettaglio, sintesi = ensemble.load_ensemble()      # punto pilota, dalla cache
pesi = {"resa": 5, "rischio": 3, "acqua": 8, "concime": 5, "suolo": 5, "profitto": 2}
punteggi = ranking.score(sintesi, pesi, "tetto_irriguo")
print(punteggi[["posizione", "classe", "punteggio", "resa_rel_mediana",
                "irrigazione_mm", "margine_lordo_eur_ha"]].head(5).round(2).to_string(index=False))
```

Esegue in meno di un secondo e stampa:

```
 posizione                             classe  punteggio  resa_rel_mediana  irrigazione_mm  margine_lordo_eur_ha
         1 frumento+cover > soia+cover > mais       0.59              0.90           99.98               2228.85
         2   frumento > frumento+cover > soia       0.59              0.86           33.33               1684.66
         3       frumento+cover > soia > mais       0.58              0.91           99.98               2224.75
         4       frumento > mais+cover > soia       0.57              0.90           99.98               2230.73
         5   frumento > frumento+cover > mais       0.57              0.89           66.65               2110.50
```

Confronto con la rotazione attuale (`"mais"`) e simulazione di dettaglio (continua dall'esempio sopra; anche questo gira in circa un secondo):

```python
from fieldwise import rotation as rt

meta = sintesi.attrs["meta"]
sintesi["attuale"] = sintesi["classe"] == ensemble.classe_rotazione_attuale("mais")
conf = ranking.confronta(sintesi, pesi, "tetto_irriguo", n_alternative=2)
for v in [conf["attuale"]] + conf["alternative"]:
    print(v["ruolo"], "|", v["classe"], "| posizione", v["posizione"], "di", conf["n_confrontate"])
    for frase in v["evidenze"] + v["rischi"]:
        print("   -", frase)

ctx = rt.build_context(lat=45.2, lon=10.0)
riga = dettaglio[(dettaglio.scenario == "tetto_irriguo") & (dettaglio.classe == conf["alternative"][0]["classe"])].iloc[-1]
out = rt.simulate(ctx, rt.Rotation.from_label(riga.etichetta), int(riga.anno_partenza), "tetto_irriguo",
                  n_avviamento=meta["n_avviamento"], dettaglio=True)
print(out["esito"], out["inizio"], "->", out["fine"], [(c["coltura"], round(c["resa"], 1)) for c in out["colture"]])
```

## File di dati leggibili direttamente

In `data/processed/lat45.200_lon10.000/`. Si leggono con `pandas.read_csv` e `json.load` senza il pacchetto, ma i file di classifica vanno usati con `ranking.*` (non riscrivere punteggio e Pareto).

| File | A che cosa serve | Colonne o chiavi principali |
|---|---|---|
| `ensemble_sintesi.csv` | Una riga per (classe, scenario): 228 righe. È l'ingresso di `ranking`. | `classe`, `scenario`, `attuale`, `n_simulazioni`, `n_scartate`; `conformita` (la più severa) e `conformita_<regime>`; `resa_rel_mediana`, `resa_rel_min`, `resa_rel_p10` (frazioni del potenziale, 1 = potenziale); `irrigazione_mm` (mm/anno); `concime_kg_n`, `n_lisciviato_kg_n`, `deficit_n_kg_n` (kg N/ha/anno); `humus_t_ha` (variazione, t/ha/anno); `giorni_caldo`; `ruscellamento_mm`, `percolazione_mm`; `margine_lordo_eur_ha` (EUR/ha/anno); `f_acqua`, `f_caldo`, `f_rotazione`, `fattore_limitante`; `quota_oltre_limite_n` (quota di annate sopra il limite di azoto); `cover_richieste`, `cover_realizzata_quota`; `equivalente_a`; `resa_t_ha_<coltura>` |
| `ensemble_dettaglio.csv` | Una riga per simulazione riuscita (11016): serve per le distribuzioni tra annate e per scegliere l'annata da simulare. | `etichetta`, `classe`, `anno_partenza`, `anno_valutato`, `scenario`, `resa_rel_media`, `resa_rel_minima`, gli stessi indicatori della sintesi per quella simulazione, `attuale` |
| `ensemble_meta.json` | Metadati del calcolo. | `calcolato_il`, `n_simulazioni`, `n_scartate`, `n_classi`, `scenari`, `n_avviamento`, `rotazione_attuale`, `annate_partenza`, `annate_partenza_con_risultati`, `anni_valutati`, `hash_parametri`, `note` |
| `validation_summary.json` | Tutti i risultati della validazione, con intervalli di confidenza al 95%. | `metodo.scenario_rappresentativo`, `smap.confronti[]`, `ndvi.confronti[]`, `istat.confronti[]` (`coltura`, `scenario`, `simulazione`, `detrend.{n, pearson, pearson_ic95}`), `ecostress.scenari.<scenario>`, `non_validato[]`, `figure`, `tabelle` |
| `validation_smap_mensile.csv`, `validation_ndvi_annuale.csv`, `validation_istat.csv`, `validation_ecostress_mensile.csv` | Serie osservate e simulate dietro i grafici di validazione. | per esempio `validation_istat.csv`: `coltura`, `scenario`, `simulazione`, `anno`, `resa_istat_t_ha`, `residuo_trend_t_ha`, `resa_relativa_sim` |
| `sensitivity_summary.json` | Risultati della sensibilità. | `conclusione` (frase), `base.<scenario>` (prime tre, attuale, alternative), `oat[]` (parametri uno alla volta), `strutturali[]`, `montecarlo.<scenario>` (`prima_resta`, `top3_restano`, `attuale_ultimo_quarto`, `tau_mediana`, `tau_p5`, `frequenza_top3`), `pesi`, `non_contano[]` |
| `power_daily.csv`, `power_site.json`, `soilgrids_agg.csv`, `modis_ndvi.csv`, `smap_daily.csv`, `imerg_daily.csv`, `arpa_*` | Dati di ingresso e di controllo in cache (meteo giornaliero POWER, suolo, NDVI, umidità, pioggia da satellite e da pluviometro). | `power_daily.csv`: `date`, `tmax`, `tmin`, `tmean`, `rain`, `srad`, `rh`, `wind` |
| `qc_summary.json`, `qc_rain_annual.csv` | Esito dei controlli di qualità sui dati (anche in `data/CHECKS.md`). | |

I grafici pronti sono in `reports/figure/` (`sensibilita_*.png`, `validazione_*.png`). Ogni file scaricato in `data/raw/` ha accanto un `.meta.json` con prodotto, versione, URL, data di download e checksum.

## Avvertenze che l'interfaccia deve mostrare

Numeri da `reports/validation.md` e `reports/sensitivity.md` (stato del 2026-11-14). Se rigeneri ensemble, validazione o sensibilità, aggiorna questa sezione: i numeri cambiano. Le ultime modifiche sono il modello dell'azoto con fattore di temperatura Q10 = 2 (assunzione, intervallo 1,7-3,0, in `params/nitrogen.yaml`; non è tra i parametri più influenti) e la priorità `profitto` nella classifica.

1. **Il punteggio è relativo** all'insieme confrontato: cambia se cambiano filtri o scenario. Serve solo a ordinare, non è una misura assoluta né confrontabile tra scenari. I pesi non cambiano le simulazioni. Mostra `risultato.attrs["avviso"]` e le `note` di `confronta`.
2. **La prima rotazione della classifica non è robusta.** Con l'incertezza congiunta dei parametri (Monte Carlo, 256 campioni) la prima resta prima solo nel 12,9% dei campioni in solo pioggia, 11,7% con il tetto irriguo, 29,7% in irrigazione libera; le prime tre restano le stesse nello 0,8%, 2,0% e 9,0%. Cambiare un solo parametro (su 179) modifica la prima nel tetto irriguo in 9 casi; i più forti sono `crops.mais.kcb.mid`, la penalità di ristoppio del mais irriguo e il tetto irriguo del mais. Con le penalità di rotazione azzerate la classifica cambia molto (tau 0,32 nel tetto irriguo). Anche i pesi scelti cambiano la prima: con pesi casuali e casi estremi arrivano prime 14-16 rotazioni diverse a seconda dello scenario. Presenta le prime posizioni come un gruppo di alternative, non come "la migliore".
3. **Più affidabile è il giudizio su ciò che sta in fondo, in particolare il mais continuo** (la rotazione di riferimento). Con pesi uguali sulle sei priorità è 45° su 45 in solo pioggia, 17° con il tetto irriguo e 27° in irrigazione libera. Nel Monte Carlo finisce nell'ultimo quarto nell'86,7%, 51,2% e 69,5% dei campioni (calcolato prima dei costi colturali per coltura: da rigenerare). Con il solo profitto è 40° su 45 in solo pioggia e 4° negli scenari irrigui. Il margine è ricavo meno concime e irrigazione simulati e meno gli altri costi colturali per coltura (seme, difesa, lavorazioni, raccolta, essiccazione: valori medi di partenza in `params/economia.yaml`, modificabili nell'app); non include affitto, ammortamenti e PAC e i prezzi sono statici. Conta soprattutto la differenza rispetto alla rotazione attuale.
4. **Validazione delle rese ISTAT** (scenario `tetto_irriguo`, n = 17 anni, correlazione sui residui dal trend [IC 95%]): mais confermato, **+0,70 [+0,33, +0,88]**; soia non confermata, +0,27 [-0,24, +0,67] (l'intervallo comprende lo zero); **frumento negativo, -0,50 [-0,79, -0,03]**. Il modello penalizza la siccità primaverile, mentre in Pianura Padana le perdite vengono dagli anni umidi (malattie, allettamento, ristagno): la resa del frumento è ottimistica e **non va letta come indicatore di rischio**. Il frumento compare spesso in alto nelle classifiche: avvisa l'utente.
5. **Validazione debole su acqua e vegetazione.** SMAP: le anomalie mensili di umidità superficiale hanno r circa 0,7 (0,71 con il tetto irriguo), ma gli scenari d'acqua non si distinguono e SMAP non valida l'acqua nella zona radicale, l'irrigazione o lo stress. NDVI MODIS: gli anni di siccità coincidono (2003, 2012, 2022; r +0,60 [+0,25, +0,82]) ma la relazione è solo ordinale e il modello esagera il 2017.
6. **ECOSTRESS: il livello dell'evapotraspirazione è sovrastimato.** In stagione di crescita il motore simula in media +1,61 mm/giorno più del satellite con il tetto irriguo (+0,57 solo pioggia, +2,42 irrigazione libera). Il segno è robusto, la grandezza no; nessun parametro è stato tarato. Il ciclo stagionale è riprodotto (r +0,77), ma la variabilità tra un anno e l'altro non è stabilita (anomalie r +0,39 [+0,13, +0,70], 5 anni).
7. **Non validati** (non ci sono osservazioni): azoto (concime, assorbimento, mineralizzazione, fissazione), **humus**, lisciviazione dei nitrati, percolazione e ruscellamento, volumi irrigui, effetto delle cover crop e delle penalità di rotazione. Mostra questi indicatori come ordini di grandezza. Gli effluenti zootecnici non sono modellati: in un'azienda con stalla la variazione di humus può essere migliore.
8. **Il modello non ha la falda** (risalita capillare): lo stress del mais senza irrigazione è probabilmente sovrastimato.
9. **Un solo punto, un solo suolo**, passato e non futuro: la cella POWER è di circa 50 km e l'ensemble usa solo annate con pioggia affidabile (POWER sovrastima la pioggia dal 2023). Può sottostimare gli estremi di un clima che cambia.
10. È uno strumento di confronto, **non una prescrizione agronomica**, e non è un prodotto né è approvato dagli enti che forniscono i dati.

Tutti i parametri: `reports/params_table.md`. Ci sono 378 voci; 29 sono assunzioni dichiarate e 56 non sono state verificate direttamente sulla fonte (`python -m fieldwise.params --check`).

## Struttura e regole per chi contribuisce

```
src/fieldwise/            motore e backend
  data/                   client di download e cache (power, soilgrids, arpa, imerg, smap, modis, istat, ecostress, earthdata, cache)
  weather.py, et0.py, soil.py          meteo, evapotraspirazione di riferimento, suolo
  water.py, nitrogen.py, humus.py      bilanci di massa
  phenology.py, yield_model.py         gradi-giorno; resa = potenziale x f_acqua x f_caldo x f_rotazione
  rotation.py                          catena di rotazione (stato mai azzerato) e simulate()
  economics.py                         margine su concime e acqua
  ensemble.py, ranking.py              ensemble di tutte le rotazioni; punteggio, Pareto, confronto
  qc.py, validation.py, sensitivity.py controlli, validazione, sensibilità
  params.py, config.py                 caricamento dei parametri; percorsi (radice cambiabile con FIELDWISE_ROOT)
params/*.yaml, SCHEMA.md  parametri con fonte o assunzione dichiarata
docs/fonti_*.md           registro delle fonti dei parametri
tests/                    suite pytest
data/raw/, data/processed/  cache dei dati (con .meta.json); data/CHECKS.md = controlli e decisioni sui dati
reports/                  validation.md, sensitivity.md, params_table.md, figure/ (generati dal motore)
```

Regole:

- **Nessun parametro senza fonte.** Ogni numero agronomico o economico sta in `params/*.yaml` come voce con `valore`, `unita`, `fonte`, `riferimento`, `url`, `verificato`, oppure come assunzione dichiarata con `assunzione: true` e `motivazione`. Contratto e regole in `params/SCHEMA.md`; `tests/test_params.py` fallisce se una voce non lo rispetta. Nessun numero agronomico nel codice.
- **Il motore non va modificato dal frontend.** Il frontend chiama le funzioni pubbliche sopra, non cambia `src/`, `params/` o i file in `data/processed/`. Se serve una funzione nuova, aggiungila al pacchetto con un test, non nell'interfaccia.
- Dopo una modifica al motore o ai parametri: `pytest`, poi `python -m fieldwise.ensemble` e, se cambia la decisione, `fieldwise.validation` e `fieldwise.sensitivity`. I numeri delle avvertenze vanno aggiornati.
- Nessuna taratura dei parametri sui risultati della validazione: i risultati negativi si riportano.
- Non salvare credenziali nel repository (`.netrc`, `.env` sono ignorati).

## Fonti dei dati

| Dato | Fonte | Uso |
|---|---|---|
| Meteo giornaliero (temperature, pioggia, radiazione, umidità, vento) | NASA POWER (Daily API, community AG) | Ingresso del motore. È un prodotto modellato, non un'osservazione. L'ensemble usa le annate fino al 2022 |
| Suolo | SoilGrids 2.0 (ISRIC), 250 m | Ingresso del motore (tessitura, densità). La sostanza organica 0-30 cm viene da ERSAF Lombardia |
| Pioggia da satellite | NASA GPM IMERG Final Daily V07 | Confronto con POWER; pioggia alternativa nella sensibilità |
| Umidità superficiale | NASA SMAP L3 enhanced 9 km (`SPL3SMP_E`) | Validazione |
| NDVI | MODIS/Terra MOD13Q1 250 m (ORNL DAAC) | Validazione |
| Evapotraspirazione | NASA ECOSTRESS (`ECO_L3T_JET.002`) | Validazione |
| Pioggia e temperatura a terra | ARPA Lombardia (open data) | Controllo qualità dei dati satellitari |
| Rese provinciali | ISTAT (Cremona) | Validazione |
| Rese potenziali | FAO/IIASA GAEZ v4 | Solo riscontro indipendente delle `resa_potenziale`, mai origine di un valore |

I parametri vengono da FAO (Paper 56, 33, AquaCrop), dai disciplinari di produzione integrata di Lombardia ed Emilia-Romagna e dalla letteratura citata in `docs/fonti_*.md`. Date e checksum di ogni download sono nei `.meta.json` in `data/raw/`.

**Licenza.** Nel repository non c'è ancora un file di licenza: va scelto prima della pubblicazione. I dati di terzi restano di chi li produce; le condizioni d'uso dei dati NASA, ISRIC, ISTAT, ORNL DAAC non sono registrate nella cache e vanno verificate sui siti degli enti prima di ridistribuirli. Per ARPA Lombardia i metadati del catalogo indicano "Creative Commons 1.0 Universal (Public Domain Dedication)". Nessun logo o simbolo NASA è usato nel progetto.
