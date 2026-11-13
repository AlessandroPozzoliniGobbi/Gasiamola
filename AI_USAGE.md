# Uso dell'intelligenza artificiale

Dichiarazione richiesta dalla NASA Space Apps Challenge 2026. Stato al 2026-11-13.

## Cosa è stato prodotto con l'IA

Il codice (`src/`, `app/`, `tests/`), la ricerca e la lettura delle fonti per i parametri (`params/`, `docs/fonti_*.md`), i rapporti (`reports/`, `data/CHECKS.md`), il report per il team, il README e questo file sono stati prodotti con agenti Claude (Anthropic) sotto la direzione del team: un agente pianificatore che divide il lavoro e ne tiene il registro (`PLAN.md`) e subagent dei modelli Opus e Sonnet. In breve: Sonnet per i client dei dati, i test, l'interfaccia e la documentazione; Opus per la ricerca dei parametri, il motore, la validazione, l'analisi di sensibilità e le revisioni indipendenti. Anche il primo motore (`legacy/fieldwise_engine.py`) e la proposta (`legacy/FIELDWISE_proposta_modello.pdf`) sono stati scritti con Claude. Le decisioni di scelta (per esempio D13, fonte della sostanza organica) sono registrate in `PLAN.md` e spettano al team. Le figure sono grafici generati da codice (matplotlib) sui dati; nessuna immagine è generata con IA e non sono usati loghi NASA.

## Come è stato controllato il lavoro

- **Parametri con fonte.** Ogni numero agronomico ha valore, unità, fonte, riferimento e URL, e un campo `verificato` (vero solo se il valore è stato letto dalla fonte durante il lavoro). Senza fonte ufficiale è `assunzione: true` e finisce in sensibilità. Lo stato si vede con `python -m fieldwise.params --check`.
- **Revisione indipendente dei parametri** (`reports/params_review.md`): un agente diverso dagli autori ha riaperto le fonti per 29 voci: 22 confermate, 7 usate fuori dalle condizioni della fonte, nessun errore di trascrizione. Le correzioni sono state applicate.
- **Test** automatici (`pytest`, 1272 test: bilanci di massa chiusi alla precisione di macchina, esempi della FAO, casi limite) e controlli di qualità dei dati (`data/CHECKS.md`).
- **Verifica scientifica indipendente del motore** (`reports/engine_review.md`) con prova di mutazione: guasti inseriti di proposito nel codice per vedere se i test li rilevano (7 su 8 rilevati; il guasto non rilevato ha portato ai test della catena di rotazione). La revisione ha trovato errori (coefficiente colturale singolo contro duale, Curve Number, test mancanti) che sono stati corretti. Una verifica indipendente dell'ensemble e della classifica: `reports/phase5_review.md`.
- **Validazione contro osservazioni** (`reports/validation.md`): SMAP, NDVI MODIS e rese ISTAT, con intervalli di confidenza e anche i risultati negativi (soia non confermata, frumento negativo).
- **Nessuna taratura sul risultato.** I parametri non sono stati modificati per avvicinare il modello alle osservazioni; quando un criterio atteso non si è verificato (caldo del mais nel 2022) è stato dichiarato non soddisfatto (`PLAN.md`, D16). L'analisi di sensibilità (`reports/sensitivity.md`) misura quali parametri incerti cambiano la decisione.

## Cosa non è stato verificato da una persona

Il team deve aggiornare questo elenco con ciò che ha controllato di persona.

- Le fonti sono state lette da agenti: il campo `verificato: true` significa che un agente ha letto il valore sulla fonte, non che una persona lo abbia riletto. Per 50 voci su 372 il valore non è stato verificato sulla fonte originale (ricordato o preso da citazioni) e 26 sono assunzioni.
- Le revisioni indipendenti sono state fatte da altri agenti, non da persone: nessun esperto agronomo o idrologo ha controllato le equazioni, i parametri o le conclusioni.
- Il codice non è stato letto riga per riga da una persona; le equazioni sono state confrontate con le fonti solo dagli agenti revisori (alcuni controlli di coerenza senza riaprire la fonte, indicati in `reports/engine_review.md`).
- L'aspetto e l'uso dell'app nel browser non sono stati controllati da un agente né da una persona (i test dell'app girano senza browser).
- I testi (README, report, rapporti) non sono stati riletti da una persona per esattezza; i numeri del report sono generati dai file della cache, quelli del README sono copiati da quei file.
- Le citazioni bibliografiche sono state raccolte dagli agenti; alcune fonti sono state consultate solo tramite sintesi o citazioni secondarie (per esempio un articolo non letto è segnalato con `verificato: false`).
