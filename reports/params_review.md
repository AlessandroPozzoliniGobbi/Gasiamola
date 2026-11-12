# Revisione indipendente dei parametri FIELDWISE

Data: 2026-11-11 (consegna 2026-11-12). Revisore: agent indipendente, non autore dei file.
File rivisti: `params/crops.yaml`, `nitrogen.yaml`, `rotation_rules.yaml`, `heat.yaml`, `cover_crop.yaml`.
`params/soil.yaml` è comparso durante la revisione: **non** ne ho controllato le fonti. L'ho usato solo per i controlli di coerenza del punto 3 (strati, densità, sostanza organica).
Il caricatore dà `--check`: nessun errore, 256 voci. La tabella `reports/params_table.md` è rigenerata con `--table`.

Metodo: ho scaricato ogni fonte durante questo lavoro (HTML/PDF, poi `pdftotext`) e ho cercato il valore nel testo. Il registro `docs/fonti_*.md` non è stato usato come prova.
Fonti aperte: FAO-56 (pagine x0490e0b e x0490e0e), AquaCrop v7.3 Annex I, ER Norme generali 2023 e 2026, Lombardia NTA Parte generale 2026, D.g.r. XII/4284/2025 (nitrati), Deryng et al. 2014, Seifert et al. 2017 (copia mssoy.org), Marini et al. 2020 (IOP), Salvagiotti et al. 2008, BENCO 2020 e Mémento Agro-Transfert 2007.

Campionamento casuale: `random.Random(2026)` sull'elenco di `fieldwise.params.iter_entries(load_params())`, una voce per file, escluse le voci obbligatorie (script in scratchpad, `sample.py`).
Voci estratte: `crops.frumento.semina_max`, `nitrogen.soia.fissazione.fissazione_max_assoluta`, `rotation_rules.successioni_vietate.soia_soia_soia.emilia_romagna_impegno_quinquennale`, `heat.colture.mais.finestra_inizio_frazione`, `cover_crop.biomassa_e_azoto.efficienza_campo`.

## 1. Verifiche sulle fonti (29 voci)

Esiti: **confermato 22**, **uso improprio 7**, discrepanza 0, riferimento impreciso 0, non verificabile 0.
In più c'è un'incoerenza interna della fonte ER, che il file eredita: vedi la nota sotto la tabella.

| # | Voce | Valore nel file | Fonte dichiarata | Cosa ho letto | Esito |
|---|------|-----------------|------------------|---------------|-------|
| 1 | crops.mais.kc.mid | 1.20 | FAO-56 Tab. 12 | Riga "Maize, Field (grain) (field corn)": Kc mid 1.20, Kc end 0.60-0.35 (nota 11), h = 2 m | confermato |
| 2 | crops.mais.ky | 1.25 | FAO-56 Tab. 24 (da FAO-33) | Tab. 24 "Seasonal yield response functions from FAO-33": Maize 1.25 | confermato (fonte secondaria, dichiarata) |
| 3 | crops.mais.p | 0.55 | FAO-56 Tab. 22 | Maize field (grain): Zr 1.0-1.7 m, p 0.55 | confermato |
| 4 | crops.mais.zr_max | 1.7 m | FAO-56 Tab. 22 | 1.0-1.7 m; scelto il massimo, come dichiarato | confermato |
| 5 | crops.frumento.kc.mid | 1.15 | FAO-56 Tab. 12 | Winter Wheat: Kc ini 0.4 su suolo gelato e 0.7 su suolo non gelato; Kc mid 1.15; Kc end 0.25-0.4 | confermato |
| 6 | crops.mais.t_base | 8.0 °C | AquaCrop Annex I, I.2 | Tbase 8.0, Tupper 30.0 | confermato |
| 7 | crops.mais.gdd_maturita | 1950 °C·d | AquaCrop I.2, 1.2 | Emergenza 60-100 GDD; maturità = emergenza + 1450-1850. Il 1950 è 100+1850: estremo superiore costruito dall'autore | confermato (valore derivato; vedi punto 2) |
| 8 | nitrogen.mais.n_assorbito | 22.7 kg N/t | ER 2023 All. 6, p. 70 | "Mais da granella (pianta intera) 2,27 ... ass."; la tabella non dichiara l'umidità | confermato |
| 9 | nitrogen.suolo.k2.per_tessitura.franco | 0.0185 /anno | ER 2023 All. 2, nota Tab. 1, p. 53 | "dal 1,7 al 2 % per i terreni di medio impasto"; a C/N equilibrato si usa il valore medio; 20 cm; N 5%. Ricalcolo: 26 t SO × 0,0185 × 50 = 24 kg N, come in Tab. 1 | confermato |
| 10 | nitrogen.efficienza_concime.minerale | 1.0 | Lombardia D.g.r. 4284/2025 All. 10; ER 2023 p. 56 | ER: "Per i concimi minerali di sintesi si assume un valore di efficienza del 100%". Lombardia: KC nell'equazione (Kc FC)+(Ko FO)=MAS, "Si considera uguale a 1" | **uso improprio**: è una convenzione contabile del MAS (azoto "efficiente"), non il recupero fisico del concime. Nel bilancio di massa annulla volatilizzazione, denitrificazione e immobilizzazione del concime |
| 11 | nitrogen.vincoli.mas.mais | 280 kg N/ha | D.g.r. 4284/2025 All. 2 Tab. 1, p. 75 | "Mais di 1^ semina (classe FAO 600-700) 280 ... 13 t/ha granella ... 17 kg N/t"; nota 112; "granella = all'umidità commerciale" | confermato |
| 12 | rotation_rules.f_rotazione.frumento_dopo_frumento | 0.82 | Marini et al. 2020, sez. 3.1, Tab. 1 | "860 and 390 kg ha-1 per year ... corresponds to a 20%-25% yield gain". Monocoltura continua per decenni contro rotazioni di 4-6 anni con medica (Padova, Bologna); NPK raccomandato uguale | **uso improprio** (in parte dichiarato): il numero vale per una monocoltura pluridecennale contro una rotazione con leguminosa pluriennale, ma qui si applica a un singolo ristoppio dentro mais-soia-frumento |
| 13 | rotation_rules.f_rotazione.mais_dopo_mais.secondo_anno | 0.981 | Seifert et al. 2017, p. 545 | "Penalties for corn tripled from 1.9 to 5.7% between 1 and 2 yr ... then leveled off". Riferito al mais **in asciutto** (Fig. 3) | **uso improprio**: il mais modellato è irriguo (`crops.mais.irrigabile = 1`). Per l'irriguo la fonte dà solo la media 1.7%, non i valori anno per anno |
| 14 | ...mais_dopo_mais.anni_successivi | 0.943 | Seifert et al. 2017 | 5.7% in asciutto; media in asciutto 4.3%, in irriguo 1.7% (0.20 Mg/ha) | **uso improprio** (stessa ragione); il limite inferiore 0.862 viene da Mudare 2025 (dato globale, cereali) |
| 15 | rotation_rules.disciplinari.lombardia.max_ristoppi_per_coltura_quinquennio | 1 | NTA Lombardia 2026 Parte gen., cap. 7, p. 6 | "almeno tre colture principali e preveda al massimo un ristoppio per ogni coltura"; punto A (cereali autunno-vernini analoghi), punto I (cover crop non contano) a p. 7 | confermato |
| 16 | heat.colture.mais.t_critica | 32 °C | Deryng 2014 Tab. A.1 | PEGASUS 1.1, Maize Tcr 32 | confermato |
| 17 | heat.colture.mais.t_limite | 45 °C | Deryng 2014 Tab. A.1 | Tlim 45 | confermato |
| 18 | heat.funzione.forma | lineare, media sulla TSP | Deryng 2014 eq. A.6-A.8 | Eq. A.6 lineare tra Tcr e Tlim; A.7 media sulla TSP; A.8 moltiplicativa | confermato |
| 19 | heat.funzione.temperatura_efficace | (T2M+T2M_MAX)/2 | Deryng 2014 App. A.3 | "Teff is defined as (Tmean + Tmax)/2" | confermato |
| 20 | cover_crop.biomassa_e_azoto.biomassa_secca | 2.9 t s.s./ha | BENCO Scheda 5, Tab. 5.1 | Segale 2,9 t s.s./ha, C/N 25,4, Npd -10 kg/ha, -3,4 kg/t (PDF p. 27) | confermato |
| 21 | cover_crop.biomassa_e_azoto.riduzione_lisciviazione | 0.56 | BENCO Scheda 6, par. 6.4 | "in media la riduzione ... non leguminose ... è del 56-70%" (PDF p. 33; non ho controllato il numero di pagina stampato, 65) | confermato |
| 22 | crops.frumento.semina_max (casuale) | 12-01 | FAO-56 Tab. 11 nota 2 | "decreases to 17 °C or December 1, whichever comes first" | confermato |
| 23 | nitrogen.soia.fissazione.fissazione_max_assoluta (casuale) | 337 kg N/ha | Salvagiotti 2008 Tab. 1 | N2 fixation, massimo 337; testo: Herridge 1982 è il massimo affidabile | confermato |
| 24 | rotation_rules.successioni_vietate.soia_soia_soia.emilia_romagna_impegno_quinquennale (casuale) | non_conforme | ER 2026 All. 1 (PDF p. 51) | Soia: "Non è ammesso il ristoppio" | confermato (esito calcolato dall'autore, corretto) |
| 25 | heat.colture.mais.finestra_inizio_frazione (casuale) | 0.45 | Deryng 2014 App. A.3 | "TSP starts ... at 0.45 GPL", con GPL in **giorni da emergenza a maturità** | **uso improprio (dichiarato)**: qui è una frazione dei GDD dalla semina. Adattamento ragionevole, ma è una scelta dell'autore, non il parametro della fonte |
| 26 | cover_crop.biomassa_e_azoto.efficienza_campo (casuale) | 0.80 | BENCO par. 5.1 | "si può adottare un valore di efficienza intorno all'80%" | confermato |
| 27 | nitrogen.mais.k1_residui (extra) | 0.126 | Mémento 2007 p. 19 Tab. 2 | Maïs grain HD 0,126, AMG 0,213. Definizione: "kg de carbone organique du sol formée par kilo de carbone" → base carbonio, corretta | confermato |
| 28 | nitrogen.soia.fissazione.quota_fissazione_max (extra) | 0.58 | Salvagiotti Tab. 1 | N2 fixation (%), "No N": media 58, IQR 46-74 | **uso improprio** in combinazione con #29: 58% è già la media osservata con l'N del suolo reale |
| 29 | nitrogen.soia.fissazione.coeff_inibizione_n (extra) | 0.0098 ha/kg | Salvagiotti Fig. 3 | "y = 337 e^-0.0098x shows the **maximum level** of N2 fixation as a function of **fertilizer-N rate**" | **uso improprio**: è la curva di frontiera (massimo) rispetto alla dose di concime. Qui si applica all'N minerale del suolo, sopra una media che già lo contiene. Dichiarato come assunzione, ma l'effetto è grave (punto 3) |

Incoerenza nella fonte ER, Tab. 1 (p. 53), ripresa da `nitrogen.yaml _meta.equazioni.k2_suolo` ("C/N > 12 → estremo basso").
Con l'estremo basso la tabella non si riproduce:
- franco: 1,7% → 22 kg N per 1% SO, la tabella dice 20;
- sabbioso: 2% → 28 kg N, la tabella dice 24.

Le righe con C/N < 9 e la riga argilloso tornano. Per C/N > 12 il motore deve usare i k2 che riproducono la tabella (0,0154 franco, 0,0169 sabbioso, 0,005 argilloso) o dichiarare la differenza.

## 2. Onestà dei campi

1. **Voci `verificato: true` che sono calcoli dell'autore.** Sono le 60 voci di `rotation_rules.successioni_vietate.*`: il riferimento dice "calcolato applicando...". Hanno `verificato: true` e come `fonte` il disciplinare, anche quando l'esito dipende dall'interpretazione "rotazione triennale ripetuta, tutte le finestre di 5 anni", che non è nel disciplinare. Gli esiti che ho ricontrollato a mano sono giusti (M-S-F conforme; M-M-S non conforme sul quinquennio e conforme sul triennio; S-S-S non conforme in ER). Vanno però marcati come derivati (`verificato: false` con regola nella nota, oppure un campo `derivato`).
   Lo stesso vale, in misura minore, per:
   - `crops.mais.gdd_maturita` (1950) e `gdd_fioritura` (1000): somme di estremi di due intervalli;
   - `heat.*.finestra_*`: frazioni riferite a una base diversa da quella della fonte.
2. **`verificato: true` insieme ad `assunzione: true`.** Riguarda `nitrogen.soia.k1_residui` (valore del pisello), `coeff_inibizione_n` e `suolo.residui.c_residui`. "Letto" vale per il numero, non per l'uso: per la coltura o variabile usata il valore non è stato letto. Serve `verificato: false`, oppure una regola nello SCHEMA su cosa significa `verificato` quando l'uso è un'assunzione.
3. **Fonte formale che in realtà è un'assunzione.**
   - `soia.resa_potenziale` 4.5 e `frumento.resa_potenziale` 8.0 citano il disciplinare lombardo, ma il valore non è nella fonte: è il limite della "produzione normale" alzato a occhio. Sono dichiarate come assunzioni, ma la motivazione ("leggermente aumentato") non è quantitativa. Il mais invece ha una resa sperimentale (15,8 t, Capo 2023). Le tre colture hanno quindi potenziali di natura diversa, e questo pesa sul confronto tra rotazioni.
   - `cover_crop.humus.coefficiente_isoumico` 0.23 è un'assunzione dichiarata, ma è ragionata male. Divide un **incremento netto** di C del suolo (300 kg C/ha/anno, media su tutte le specie e durate, BENCO 7.1) per il C apportato dalla sola segale. Il risultato non è un k1: incorpora già la mineralizzazione e altre specie. La stessa fonte usata per i k1 (Mémento Tab. 2) dà per "Engrais vert" k1 HD 0,039 (AMG 0,076): 0,23 è circa 6 volte il valore HD.
4. **Fonti fuori gerarchia o improprie.**
   - `cover_crop.frazione_carbonio_sostanza_secca` (0.45) è citata da Deryng 2014, un articolo sul caldo che la riprende da un'altra fonte. Il numero è plausibile e coincide con `nitrogen.suolo.residui.c_residui` (Mémento), ma la stessa grandezza ha due fonti in due file: va unificata.
   - `crops.frumento.semina` e `semina_min` vengono da un disciplinare di filiera privato (dichiarato).
   - SWAT è classificato come "altro" (dichiarato).
   - Nessuna fonte fuori gerarchia non dichiarata.
5. **Assunzioni con motivazione debole.**
   - `nitrogen.suolo.residui.rilascio_completo_dopo_una_coltura = 1.0`: chiude il bilancio, ma non ha base agronomica. Gli stocchi di mais (C/N circa 55, vedi punto 3) non si mineralizzano del tutto in una stagione.
   - `cover_crop.n_assorbito` 51 kg/ha è derivato ed è marcato onestamente `verificato: false`.

## 3. Coerenza tra file (conti a mano)

**Umidità della granella.**
- crops: mais al 14%, soia e frumento al 13%.
- nitrogen: coefficienti ER per t di granella senza umidità dichiarata (MAS lombardo: "umidità commerciale").

Le basi sono compatibili se "commerciale" vuol dire 14% per il mais e 13% per soia e frumento. Va scritto in un solo punto, ad esempio `crops.*.umidita_granella`, e il codice lo deve usare sia per l'N sia per l'indice di raccolta. L'HI di AquaCrop è su sostanza secca ("crop yield is always reported as dry matter"): `nitrogen._meta` lo prevede correttamente (conversione con l'umidità).

**Indice di raccolta e residui** (resa potenziale, HI di crops.yaml, C 0,45):

| Coltura | Granella SS (t/ha) | Residui SS (t/ha) | N nei residui = resa × (ass − asp) | N% residui | C/N implicito |
|---|---|---|---|---|---|
| Mais 15,8 t al 14% | 13,6 | 13,6 | 15,8 × 7,1 = 112 kg | 0,82% | circa 55 (plausibile) |
| Frumento 8,0 t al 13% | 7,0 | 7,5 | 8 × 5,6 = 45 kg | 0,59% | circa 76 (plausibile) |
| Soia 4,5 t al 13% | 3,9 | 5,9 | 4,5 × 4,8 = 22 kg | **0,37%** | **circa 120** |

La soia non è coerente. Salvagiotti (Tab. 1) dà N nei residui 1,21% in media (IQR 0,80-1,55) e NHI 0,73. Il rapporto ER asp/ass (58,2/63 = NHI 0,92) insieme all'HI 0,40 di AquaCrop produce residui di soia quasi senza azoto.
- Correzione: usare `soia.n_assorbito` circa 79 kg N/t (Salvagiotti, già nell'intervallo), oppure ridurre la biomassa dei residui per le foglie cadute.
- Di conseguenza: con 0,428 t SO/ha umificate servono 21 kg N, cioè tutto l'N dei residui di soia.

**Finestra del caldo contro la fenologia** (`gdd_fioritura / gdd_maturita`):
- mais 1000/1950 = 0,51;
- soia 1330/2470 = 0,54;
- frumento 1330/2395 = 0,56.

La fioritura cade dentro [0,45; 0,70] per tutte e tre le colture. In GDD la finestra va da 878 a 1365 per il mais, da 1112 a 1729 per la soia, da 1078 a 1677 per il frumento (dal 20/4 circa a inizio giugno). In Deryng l'antesi è a 0,50 della durata da emergenza in giorni; qui sta a 0,51-0,56 dei GDD dalla semina, quindi la finestra comincia leggermente prima dell'antesi, come nella fonte.

**Temperatura per il caldo.** Teff = (T2M + T2M_MAX)/2 si calcola con le variabili POWER disponibili (T2M, T2M_MAX, T2M_MIN), quindi è coerente.
- Mais: un luglio tipico a Cremona (Tmedia 25,7 °C, Tmax circa 31) dà Teff circa 28 °C, sotto 32: f_caldo vicino a 1, come il 0,94 del 2022 annotato in PLAN.
- Frumento: con Tcr 25 °C (soglia del frumento **primaverile**) e Teff a fine maggio-giugno spesso tra 24 e 27 °C, la penalità rischia di comparire quasi ogni anno.

Va controllato contro le rese ISTAT prima di accettarlo.

**Strato dell'humus.**
- `nitrogen.profondita_humus` = 0,20 m (ER), mentre `soil.yaml` usa uno strato 0-30 cm con SO 3,563% e densità 1,433 (SoilGrids). Lo stesso soil.yaml scrive "humus 0-30 cm 153 t/ha".
- I k2 sono ricavati all'indietro dalla Tab. 1 ER con densità 1,30 (franco). Applicati a densità 1,433 danno il 10% in più di mineralizzazione per unità di SO%.
- Con SO 3,56%, 0,20 m e densità 1,433: H = 102 t SO/ha, mineralizzazione 0,0185 × 102 = 1,89 t SO, cioè **94 kg N/ha/anno**. La Tab. 1 ER pone invece un tetto ("rimane costante per tenori di S.O. superiori al 3%"): 24 × 3 = 72 kg.

Serve una sola definizione di strato (0,20 oppure 0,30 m) usata da azoto, humus e acqua, con il tetto ER o con la sua assenza dichiarata.

**Cover crop.**
1. Le equazioni di `nitrogen._meta.equazioni` **non** hanno una voce per la cover. Mancano l'assorbimento dal N_min nell'intercoltura, il pool N_cover, il rilascio o l'immobilizzazione alla terminazione (Npd -10 kg/ha) e l'umificazione del suo C. La chiusura ENTRATE − USCITE = DELTA non la contiene. Le "regole_d_uso" di cover_crop.yaml descrivono un flusso che il motore azoto non prevede: vanno scritte nelle equazioni, con l'umificazione espressa come k1 sul C × 1,724, come per i residui.
2. Calendario nella rotazione mais-soia-frumento:
   - **Mais → soia.** Terminazione tipica il 31/3 e semina della soia il 5/5: 35 giorni, oltre il limite SRA06 di 30 giorni. Spostando la terminazione ad aprile, biomassa e Npd di Tab. 5.1 (fine marzo) non valgono più.
   - **Soia → frumento.** Maturità il 23/9 e semina il 30/10: meno di 40 giorni, nessuna cover possibile. Va bene, ma va detto.
   - **Frumento → mais.** Raccolta circa il 25/6. SRA06 impone la semina della cover entro 30 giorni, cioè entro il 25/7, ma la segale va seminata a settembre-ottobre (BENCO Tab. 8.1) e la biomassa di 2,9 t si riferisce a semine di settembre. Segale a luglio non ha dati; con semina a settembre si perde il premio SRA06.
   - In crops.yaml manca la **data di raccolta**: c'è solo la maturità fisiologica. Dopo la maturità il mais da granella resta in campo 2-4 settimane, quindi la semina della cover dipende da un parametro che non esiste.
3. Kc 0,7 e radici 1,0 m sono compatibili con le colture. Nel modello idrico la cover consuma acqua prima del mais, ed è corretto.

**Penalità di rotazione come fattore moltiplicativo.**
- Seifert: studio osservazionale, concimazione dell'agricoltore (non controllata). La penalità comprende la risposta all'N e la differenza di gestione.
- Marini: NPK uguale nei due trattamenti; le rotazioni di confronto contengono medica, quindi il fattore comprende anche l'apporto di N della leguminosa.

Nel motore la resa è già limitata dal bilancio dell'N, che contiene anche il credito di precessione (-40 kg N dopo stocchi di mais interrati, Tab. 4 ER). Il fattore moltiplicativo rischia quindi di **contare due volte** l'effetto azoto. In più: Seifert vale per il Midwest in asciutto, mentre il mais di Cremona è irriguo (penalità media 1,7% e non 4,3%). Marini vale per una monocoltura continua contro rotazioni di 4-6 anni, non per un ristoppio.

**Plausibilità del bilancio** (mais-soia-frumento, suolo franco, potenziali di crops.yaml):

*Azoto.*
- Mais: U = 15,8 × 22,7 = 359 kg N; asportato 246; MAS = 280 + 2,8 × 17 = 328. Concime circa 280-300 kg (in linea con la pratica cremonese).
- Frumento: U = 237; MAS = 180 + 1,5 × 22 = 213.
- **Soia: U = 283 kg N.** Con N_min = 50 si ha FIX = 283 × 0,58 × e^(−0,49) = 100 kg, quindi 183 kg devono venire dal suolo. Il motore concima la soia con circa 130 kg (il MAS è 30) oppure riduce la resa per carenza di N.

La soia non concimata che fissa 100-170 kg (Salvagiotti, Fig. 2: fissazione = 0,66 U − 19, cioè circa 168 kg con U = 283) è la norma: la formula attuale la rende impossibile. È l'errore che pesa di più sul confronto tra rotazioni con e senza soia.

*Humus.* Apporti per rotazione:
- mais 0,126 × 6,1 t C × 1,724 = 1,33 t SO;
- frumento 0,55 t SO;
- soia 0,43 t SO;
- in media 0,77 t SO/anno.

H di equilibrio = 0,77 / 0,0185 = 42 t SO/ha, cioè circa 1,6% di SO su 0-20 cm. È un ordine di grandezza sensato per la Pianura Padana: ERSAF misura 13,5 g C/kg, cioè il 2,3% di SO.

Con la SO iniziale SoilGrids del 3,56% il modello perde invece circa 1,1 t SO/ha/anno (circa 1%/anno) in **tutte** le rotazioni. La classifica sarebbe dominata da un valore iniziale sospetto, già segnalato in PLAN. L'ordine di grandezza è plausibile solo partendo dal dato ERSAF.

## 4. Correzioni prima di scrivere il motore (in ordine di importanza)

**Errori certi**
1. Fissazione della soia (`nitrogen` FIX). Togliere l'esponenziale su N_min applicato alla media 0,58 (che già incorpora l'N del suolo), oppure riformulare. Esempio: frazione fissata = 0,66 − 19/U (Salvagiotti Fig. 2, dosi < 10 kg N) per la soia non concimata, con l'inibizione solo per la dose di concime. Senza correzione la soia viene concimata o perde resa.
2. Cover crop assente dalle equazioni dell'azoto e dell'humus: aggiungere pool, flussi e termine nella chiusura.
3. `cover_crop.coefficiente_isoumico` 0,23: non è un k1. Usare 0,039 (Mémento Tab. 2, Engrais vert, HD), o un valore da paglia (0,094) motivato dal C/N 25, e mettere 0,23 in sensibilità.
4. Strato dell'humus: unificare 0,20 m contro 0-30 cm e la densità (ER contro SoilGrids); applicare o dichiarare il tetto ER oltre il 3% di SO.
5. `efficienza_concime.minerale = 1,0` nel bilancio di massa: è una convenzione normativa. Tenerla per il calcolo MAS e aggiungere una perdita fisica del concime (volatilizzazione e denitrificazione) con fonte, oppure dichiarare che l'unica perdita del concime è la lisciviazione.
6. Residui di soia con 0,37% di N: portare `soia.n_assorbito` verso 79 kg/t o rivedere la biomassa dei residui.
7. Regola k2 per C/N > 12: allinearla ai valori di Tab. 1 ER (vedi la nota sotto la tabella del punto 1).
8. Ricontrassegnare come derivati le 60 voci di `successioni_vietate` e i doppi flag `verificato`/`assunzione`.

**Scelte discutibili da mandare in analisi di sensibilità**
- `f_rotazione.mais_dopo_mais`: usare come base il valore irriguo (0,983) e tenere quello in asciutto come alternativa. Valutare il doppio conteggio con il credito di precessione: provare la variante con f = 1 e solo il bilancio N.
- `frumento_dopo_frumento` 0,82: intervallo da allargare verso 1 per il singolo ristoppio.
- Soglia del caldo del frumento (25 °C, frumento primaverile) su Teff: controllo contro le rese ISTAT; alternativa AquaCrop 35 °C su Tmax.
- SO iniziale: SoilGrids 3,56% contro ERSAF 2,33% (è il parametro che più sposta il bilancio dell'humus).
- Rese potenziali di soia e frumento (assunzioni) contro quella sperimentale del mais.
- `rilascio_completo_dopo_una_coltura` = 1: provare 0,5.

**Da dichiarare come limite**
- La data di raccolta non è modellata (solo la maturità fisiologica), e da essa dipende la finestra della cover.
- Calendario della cover incompatibile con SRA06 dopo il frumento (semina entro il 25/7) e al limite tra mais e soia (35 giorni contro 30).
- Penalità di rotazione da contesti non padani (Seifert, Midwest) o con rotazioni con medica (Marini).
- Le soglie GDD AquaCrop sono tarate con il metodo 3, il motore usa il metodo 1. Effetto piccolo, ma va detto.
- `soil.yaml`: fonti non riviste in questa revisione.
