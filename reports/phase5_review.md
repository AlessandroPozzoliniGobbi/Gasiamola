# Verifica indipendente fase 5 (ensemble + classifica)

Esito: la fase 5 si chiude con riserva. Nessun difetto bloccante sui numeri; ci sono difetti di formulazione
(frasi fuorvianti per l'agricoltore) e di robustezza da correggere. Script di verifica nello scratchpad della sessione.

## Criteri
| # | Esito | Misura |
|---|-------|--------|
| 1 | Superato (con difetto D4) | 216 rotazioni distinte, 76 classi cicliche, nessuna esclusa. 216 x 23 annate x 3 scenari = 14904 tentativi = 11016 riuscite + 3888 scartate (contate). Attuale: "mais" -> +1 classe marcata; "mais > soia+cover > frumento" -> classe `frumento > mais > soia+cover` marcata; "soia > frumento" e ["frumento","mais"] (lunghezza 2) -> +1 classe, conformita `non_valutabile`. |
| 2 | Superato | n_simulazioni + n_scartate = n_membri x 23 in tutte le 228 righe. 17 annate di partenza producono risultati (2000-2016), 6 scartate per "oltre la serie meteo affidabile". Le scartate non entrano nelle statistiche (n per riga = riuscite). Vedi D6. |
| 3 | Superato | Presenti resa mediana/min/p10, irrigazione, concime, N lisciviato, humus, giorni_caldo, f_acqua/f_caldo/f_rotazione (+ ruscellamento, percolazione, deficit N). |
| 4 | Superato | 7.0 s, 6.8 s, 6.3 s (limite 60 s). |
| 5 | Superato | score() su 3 scenari con pesi uguali e solo "acqua": la sintesi resta identica (equals); grep: ne' ensemble.py ne' rotation.py contengono pesi di preferenza (solo "peso" fisico dell'assorbimento N in rotation.py:575). |
| 6 | Superato | Forza bruta indipendente vs pareto_front: 31/33/29 non dominate (solo_pioggia/tetto/libera), insiemi identici. Senza tolleranza (esatto) libera darebbe 31: la tolleranza 1e-6 e' voluta (D8, minore). |
| 7 | Superato | 5 classi a seme 12345 x 3 scenari: differenza massima 0 su mediana, min, p10 di resa e mediana di irrigazione, N lisciviato, humus; verificato anche su tutte le 228 righe per mediana e min (diff 0). |
| 8 | Parziale | Cicliche: 76/76 classi hanno esattamente le permutazioni cicliche come membri. Equivalenti: 93 righe (31 classi x 3), tutti gli indicatori identici (<1e-9) tranne `resa_rel_p10` in 6 righe (2 classi: `frumento+cover > frumento > frumento` e `frumento+cover > frumento+cover > frumento` vs `frumento > frumento > frumento`), differenza 0.0119 (D3). |
| 9 | Superato | Punteggio a mano su 3 rotazioni = funzione (0.64574, 0.504255, 0.328349). Verso corretto (resa +, irrigazione/concime/N lisciviato -, humus +). Punteggi parziali in [0,1]. Indicatore costante -> 0.5; pesi {} / tutti 0 / negativi / NaN / priorita' ignota -> ValueError; solo_conformi=True lascia 8 classi (regime Lombardia) ; filtro che svuota -> ValueError chiaro; regime ignoto -> ValueError. |
| 10 | Superato per i numeri, non per la formulazione | 561 numeri nelle frasi di evidenze e rischi (3 attuali x 3 scenari x pesi uguali / solo acqua x alternative): 0 non riconducibili alla sintesi. Sempre >= 2 alternative distinte e diverse dall'attuale (0 problemi). Frase fuorviante D1. |
| 11 | Superato | Con rete bloccata (socket patchato) e FIELDWISE_OFFLINE=1 e =0: load_ensemble ok (11079 righe dettaglio, 231 sintesi), run_ensemble ok, cache == ricalcolo (diff 0), CacheMiss per punto assente, confronta funziona sulla cache. |
| 12 | Superato | pytest completo: codice di uscita 0. Tre esecuzioni dell'ensemble: dettaglio e sintesi identici (DataFrame.equals). |

## Difetti in ordine di gravita'
- D1 (medio, fuorviante) `ranking._rischi`: la frase "nell'anno peggiore la resa relativa scende a X (attuale: Y)" e' scritta sempre, anche quando X > Y (6 alternative su 6 nel caso "mais": 0.82 contro 0.73). Un miglioramento e' presentato come rischio. Idem `_evidenze_e_peggioramenti`: la stessa grandezza compare in evidenze (+12%) e in rischi.
- D2 (medio) `ranking.score`: se tutti gli indicatori pesati sono costanti (es. peso solo "acqua" in `solo_pioggia`, irrigazione = 0 ovunque) tutti i punteggi valgono 0.5 e l'ordine e' alfabetico; `frumento > frumento > frumento` risulta "primo" senza avviso e `confronta` lo propone come migliore. Servirebbe una nota ("la priorita' scelta non discrimina in questo scenario").
- D3 (basso) `ensemble._sintesi`/`_equivalenze`: p10 di una classe equivalente differisce (0.0119) perche' il percentile e' calcolato su 51 valori (3 membri) contro 17; contraddice "indicatori identici".
- D4 (basso/robustezza) `ensemble.parse_rotazione` / `run_ensemble`: coltura sconosciuta ("pomodoro") o stringa vuota danno `KeyError` grezzo da `rotation._next_sowing`; nessuna validazione con ValueError comprensibile contro le colture di `ctx.crop`.
- D5 (basso) la rotazione "mais" (lunghezza 1) e "mais > mais > mais" sono classi distinte con numeri diversi (resa mediana 0.917 vs 0.912, concime 312 vs 280 kg N/ha): stessa monocoltura, risultati diversi non spiegati; `confronta` non esclude l'una come alternativa all'altra (mai accaduto nei 18 casi provati).
- D6 (basso) `meta.annate_partenza` = [2000, 2022] ma le simulazioni riuscite usano solo 2000-2016 (la serie affidabile finisce nel 2019): il rischio non include le annate recenti; il metadato induce a pensare il contrario.
- D7 (basso, linguaggio) "resa nell'anno peggiore" e' il minimo, tra le annate di partenza, della resa media della rotazione triennale, non la resa del singolo anno peggiore (quella e' `resa_rel_minima_coltura`). Il nome tecnico del regime ("lombardia_impegno_quinquennale") e "il fattore che limita la resa..." tra le evidenze sono gergo/fuori posto per un agricoltore.
- D8 (minimo) `pareto_front`: tolleranza relativa 1e-6; a tolleranza zero il fronte "libera" passa da 29 a 31.
- D9 (minimo, da lettura del codice, non eseguito) `confronta`: se la rotazione attuale ha 0 simulazioni riuscite viene tolta da `insieme` e la nota dice "non marcata nella sintesi", che e' inesatto.

Nessuna incoerenza numerica trovata: resa min <= p10 <= mediana in tutte le righe, nessun NaN negli indicatori principali, nessuna resa > 1, irrigazione 0 in solo_pioggia, nessun valore negativo di irrigazione o lisciviazione.

## Giudizio
La fase 5 si puo' chiudere dopo correzione di D1 e D2 (testo/nota, poche righe) e, preferibilmente, D4 e D6; gli altri sono rimandabili. I criteri numerici 1-12 sono tutti soddisfatti.
