# FIELDWISE — piano di lavoro

NASA Space Apps Challenge 2026, challenge "Field Shift: Adapting Farms with NASA Data".
Strumento di supporto alle decisioni: confronta la rotazione attuale di un campo con
almeno altre due, con evidenze e rischi. Area pilota: provincia di Cremona (lat 45,2, lon 10,0).

Ultimo aggiornamento: 2026-11-11.

## Principi non negoziabili

1. Nessun parametro inventato: ogni numero vive in `params/*.yaml` con valore, unità, fonte,
   tabella/pagina, URL, nota. Senza fonte ufficiale → `assunzione: true` + motivazione + analisi di sensibilità.
2. Gerarchia delle fonti: FAO (56, 33, AquaCrop) → enti pubblici italiani (disciplinari Lombardia
   ed Emilia-Romagna, CREA, ISTAT, ARPA) → peer-reviewed → altro solo se dichiarato.
3. Motore = bilanci di massa (acqua, azoto, humus) a passo giornaliero. Niente vettori dinamici,
   niente punteggi pesati arbitrari. I pesi dell'agricoltore entrano solo nella classifica finale.
4. Lo stato del suolo non si azzera mai tra una coltura e la successiva.
5. Niente previsioni meteo: l'incertezza è l'ensemble delle annate storiche.
6. Riproducibilità: dati in cache con data di download e versione; la demo funziona senza rete.
7. Onestà: una validazione debole o negativa si riporta così com'è.

## Decisioni prese

| # | Decisione | Motivo |
|---|-----------|--------|
| D1 | La radice del repository è questa cartella (`nasa/`), che corrisponde a `fieldwise/` nella specifica | graphify e i comandi girano dalla cartella di lavoro |
| D2 | Il vecchio motore e il PDF stanno in `legacy/` (copie da `~/Downloads`), sola lettura, usati come specifica | il progetto si riscrive da capo |
| D3 | Chiavi dei YAML in italiano (`valore, unita, fonte, riferimento, url, nota, assunzione, motivazione, verificato`), contratto in `params/SCHEMA.md` | coerenza con la specifica (`assunzione: true`) |
| D4 | Ogni parametro ha `verificato: true/false`: true solo se il valore è stato letto dalla fonte durante il lavoro | distinguere ciò che è stato controllato da ciò che è ricordato |
| D5 | Cache: `data/raw/<sorgente>/<punto>/` + `<file>.meta.json`; elaborati in `data/processed/<punto>/*.csv`; `FIELDWISE_OFFLINE=1` vieta la rete | principio 6 |
| D6 | Il calendario di ogni rotazione (semine, fasi in gradi-giorno, raccolte) dipende solo dal meteo: si precalcola, poi un unico ciclo giornaliero dell'acqua attraversa tutta la rotazione; azoto e humus si aggiornano a fine segmento | stato mai azzerato + nucleo numerico compilabile con numba (ensemble < 60 s) |
| D7 | Ambiente: `.venv` Python 3.11 creato con uv; pacchetto installato in modalità sviluppo | riproducibilità |
| D9 | Le costanti interne delle equazioni pubblicate (Penman-Monteith FAO-56, Saxton-Rawls) restano nel codice con il numero dell'equazione citato accanto; nei YAML stanno ingressi, scelte e parametri agronomici | sono parte dell'equazione, non parametri regolabili |
| D10 | `params/cover_crop.yaml` e `src/fieldwise/soil.py` (pedotrasferimento) aggiunti alla struttura | evitare che due agent scrivano lo stesso file; tenere il pedotrasferimento separato dal bilancio idrico |
| D11 | Dal 2026-11-12: al massimo due agent alla volta, in ordine di dipendenza; agent nuovo con brief stretto invece di riprendere agent con contesto molto grande; Opus solo per il giudizio scientifico; un'unica correzione dei parametri in un solo agent | richiesta dell'utente dopo quattro arresti per limite d'uso: ottimizzare i token nella finestra di 5 ore a parità di qualità |
| D12 | Verifica delle fasi 3 e 4: dopo la fase 3 un agent Sonnet scrive ed esegue i test sui criteri di accettazione (bilanci chiusi, Ks, esempio FAO); la verifica scientifica Opus si fa una volta sola sulle fasi 3 e 4 insieme | la fase 4 riscrive il calendario su cui poggia la fase 3: una verifica unica evita di rivedere due volte lo stesso codice |
| D13 | Sostanza organica 0–30 cm del punto pilota: valore ERSAF (2,33%) al posto di SoilGrids (3,56%), che resta come alternativa in sensibilità; tessitura e densità da SoilGrids | gerarchia delle fonti (ente pubblico italiano che misura in zona); proposta all'utente il 2026-11-12, nessuna obiezione; modificabile |
| D14 | Il bilancio dell'azoto passa a passo giornaliero (la specifica della fase 3 diceva "a fine segmento come nella versione attuale") | con l'aggiornamento a fine segmento la cover crop aumentava la lisciviazione a regime e sotto il frumento la lisciviazione era zero: la lisciviazione dipende dai tempi tra disponibilità e drenaggio; coerente con il principio 3 |
| D15 | Ogni rotazione si valuta sul secondo di due cicli consecutivi (un ciclo di avviamento) | senza avviamento concime e lisciviazione dipendono dallo stato iniziale arbitrario (concime −10% in mediana); costo: 17 annate di partenza invece di 20 |
| D16 | Funzione del caldo: Deryng et al. 2014 senza taratura; finestra in giorni per mais e soia (fedele alla fonte), in gradi-giorno per il frumento autunnale; AquaCrop e Teixeira in sensibilità come incertezza strutturale. Il criterio "f_caldo chiaramente basso per il mais nel 2022" è dichiarato NON soddisfatto (0,958 con POWER, 0,99 con le stazioni) | nessuna taratura sul risultato; nel modello la perdita del 2022 viene dall'acqua |
| D17 | Nessuna rotazione esclusa: i disciplinari 2026 non vietano successioni tra le tre colture, limitano i ristoppi; le rotazioni sono etichettate conforme / in deroga / non conforme | la rotazione attuale dell'utente va sempre mostrata |
| D18 | Ricostruzione del grafo a fine fase con `graphify update .` (solo codice, senza costo); la ricostruzione completa `/graphify .` con l'estrazione semantica dei documenti si fa una volta prima della verifica finale | economia di token (D11) |
| D8 | Esclusi dal grafo: `data/`, `reports/figure/`, `.venv/` (`.graphifyignore`) | dati e immagini non sono codice |

## Stato delle fasi

| Fase | Contenuto | Chi | Verifica | Stato |
|------|-----------|-----|----------|-------|
| 0 | Grafo iniziale, ambiente, scheletro, contratti | pianificatore | — | fatto |
| 1 | Dati e controlli di qualità | Sonnet (client), Opus (anomalie) | Sonnet diverso | in corso |
| 2 | Parametri dalle fonti | Opus | Opus diverso (≥10 parametri a campione) | in corso |
| 3 | Motore di base (ET0, acqua, azoto, humus) | Opus; test Sonnet | Opus diverso | da fare |
| 4 | Gradi-giorno, caldo in fioritura, penalità di rotazione, fattori moltiplicativi | Opus | Opus diverso | da fare |
| 5 | Ensemble e classifica | Opus progetta, Sonnet implementa | Sonnet diverso | da fare |
| 6 | Validazione (SMAP, NDVI, ISTAT) | Opus | Opus diverso | da fare |
| 7 | Analisi di sensibilità | Opus | Opus diverso | da fare |
| 8 | Interfaccia Streamlit | Sonnet | Sonnet diverso | da fare |
| 9 | README, report PDF, verifica finale | Sonnet; Opus verifica | — | da fare |

Il grafo si ricostruisce (`/graphify .`) alla fine delle fasi 3, 4, 5, 6, 7, 8 e prima della verifica finale.

## Blocchi aperti

- **Credenziali Earthdata assenti** (`~/.netrc` non esiste, nessuna variabile d'ambiente): IMERG e SMAP
  non si possono scaricare. I client vengono scritti e provati con dati finti; il download reale parte
  quando le credenziali ci sono. Senza IMERG il confronto delle piogge è POWER contro ARPA; senza SMAP
  la validazione dell'umidità non si fa.

## Registro

- 2026-11-12 notte — FASE 1 completa: IMERG (9253 giorni, bilineare su quattro celle) e SMAP (3845 giorni,
  2323 di qualità raccomandata) in cache; controllo qualità rieseguito senza errori. IMERG sovrastima i
  totali annui del 21% contro il pluviometro (POWER 1%), ma ha correlazione giornaliera migliore (0,73 contro
  0,59): POWER 2000–2022 confermato per il motore, IMERG alternativa per la sensibilità (`data/CHECKS.md`).
  Azoto a passo giornaliero consegnato (D14), con assorbimento ripartito sulla traspirazione (Kcb FAO-56
  tab. 17); test Sonnet: 131 nuovi, suite verde.
  VERIFICA SCIENTIFICA FASI 3–4 (`reports/engine_review.md`, Opus indipendente): bilanci corretti, equazioni
  fedeli, nessuna taratura; 12 controlli sulle fonti su 16 conformi; 7 mutazioni su 8 rilevate dai test.
  Condizioni per chiudere: (1) doppio coefficiente FAO-56 per tutte le superfici (oggi una cover consuma
  meno del suolo nudo bagnato e fa salire la percolazione); (2) Curve Number di AquaCrop (72, indipendente
  dalla copertura) come default; (3) soglie C/N nei YAML e testi dei parametri riallineati; (4) limiti
  dichiarati. In corso (Opus). Poi: adeguamento dei test (Sonnet), ensemble (fase 5).
  Push dei due commit dell'utente su `origin/main` eseguito su sua richiesta; il lavoro successivo non è
  committato.
- 2026-11-12 sera — Credenziali Earthdata arrivate; SMAP provato, IMERG sbloccato dopo l'autorizzazione di
  GES DISC; client IMERG esteso alle quattro celle (Sonnet); download completi rilanciati staccati dalla
  sessione (log in `data/logs/`). Da fare a download finiti: `python -m fieldwise.qc` e confronto
  IMERG/POWER/ARPA.
  FASE 3: difetto dello strato evaporante corretto (limite inferiore da FAO-56 eq. 73); `nitrogen.py` e
  `humus.py` consegnati; soia senza concime con deficit dichiarato; cover limitata. Test Sonnet: suite a
  926 verdi (criteri di accettazione della fase 3 tutti coperti).
  FASE 4: `phenology.py`, `yield_model.py`, `rotation.py`, `params/scenarios.yaml` consegnati. Mais: ciclo
  125 giorni nel 2022 contro 164 nel 2014; frumento continuo penalizzato (0,82) e ultimo con l'irrigazione.
  DIFETTO STRUTTURALE trovato dal modulo di rotazione: azoto a fine segmento → la cover aumentava la
  lisciviazione. In corso (Opus): azoto a passo giornaliero (D14). Poi: adeguamento dei test (Sonnet),
  test di `rotation.py`, verifica scientifica unica delle fasi 3–4 (Opus), ensemble.
- 2026-11-12 16:30 — FASE 1 chiusa per i dati senza credenziali. Decisioni scritte in `data/CHECKS.md`
  (sezione Decisioni, D1–D7) e tradotte in `src/fieldwise/weather.py`: pioggia POWER senza correzioni con
  ensemble limitato alle annate 2000–2022 (cinque pluviometri ARPA confermano la sovrastima: 1,17 nel 2023,
  1,38 nel 2024, 1,72 nel 2025); temperature POWER; ISTAT 2006–2022 sulle anomalie; NDVI sulla finestra;
  IMERG da estendere alle quattro celle quando arriveranno le credenziali.
  CALDO 2022: f_caldo del mais = 0,94 con POWER e 0,99 con le stazioni affidabili; AquaCrop dà 1,00,
  Teixeira sulla massima 0,89 (articolo non letto). Decisione: resta Deryng (nessuna taratura sul risultato);
  il criterio "2022 chiaramente basso" è dichiarato NON soddisfatto; le alternative entrano in sensibilità.
  FASE 2 chiusa: le 16 correzioni della revisione applicate a `nitrogen.yaml`, `rotation_rules.yaml`,
  `cover_crop.yaml`, `soil.yaml` (D13). Un test di `test_soil.py` adeguato alla decisione D13 (approvato).
  Limite nuovo: tutte le rotazioni perdono humus (effluenti zootecnici non modellati).
  FASE 3: `water.py` consegnato (chiusura < 1e-11 mm; 0,04 s per milione di passi) e provato da Sonnet
  (74 test; suite a 384). Difetto trovato dai test: strato 0–30 cm sotto il punto di appassimento sul suolo
  nudo dopo una coltura (contabilità dello strato evaporante). In corso (Opus): correzione + `nitrogen.py`
  + `humus.py`. FASE 4 prima parte in corso (Opus): `phenology.py`, `yield_model.py`.
- 2026-11-12 14:40 — Quarto arresto (11:15 circa) con quattro agent Opus in parallelo; nessuno aveva ancora
  scritto file. Nuova strategia (D11). Ripartiti solo due: motore limitato a `water.py`, e un agent nuovo
  che applica in una volta tutte le correzioni dei parametri decise dopo la revisione (compresa D13).
  In coda, nell'ordine: interpretazione delle anomalie + decisioni + `weather.py`; `nitrogen.py`/`humus.py`;
  test della fase 3 (Sonnet); fase 4.
- 2026-11-12 11:00 — Fase 1: client MODIS consegnato (595 date), controllo qualità consegnato (45 controlli:
  24 OK, 9 attenzione, 0 errori, 11 non disponibili per IMERG/SMAP; 203 test verdi). Pioggia POWER/ARPA:
  rapporto 1,02 nel 2000–2022 e 1,46 nel 2023–2025. Temperature: il sensore di Persico Dosimo è anomalo
  (salto 2005–06); riferimento = Casalbuttano e Gambara; POWER regge sulla massima media estiva (−0,3 °C)
  ma non sul conteggio dei giorni sopra 35 °C. In corso: interpretazione delle anomalie, decisioni scritte
  in `data/CHECKS.md` e `weather.py` (Opus).
  Fase 2: `soil.yaml` consegnato (franco; 215 mm di acqua disponibile su 1,5 m). Revisione indipendente
  (`reports/params_review.md`): 29 voci controllate sulle fonti, 22 confermate, 7 usate fuori dalle
  condizioni della fonte, nessun errore di trascrizione. Correzioni affidate agli autori: fissazione della
  soia, efficienza del concime, cover crop nelle equazioni dell'azoto e suo coefficiente isoumico, strato
  dell'humus, residui di soia, penalità di rotazione per condizione (irriguo/asciutto, primo ristoppio/
  monosuccessione). Aggiunta allo schema la chiave `derivato`.
  Fase 3: lanciato il motore (acqua, azoto, humus), a partire dal bilancio idrico.
  DECISIONE IN ATTESA DELL'UTENTE — sostanza organica 0–30 cm: SoilGrids 3,56% (humus 153 t/ha) contro
  ERSAF 2,33% (100 t/ha). Raccomandazione: ERSAF per la sostanza organica, SoilGrids per la tessitura.
  Limite da dichiarare: falda a 110–150 cm non modellata.
- 2026-11-12 09:20 — Terzo arresto per limite d'uso (notte); ripartiti MODIS (download completo, manca il
  rapporto), controllo qualità (3 test rossi da sistemare), controllo incrociato delle temperature ARPA
  (tre stazioni in più già scaricate), suolo (`soil.py` scritto, mancano test e `soil.yaml`), revisione
  indipendente dei parametri.
- 2026-11-11 23:30 — Consegnati `et0.py` (Esempio 18 FAO-56 entro lo 0,01%), `crops.yaml` (78 voci),
  `nitrogen.yaml` (60 voci), `rotation_rules.yaml`, `heat.yaml`, `cover_crop.yaml` (118 voci), temperature ARPA.
  Punti aperti emersi:
  (a) f_caldo del mais nel 2022 = 0,94 con la funzione pubblicata (Deryng et al. 2014) e meteo POWER: il
  criterio "2022 chiaramente basso" non è soddisfatto; nessuna taratura fatta.
  (b) Temperature: POWER schiaccia gli estremi in media (massima estiva −1,3 °C), ma anno per anno
  contraddice la stazione di Persico Dosimo sui giorni sopra 35 °C (2022: 31 contro 12; 2019: 18 contro 40);
  la stazione sembra disomogenea. In corso il confronto con altre tre stazioni.
  (c) Disciplinari 2026: nessuna successione vietata tra mais, soia e frumento, solo limiti ai ristoppi;
  le rotazioni si etichettano (conforme / in deroga / non conforme), non si escludono.
  (d) Conflitti tra fonti mandati in sensibilità: azoto assorbito dalla soia (63 contro 79 kg N/t), k2
  (0,015–0,024), spessore dello strato di humus (0,20 contro 0,30 m), penalità del mais in monosuccessione.
- 2026-11-11 22:15 — Secondo arresto per limite d'uso (17:55 circa); ripartiti alle 22:15 i sei agent rimasti:
  MODIS (download a un terzo), `crops.yaml`, `nitrogen.yaml`, regole di rotazione/caldo/cover, suolo
  (Saxton-Rawls + `soil.yaml`), `et0.py` (anticipato dalla fase 3 perché serve al controllo qualità).
- 2026-11-11 17:55 — Consegnati e provati (109 test verdi): client POWER, ARPA, ISTAT, SoilGrids, Earthdata
  (IMERG/SMAP: solo codice, download reale in attesa delle credenziali), caricatore dei parametri.
  Osservazioni da portare al controllo qualità: pioggia POWER 2023–2025 sopra ARPA del 33–68%;
  sostanza organica SoilGrids 3,6% (0–30 cm) sospetta alta; quota della cella POWER 171 m contro 45 m del campo;
  punto pilota su un vertice della griglia IMERG; rese ISTAT solo dal 2006 e calcolate (produzione/superficie);
  IMERG Final fermo al 2025-09-30.
- 2026-11-11 17:15 — Prima ondata (7 agent Sonnet per i client e il caricatore dei parametri, 3 agent Opus
  per i parametri) interrotta dal limite d'uso prima che scrivessero file; fatta ripartire dagli stessi brief.
  Aggiunto `params/cover_crop.yaml` alla struttura (specie e parametri della cover crop in un file a sé,
  per non far scrivere lo stesso file a due agent).
- 2026-11-11 — Fase 0: grafo iniziale (74 nodi, 107 archi, 9 comunità; 18 archi con estremo mancante
  segnalati dal controllo di integrità), `graphify claude install`, ambiente e scheletro.
