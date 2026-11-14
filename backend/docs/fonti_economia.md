# Fonti di `params/economia.yaml`

Data di accesso di tutte le fonti: 2026-11-14. I valori sono stati letti dai riassunti dei risultati di ricerca
web (non aprendo ogni listino), quindi in `economia.yaml` i prezzi sono `verificato: false`. Da riaprire e
confermare prima di citarli.

## 1. Prezzi della granella (EUR/t)

- Borsa Merci di Piacenza, seduta del 5 novembre 2026, riportata da ilPiacenza (11 novembre 2026):
  granoturco nazionale comune ibrido prod. 2026 251-257 EUR/t; soia in granella 503-507 EUR/t.
  URL: https://www.ilpiacenza.it/economia/prezzi-all-ingrosso-in-calo-il-grana-padano-granoturco-e-soia-aumenti-per-foraggi-e-farine.html
- Camera di Commercio Emilia-Romagna, listino prezzi all'ingrosso cereali n. 21 del 22 ottobre 2026:
  frumento tenero nazionale prod. 2026 270-274 EUR/t; mais 256-262; soia 509-513.
  URL: https://prezzi.emilia.camcom.it/dataentry/site/ingrosso/lists/download/pdf?category=3741
- Non usato: bollettino CCIAA Cremona (https://www.cr.camcom.it/files/Statistica/Prezzi/bollettini_trimes/2026/20261.pdf),
  non raggiungibile (HTTP 410). Se si ottiene il listino di Cremona, sostituire i tre prezzi.

## 2. Azoto (EUR/kg N)

- Urea 46% N: 637 EUR/t in Francia il 2 novembre 2026, 605-745 EUR/t in Germania il 3 novembre 2026
  (report di mercato UE trovato via ricerca web, non un listino italiano): 637/460 = 1,38 EUR/kg N, arrotondato a 1,4.
- Contesto: urea granulare FCA Italia da 530 a 700 EUR/t tra il 26 febbraio e il 12 marzo 2026 (Bonafide Research).
  Il prezzo e' molto volatile: e' un'assunzione dichiarata.

## 3. Irrigazione (EUR/ha per mm)

- Vigo F., Universita' degli Studi di Milano, progetto SMART WUE (PSR Lombardia 16.2.01), "Valutazioni economiche ed
  ambientali dei diversi sistemi irrigui del mais", tabelle "Volumi irrigui" e "Analisi economica" (5 aziende, 2024).
  URL: https://smartwue.unimi.it/wp-content/uploads/sites/54/2024/12/Valutazioni-economiche-ed-ambientali-dei-diversi-sistemi-irrigui-del-mais.pdf
- Conversione: costo irrigazione (EUR/ha) / mm distribuiti (m3/ha / 10), anno 2024:

  | Metodo | m3/ha | mm | EUR/ha | EUR/ha per mm |
  |---|---|---|---|---|
  | Pivot | 2250 | 225 | 184,01 | 0,82 |
  | Scorrimento | 4404 | 440 | 125,10 | 0,28 |
  | Microirrigazione | 2520 | 252 | 371,38 | 1,47 |
  | Rotolone | 2500 | 250 | 394,37 | 1,58 |

- Il costo e' di impianto e uso (capacita' operativa, ripetizioni, ammortamento, manutenzione). Non include il contributo
  consortile, che ha natura tributaria ed e' dovuto anche senza prelievo. Scelto 0,8 (pivot).

## Cosa non e' nel margine
Seme, difesa, meccanizzazione, costi fissi, contributi PAC. Scelta dell'utente: i costi sono solo quelli che il modello simula.
