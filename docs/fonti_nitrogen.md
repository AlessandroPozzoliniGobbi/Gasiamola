# Fonti di `params/nitrogen.yaml`

Data di accesso di tutte le fonti: 2026-11-11. I PDF sono stati scaricati e letti per intero nelle parti citate
(testo estratto con `pdftotext`); i numeri in `nitrogen.yaml` con `verificato: true` sono stati letti lì.

## 1. Regione Emilia-Romagna — Disciplinari di produzione integrata 2023, Norme generali

- Riferimento: Regione Emilia-Romagna, Direzione generale Agricoltura, caccia e pesca (2023). *Disciplinari di
  produzione integrata 2023 – Norme generali* (87 pp.).
- URL: https://agricoltura.regione.emilia-romagna.it/produzioni-agroalimentari/agricoltura-sostenibile/agricoltura-integrata/Collezione-dpi/dpi_2023/norme/norme_generali-2023.pdf/@@download/file
- Cosa ho letto:
  - Allegato 2 "Metodo del bilancio previsionale", pp. 53-56: equazione N = A − B + C + D − E − F − G;
    Tab. 1 (N mineralizzato per % SO, per tessitura e C/N) e la sua nota (tassi di decomposizione della SO per
    tessitura, 20 cm, N nella SO 5%); Tab. 2 (azoto pronto e densità apparente); voce C (lisciviazione Ca e Cb);
    Tab. 3 (fattori di immobilizzazione e dispersione); Tab. 4 (azoto da precessione); voce G (deposizione,
    ~20 kg/ha/anno); efficienza dei concimi di sintesi 100%.
  - Allegato 3, pp. 65-66: conversione C organico → SO (1,724), classi di tessitura, C/N 9-12.
  - Allegato 6, pp. 69-70: coefficienti di assorbimento e asportazione (mais da granella, soia, grano tenero).
  - Allegato 7, pp. 72-73: coefficienti tempo.
  - Allegato 9, pp. 75-76: MAS (usati come conferma di quelli lombardi).
- Limiti: la tabella dell'Allegato 6 non dichiara l'umidità della granella. Versione 2023: ho letto anche le
  modifiche 2025 (BUR ER n. 45 del 25/02/2025, allegato 1,
  https://bur.regione.emilia-romagna.it/area-bollettini/n-45-del-25-02-2025-parte-seconda/d-m-4980-2014-l-r-28-1999-art-5-aggiornamento-dei-disciplinari-di-produzione-integrata-2025-norme-generali-norme-di-coltivazione-parte-difesa-fitosanitaria-e-controllo-delle-infestanti-e-parte-norme-agronomiche-piano-di-controllo-sqnpi-regionale/allegato-1)
  e 2026 (BUR ER n. 66 del 24/03/2026, allegato 1,
  https://bur.regione.emilia-romagna.it/area-bollettini/n-66-del-24-03-2026-parte-seconda/d-m-4980-2014-l-r-28-1999-art-5-aggiornamento-dei-disciplinari-di-produzione-integrata-2026-norme-generali-norme-di-coltivazione-parte-difesa-fitosanitaria-e-controllo-delle-infestanti-e-parte-norme-agronomiche-piano-di-controllo-sqnpi-regionale/allegato-1):
  aggiungono solo mirtillo e luppolo all'Allegato 6 e non toccano le voci usate. Le modifiche 2024 non le ho
  trovate né lette.

## 2. Regione Lombardia — Programma d'azione nitrati 2024-2027 (zone vulnerabili)

- Riferimento: Regione Lombardia (2025). D.g.r. 30 aprile 2025 n. XII/4284, *Aggiornamento del programma d'azione
  regionale per la protezione delle acque dall'inquinamento provocato dai nitrati provenienti da fonti agricole
  nelle zone vulnerabili ai sensi della Direttiva nitrati 91/676/CEE – 2024-2027*. BURL Serie Ordinaria n. 19 del
  6 maggio 2025.
- URL: https://www.regione.lombardia.it/content/dam/rl/canali-tematici-servizi/10-agricoltura/10-direttiva-nitrati/red-normativa-nitrati-agr/accordion/acc-zone-vulnerabili-2024-2027/Delibera%2030%20aprile%202025%20-%20n.%204284.pdf
- Cosa ho letto: par. 4.4 (limite di 170 kg N/ha/anno da effluenti, p. 42); par. 4.5 e Allegato 2, Tabella 1
  (MAS, rese di riferimento, fattori correttivi, note; pp. 74-77); Allegato 10 (equazione Kc·FC + Ko·FO = MAS,
  Kc = 1, Tabella 1 delle efficienze; pp. 101-102).
- Limiti: il disciplinare di produzione integrata della Lombardia con norme di fertilizzazione proprie non l'ho
  trovato online; il CSR lombardo (intervento SRA01) rinvia ai disciplinari regionali o delle regioni limitrofe,
  per cui ho usato quelli dell'Emilia-Romagna. Il Programma non contiene coefficienti di assorbimento né il
  metodo di bilancio dettagliato.

## 3. Salvagiotti et al. (2008)

- Riferimento: Salvagiotti F., Cassman K.G., Specht J.E., Walters D.T., Weiss A., Dobermann A. (2008).
  Nitrogen uptake, fixation and response to fertilizer N in soybeans: A review. *Field Crops Research* 108(1):
  1-13. doi:10.1016/j.fcr.2008.03.001.
- URL letto: https://www.mssoy.org/sites/default/files/documents/nebraska-n-review-2008-ok.pdf (copia del
  deposito DigitalCommons@University of Nebraska-Lincoln, Agronomy & Horticulture Faculty Publications, paper 133).
- Cosa ho letto: abstract; Tab. 1 (statistiche della meta-analisi: fissazione %, NHI, N nella granella); Fig. 1
  (pendenza 0,0127 t granella/kg N); Fig. 3 (curva y = 337 e^(−0,0098x)) e testo pp. 5-6.
- Limiti: la funzione di inibizione è in funzione della dose di concime, non dell'azoto minerale del suolo
  (vedi l'assunzione in `soia.fissazione.coeff_inibizione_n`). Copia d'autore, non la versione dell'editore.

## 4. Mémento Sols et Matières Organiques (Agro-Transfert, 2007)

- Riferimento: Duparque A., Ancelin O., Duranel J., Dersigny C., Fleutry L. (2007). *Mémento Sols et Matières
  Organiques*. Agro-Transfert Ressources et Territoires e Chambres d'Agriculture de Picardie.
- URL: https://www.agro-transfert-rt.org/wp-content/uploads/2025/08/Memento_sols_et_matiere_organique.pdf
- Cosa ho letto: p. 5 (conversione C → MO 1,7-2); p. 19, Tableau 2 (k1 Hénin-Dupuis e AMG per coltura);
  p. 20, Tableau 3 (k2 per tipo di suolo e formule di Rémy e Marin-Laflèche 1974, Machet et al. 1990, Mary et
  al. 1999); p. 25 (N/C della SO = 0,10, 4200 t/ha di terra); pp. 33-34 (calcolo dell'humus dai residui);
  p. 42 (esempio con C della paglia 0,45).
- Limiti: fonte tecnica francese (Chambres d'agriculture e Agro-Transfert), non un manuale FAO né un ente
  italiano: categoria "altro", dichiarata. Le fonti primarie (Rémy e Marin-Laflèche 1974/1976; Machet et al.
  1990; Wylleman 1999) non sono state consultate. La formula di Machet è stampata con parentesi sbagliate; la
  forma usata è quella che riproduce i valori della tabella (controllo numerico in `nitrogen.yaml`). Il k1
  della soia non c'è: si usa il pisello proteico.

## 5. SWAT — documentazione teorica e di input

- Riferimento: Neitsch S.L., Arnold J.G., Kiniry J.R., Williams J.R. (2011). *Soil and Water Assessment Tool
  Theoretical Documentation, Version 2009*. Texas Water Resources Institute Technical Report TR-406.
  URL: https://swat.tamu.edu/media/99192/swat2009-theory.pdf
- Riferimento: Arnold J.G. et al. (2012). *SWAT Input/Output File Documentation, Version 2012*. Texas Water
  Resources Institute TR-439. URL: https://swat.tamu.edu/media/69296/swat-io-documentation-2012.pdf
- Cosa ho letto: sez. 4:2.1 "Nitrate movement", eq. 4:2.1.2-4:2.1.8 (p. 269-270); I/O cap. 22, variabile
  ANION_EXCL (valore predefinito 0,50, p. 304).
- Limiti: modello USDA-ARS/Texas A&M, categoria "altro" dichiarata; scelto perché l'equazione di Burns (1975,
  *J. Agric. Sci.* 85: 443-454) non è ad accesso aperto e non l'ho potuta leggere.

## Fonti cercate e non usate

- Andriulo, Mary, Guérif (1999), *Agronomie* 19: 365-377 (HAL INRAE e agronomy-journal.org): accesso bloccato
  da sistemi anti-bot, non letto.
- Kätterer et al. (2011), *Agric. Ecosyst. Environ.* 141: 184-192 (coefficienti Hénin-Dupuis per stocchi e
  paglia): il deposito SLU rimanda altrove, non letto.
- Materiale didattico dell'Università Mediterranea di Reggio Calabria sulla formula di Rémy: link non più attivo.
- Disciplinare di produzione integrata della Lombardia (norme agronomiche): non trovato.

## Aggiornamento 2026-11-12 (correzioni dopo `reports/params_review.md`)

- **Salvagiotti et al. (2008)**, riletto (stesso URL): Tab. 1 completa (N residui 1,21%, NHI 0,73 con IQR 0,64-0,82,
  fissazione % "No N" max 98 / 75% 74 / media 58); testo p. 4 (pendenza 12,7 kg granella/kg N, "5 Mg ha-1 accumulates
  about 400 kg N ha-1"); testo p. 5 ("When less than 85 kg N ha-1 was applied ... N uptake levels were above 350 kg N
  ha-1, the proportion of N derived from biological fixation ranged from 35 to 86%"); didascalie Fig. 2 (FIX = 0,66 U − 19)
  e Fig. 3 (curva limite in funzione della dose di concime). Usato per `soia.n_assorbito` (78,7), `soia.nhi` (0,73),
  `soia.n_asportato` (derivato 57,5), `soia.fissazione.quota_fissazione_max` (0,86) e per il nuovo uso di
  `coeff_inibizione_n` (solo sulla dose di concime).
- **Moretti B., Bertora C., Grignani C., Lerda C., Celi L., Sacco D. (2020).** Conversion from mineral fertilisation to MSW
  compost use: nitrogen fertiliser value in continuous maize and test on crop rotation. *Science of the Total Environment*,
  doi:10.1016/j.scitotenv.2019.135308. URL letto (manoscritto d'autore, archivio AperTO dell'Università di Torino):
  https://iris.unito.it/bitstream/2318/1726469/1/STOTEN-D-19-08926.pdf
  - Cosa ho letto: par. 2.2.1 (trattamenti, 198 kg N/ha/anno da urea), par. 2.2.3 eq. 1 (Nitrogen Apparent Recovery per
    differenza), par. 3.1.2 (NAR mais M-Min 90, 85, 76%), par. 3.2 (R-Min 91, 88, 82%).
  - Limiti: versione d'autore sottomessa, non quella dell'editore; una sola prova (pianura padana occidentale); NAR solo per il mais.
  - Usato per `efficienza_concime.recupero_apparente.mais` (0,84).
- **Ladha et al. (2005)**, *Adv. Agron.* 87: 85-156: cercato, non letto (copia CORE bloccata, 403). Il 57% del frumento
  è preso da citazioni secondarie: `recupero_apparente.frumento` è un'assunzione.
- **Cassman, Dobermann, Walters (2002)**, *Ambio* 31: 132-140: cercato su DigitalCommons UNL e CORE, download bloccato
  (403) in due tentativi: non usato.
- **ER Norme generali 2023, Tab. 1 p. 53**: non riletta; i k2 per C/N < 9 e > 12 (`suolo.k2.cn_basso`, `cn_alto`) sono
  ricavati dai valori della tabella già trascritti in `n_mineralizzato_disciplinare` (confermati dal revisore) e marcati
  `derivato: true`. Il tetto oltre il 3% di SO (`suolo.soglia_so_tetto`) è la frase della stessa tabella.
