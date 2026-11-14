# Revisione del collegamento frontend ↔ API ↔ motore


## Verdetto

**Fila con correzioni.** I numeri arrivano dal motore all'utente senza errori: su 6 casi confrontati
con `ranking.confronta` lo scarto massimo è 0,0, e il flusso nel browser (analisi → report → PDF)
funziona. Quello che non fila sono **le parole intorno ai numeri**: la pagina indica come
"raccomandata" un'alternativa anche quando la rotazione attuale è la migliore per le priorità scelte.
Inoltre il margine è descritto come se escludesse i costi colturali, che invece il motore sottrae.
Le frasi inglesi lasciano poi cadere i rischi del motore (limite normativo dell'azoto, conformità
della rotazione attuale). Infine mancano quasi tutte le avvertenze dei rapporti (stabilità della
classifica, azoto e humus non validati, sovrastima ECOSTRESS).

## Come ho verificato

- API avviata con `.venv` su **porta 8001**, `FIELDWISE_OFFLINE=1`: la 8000 e la 3000 erano già
  occupate da server dell'utente, che non ho toccato. Server fermato alla fine.
- Richieste vere: punto pilota (`use_pilot_reference` true/false); un punto a 7,6 km (Cremona città);
  un punto a 50 m dal pilota; un punto a 70 km (Milano); punti fuori area (Roma, un punto a 106 km dal
  pilota ma dentro il cerchio del frontend, lat/lon invertite); `/prepare` offline; i tre scenari;
  **tutte le 216 rotazioni × 3 scenari** (648 richieste, tutte HTTP 200 con 2 alternative); pesi
  uguali, solo profitto, pesi misti, solo acqua in "solo pioggia"; input non validi; export PDF.
- Confronto diretto col motore (`ensemble.load_ensemble` + `ranking.confronta`/`score` con gli
  stessi argomenti di `api.py`) su 6 casi: etichette, punteggi e 8 indicatori identici (**scarto
  massimo 0,0**). Identità del margine nella sintesi: ricavo − concime − irrigazione − altri costi =
  margine (errore 9e-13). Gli altri costi valgono tra 880 e 1950 €/ha.
- La cache del pilota è aggiornata: `ensemble.run_ensemble()` ricalcolato in memoria (senza
  salvare) dà una sintesi identica a quella in cache (scarto 0,0; stesso `hash_parametri`).
- Browser (chrome-devtools, contesto isolato). Ho usato il frontend dell'utente sulla porta 3000,
  perché Next rifiuta un secondo `next dev` nella stessa cartella. Le chiamate verso `:8000` sono
  state reindirizzate a `:8001` con uno script iniettato nella pagina, così nessuna richiesta è
  arrivata all'API dell'utente (che non è offline). Il flusso di analisi chiama `/prepare` e poi
  `/analyze`; il report mostra gli stessi numeri dell'API; Export PDF restituisce HTTP 200,
  `application/pdf`, 20 kB. Un campo non pilota, offline, dà un errore pulito.
- `pytest -q`: **exit 0** (circa 1310 test superati, 1 saltato). `npx tsc --noEmit`: **exit 0**.
  `npm run lint`: **exit 1** (7 errori, 2 avvisi; vedi n. 17).

## Problemi

### Bloccanti

**1. La "raccomandazione" contraddice le priorità dell'utente quando la rotazione attuale è la
prima.**
File: `frontend/src/components/reports/ReportDashboard.tsx:215-223` e `api.py:139-140`; l'API non
espone `posizione`, `ruolo` né `non_dominata`.
Prova (browser): campo pilota, rotazione mais > mais > mais, tetto irriguo, solo `profitto: 10`. L'API
dà all'attuale punteggio 1,000 (posizione 1 nel motore) e all'alternativa 1 punteggio 0,037. La
pagina però titola "ROTATION RECOMMENDATION: Winter wheat → Maize + rye → Soybean — Leading
alternative for the selected farming priorities". La scheda Economia della stessa pagina mostra
**Δ −383 EUR/ha/anno**. Un caso simile si ha con "solo acqua" in "solo pioggia": tutti i punteggi
valgono 0,5 e il motore avvisa "le rotazioni non si distinguono", ma la pagina indica comunque una
raccomandazione, con l'avviso solo in fondo alle note e in italiano.
Correzione: esporre `posizione`/`ruolo`/`non_dominata`/l'avviso dal motore. Se l'attuale è prima o il
punteggio non discrimina, dire "la rotazione attuale è già la migliore per queste priorità" invece di
"raccomandata".

### Da correggere

**2. Il margine è descritto in modo sbagliato: il motore sottrae anche i costi colturali.**
File: `api.py:322` (nota "excludes seed, crop protection, machinery"), `api.py:105` ("partial gross
margin"), `ReportDashboard.tsx:283-284`, `Analysis.tsx:257`, `reportMarkdown.ts:99` e `:127`,
`reportTypes.ts:101`, `HistoricalWindowPlot.tsx:13`, `report_export.py` (etichette "Partial gross
margin").
Prova: `economics.componenti` calcola il margine come ricavo − concime − irrigazione − altri costi
(seme, difesa, lavorazioni, raccolta, essiccazione, trasporti), e nella sintesi gli altri costi
valgono 880–1950 €/ha. Il browser invece mostra "Each margin is crop revenue minus nitrogen
fertilizer and irrigation costs … Excludes seeds, crop protection, machinery, labor".
Correzione: scrivere "margine: ricavo meno concime, irrigazione e costi colturali per coltura (valori
predefiniti di `params/economia.yaml`); esclusi affitto, ammortamenti e PAC" e togliere "partial".

**3. Le frasi inglesi perdono i rischi del motore e ne inventano l'assenza.**
File: `api.py:88-130`.
Prova: pilota, mais > soia > frumento, tetto irriguo, pesi uguali. Per l'alternativa 1
(`frumento+cover > soia+cover > mais`) l'API scrive "No decline in the displayed indicators; model
uncertainty still applies", mentre il motore dice "in 100% delle annate almeno una coltura supera
il limite normativo di azoto (attuale: 94%)". Vanno perse anche la praticabilità della cover
(`cover_realizzata_quota`) e il fattore limitante. Il testo italiano resta in
`sourceNotesItalian`, ma il frontend non lo legge (non è nemmeno nel tipo TypeScript).
Correzione: tradurre anche `quota_oltre_limite_n`, `cover_realizzata_quota` e lo stato di conformità
dai valori della sintesi, oppure mostrare `sourceNotesItalian`.

**4. La rotazione attuale non riceve mai rischi.**
File: `api.py:96-97` (restituisce `[]` per l'attuale).
Prova: mais > mais > mais. Il motore dice "non conforme al disciplinare di produzione integrata
(Lombardia, impegno quinquennale)" e "nell'annata peggiore la resa … scende a 0.84"; l'API restituisce
`risks: []`. Il PDF scrive "No specific risk note was supplied; this does not establish that the
strategy is risk-free", che è falso.
Correzione: per l'attuale costruire i rischi assoluti (conformità, limite dell'azoto, annata
peggiore) come fa `ranking._rischi(att, None, …)`.

**5. Nel grafico storico l'asse degli anni è spostato di 3 anni e il periodo dei dati è
sottostimato.**
File: `api.py:205-206` (`groupby("anno_partenza")`, `endYear = max(anno_valutato)`) e `api.py:309`.
Prova: il primo punto ha `startYear 2000, endYear 2003`, ma `anno_valutato` è l'**inizio** del ciclo
valutato (il 2000 è l'anno di avviamento). Il punto "2000" descrive dunque il ciclo 2003–2005 e
l'asse va 2000–2016 invece di 2003–2019. Il campo `dataPeriod` dice "2003–2019 (historical years)",
mentre il meteo usato va dal 2000 al 2022 (avviamento compreso). Il limite 2000–2022 è rispettato.
Correzione: usare `anno_valutato` sull'asse e scrivere "meteo 2000–2022, cicli valutati che
iniziano nel 2003–2019".

**6. Mancano le avvertenze dei rapporti.**
File: `api.py:310-322`, `ReportDashboard.tsx:322-327`.
Prova (browser): il report mostra solo la nota "Wheat-yield validation was negative". Non compaiono:
la stabilità della classifica (`reports/sensitivity.md`, tabella di incertezza congiunta: la prima
resta prima nel **12,9% / 11,7% / 29,7%** dei campioni per solo pioggia / tetto irriguo /
irrigazione libera; sono i 13/12/30% del brief); azoto e humus senza osservazioni
(`validation.md:318-319`); la sovrastima stagionale dell'evapotraspirazione rispetto a ECOSTRESS
(+1,6 mm/giorno col tetto irriguo, `validation.md:309-310`). Nel componente in uso nemmeno
`engine.methodologyNote` è mostrato: compare solo nel PDF e nell'Excel (era mostrato nel file
inutilizzato `src/app/reports/ReportDashboard.tsx:240`).
Correzione: aggiungere queste note, con i numeri, nell'API e un riquadro "Limiti" in Panoramica.

**7. Per l'alternativa 2 non si spiega il criterio di scelta.**
File: `api.py:139`, `ReportDashboard.tsx:232-235`.
Prova: nel motore la seconda alternativa è "migliore_rischio" (resa nell'annata peggiore), non la
seconda per punteggio. Nel caso pilota l'alternativa 2 ha punteggio 0,608, posizione 3. La pagina la
presenta come "the alternatives selected by the ranking model".
Correzione: inviare `ruolo` e scrivere "migliore sull'annata peggiore".

**8. Un campo entro circa 50 m dal pilota può sovrascrivere la cache del pilota (in linea).**
File: `local_analysis.py:31-38` e `:194-197`, `api.py:241` e `:262` (soglia di 1 m).
Prova: il punto `[10.0004, 45.2003]` (circa 50 m) non è "exact_pilot", ma `normalized_point` lo
arrotonda a `(10.0, 45.2)` e `_point_dir` restituisce
`data/processed/lat45.200_lon10.000`. Offline dà 409 (verificato). In linea `_work`
rigenererebbe con parametri SoilGrids e salverebbe con `save_ensemble(lat=45.2, lon=10.0)` sopra
l'ensemble del pilota. `_cache_is_current` controlla solo i file YAML e quindi accetterebbe la cache
sovrascritta. Da quel momento ogni report "Cremona pilot" mostrerebbe risultati locali. Non l'ho
eseguito, perché richiede la rete.
Correzione: in `/prepare` e `/analyze` trattare come pilota ogni punto che arrotonda alla cella del
pilota, e vietare a `_work` di scrivere in quella cartella.

**9. Il centro dell'area è diverso tra frontend e API.**
File: `frontend/src/lib/mapConfig.ts:7` (Cremona città 10.0244, 45.1336) e `api.py:28` (pilota 10.0,
45.2): 7,6 km di differenza.
Prova: il punto `[10.035, 44.245]` è a 98,8 km dal centro del frontend (si può disegnare), ma
`/prepare` risponde 422 OUTSIDE_DEMO_AREA perché è a 106,2 km dal pilota.
Correzione: usare per il cerchio del frontend il centro del pilota esposto da `/api/v1/health`
(`pilotPoint`).

**10. Offline il flusso principale non produce mai un report, salvo che sul punto esatto del
pilota.**
File: `frontend/src/lib/engineApi.ts:36` (`use_pilot_reference: false` fisso),
`Analysis.tsx:122`.
Prova (browser): un campo a Cremona città dà "The selected field has no cached local climate and soil
results. Set FIELDWISE_OFFLINE=0 …". L'errore è pulito e corretto (nessuna sostituzione nascosta col
pilota), ma la modalità `pilot_reference` dell'API non è raggiungibile dall'interfaccia, e per la
dimostrazione offline un campo disegnato a mano non funziona mai.
Correzione: dopo `PREPARATION_UNAVAILABLE` offrire un pulsante esplicito "usa il riferimento del
pilota di Cremona", con l'etichetta già prevista (`sourceMode: pilot_reference`).

**11. Il nome della rotazione attuale non corrisponde a quello inserito.**
File: `api.py:139` (`label = classe` canonica).
Prova: l'utente inserisce Maize → Soybean → Winter wheat. Il report mostra come "Current rotation"
Winter wheat → Maize → Soybean (stessa classe ciclica, ordine diverso), mentre la scheda Dettagli
mostra l'ordine inserito.
Correzione: mostrare l'ordine dell'utente e indicare "(stessa rotazione ciclica)".

**12. In modalità locale le frasi citano comunque la Lombardia.**
File: `api.py:121-125`.
Prova (da codice): in `local_estimate` le note dicono "No region-specific compliance filter was
applied", ma i rischi riportano "Not compliant with the Lombardy … rules" e `_rischi` del motore
usa `regime=None` (il peggiore tra i regimi). Le due cose sono incoerenti.
Correzione: in modalità locale usare lo stato del regime peggiore e dirlo.

### Minori

**13.** `api.py:111`: qualsiasi differenza sopra 1e-7 diventa una frase, e ne nascono frasi come
"Worst-year relative yield: 93.7% to 93.7%." (verificato in irrigazione libera). Correzione: usare le
soglie del motore (`SOGLIA_EVIDENZA` 5%, `SOGLIA_HUMUS`).

**14.** `api.py:322`: le note italiane del motore ("con queste priorita' e questo scenario le rotazioni
non si distinguono") finiscono nell'interfaccia inglese. Correzione: tradurle con una tabella fissa.

**15.** `ReportDashboard.tsx:79`: con l'economia disattivata, il menu del grafico Compare offre comunque
"Economic margin" (visto nel browser). Correzione: filtrare `REPORT_METRICS` come in
`reportMarkdown.ts:43`.

**16.** `api.py:46`: un punto `NaN` produce HTTP 500, perché la risposta 422 riporta il NaN e non è JSON
valido. Una priorità `true` è accettata come 1. Dal frontend non succede. Correzione: validatore
`strict`/`allow_inf_nan=False`.

**17.** `npm run lint` esce con 1: `test-advanced-analysis.cjs` (6 `require` vietati) e
`ReportDashboard.tsx:152` (setState dentro useEffect). Correzione: escludere il `.cjs` dal lint o
convertirlo, e calcolare la scheda visibile senza effetto.

**18.** Codice morto: `src/app/reports/ReportDashboard.tsx` non è importato da nessun file, e
`reportDemo.ts` (`createDemoReport`) non è usato (`/reports/preview` reindirizza). I valori
dimostrativi non possono finire in un report vero (verificato con grep), ma conviene eliminarli.

**19.** `local_analysis.py:64` e `:203-204`: l'impronta non copre `ensemble_dettaglio.csv` (da cui
derivano le finestre storiche) né `power_site.json`. `_JOBS` cresce senza limite. Ogni punto
diverso entro 100 km avvia un ensemble completo e crea una cartella in `data/processed`, quindi
un'API esposta in rete sarebbe facile da sovraccaricare. Dopo un riavvio, i job in corso si perdono
(il frontend riceve 404 e mostra un errore). Correzione: impronta anche per il dettaglio, limite ai
job, nessuna esposizione pubblica senza autenticazione.

**20.** `api.py:157-176`: `_cache_is_current` confronta solo gli YAML dei parametri, non la versione
del codice del motore. Oggi la cache è corretta (ricalcolo identico), ma una modifica al codice senza
modifiche agli YAML non verrebbe rilevata. Correzione: salvare e confrontare `__version__` o un hash
del codice.

**21.** `report_export.py:39-42`: su macOS non trova font Unicode e usa Helvetica. In Anteprima "→",
"−", "Δ" e "≥" si vedono, ma con altri lettori potrebbero non vedersi. Correzione: aggiungere i
percorsi macOS o includere un font TTF.

**22.** `frontend/src/views/Home.tsx`: "In just a few moments, you'll receive…", mentre la preparazione
locale richiede minuti (lo dice anche `Analysis.tsx:293`). Le pagine `progetto/*` sono vuote: non
contengono numeri inventati, ma nemmeno i limiti.

## Cosa funziona (verificato)

- **Numeri.** Su 6 casi (tre scenari, pesi uguali, solo profitto, pesi misti con cover, rotazione
  inserita in un altro ordine) etichette, punteggi e indicatori dell'API coincidono con
  `ranking.confronta` del motore (scarto 0,0). `comparedRotations` coincide con `n_confrontate`.
- **Unità.** `resa_rel_*` sono frazioni e il frontend moltiplica per 100 una sola volta; irrigazione
  in mm/anno, concime e lisciviazione in kg N/ha/anno, humus in t/ha/anno, margine in €/ha/anno. I
  nomi dei campi TypeScript corrispondono a quelli dell'API. I segni sono giusti (Δ = alternativa −
  attuale, nel PDF e nella scheda Economia). Nel percorso reale il frontend non ricalcola né inventa
  valori.
- **Pesi.** Passano soltanto a `ranking.confronta`/`score`. Le chiavi sconosciute sono rifiutate, così
  come i valori fuori 0–10 e la somma nulla. Azzerare `profitto` senza economia avanzata è coerente:
  il margine non entra nel punteggio e la scheda Economia è nascosta. Il fronte di Pareto resta sui
  7 indicatori del motore, come dichiara la pagina.
- **Rotazioni.** Le 216 rotazioni (con e senza cover, ogni ordine) × 3 scenari ricevono tutte una
  risposta 200 con l'attuale e 2 alternative. `classe_rotazione_attuale` riconduce correttamente
  ordine e classe ciclica. Le alternative sono conformi al regime lombardo e l'attuale resta visibile
  anche se non conforme (mais > mais > mais).
- **Area.** Il limite di 100 km funziona (Roma, lat/lon invertite e 106 km → 422). Entro 100 km senza
  dati locali la risposta è 409 LOCAL_DATA_NOT_READY, senza sostituire di nascosto i dati del pilota.
  `use_pilot_reference: true` dà `sourceMode: pilot_reference` con la nota "NOT location-specific".
- **Offline.** `/prepare` per un campo nuovo risponde 409 PREPARATION_UNAVAILABLE con un messaggio
  chiaro, e nel browser l'errore compare sotto il pulsante. Il pilota risponde "ready".
- **Cache.** La cache del pilota è aggiornata (ricalcolo in memoria identico). Il controllo delle
  impronte accetta file con fine riga LF o CRLF.
- **Campi nuovi (`local_analysis.py`).** Usa `rotation.build_context` del motore, che tramite
  `weather.available_years` esclude la pioggia POWER dopo il 2022. Il suolo viene da SoilGrids con le
  funzioni del motore (`soil.profile_properties`, Saxton–Rawls). Il clima viene da NASA POWER. Non
  modifica file del motore né `params/` (usa `params.override` in memoria). Marca le voci cambiate
  `verificato: False` con la fonte, e il report le etichetta "local_estimate … NOT a validated
  field-scale forecast". Il lock protegge `_JOBS`, e un secondo avvio sullo stesso punto riusa il job.
- **Sicurezza di base.** CORS limitato a localhost:3000 (più l'elenco da variabile d'ambiente),
  senza credenziali. Il nome del file PDF è ripulito. I campi sconosciuti di `/analyze` sono
  rifiutati (`extra="forbid"`). Il testo del PDF è sottoposto a escape.
- **Export.** Il PDF dal browser restituisce HTTP 200, `application/pdf`, 20 kB, con il nome del
  file corretto. Una richiesta con markdown troppo corto risponde 422.
- **Test e controlli.** `pytest -q` exit 0; `tsc --noEmit` exit 0.

## Cosa non ho potuto verificare

- La preparazione in linea di un campo nuovo (download POWER/SoilGrids, `_work`, scrittura di
  `fieldwise_local.json`) e quindi il percorso `local_estimate` con dati veri: vietato andare in rete.
  È verificato solo dal codice e dal test con mock.
- La sovrascrittura della cache del pilota (n. 8): dedotta dal codice e dal percorso calcolato, non
  eseguita.
- Excel: ho letto il codice, non ho aperto il file generato.
- La resa dei glifi del PDF con lettori diversi da Anteprima di macOS.
