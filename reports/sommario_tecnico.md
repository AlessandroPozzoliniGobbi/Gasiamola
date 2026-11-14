# FIELDWISE — sommario tecnico dello stato effettivo

**Versione analizzata:** commit `e2be4e5` (`e2be4e5076a26774dec53af4e2907c27bbc7e5ea`, 14 novembre 2026), più le modifiche locali non committate presenti nel workspace. La cache dell’ensemble è stata calcolata il 14 novembre alle 17:48 UTC sul punto pilota 45,2 N, 10,0 E: 11.016 simulazioni riuscite, 3.888 scartate, 76 classi grezze e un ciclo di avviamento. Le annate di partenza con risultati sono 2000–2016; i cicli valutati coprono 2003–2019. La cache registra l’hash dei parametri correnti, inclusi i costi per coltura aggiunti localmente.

Il commit introduce il fattore termico Q10 per azoto, il margine economico e la priorità «profitto», la validazione ET con ECOSTRESS e il confronto di plausibilità con GAEZ v4; GAEZ non modifica i valori delle rese. Il commit lascia il repository come motore/backend: l’interfaccia non è presente nel codice tracciato. Dopo il commit, il workspace ha aggiunto costi unitari per coltura, il loro ricalcolo nella classifica e una nuova cache economica. Queste modifiche sono locali e non committate; il riepilogo le tratta come stato di lavoro corrente. La sensibilità pubblicata precede l’inclusione dei costi per coltura e va rigenerata prima di usarla per affermare la robustezza dell’attuale ranking.

## 1. Decisioni e perimetro

### Colture, rotazioni, territorio e tempo

Le colture principali definite nei parametri sono **mais, soia e frumento tenero**. L’unica cover crop simulata è **segale**, opzionale dopo ciascuna coltura principale. L’ensemble standard combina ogni sequenza di tre colture (3³) con le otto configurazioni sì/no della cover: **216 rotazioni** prima della riduzione per equivalenza ciclica. Le permutazioni che differiscono solo dal punto di partenza sono accorpate in classi; cover mai praticabili rendono alcune classi equivalenti. La classifica corrente considera 45 classi per scenario dopo queste esclusioni. Il motore accetta anche rotazioni di lunghezza diversa se fornite esplicitamente, ma non le confronta sempre su cicli temporali omogenei. [rotation.py:127–169, 459–537](../src/fieldwise/rotation.py), [ensemble.py:173–188](../src/fieldwise/ensemble.py)

L’interfaccia di calcolo accetta coordinate, ma la configurazione agronomica e la validazione effettive sono quelle del punto pilota in provincia di Cremona. Le coordinate selezionano il meteo POWER in cache; **il profilo del suolo usato dalla simulazione viene invece letto dai parametri statici del pilota**. Il caricamento del motore non collega automaticamente un nuovo download SoilGrids alle proprietà di quel punto. Per un altro territorio occorre fornire un profilo e parametri coerenti; altrimenti il risultato combina altro meteo con il suolo pilota. La conformità regionale è codificata per quattro regimi di Lombardia ed Emilia-Romagna, non per territori generici. [rotation.py:288–359](../src/fieldwise/rotation.py), [soil.yaml:1–17](../params/soil.yaml), [README.md:38, 68](../README.md)

Ogni simulazione usa meteo storico giornaliero. Non ci sono previsioni meteorologiche né scenari climatici futuri. La rotazione standard ha tre colture principali e viene valutata dopo un ciclo di avviamento; l’orizzonte valutato è il ciclo dalla prima semina alla vigilia della semina del ciclo successivo, quindi dipende dalle colture e dalle date raggiunte nel meteo.

### Scelte, esplorazione e parametri fissi

- **Scelti dall’utilizzatore dell’API:** coordinate del campo; rotazione attuale, se nota; scenario irriguo; pesi delle sei priorità; eventuale filtro di conformità. Può passare una lista ridotta di rotazioni invece dell’ensemble standard.
- **Esplorati dall’ensemble standard:** tutte le sequenze triennali delle tre colture e le configurazioni di cover. Il confronto non sceglie un tipo di irrigazione: esegue separatamente tre scenari predefiniti.
- **Fissi nella configurazione corrente:** parametri di colture, calendari, suolo pilota, parametri agronomici, prezzi e costi di riferimento, condizioni iniziali del suolo e regole di irrigazione. Il backend permette override di parametri e, con `economics.ricalcola_margine`, costi per coltura; non esiste qui un’interfaccia agricoltore che raccolga questi dati.

### Vincoli, esclusioni e avvisi

Una simulazione non produce numeri se il ciclo esce dagli anni meteo affidabili, la maturità non viene raggiunta, la finestra fenologica è degenere o la semina successiva è impossibile secondo il calendario. Un conflitto di calendario è rinviato all’annata successiva per default e segnalato; l’opzione più rigida può scartarlo. Se una cover richiesta non entra nella finestra agronomica, il motore lascia il terreno nudo e registra il motivo: non scarta l’intera rotazione. I requisiti del premio SRA06 producono avvertenze, non decidono la praticabilità agronomica.

La conformità ai disciplinari non equivale a un divieto legale di simulazione: la rotazione è etichettata conforme, in deroga o non conforme. Un filtro può escludere le non conformi, ma mantiene la rotazione attuale per consentire il confronto. Il superamento del MAS azotato è un indicatore/avvertenza e non riduce la resa né scarta la rotazione. I tetti irrigui limitano la quantità erogata e possono quindi aumentare lo stress idrico; non sono un criterio di esclusione. Le penalità di ristoppio, invece, riducono direttamente la resa simulata.

## 2. Dati e input

| Fonte | Uso effettivo | Copertura e trasformazioni | Natura del dato |
|---|---|---|---|
| **NASA POWER** | Unico driver meteorologico predefinito del motore | Cache giornaliera al pilota dal 2000 al 2025; colonne operative `tmax`, `tmin`, `tmean`, `rain`, `srad`, `rh`, `wind`. Da temperatura si ricavano gradi-giorno; da temperatura, radiazione, umidità e vento si calcola ET0 Penman–Monteith. La pioggia POWER è marcata affidabile fino al 2022; l’ensemble usa il 2000–2022. La cella è di circa 50 km e quota 171 m al pilota. | Rianalisi/prodotti assimilati, non misura diretta del campo. I confronti ARPA indicano eccessi di pioggia POWER nel 2023–2025; quegli anni sono esclusi dalla forzante predefinita. |
| **SoilGrids 2.0** | Tessitura, densità e proprietà del profilo pilota; ingresso statico alla pedotrasformazione | Estrazione puntuale a 250 m, aggregazione per orizzonti e poi in strati 0–30 e 30–150 cm. Saxton–Rawls ricava capacità di campo, punto di appassimento, saturazione e conducibilità. Lo scheletro e la correzione di densità non sono applicati nella configurazione scelta. | Prodotto globale modellato, non analisi del terreno dell’appezzamento. |
| **ERSAF Lombardia** | Carbonio organico/SO iniziale 0–30 cm del pilota | Media 2020–2023 per la Bassa Pianura Centrale: 13,5 g C/kg, convertiti in 2,327% SO. Scelta al posto del 3,563% SoilGrids; il dato è regionale, non una misura nel punto. | Osservazioni regionali aggregate. La tessitura e la densità restano SoilGrids; sotto 30 cm resta SoilGrids. |
| **ARPA Lombardia** | Controllo della pioggia e delle temperature POWER | Pluviometri e stazioni selezionati vicino al pilota, con coperture e buchi diversi. Non sono l’ingresso meteo predefinito. | Osservazioni a terra; non disponibili con copertura omogenea per ogni campo. |
| **GPM IMERG Final V07** | Forzante alternativa per sensibilità e controlli sulla pioggia | Serie giornaliera in cache 2000-06–2025-09, bilineare sulle quattro celle al pilota. Non è la pioggia predefinita: sui totali annui 2001–2022 il rapporto medio con ARPA riportato è 1,21 contro 1,01 per POWER. | Prodotto satellitare. |
| **SMAP SPL3SMP_E V006** | Validazione dell’umidità superficiale, non ingresso del motore | 2015-03–2025-12; 2.323 giorni con qualità raccomandata. Il confronto principale arriva al 2022 e usa anomalie mensili 0–5 cm. | Osservazione satellitare con qualità filtrata, scala spaziale circa 9 km. |
| **MODIS MOD13Q1** | Validazione di NDVI, non ingresso del motore | Compositi NDVI a 16 giorni; si usa la media luglio–agosto di una finestra 9×9, circa 2 km, filtrando pixel/date per qualità. Confronto annuale 2001–2022. | Osservazione satellitare; la finestra mescola colture e campi irrigui/asciutti. |
| **ISTAT** | Validazione delle rese, non ingresso del motore | Provincia di Cremona, serie dal 2006. La resa è calcolata come produzione raccolta / superficie totale; il confronto principale è 2006–2022. Irriguo e asciutto sono mescolati. | Statistica ufficiale provinciale, non resa misurata sul campo né fornita direttamente come resa. |
| **ECOSTRESS ECO_L3T_JET.002** | Verifica dell’ET simulata, non ingresso | 31 punti su seminativi provinciali, 2018-07–2022-12; 6.535 passaggi validi su 20.194. L’esito principale usa passaggi associati a coltura solo dove la classificazione è netta. | Stima satellitare modellata; la documentazione dell’unità è incoerente (mm/giorno contro W/m²), limite dichiarato nel rapporto di validazione. |
| **FAO/IIASA GAEZ v4** | Riscontro esterno dei valori di resa potenziale | Confronto di plausibilità per rese potenziali; non alimenta l’ensemble e non ha cambiato i valori di `crops.yaml`. | Modello globale, non osservazione locale. |

I parametri di crop, cover, azoto, rotazioni, suolo e scenari sono nei file `params/*.yaml`. Le equazioni e i coefficienti sono attribuiti a fonti come FAO-56, FAO-33, AquaCrop, Saxton–Rawls, disciplinari regionali e letteratura. La provenienza è eterogenea: alcune voci sono misurate o lette in fonte, altre derivate o dichiarate assunzioni; il campo `verificato` e le note dei parametri distinguono i casi. Tra le assunzioni con effetto pratico vi sono Q10 = 2, i coefficienti di ristoppio, la segale come unica cover, il tetto irriguo della soia di 100 mm e diversi costi/prezzi economici. `docs/fonti_*.md` descrive le fonti e i limiti.

**Informazioni che deve fornire l’agricoltore per un confronto personalizzato:** coordinate; rotazione attuale (incluse eventuali cover) e scenario/priorità scelti. Non sono richiesti dati aziendali per produrre un risultato. Per rappresentare l’azienda in modo più fedele servono però profilo del suolo, storia colturale, rese, irrigazione e fertilizzazione osservate. I costi per coltura si possono passare alla funzione `ricalcola_margine`, ma nel repository attuale manca l’interfaccia che li raccolga. Non si chiedono in input al motore le quantità reali di concime o acqua della pratica corrente.

## 3. Modello del suolo e delle colture

### Fenologia e passo temporale

La simulazione procede **giorno per giorno**. I gradi-giorno sono `GDD_t = max(0, min(Tmedia_t, Tupper) − Tbase)`. L’accumulo termico determina fasi, fioritura e maturità; il calendario di semina usa finestre colturali e tempi minimi tra raccolta e semina. Non sono modellati vernalizzazione o fotoperiodo. Le variabili giornaliere sono aggregate per coltura, ciclo e annata.

### Acqua

Il profilo idrico ha due strati: 0–30 cm e 30–150 cm. Il motore mantiene acqua `W1`, `W2` e deplezione dello strato evaporante `De`, in mm. Tessitura, `fc`, `wp`, saturazione, `Ksat`, spessori, Curve Number e parametri evaporativi sono statici durante la simulazione. Radici, copertura, coefficienti colturali, acqua, ruscellamento, evaporazione, traspirazione, irrigazione e percolazione cambiano nel tempo. La variazione di humus non aggiorna `fc`, `wp` o `Ksat` durante il ciclo; non c’è falda né risalita capillare.

Bilancio giornaliero del profilo:

```text
ΔS = P + I − RO − ETa − DP
```

con stoccaggio `S` [mm], pioggia `P`, irrigazione netta `I`, ruscellamento `RO`, evapotraspirazione effettiva `ETa` e drenaggio profondo/percolazione `DP`. Nel metodo predefinito a doppio coefficiente FAO-56:

```text
ETc = (Kcb + Ke) ET0
ETa = Ks Kcb ET0 + Ke ET0
RAW = p TAW
```

`Kcb` descrive la traspirazione potenziale della coltura, `Ke` l’evaporazione dal suolo, `Ks` lo stress da esaurimento dell’acqua disponibile, `TAW` l’acqua totale disponibile e `RAW` la soglia di irrigazione. Il ruscellamento usa Curve Number; l’acqua oltre capacità di campo passa allo strato inferiore e poi può diventare percolazione.

### Azoto e humus

Il bilancio di N è giornaliero e mantiene `N_min`, `N_res`, `N_cov` [kg N/ha] e l’azoto della coltura in piedi. `N_min` è l’azoto minerale disponibile; `N_res` è N organico in residui non ancora rilasciati; `N_cov` è N nella cover viva. L’humus `H` [t SO/ha] è uno stock unico nei primi 20 cm, inizializzato a circa 66,7 t SO/ha con SO ERSAF e densità SoilGrids. L’azoto iniziale minerale deriva dal coefficiente `n_pronto` per tessitura moltiplicato per N totale del suolo; residui/cover iniziano a zero.

Mineralizzazione e humus seguono, in forma essenziale:

```text
fT = Q10^((T − Tmedia)/10), normalizzato a media 1
Hmin = k2 · min(H, Htetto) · Δt
Hfine = Hinizio − Hmin + Hres + Hcov
```

La mineralizzazione e il rilascio dei residui sono distribuiti nei giorni usando `fT`; con Q10 normalizzato cambia la distribuzione stagionale, non il totale annuo del coefficiente. I residui della coltura dipendono dalla resa simulata e dalla parte lasciata in campo; la segale apporta humus e N secondo biomassa/parametri di cover. Il N attraversa i segmenti tramite pool minerale, residui, assorbimento, deposizione, mineralizzazione, fissazione della soia e lisciviazione. La lisciviazione giornaliera è funzione della percolazione e del N minerale presente; la soia fissa N fino al limite parametrico.

### Trasferimento tra colture e resa

Lo stato idrico, minerale, residuo e humus non viene azzerato tra colture o intervalli. La resa della coltura precedente modifica i residui organici e l’azoto asportato; la cover intercetta N, usa acqua e restituisce biomassa/residui al termine. Un credito di precessione influisce sul fabbisogno azotato. Separatamente, `f_rotazione` applica coefficienti per ristoppio in base alle due colture principali precedenti; la cover non interrompe il ristoppio.

La resa assoluta è:

```text
Y = Ypot · facqua · fcaldo · frotazione
facqua = clip[0,1](1 − Ky · (1 − ETa/ETc))
```

`Ypot` è un valore fisso [t/ha] da `crops.yaml`; l’equazione idrica è FAO-33. `fcaldo` è la media giornaliera nella finestra sensibile: il default Deryng usa una funzione lineare limitata tra temperatura critica e limite, con temperatura efficace `(Tmedia + Tmax)/2`. **I soli fattori che moltiplicano la resa nel codice sono acqua, caldo e successione. L’azoto non è un fattore di resa.** N deficitario, fissazione, mineralizzazione, lisciviazione, variazione di humus e superamento MAS sono contabilizzati/mostrati ma non abbassano `Y`; l’humus variabile non retroagisce sulle proprietà idrauliche.

### Quantità di irrigazione e concime

L’irrigazione è una regola automatica, non una variabile ottimizzata: quando l’esaurimento supera `RAW`, il modello tenta di riportare il profilo a capacità di campo. La dose è limitata dal tetto netto residuo per coltura; la cover non viene irrigata. Scenari: **solo pioggia** (0 mm), **tetto irriguo** (mais 200 mm e soia 100 mm per ciclo; il tetto soia è assunzione), **irrigazione libera** (nessun tetto). I volumi sono netti; non sono applicate perdite di distribuzione.

Il concime è calcolato automaticamente in risposta alla domanda di N: assorbimento obiettivo = resa simulata × coefficiente `n_assorbito` [kg N/t]; il N minerale del suolo copre prima la domanda; per le colture non leguminose il deficit viene convertito in concime dividendo per il recupero apparente. La soia usa fissazione biologica fino al tetto parametrico. Non è una ricerca dell’ottimo agronomico né una prescrizione di calendario/dose aziendale. Un’eventuale carenza residua è un indicatore, ma non entra nella funzione di resa.

## 4. Scenari e incertezza

Le annate dell’ensemble sono **annate storiche osservate/ricostruite**, non generate da un modello climatico: per ogni anno affidabile si ripete lo stesso meteo giornaliero per le rotazioni. La sintesi non assegna probabilità meteorologiche; tratta le annate disponibili come campioni empirici e non ponderati. Il rischio in classifica è `resa_rel_min`, cioè il minimo storico della resa relativa media del ciclo tra le simulazioni della classe. Sono anche calcolati mediana e percentile 10, ma il ranking non usa il percentile 10.

Ogni replica parte con condizioni convenzionali uguali: profilo idrico a capacità di campo (`frazione_acqua_disponibile=1`), N minerale stimato da tessitura e N totale, residui/cover vuoti, humus iniziale da SO e densità. Si simula un ciclo di avviamento prima di valutare la rotazione, per ridurre la dipendenza dall’inizializzazione. La condizione iniziale non è misurata per il campo dell’agricoltore e non è campionata come distribuzione.

La cache corrente ha 23 annate tentate (2000–2022); per completare spin-up e ciclo entro la serie affidabile, i risultati disponibili partono dal 2000 al 2016 e valutano cicli dal 2003 al 2019. Il rapporto di qualità esclude la pioggia POWER 2023–2025, sovrastimata rispetto alla rete ARPA; IMERG resta una forzante di sensibilità, non il default. [weather.py:48–63, 93–163](../src/fieldwise/weather.py), [ensemble_meta.json](../data/processed/lat45.200_lon10.000/ensemble_meta.json)

## 5. Obiettivi, punteggi e pesi

La classifica attuale usa sei priorità e sette indicatori:

| Priorità | Indicatore/i effettivi | Verso favorevole |
|---|---|---|
| Resa | Mediana storica della resa relativa (`resa_rel_mediana`) | Più alto |
| Rischio | Peggiore resa relativa storica (`resa_rel_min`) | Più alto |
| Acqua | Irrigazione [mm/ha/anno] | Più basso |
| Concime | N fertilizzante [kg N/ha/anno] | Più basso |
| Suolo | Variazione humus [t/ha/anno] e N lisciviato [kg N/ha/anno] | Più humus, meno lisciviazione |
| Profitto | `margine_lordo_eur_ha` [€/ha/anno] | Più alto |

Per ogni indicatore `j`, normalizzazione min–max sull’insieme confrontato:

```text
zj = (xj − min(xj)) / (max(xj) − min(xj))    se più alto è meglio
zj = 1 − (xj − min(xj)) / (max(xj) − min(xj)) se più basso è meglio
parziale(priorità) = media degli indicatori della priorità
punteggio = Σpriorità peso(priorità) · parziale(priorità) / Σpriorità peso(priorità)
```

Un indicatore costante vale 0,5 per tutte le alternative. **Non c’è un peso predefinito nel backend:** `ranking.score` richiede un peso non negativo per una o più delle sei priorità. I pesi uguali sono usati nell’analisi di sensibilità/esempi, non costituiscono un default imposto al prodotto; l’interfaccia non è inclusa nel repository. Non si possono separare i due indicatori di suolo con pesi di primo livello: dentro “suolo” hanno peso uguale. Se suolo e profitto ricevono uguale peso utente, i due gruppi contribuiscono ugualmente al punteggio, ma non rappresentano impatti assoluti confrontabili: ciascuno è stato normalizzato sul proprio intervallo.

Il punteggio cambia aggiungendo/togliendo alternative, applicando filtri di conformità o cambiando scenario, perché i minimi e massimi cambiano. È relativo all’insieme, non una probabilità né una misura assoluta di beneficio. Il backend può restituire l’intero fronte di Pareto (default: tutti e sette gli indicatori); `ranking.confronta` propone per default due alternative: la migliore per punteggio tra quelle non dominate e una distinta migliore sul criterio di rischio. Non è quindi limitato a una sola opzione, ma la funzione di confronto non restituisce da sola l’intero fronte come elenco di raccomandazioni.

La sintesi espone anche resa in t/ha per coltura, fattori di acqua/caldo/rotazione, giorni caldi, ruscellamento, percolazione, deficit N, fissazione, quota di annate sopra MAS, conformità e praticabilità della cover. Questi campi **non** entrano tutti nel ranking: la conformità può filtrare l’insieme; gli altri non elencati sopra sono descrittivi o influenzano indirettamente variabili classificate.

## 6. Componente economica

### Formula e valori attuali

Il margine annualizzato usa ricavi, costi N/acqua e, nelle modifiche locali correnti, costi per coltura:

```text
ricavo = Σi (resa_i [t/ha] × prezzo_i [€/t]) / anni del ciclo
costo altri = Σc (frequenza colturale c [cicli/anno] × costo_c [€/ha coltivato])
margine = ricavo − N_anno × prezzo_N − acqua_anno × costo_mm − costo_altri
```

I prezzi della granella sono costanti per coltura nella simulazione: mais **254 €/t**, soia **505 €/t**, frumento **272 €/t**. Sono valori puntuali ricavati dai punti medi di listini di ottobre/novembre 2026 (Piacenza/Emilia-Romagna), non una media pluriennale; le fonti nel repository sono dichiarate non verificate. Azoto: **1,40 €/kg N**, assunzione. Irrigazione: **0,80 €/ha per mm**, proxy da aziende con pivot; l’origine include impianto/uso, ammortamento e manutenzione ma non un investimento scelto dal motore.

Il workspace corrente aggiunge altri costi fissi per ettaro coltivato: mais **1.950 €/ha**, frumento **880 €/ha**, soia **1.500 €/ha**. Sono stime di partenza non verificate, derivate da fonti di costi colturali e da assunzioni; `ricalcola_margine` permette di sostituirle e ricalcolare la colonna economica prima del ranking. Concime e acqua hanno quantità variabili simulate; le altre operazioni sono aggregate in un costo €/ha per coltura, non calcolate da quantità variabili di seme, fitofarmaci, carburante o ore-macchina.

Il codice corrente quindi realizza in parte l’impostazione “prezzi unitari fissi, quantità simulate variabili, senza investimento strutturale”: lo fa per granella, N e acqua, ma le spese colturali extra sono importi fissi per ettaro e i prezzi non sono medie pluriennali. Non calcola un utile aziendale completo: non include affitto, PAC, costi fissi aziendali o una decisione CAPEX; le stime di costo e la dose N non sono validate con contabilità aziendale/osservazioni agronomiche. Il termine `profitto` del ranking va letto come **margine parziale modellato**. Fonti e assunzioni: [economia.yaml](../params/economia.yaml), [fonti_economia.md](../docs/fonti_economia.md), [economics.py](../src/fieldwise/economics.py).

## 7. Utilizzo concreto e output

Nel backend il flusso è: caricare/fornire coordinate e dati in cache; specificare la rotazione attuale; generare o caricare l’ensemble; scegliere lo scenario idrico e i pesi; opzionalmente applicare il filtro di conformità; confrontare pratica attuale e alternative, leggendo differenze, indicatori e avvisi. La rotazione attuale non viene inferita dai dati: la cache corrente ha `rotazione_attuale: null`; deve essere marcata dall’utilizzatore. Se non fa parte delle rotazioni standard viene simulata a parte e la differenza di durata va evidenziata.

### Esempio calcolato dalla cache corrente

Ricalcolo della classifica con `ranking.score` sulla cache locale più recente, scenario `tetto_irriguo`, sei pesi uguali a 1, 45 classi non equivalenti. La rotazione attuale è stata marcata in memoria come `mais` (mais continuo; scelta di esempio, non dato di un’azienda). La prima è `frumento+cover > mais+cover > mais`: punteggio relativo **0,6505**, resa relativa mediana **0,9290**, minimo storico **0,8385**, irrigazione **133,30 mm/ha/anno**, concime **271,06 kg N/ha/anno**, variazione humus **−0,149 t/ha/anno**, N lisciviato **8,19 kg N/ha/anno**, margine **1.058,67 €/ha/anno**. Mais continuo è **17° su 45**, punteggio **0,5810**, resa mediana **0,9122**, irrigazione **199,95 mm/ha/anno**, concime **272,47 kg N/ha/anno**, humus **+0,004 t/ha/anno**, lisciviazione **11,59 kg N/ha/anno**, margine **1.170,40 €/ha/anno**. I valori provengono da `ensemble_sintesi.csv` (calcolata alle 17:48 UTC con l’hash parametri registrato in `ensemble_meta.json`) e dalla funzione di ranking del workspace corrente. Il punteggio 0,6505 serve solo a ordinare queste 45 classi; il margine è una media storica €/ha/anno e non una previsione o un utile d’impresa.

## 8. Validazione, limiti e modifiche

### Test software e validazione contro dati

Il repository contiene test unitari per dati, bilanci di acqua/N, humus, fenologia, resa, rotazione, ranking ed economia. Il test economico è stato modificato nel workspace per includere i nuovi costi per coltura e il ricalcolo con valori dell’agricoltore. **In questo sommario non ho eseguito la suite, quindi non attribuisco un esito “verde” al commit o alle modifiche locali.** La chiusura numerica dei bilanci è un controllo di coerenza del codice, non una validazione agronomica.

La validazione contro osservazioni riportata in `reports/validation.md` fissa i metodi prima del confronto e include risultati positivi e negativi:

- **Mais, rese ISTAT:** nello scenario tetto irriguo, correlazione Pearson delle anomalie dal trend `r=+0,70` (IC 95% `+0,33…+0,88`, 17 anni). Segnale favorevole ma limitato: resa ISTAT provinciale, irrigazione e asciutto mescolati; errori notevoli nel 2013 e 2017.
- **Soia, rese ISTAT:** `r=+0,27` (IC `−0,24…+0,67`), non confermata; le osservazioni includono soia di secondo raccolto non simulata.
- **Frumento, rese ISTAT:** `r=−0,50` (IC `−0,79…−0,03`), risultato negativo. Il modello rappresenta la siccità ma non le perdite da anni umidi, malattie, allettamento e ristagno; la resa del frumento non va interpretata come rischio annuale locale.
- **SMAP:** anomalie mensili dell’umidità superficiale contro lo strato evaporante simulato, rotazione tetto irriguo `r=+0,70` (`+0,62…+0,79`, 92 mesi). Supporta solo la dinamica superficiale; non distingue gli scenari e non valida acqua radicale, irrigazione o stress di resa.
- **NDVI MODIS:** correlazione con `f_acqua` del mais in tetto irriguo `r=+0,60` (`+0,25…+0,82`, 22 anni). Le annate secche coincidono in parte, ma la finestra da 2 km mescola colture e il modello sovrastima lo stress nel 2017.
- **ECOSTRESS ET:** in stagione di crescita, tetto irriguo, bias medio simulato–satellite `+1,61 mm/giorno`; correlazione grezza `+0,77`, ma sulle anomalie interannuali `+0,39` (`+0,13…+0,70`) in soli cinque anni. Il ciclo stagionale è riprodotto, il livello ET è sovrastimato e la variabilità annuale non è stabilita. L’unità ECOSTRESS resta ambigua nella documentazione.

Non risultano validati con osservazioni locali l’assorbimento e il concime N, la fissazione, l’humus, la lisciviazione, la percolazione/ruscellamento, i volumi irrigui, l’effetto causale delle cover e delle penalità di rotazione, né la prestazione dopo il 2022. I confronti disponibili non dimostrano un incremento di resa o profitto.

### Cosa è cambiato, cosa funziona e cosa manca

- **Nel commit del 14 novembre:** fattore Q10 sul tempo della mineralizzazione/rilascio di N; componenti economiche di base e priorità `profitto`; client e controllo ECOSTRESS; confronto GAEZ dichiarato solo come verifica. È stato rimosso dal repository tracciato il codice Streamlit e il report precedente, lasciando il backend.
- **Nel workspace non committato:** costi extra per coltura, annualizzazione per frequenza di coltura, colonne economiche dettagliate e funzione di ricalcolo per i costi dell’agricoltore; README e cache aggiornati. La cache è stata rigenerata, ma `reports/sensitivity.md` dichiara di riferirsi a commit `39ed21a` e la modifica locale del README segnala che la sensibilità precede i costi colturali: le probabilità di robustezza pubblicate non descrivono il ranking economico corrente.
- **Attualmente funziona:** simulazione giornaliera deterministica di acqua, N e humus; calendario/resa per le colture configurate; confronto storico in tre regole irrigue; output aggregati, filtri di conformità, punteggio relativo e fronte di Pareto; margine parziale con i valori economici correnti. È un supporto a confronti condizionati, non un sistema di previsione o ottimizzazione aziendale.
- **Sviluppi ancora necessari:** la lista esplicita trovata è in un report locale del 13 novembre, non nel commit corrente: includere falda/risalita capillare; rappresentare perdite del frumento negli anni umidi; modellare effluenti; collegare meglio stress N e resa; usare rese, colture, acqua e suolo misurati per appezzamento; migliorare la risoluzione di NDVI; ricalibrare le penalità di rotazione su dati padani; estendere l’analisi temporale con una pioggia affidabile. Sono proposte di lavoro, non funzionalità implementate né un backlog versionato.
- **Benefici sostenibili nel report:** si può affermare che il motore produce confronti riproducibili tra rotazioni e scenari, con variabili esplicite e alcuni segnali coerenti per il mais e per le anomalie superficiali. Non si può affermare che l’alternativa prima in classifica aumenti resa o reddito, riduca perdite o migliori il suolo in azienda: resa soia non confermata, frumento negativo, dimensione economica basata su prezzi/costi di riferimento e processi di N/humus non validati.

## Riferimenti implementativi e dei risultati

- Perimetro/API e variabili restituite: `README.md:1–14, 38–104, 151–177`.
- Meteo e affidabilità annate: `src/fieldwise/weather.py:48–63, 93–175`.
- Rotazioni, calendario, trasferimento degli stati e ciclo simulato: `src/fieldwise/rotation.py:127–169, 288–359, 459–537, 597–729`.
- Suolo idrico/pedotrasferimento: `src/fieldwise/soil.py:88–163, 214–294`; `src/fieldwise/water.py:161–322, 750–915, 1011–1085`.
- Resa: `src/fieldwise/yield_model.py:101–149, 211–224`; `src/fieldwise/water.py:1103–1109`.
- Azoto e humus: `src/fieldwise/nitrogen.py:139–225, 283–440, 452–545`; `src/fieldwise/humus.py:128–196`; parametri e convenzioni in `params/nitrogen.yaml`.
- Classifica, Pareto e confronto: `src/fieldwise/ranking.py:28–35, 141–197, 203–225, 374–451`.
- Economia e aggregazione: `src/fieldwise/economics.py:30–105`; `src/fieldwise/ensemble.py:173–188, 250–267, 324–379`.
- Risultati di validazione: `reports/validation.md:29–75, 76–188, 200–275`; sensibilità precedente ai nuovi costi: `reports/sensitivity.md`.
- Copertura, parametri e provenienza dei dati: `params/soil.yaml`, `params/scenarios.yaml`, `params/crops.yaml`, `params/cover_crop.yaml`, `params/economia.yaml`, `docs/fonti_*.md`, `data/CHECKS.md`.
