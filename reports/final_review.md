# FIELDWISE - verifica finale indipendente

Data: 2026-11-13. Verificatore: agente indipendente (non autore del codice). Stato verificato: commit `a767a8e`. Il working tree coincide con HEAD per `src/`, `params/`, `app/`, `reports/`, `README.md`; differiscono solo i file di stato in `.omc/`. Nel repository è stato scritto solo questo file. Installazione, test e demo sono stati eseguiti su una copia in una cartella temporanea (senza `.venv`, `.git`, `graphify-out`, `.omc`; con `data/`).

## 1. Installazione da zero

| Passo (come scritto nel README) | Esito | Note |
|---|---|---|
| `uv venv --python 3.11 .venv` | OK | |
| `uv pip install --python .venv/bin/python -r requirements.txt` | OK | 2,6 s con la cache di uv già presente sulla macchina: un'installazione con cache vuota non è stata misurata |
| `uv pip install --python .venv/bin/python -e .` | OK | `fieldwise==0.2.0` |
| Variante senza uv (`python3.11 -m venv ... pip install -r requirements.txt -e .`) | non provata | |
| `FIELDWISE_OFFLINE=1` + proxy inesistente (`HTTP(S)_PROXY=127.0.0.1:9`), `pytest -q -rfEs` | exit 0 | 1272 test raccolti (uguale al README), 1271 passati, 1 saltato, 0 falliti; 103 s (il README dice "circa 1 minuto"; un altro giro sulla stessa macchina ha impiegato 65 s) |
| Test saltato | atteso | `tests/test_weather.py:117`: "IMERG presente in cache: il caso CacheMiss non è verificabile" |
| Avvisi | non bloccanti | `Pandas4Warning` `Timestamp.dayofyear` (`src/fieldwise/weather.py:180`), 962 occorrenze; `PytestRemovedIn10Warning` per fixture di classe (`tests/test_water.py`) |

Dipendenze mancanti: nessuna. Comandi che non funzionano come scritti: nessuno.

## 2. Demo offline (rete negata da variabile d'ambiente e da proxy inesistente)

| Comando | Esito | Durata |
|---|---|---|
| `python -m fieldwise.params --check` | "Nessun errore"; 372 voci, 26 assunzioni, 50 non verificate | <1 s |
| `python -m fieldwise.ensemble --lat 45.2 --lon 10.0 --attuale "mais"` | exit 0; 11.016 simulazioni, 76 classi per 3 scenari. `ensemble_sintesi.csv` ed `ensemble_dettaglio.csv` **identici byte per byte** alla cache; in `ensemble_meta.json` cambiano solo `calcolato_il` e `tempo_s` | 6 s |
| `python -m fieldwise.validation --no-figure` | exit 0; `validation_summary.json` identico byte per byte | 23 s |
| `streamlit run app/streamlit_app.py --server.headless true --server.port 8611` | `/_stcore/health` = ok, `/` = HTTP 200; processo chiuso | ~5 s |
| `pytest tests/test_app.py` | exit 0, 23 test | 18 s |
| Loghi NASA nel repository | nessuno: le sole immagini tracciate sono le 7 figure in `reports/figure/`. `README.md:200` dichiara "Nessun logo o simbolo NASA" | |
| Affermazioni di affiliazione o approvazione | nessuna in `app/`, `README.md`, `AI_USAGE.md`, nel report o in `docs/` (ricerca di logo, endorse, affiliat, approvat, ufficiale, sponsor, patrocin) | |

## 3. Numeri del report e del README contro gli output

Fonti: `ensemble_sintesi.csv` e `ensemble_dettaglio.csv` (rigenerati e identici), `ensemble_meta.json`, `validation_summary.json`, `sensitivity_summary.json`, `data/CHECKS.md`, `fieldwise.ranking.score` (pesi uguali), `fieldwise.params --check`.

| # | Report / README (sezione) | Valore nel testo | Ricalcolato o riletto | Esito |
|---|---|---|---|---|
| 1 | In breve | 11.016 simulazioni in 6,7 s | meta 11016; 6,683 s | OK |
| 2 | In breve / §9 / §11 / README | mais continuo 45/45, 30/45, 43/45 | `score`: 45/45, 30/45, 43/45 | OK |
| 3 | Tab. cambiamenti | 372 voci, 26 assunzioni, 50 non verificate | `--check`: 372 / 26 / 50 | OK (ma vedi P5) |
| 4 | Tab. cambiamenti | cover: lisciviazione 21,0 → 15,7 (25%) | 21,04 → 15,69 (−25,4%) | OK |
| 5 | Tab. cambiamenti | libera: mais 294 mm, 302 kg N; MSF 197 mm, 174 kg N | 294,4 / 302,4; 196,6 / 173,9 | OK |
| 6 | §2 / CHECKS | ET0 890 mm/anno | CHECKS D2: 890 | OK |
| 7 | Tab. cambiamenti | rapporto pioggia 1,02 fino al 2022, 1,46 dopo | CHECKS: 1.02 / 1.46 | OK |
| 8 | §4 | mediana di f_acqua del mais continuo 0,60 / 0,94 / 1,00 | sintesi 0,597 / 0,938 / 1,000, ma è una **media**; la mediana sul dettaglio è **0,58** in solo pioggia | **NON OK (etichetta)** |
| 9 | §4 | f_caldo del mais continuo tra 0,972 e 0,999 | dettaglio 0,972 – 0,999 | OK |
| 10 | §4 / PLAN D16 | f_caldo 2022 = 0,958 | CHECKS: 0,958 | OK |
| 11 | §5 | 76 classi, 45 non equivalenti | 76 / 45 per scenario | OK |
| 12 | §6 | 17 annate di partenza, anni valutati 2003-2019 | meta e dettaglio: 17; 2003-2019 | OK |
| 13 | §7 | 3.888 scartate | meta 3888 | OK |
| 14 | §9 solo pioggia | mais continuo 0,54 / 0,44 / 0 / 136 / 12 / −469 | 0,54 / 0,44 / 0 / 135,9 / 12,2 / −0,47 t | OK |
| 15 | §9 tetto | MSF 0,90 / 0,80 / 100 / 172 / 15 / −476 | 0,901 / 0,798 / 100,0 / 171,6 / 14,96 / −0,476 | OK |
| 16 | §9 libera | M>F+c>S 0,99 / 0,93 / 202 / 169 / 14 / −406 | 0,988 / 0,930 / 202,5 / 169,2 / 13,9 / −0,406 | OK |
| 17 | §9 | frumento continuo 0,77 / 0,72 / 194 / 6 / −729 | 0,77 / 0,72 / 193,6 / 6,02 / −0,73 | OK |
| 18 | §9 | −33% acqua, −42% concime (libera) | −33,2% / −42,5% | OK |
| 19 | §9 | humus in calo in 73 classi su 76 (tetto irriguo) | 73/76 | OK |
| 20 | §9 classifica | prime e punteggi 0,68 / 0,65 / 0,63; mais continuo 0,27 / 0,47 / 0,47 | identici | OK |
| 21 | §9 classifica | prima tra le conformi 0,83 / 0,67 / 0,74 | identici, stesse classi | OK |
| 22 | §10 | SMAP, mais continuo, tetto: +0,71 [+0,62, +0,81], n = 92 | 0,714 [0,625, 0,806], 92 | OK |
| 23 | §10 / README | ISTAT mais, tetto: +0,70 [+0,33, +0,88], n = 17 | identico | OK |
| 24 | §10 / README | soia +0,27 [−0,24, +0,67]; frumento −0,50 [−0,79, −0,03] | identici | OK |
| 25 | §10 | NDVI lug-ago: +0,63 (solo pioggia) e +0,60 (tetto), n = 22 | 0,63 / 0,60, 22 | OK |
| 26 | §11 | prima cambia con 29 / 1 / 9 parametri; 107 non contano, 82 senza effetto | OAT: 29 / 1 / 9; 107; 82 | OK |
| 27 | §11 MC | 226 campioni validi; prima resta 62/33/36%; ultimo quarto 99/92/99% | 226; 61,5 / 33 / 36; 99,1 / 92,0 / 98,7 | OK |
| 28 | §11 tab. strutturali | tau e "cambia la prima" delle 10 scelte | tutti identici | OK |
| 29 | §11 pesi | 9 / 12 / 16 prime diverse | 9 / 12 / 16 | OK |
| 30 | §12 | lisciviazione tra 6 e 21 kg N/ha/anno | 6,0 – 21,2 | OK |
| 31 | §12 / CHECKS | pioviggine 31% contro 21%; giorni sopra 35 °C r 0,46 | CHECKS: 31% / 21%; 0,46 | OK |
| 32 | README | 1272 test | 1272 raccolti | OK |
| 33 | README | ensemble "circa 7 secondi" | 6 s | OK |
| 34 | README | SMAP r circa 0,7; NDVI r circa 0,6 | 0,71; 0,60-0,63 | OK |

**Sensibilità contro ensemble in cache.** L'hash dei parametri è lo stesso (`2b8a878cc861…` in `sensitivity_summary.json`, `reports/sensitivity.md` ed `ensemble_meta.json`). Le prime tre rotazioni per scenario in `base` coincidono con `score` sull'ensemble attuale in tutti e tre gli scenari, e coincide anche la posizione del mais continuo. Unica differenza: `sensitivity.md` cita "ensemble calcolato il 2026-11-13T13:10:26", mentre la cache dice 13:26:10. Il contenuto è identico, perché l'ensemble è deterministico (verificato rigenerandolo), quindi la differenza è solo di presentazione. `sensitivity.md` cita inoltre il commit 2f8776d "con modifiche locali non registrate": da allora le modifiche sono finite in a767a8e.

## 4. Parametri a campione

Metodo: `iter_entries` su tutti i `params/*.yaml`; voci con `verificato: true` il cui percorso non compare in `reports/params_review.md`: 295 voci. `random.seed(20261113)`, `random.sample(..., 8)`. Pagine web aperte: 7 (6 fonti più 1 tentativo su MODIS, vedi 5f).

| Voce | Valore | Fonte aperta | Valore nella fonte | Esito |
|---|---|---|---|---|
| `heat.colture.frumento.t_limite` | 35 °C | Deryng et al. 2014, Tab. A.1 (PEGASUS 1.1) | frumento Tcr 25, Tlim 35 (anche mais 32/45, soia 35/40) | OK |
| `cover_crop.calendario_agronomico.semina_oltre_cui_cala_la_produttivita` | 09-15 | BENCO 2020, §3.2 | "Semine oltre la metà di settembre generalmente comportano una minore produttività" | OK |
| `crops.frumento.t_upper` | 26 °C | AquaCrop v7.3 Annex I, I.10 Wheat (luglio 2026) | Tupper 26,0 | OK (la taratura è per frumento primaverile: da dichiarare) |
| `rotation_rules.successioni_vietate.mais_soia_soia.lombardia_impegno_quinquennale` | non_conforme | Lombardia, Norme tecniche 2026, Parte generale, pp. 6-7 | quinquennale: almeno 3 colture principali, al massimo un ristoppio per coltura; deroga a 2 colture | OK (esito derivato dalla regola, coerente) |
| `cover_crop.acqua.frazione_p` | 0,55 | FAO-56, Tab. 22 | cereali (orzo, avena, frumento) p = 0,55; la segale da granella non è in tabella | OK per analogia |
| `soil.strati_soilgrids.s0_30.carbonio_organico` | 13,5 g/kg | ERSAF 2024, Tab. 19 | Bassa Pianura Centrale 13,5 ± 4,7 | OK |
| `crops.mais.gdd_emergenza` | 100 | AquaCrop Annex I, I.2 Maize | dalla semina all'emergenza 60 - 100 GDD | OK (estremo alto) |
| `soil.strati_soilgrids.s100_200.sat` | 0,4372 | Saxton e Rawls 2006 (ricalcolato a mano: S 37,5%, C 24%, OM 1,448%) | θs = 0,4372 con DF = 1 | OK (con la densità SoilGrids di 1,53 sarebbe 0,423: è una scelta di metodo) |

Controllo con `fieldwise.params`: 0 voci senza fonte né `assunzione: true` + `motivazione` (il controllo lo impone e restituisce "Nessun errore"). Assunzioni: 26. Non verificate: 50. Voci con fonte bibliografica: 357 su 372; le altre 15 sono assunzioni motivate.

## 5. Principi non negoziabili

| Principio | Esito | Evidenza |
|---|---|---|
| (a) nessun parametro inventato | rispettato | `--check` senza errori; 8/8 voci a campione confermate sulla fonte; 26 assunzioni con motivazione |
| (b) gerarchia delle fonti dichiarata | rispettato | PLAN principio 2; per la sostanza organica ERSAF prevale su SoilGrids (D13), SoilGrids resta in sensibilità |
| (c) bilanci di massa giornalieri; pesi solo nella classifica | rispettato | `ranking.py` (intestazione) è l'unico modulo con i pesi; `rotation.py` ed `ensemble.py` non importano `ranking` né `PRIORITA` |
| (d) stato mai azzerato tra colture | rispettato | ciclo giornaliero unico (PLAN D6); `tests/test_rotation.py::test_stato_ereditato_conta`; un solo stato iniziale, a capacità di campo, prima del ciclo di avviamento |
| (e) niente previsioni meteo | rispettato | ensemble di annate storiche 2000-2022; l'app dice "Non sono previsioni del tempo" (`app/fw_confronto.py:174`) |
| (f) riproducibilità | parziale | 226 file `.meta.json` con `downloaded_at_utc`, `version`, `product`, `url`, `sha256`; manca solo per `data/raw/istat/_ratelimit/last_request.txt` (file di stato, non un dato). **MODIS: collezione ancora non chiarita**: i meta e il README (riga 132) dicono "versione non dichiarata dal servizio" (dichiarata, non risolta; la pagina di documentazione ORNL non la riporta in forma testuale). Ensemble e validazione rigenerati identici. La sensibilità è stata calcolata con modifiche non registrate, ora nel commit a767a8e |
| (g) onestà | rispettato | soia, frumento e caldo 2022 sono riportati con la stessa evidenza in README (righe 167, 180), report (In breve, riquadro in §4, §10, §12) e app (`st.error` sul frumento, avviso su ogni alternativa con frumento, testo sul caldo 2022). Unica eccezione: le formule in P5 |

## 6. Requisiti della challenge

| Requisito | Esito | Evidenza |
|---|---|---|
| Attuale contro almeno 2 alternative, con evidenze e rischi | soddisfatto | `ranking.confronta(n_alternative=2)`, pagina *Confronto*: attuale sempre mostrata, frasi "A favore" e rischi, fronte non dominato, conformità |
| Dati NASA usati in modo sostanziale | soddisfatto | **nel motore**: NASA POWER (meteo giornaliero ed ET0; prodotto modellato da MERRA-2 e radiazione satellitare, non osservazione diretta). **Solo come alternativa in sensibilità**: GPM IMERG V07. **Solo nella validazione**: SMAP SPL3SMP_E, MODIS MOD13Q1. SoilGrids e ISTAT non sono NASA |
| Spiegazioni per l'agricoltore | corrette e comprensibili | ET0 (prato ben bagnato, mm = l/m², si calcola dal meteo), SMAP (5 cm, 9 km, non vede le radici), NDVI (verde, 16 giorni, 250 m, satura), satellite contro misura a terra: corretti. Due semplificazioni minori: NDVI "tra 0 e 1" (in realtà tra −1 e 1); il NDVI usato nella validazione è una finestra di 2 km, non il pixel da 250 m |
| Affermazioni troppo forti | poche | "Ogni parametro ha una fonte" (P5); "f_acqua mediana" che è una media (P4); "il mais regge" con n = 17 su rese provinciali, accompagnato però da cautele adeguate |

## 7. Coerenza dei documenti e igiene del repository

| Controllo | Esito |
|---|---|
| File promessi dalla struttura del README | tutti presenti e tracciati (moduli, `params/SCHEMA.md`, 5 rapporti, PDF, `build_report.py`, 7 figure, `docs/fonti_*.md`, `legacy/`) |
| PLAN contro report e README | numeri coerenti (validazione, sensibilità, D13, D16). Incoerenze: (i) "Blocchi aperti" dice ancora che mancano le credenziali Earthdata e che IMERG e SMAP non si scaricano, mentre la cache e la validazione li usano; (ii) fase 9 "in corso"; (iii) il registro dice "la cover dimezza la lisciviazione" (vero per singolo intervallo) mentre il report dice "riduce meno: 25%"; (iv) "22 test" dell'app, ora sono 23 |
| AI_USAGE | coerente (1272 test, 29 voci riviste, 50/372 non verificate, 26 assunzioni) |
| CHECKS contro report | coerenti sui numeri controllati |
| Tracciati che non dovrebbero esserlo | `.omc/` (224 file di stato di uno strumento locale, con id di sessione, modificati a ogni sessione); `.claude/settings.json`, `.codex/hooks.json`; `graphify-out/` (20 file, circa 5 MB, comprese copie datate); `runs.pkl` (400 KB nella radice, pickle non referenziato da nessun file); `data/raw/istat/_ratelimit/last_request.txt`; `AGENTS.md` e `CLAUDE.md` (istruzioni per agenti: accettabili se dichiarate) |
| Dati pesanti | `data/raw/istat/cremona/dataflow_list.xml` (13 MB) e `structure_COLTIVAZIONI_2.xml` (10 MB): catalogo e struttura SDMX, necessari solo come provenienza dei codici |
| Segreti | nessuno trovato (`.netrc` ed `.env` nel `.gitignore`; ricerca di chiavi e token senza risultati; `~/.netrc` non letto) |
| Storia git | 6 commit, tutti con il messaggio "Descrizione delle modifiche" (5 nello snapshot iniziale più `a767a8e`, comparso durante la verifica): messaggi non informativi |

## LISTA DEI PROBLEMI

### Bloccanti per la consegna
Nessuno. Installazione, test, demo offline, app e numeri sono riproducibili.

### Da correggere
- **P1. Stato di strumenti locali tracciato in git.** `.omc/`, `.claude/`, `.codex/`, `graphify-out/`, `runs.pkl`, `data/raw/istat/_ratelimit/`. Evidenza: `git ls-files`. La storia di `.omc` contiene id di sessione locali. Correzione: `git rm -r --cached` di questi percorsi e aggiunta al `.gitignore`.
- **P2. Il PLAN è fermo a uno stato precedente.** `PLAN.md`, "Blocchi aperti": dice che IMERG e SMAP non si scaricano per mancanza di credenziali Earthdata, ma sono in cache e usati; la fase 9 è "in corso". Correzione: chiudere il blocco, registrare la verifica finale e chiudere la fase 9.
- **P3. Riferimento all'ensemble superato nella sensibilità.** `reports/sensitivity.md:11` e `sensitivity_summary.json` citano l'ensemble delle 13:10:26 e "modifiche locali non registrate"; la cache è delle 13:26:10. Il contenuto è identico (verificato), quindi il problema è di tracciabilità. Correzione: rilanciare la sensibilità (circa 6 min) sul commit attuale, oppure aggiungere una nota "ensemble rigenerato identico; codice = a767a8e".
- **P4. f_acqua chiamata "mediana" ma calcolata come media.** `reports/FIELDWISE_report.md` §4 e §12 ("mediana di f_acqua 0,60"); `reports/build_report.py:321,545` legge la colonna `f_acqua` della sintesi, che `ensemble.py:20` dichiara media. La mediana vera in solo pioggia è 0,58. Correzione: scrivere "media" oppure calcolare la mediana sul dettaglio.
- **P5. Formule troppo forti sulle fonti.** Report, "In breve" ("Ogni parametro ha una fonte") e tabella ("372 voci, ognuna con fonte"). Evidenza: `--check` conta 357 voci con fonte; le altre 15 sono assunzioni (8 su 9 in `scenarios`). Correzione: "ognuna con una fonte o con un'assunzione motivata".
- **P6. Avviso deprecato di pandas.** `src/fieldwise/weather.py:180` usa `Timestamp.dayofyear`, che sarà rimosso. Correzione: usare `day_of_year`, altrimenti con pandas 4 i test si rompono.

### Da dichiarare
- **P7. Collezione MODIS ancora non dichiarata.** README riga 132 e `.meta.json`. Correzione: verificare la colonna "Collection" del servizio ORNL (presumibilmente 6.1, ma non confermato da me) e scriverla, oppure lasciare la dichiarazione attuale.
- **P8. Origine di alcuni parametri.** `crops.frumento.t_upper` viene da una taratura AquaCrop per frumento primaverile, applicata al frumento autunnale. `cover_crop.acqua.frazione_p` è preso per analogia con i cereali (la segale non è nella Tab. 22). `sat` è calcolato con DF = 1 e non con la densità SoilGrids. Correzione: una nota per ciascuna voce.
- **P9. POWER non è un'osservazione diretta.** È modellato da MERRA-2 e da radiazione satellitare, mentre SMAP e MODIS entrano solo nella validazione. Correzione: dirlo in una riga nel README e nel report, alla voce "dati NASA usati".
- **P10. Dettagli minori.** Tempo dei test (65-103 s contro "circa 1 minuto"); NDVI "tra 0 e 1"; la variante d'installazione senza uv non è stata provata; i messaggi di commit non sono informativi.

## Giudizio
Il lavoro si può dichiarare chiuso alla condizione di correggere P1-P5, che richiedono poco tempo e non toccano il motore né i risultati. P6-P10 si possono dichiarare o correggere a scelta. I risultati numerici, la riproducibilità offline e l'onestà sui risultati negativi reggono la verifica.
