# Verifica scientifica indipendente del motore (fasi 3 e 4)

Data: 2026-11-12. Moduli verificati: `src/fieldwise/water.py`, `nitrogen.py`, `humus.py`, `phenology.py`,
`yield_model.py`, `rotation.py`. Parametri: sezioni `_meta` di `nitrogen`, `heat`, `rotation_rules`,
`cover_crop`, `scenarios` e singole voci lette con `fieldwise.params.get`. Fonti aperte (4 pagine web):
FAO-56 cap. 8 e cap. 7, AquaCrop v7.3 Reference Manual cap. 3 (PDF), Deryng et al. 2014 (ERL 9, 034011).
Le verifiche numeriche sono script usa-e-getta fuori dal repository, eseguiti sul punto pilota
(meteo 2000-2022, 17 annate di partenza per rotazione, un ciclo di avviamento, D15). Nessun file di codice,
parametro o test è stato modificato.

## A. Equazioni rispetto alle fonti

| # | Controllo | Cosa dice la fonte | Cosa fa il codice | Esito |
|---|---|---|---|---|
| A1 | TAW (FAO-56 eq. 82, cap. 8 letto) | TAW = 1000 (θFC − θWP) Zr | `taw1`, `taw2`, TAW = f1 TAW1 + f2 TAW2 (`_kernel`) | Conforme. La somma per strati è la generalizzazione corretta a due strati |
| A2 | RAW e correzione di p (eq. 83, nota 2 della tab. 22) | RAW = p TAW; p = p_tab + 0,04 (5 − ETc), con 0,1 ≤ p ≤ 0,8 ed ETc in mm/g | `p_adjusted` e `_kernel` righe 478-483 | Conforme |
| A3 | Ks (eq. 84, 86) | Ks = (TAW − Dr)/((1 − p) TAW) se Dr > RAW, altrimenti 1; 0 ≤ Dr ≤ TAW. Dr è quello di **inizio giornata** (= Dr,i-1 di fine giorno precedente; es. 37-38) | stessa formula e stesso limite; prova numerica: Ks = 1,000 a Dr/TAW = 0,495 (sotto RAW), 0,99 a 0,505, 0,50 a 0,75 e 0 a Dr = TAW | Conforme nella forma. Scarto minore: il codice calcola Dr **dopo** la pioggia e l'irrigazione del giorno. FAO-56 lo ammette solo se pioggia e irrigazione cadono presto nella giornata (es. 38). È una scelta da dichiarare |
| A4 | Percolazione profonda (eq. 88) | DP = (P − RO) + I − ETc − Dr,i-1 ≥ 0, con l'acqua oltre fc drenata | eccesso oltre fc drenato in cascata nello stesso giorno, prima dell'ET | Conforme (il drenaggio avviene prima dell'ET, coerente con la cascata dichiarata) |
| A5 | Regola irrigua (cap. 8) | irrigare quando Dr ≥ RAW, con Ii ≤ Dr,i | I = Dr se Dr > RAW, entro il tetto del segmento | Conforme |
| A6 | Correzione climatica di Kc e Kcb (eq. 62, 65, 70) | Kc(Tab) + [0,04 (u2 − 2) − 0,004 (RHmin − 45)] (h/3)^0,3, con 1 ≤ u2 ≤ 6, 20 ≤ RHmin ≤ 80; su Kc end e Kcb end solo se il valore tabulato è ≥ 0,45 (cap. 7 letto) | `kc_climate_correction`, `kc_end_climate_correction` (soglia 0,45); RHmin da eq. 63 con Tdew ≈ Tmin | Conforme |
| A7 | Strato evaporante: TEW e Kr (eq. 73, 74) | TEW = 1000 (θFC − 0,5 θWP) Ze; Kr = (TEW − De,i-1)/(TEW − REW) con De di **fine giorno precedente** | stessa formula, ma Kr usa De **dopo** la pioggia del giorno | Forma conforme. Scarto minore: lo stesso problema di ordine di A3 |
| A8 | Ke sul suolo nudo (eq. 71, 72; es. 31) | Ke = min(Kr (Kc max − Kcb), few Kc max); per il suolo quasi nudo **Kcb ≈ 0,15** (evaporazione diffusiva), come nell'es. 31 con Kc max 1,20; Kc max da eq. 72 (≥ Kcb + 0,05, circa 1,05-1,30) | Kcb = 0 e Kc max = 1,2 fisso. Il docstring dice "come indicato nel testo di FAO-56 per il suolo nudo" | **Non conforme nella motivazione.** FAO-56 usa Kcb 0,15; `crops.suolo_nudo.kcb_suolo_nudo = 0,15` esiste in YAML ma non è usato. Con Kcb = 0 l'evaporazione cessa a De = TEW, quindi il suolo nudo asciutto perde meno acqua |
| A9 | Limite inferiore dello strato 1 (correzione del difetto) | eq. 73: Ze fino a 0,5 θWP; eq. 82: il resto dello strato fino a θWP | W1_min = 1000 (θWP z1 − 0,5 θWP Ze); De vincolato a [FC1 − W1 − TAW_sotto, min(TEW, FC1 − W1)] (`_de_consistent`) | Conforme e internamente coerente: ricavato dalle due equazioni; sui dati reali nessuno strato esce dai limiti |
| A10 | Curve Number (AquaCrop eq. 3.7e-f letto; NEH 630 cap. 10 non riaperto) | RO = (P − Ia)²/(P − Ia + S), S = 254 (100/CN − 1). NEH: Ia = 0,2 S; AquaCrop: Ia = 0,05 S | `_scs_runoff`, Ia = 0,2 S, applicato alla pioggia giornaliera | Forma conforme. I CN 85/83/91 sono i valori NEH tab. 9-1 per HSG C (filari, cereali a paglia, maggese nudo). HSG C è coerente con Ksat = 2,49 µm/s (215 mm/g, tab. 3.7a di AquaCrop: 36-346 mm/g = C). L'applicazione giornaliera è prassi (SWAT), non NEH (che ragiona per evento): da dichiarare |
| A11 | Risposta della resa all'acqua (FAO-33, FAO-56 eq. 90) | 1 − Y/Ym = Ky (1 − ETa/ETc) sulla stagione | `relative_yield_fao33`, limitata a [0, 1], ETa ed ETc stagionali del segmento | Conforme |
| A12 | Gradi-giorno (AquaCrop cap. 3 par. 3.3.1, letto) | Method 1: Tavg = (Tx + Tn)/2, limitata a [Tbase, Tupper] | Tavg = T2M di POWER (media oraria), (Tx + Tn)/2 solo se manca | Scarto dichiarato ma diverso dalla fonte. Effetto misurato trascurabile: +0,08 °C apr-set, durata mediana del ciclo del mais 146 g in entrambi i casi |
| A13 | Caldo, Deryng et al. 2014 App. A.3 (letto) | Teff = (Tmean + Tmax)/2; f giornaliero lineare tra Tcr e Tlim nella TSP da 0,45 a 0,70 della GPL; media sulla TSP (A.7). Tab. A.1: mais 32/45, soia 35/40, frumento primaverile 25/35 | `heat_factor`, `_linear_daily`, `_window_mask` (GPL in giorni da emergenza a maturità); soglie di heat.yaml identiche alla tab. A.1 | Conforme. In Deryng l'eq. A.8 applica f_HSA al carbonio degli organi di raccolta, non direttamente a Y (l'equazione è un'immagine e non è leggibile). La forma moltiplicativa Y × f è un'approssimazione da dichiarare |
| A14 | Ks logistico di AquaCrop (eq. 3.2c, letta) | Ks = Sn Sx/(Sn + (Sx − Sn) exp(−r (1 − Srel))); r da Ks = 0,5 a Srel = 0,5; "a small value for Sn" senza valore | `_AQ_R` ricavato correttamente; Sn = 0,001 dichiarato; Ks riscalato | Conforme (solo in sensibilità) |
| A15 | Hénin-Dupuis (fonte non riaperta: Mémento 2007 non accessibile in questa sessione) | dH/dt = k1 A − k2 H | H_min = k2 min(H, H_tetto)/365 al giorno; H_res = k1 SS_res c_res 1,724; tetto oltre il 3% di SO (ER) | Coerente con la forma pubblicata e con `nitrogen._meta`. Con C/N = 11,6, k2 = 0,0185/anno, che è la colonna 9-12 per il franco |
| A16 | Lisciviazione SWAT (eq. 4:2.1.2 e 4:2.1.8; fonte non riaperta) | per strato: NO3 lisciviato = NO3_ly (1 − exp(−w_perc/((1 − θe) SAT_ly))) | stessa forma su un solo serbatoio, con SAT = profilo intero di 1,5 m (673 mm, denominatore 337 mm) | Forma conforme. Applicarla a un solo strato con la SAT di tutto il profilo diluisce la lisciviazione per mm drenato di circa 5 volte rispetto allo strato 0-30 (70 mm). È già dichiarato nei limiti; va messo in sensibilità |

Esiti: 12 conformi (di cui 3 con uno scarto minore di ordine o di definizione da dichiarare: A3, A7, A12),
3 conformi con un'approssimazione da dichiarare (A10, A13, A16), 1 non conforme nella motivazione (A8).
Fonti aperte in questa sessione: A1-A9, A10 (AquaCrop), A12, A13, A14. A15 e A16 sono controlli di
coerenza, senza la fonte riaperta.

## B. Numeri nel codice

| File:riga | Numero | Natura | Giudizio |
|---|---|---|---|
| `water.py:301-304` | 1, 6, 20, 80, 0,1, 10, 0,04, 2, 0,004, 45, 3, 0,3 | costanti delle eq. 62/65 | ammesse (D9), citate |
| `water.py:310` | 0,45 | soglia dell'eq. 65/70 | ammessa, citata |
| `water.py:318, 478-482` | 0,04, 5, 0,1, 0,8 | nota della tab. 22 | ammesse, citate |
| `water.py:389-390` | 25400, 254, 0,2 | eq. CN (Ia = 0,2 S) | ammesse, ma **λ = 0,2 andrebbe in YAML**: AquaCrop usa 0,05 ed è un'alternativa necessaria (vedi E1) |
| `water.py:443-446` | 0,5 | ARC II a metà tra wp e fc (regola di soil.yaml) | ammessa (regola citata) |
| `water.py:174, 428` | 0,5 θWP | eq. 73 | ammessa |
| `humus.py:75` | **9,0 e 12,0** (soglie di C/N per scegliere la colonna di k2) | soglie agronomiche del metodo ER | **non in YAML**: citate nel docstring, ma sono numeri agronomici; spostarle in `nitrogen.suolo.k2` |
| `yield_model.py:33-34` | Sn = 0,001, Sx = 1 | costanti dell'eq. 3.2c di AquaCrop | dichiarate come scelta; solo sensibilità |
| `nitrogen.py:146` | 10 | conversione da % a g/kg | conversione d'unità |
| `rotation.py:76` contro `humus.py:51` | 365,25 contro 365 | durata in anni | incoerenza minima (0,07% sugli indicatori annui); unificare |
| `water.py` (Kcb del suolo nudo = 0 implicito) | 0 | sostituisce il valore YAML 0,15 | vedi A8: un parametro in YAML che non viene usato |

Nessun numero agronomico nascosto nei bilanci di massa oltre a quelli in tabella.

## C. Criteri di accettazione delle fasi 3 e 4 (riprodotti)

| Criterio | Mia misura | Esito |
|---|---|---|
| Chiusura del bilancio idrico ≤ 0,01 mm su rotazione reale | massimo su 5 rotazioni × 17 annate × 3 scenari (255 simulazioni): 2,7e-12 mm sull'intera simulazione, 1,2e-13 mm al giorno | Soddisfatto |
| Chiusura del bilancio dell'azoto | rotazione intera 2,4e-11 kg N/ha; giorno 1,3e-12; segmento ~1e-11 | Soddisfatto |
| Ks = 1 sotto RAW, 0 al punto di appassimento | 1,000 / 0,990 / 0,500 / 0,000 a Dr/TAW = 0,495 / 0,505 / 0,75 / 1 (atteso identico) | Soddisfatto |
| Ogni fattore di resa in [0, 1] e citato | clip in `crop_yield` e `water_factor`; fonti: FAO-33, Deryng tab. A.1, Seifert 2017, Marini 2020, AHDB | Soddisfatto |
| Le fasi seguono i gradi-giorno; un anno caldo accorcia il ciclo | mais seminato il 15/4: 125-164 g, correlazione durata-Tmedia = −0,99; 2022 = 125 g (il più corto) | Soddisfatto |
| Kc e radici seguono la frazione di gradi-giorno | a fine sviluppo frazione 0,3497 (punto di passaggio 0,3436), Kc = Kc mid corretto 1,152, Zr al massimo (1,5 m, limitato dal profilo) | Soddisfatto |
| Stato mai azzerato lungo la rotazione | un solo nucleo per acqua e azoto; la chiusura sull'intera rotazione (riga 2) esclude azzeramenti; la mutazione M4/M5 (sez. F) viene rilevata | Soddisfatto |
| Il frumento continuo non vince senza giustificazione | solo pioggia: resa relativa media FFF 0,787 > MSF 0,733 > MMM 0,535; con irrigazione MSF vince (0,913 e 0,991 contro 0,787). La giustificazione c'è (f_acqua 0,996 del frumento contro 0,58 del mais in asciutto) ma FFF supera il MAS in 42 colture su 51 | **Con riserva**: la resa relativa tra colture diverse non è da sola un criterio di confronto; la classifica va presentata con più indicatori |
| f_caldo del mais nel 2022 (D16) | Deryng, finestra in giorni: **0,958** (riprodotto); in GDD 0,942; AquaCrop 1,00; Teixeira 0,999. Le soglie sono identiche alla tab. A.1 di Deryng, nessun parametro dipende dall'annata | Il valore dichiarato è corretto, nessuna taratura. Requisito non soddisfatto e correttamente dichiarato |

## D. Plausibilità per la bassa pianura lombarda (mediana su 17 annate; pioggia 789 mm/anno, ET0 888 mm/anno)

Annuali per ciclo valutato (mm/anno, kg N/ha/anno, t SO/ha/anno); "resa" = resa della coltura indicata.

| Rotazione | Scenario | Ruscell. | Percol. | Irrig. | Concime | Lisciv. | ΔH | Rese (t/ha) |
|---|---|---|---|---|---|---|---|---|
| MMM | solo pioggia | 89 | 117 | 0 | 131 | 13 | −0,48 | mais 8,3 |
| MMM | tetto | 89 | 169 | 200 | 286 | 18 | 0,00 | mais 14,9 |
| MMM | libera | 89 | 222 | 290 | 307 | 24 | +0,05 | mais 15,5 |
| M>S>F | solo pioggia | 83 | 137 | 0 | 120 | 14 | −0,65 | 8,7 / 3,2 / 7,8 |
| M>S>F | tetto | 83 | 149 | 100 | 171 | 16 | −0,48 | 15,0 / 3,8 / 7,9 |
| M>S>F | libera | 83 | 201 | 194 | 173 | 19 | −0,43 | 15,7 / 4,5 / 7,9 |
| FFF | tutti | 57 | 166 | 0 | 198 | 8 | −0,72 | frumento 6,5 |
| SSS | solo pioggia | 94 | 115 | 0 | 0 | 13 | −0,88 | soia 2,9 |
| SSS | libera | 94 | 192 | 308 | 0 | 22 | −0,78 | soia 4,0 |
| M>S>F tutte con cover | solo pioggia | 44 | 170 | 0 | 119 | 11 | −0,59 | 8,7 / 3,2 / 7,8 |

Mais: ETc stagionale 539 mm (145 g); ETa 350 mm in asciutto, 524 con tetto, 539 con irrigazione libera; irrigazione
netta libera 290-320 mm.

Giudizio sugli ordini di grandezza:
- **Plausibili:** ETc del mais (539 mm; atteso circa 500-650), irrigazione netta (290-320 mm; atteso 250-400),
  rese irrigue (14,9-15,7 t/ha, vicine al potenziale di 15,8; la media lombarda è più bassa, ma lo scenario è
  potenziale-limitato dall'acqua), frumento 7,8 t/ha, soia 3,2-4,5 t/ha, fissazione 57-90 kg N/ha/anno nella
  triennale, perdita di humus dello 0,6-1,3% dello stock all'anno.
- **Fuori scala, alti:** ruscellamento 83-94 mm/anno (11-12% della pioggia su un campo pianeggiante; atteso
  < 30-50). La causa è il CN 91 del suolo nudo nell'intercoltura: 81 mm in 240 giorni dopo il mais (vedi E1).
- **Fuori scala, bassi:** lisciviazione 8-24 kg N/ha/anno (per mais irriguo in pianura padana la letteratura
  riporta in genere diverse decine di kg). Le cause sono tre: il concime copre la domanda giorno per giorno e
  non passa mai da N_min; la perdita del concime (PERD_F, circa 50 kg con il mais irriguo) è contata a parte;
  la SAT del profilo intero sta al denominatore. Anche la percolazione in asciutto è bassa (115-140 mm), e
  manca la risalita capillare da falda (CR = 0). Questo sovrastima lo stress del mais in asciutto
  (f_acqua 0,58) dove la falda è superficiale.
- **Indicatori normativi:** il concime del frumento (198-216 kg N/ha) supera il MAS nella maggior parte delle
  annate (FFF 42/51). Il mais irriguo con cover lo supera 17 volte su 17. Il motore fa bene a mostrarlo, ma
  n_assorbito del frumento (29,6 kg/t) e il recupero apparente 0,57 vanno messi in sensibilità.
- `etc_anno` somma l'ETc delle colture e l'evaporazione potenziale Kc_max ET0 del suolo nudo: FFF 933 mm > MMM
  871 mm. Va etichettato, perché non è un'"ETc colturale".

## E. Questioni aperte

**E1. Ruscellamento.** AquaCrop v7.3 (cap. 3, par. 3.7.4 e tab. 3.7a, letti) assegna il CN dal Ksat dello
strato superficiale: con Ksat = 215 mm/g (soil.yaml) il suolo è nel gruppo C (36-346 mm/g), con **CN = 72 per
AMC II e Ia = 0,05 S**. È la media del complesso "small grain, good" del NEH. Il manuale dice esplicitamente che
il CN del suolo non deve considerare uso e copertura, che passano dalla gestione del campo. Sulla serie di pioggia
del punto pilota, senza retroazione dell'umidità, i valori annui sono: CN 91 nudo 120 mm/anno, CN 85 filari
48, CN 83 cereali 35, AquaCrop CN 72 con Ia = 0,05 S 45. Raccomando AquaCrop CN 72 con Ia = 0,05 S come default,
per tre motivi: è la fonte FAO, prima nella gerarchia; elimina l'artefatto per cui la cover aumenta l'infiltrazione
solo perché il nudo ha CN più alto; il campo dopo la raccolta non è un "maggese nudo" del NEH. Il NEH per classe
di copertura resta in sensibilità. Serve rendere λ (Ia/S) un parametro YAML: con CN 72 e λ = 0,2 il
ruscellamento crollerebbe a 5 mm/anno, quindi CN e λ non vanno mescolati (lo dice già soil.yaml). Dopo il
cambio, il ruscellamento atteso è circa 45 mm/anno, coerente con un campo pianeggiante.

**E2. Cover crop: un limite più un'incoerenza da correggere, nessun errore aritmetico.** Misure su M>S>F con e
senza segale, solo pioggia:
- (a) **Poco N da intercettare:** N_min alla semina della cover = 10,6 kg/ha in mediana, perché il concime non
  resta mai nel suolo. Le riduzioni pubblicate del 56-70% valgono con nitrato residuo dopo la raccolta.
- (b) **La cover aumenta il drenaggio:** dopo il mais la percolazione passa da 35 a 132 mm e la lisciviazione
  sale da 5,7 a 10,1 kg. Le cause sono due: il CN (ruscellamento 81 → 39 mm) e l'ET della cover (Kc singolo
  costante 0,7), che è più bassa di quella del suolo nudo bagnato (Kr × 1,2 ET0): 225 contro 245 mm.
  Lo stesso difetto compare alla semina delle colture: il giorno prima il suolo nudo bagnato evapora
  1,2 ET0, dopo la semina il mais (Kc ini 0,3) solo 0,3 ET0. FAO-56 chiede un Kc ini calcolato dalla
  frequenza delle bagnature (fig. 29-30), non il valore tabulato. È un'incoerenza tra Kc singolo e
  coefficiente duale: è un ERRORE da correggere (sotto).
- (c) **Concentrazione per mm drenato:** la cover riduce L/DP del 30% dopo il mais e del 63% dopo il frumento,
  quest'ultimo dentro l'intervallo pubblicato.
- (d) **Tempi di assorbimento:** il 55% dell'assorbimento cade tra settembre e dicembre, quindi la spiegazione
  in `nitrogen._meta.limiti` ("assorbimento non concentrato in autunno") non è la causa principale e va
  corretta. Il tetto di 51 kg viene raggiunto in mediana.

Il 26% non è un errore di riparto: va dichiarato come limite dopo la correzione di (b), dicendo che la
riduzione relativa è bassa perché la lisciviazione assoluta è piccola.

**E3. Azoto e resa.** La scelta è accettabile per uno strumento di confronto se dichiarata: lo scenario è
"azoto non limitante, con costo e rischio ambientale espliciti" (concime, PERD_F, MAS, deficit della soia).
Il deficit della soia è 0 in mediana, quindi l'ipotesi non sposta le rese. Sul doppio conteggio: la penalità
di Seifert 2017 è osservata con una concimazione degli agricoltori che di norma compensa l'azoto, quindi è
soprattutto non-azoto. Il credito −40 kg N agisce solo sul concime, non sulla resa. Sulla resa non c'è doppio
conteggio; nel confronto l'effetto azoto del ristoppio compare due volte solo in parte, come resa più bassa e
come concime in più. Da dichiarare così: "le penalità di ristoppio possono contenere un effetto azoto già
rappresentato dal credito di precessione; variante f_rotazione = 1 in sensibilità" (già previsto in
rotation_rules). In più va scritto nel report che la resa non risponde all'azoto e che le rotazioni povere
di azoto si distinguono per concime e MAS, non per resa.

## F. Sensibilità dei test (mutazioni)

Copie di `src/fieldwise` fuori dal repository (scratchpad, `PYTHONPATH`), con params/data collegati; suite dei
moduli del motore (test_water, test_nitrogen, test_humus, test_phenology, test_yield_model, test_weather; 106
test, tutti verdi sull'originale).

| Mutazione | Rilevata? | Test che la rilevano |
|---|---|---|
| M1 segno dell'ET dallo strato 2 (`w2 += e2`) | Sì | chiusura, limiti degli strati, continuità, stress |
| M2 Ks invertito (`ks = 1 − ks`) | Sì | `TestStress` (3 test) |
| M3 f_acqua non limitata a 1 (`relative_yield_fao33`) | Sì, ma da **un solo** test | `test_relative_yield_fao33` |
| M3b resa senza limiti in `crop_yield` | Sì | `test_crop_yield_fattori_in_0_1_ingressi_estremi` |
| M4 stato idrico azzerato a ogni nuovo segmento | Sì | chiusura su più segmenti, `test_stato_non_si_azzera_tra_segmenti` |
| M5 N_min azzerato alla semina | Sì | `test_chiusura_segmento` |
| M6 lisciviazione raddoppiata (esponente × 2) | Sì, ma da **un solo** test indiretto | `test_concime_cala_con_n_min[mais]` |
| M7 curva di Kc invertita nella catena di rotazione (`rotation._daily_inputs`) | **No** | nessuno: `rotation.py` non ha test |

## Elenco finale per gravità

### ERRORI da correggere prima dell'ensemble
1. **Kc singolo della vegetazione contro coefficiente duale del suolo nudo** (`water._kernel`, ramo
   coltura/cover; `rotation._daily_inputs`). Una cover o una coltura appena seminata evapotraspira meno del
   suolo nudo bagnato, e questo inverte l'effetto della cover sul drenaggio (35 → 132 mm dopo il mais).
   *Correzione:* usare per tutte le superfici il coefficiente duale di FAO-56 cap. 7 (Kcb da crops.yaml e
   cover_crop.yaml, già presenti, più Ke con few = 1 − fc). Lo strato evaporante esiste già nel nucleo.
   Ripiego minimo: Kc_eff = max(Kc, Kr Kc_max) nei giorni di coltura e di cover.
2. **Kcb del suolo nudo = 0 attribuito a FAO-56** (`water.py` docstring e `_kernel` ramo `s_type == 2`):
   FAO-56 (es. 31) usa 0,15 e `crops.suolo_nudo.kcb_suolo_nudo = 0,15` non è usato. *Correzione:* usare il
   parametro (Ke = Kr (Kc_max − 0,15) più 0,15 ET0 dallo strato 1), oppure correggere la citazione e dichiarare
   la scelta. Va fatto insieme al punto 1.
3. **`rotation.py` senza test** (mutazione M7 non rilevata). *Correzione:* test su una rotazione reale che
   verifichino chiusura (acqua e N) dentro `simulate`, continuità dello stato tra segmenti, Kc al passaggio
   end_dev uguale a Kc mid e un caso di conflitto di calendario.
4. **Testo dei parametri non coerente con il codice:** `cover_crop._meta.regole_d_uso` dice ETa/ET0 mentre il
   codice usa Tr = Ks Kcb ET0; `nitrogen._meta.limiti` spiega il 26% con l'assorbimento non autunnale, ma il
   55% dell'assorbimento avviene tra settembre e dicembre. *Correzione:* aggiornare i due testi (lavoro
   documentale).
5. **Soglie di C/N 9 e 12 nel codice** (`humus.k2_from_params`, riga 75). *Correzione:* spostarle in
   `nitrogen.suolo.k2` con la fonte.

### SCELTE DISCUTIBILI da mandare in analisi di sensibilità
- CN: AquaCrop CN 72 con Ia = 0,05 S come default (raccomandato, E1) contro NEH per classe di copertura; λ in YAML.
- Correzione del CN con l'umidità antecedente (use_amc, oggi spenta).
- SAT della lisciviazione: profilo intero (673 mm) contro strato 0-30 o zona radicale.
- Riparto dell'assorbimento di N: traspirazione / ETa / ETa/ET0 (già previsto).
- f_rotazione = 1 (doppio conteggio, E3); recupero apparente del concime e n_assorbito del frumento (MAS).
- f_caldo: Deryng in giorni / in GDD / AquaCrop / Teixeira (già previsto).
- Ordine dei calcoli del giorno: Ks e Kr con Dr e De di inizio giornata (FAO-56) contro dopo la pioggia
  (attuale).
- Kc_max fisso 1,2 contro eq. 72.

### LIMITI da dichiarare nel report
- Nessuna falda né risalita capillare (CR = 0): lo stress del mais in asciutto è probabilmente sovrastimato nella
  bassa pianura.
- Il concime non passa mai da N_min: la lisciviazione (8-24 kg N/ha/anno) è probabilmente sottostimata. La quota
  persa del concime è in PERD_F, non nella lisciviazione.
- L'azoto non limita la resa; la penalità di ristoppio può contenere un effetto azoto (E3).
- La resa relativa tra colture diverse non basta per classificare: in asciutto FFF ha la resa relativa più alta.
- La riduzione della lisciviazione con la cover è bassa in termini relativi perché la lisciviazione assoluta è
  piccola (E2).
- Il criterio "f_caldo basso per il mais nel 2022" non è soddisfatto (0,958): la perdita del 2022 viene
  dall'acqua (D16).
- CN applicato alla pioggia giornaliera di prodotti a griglia (massimo giornaliero della serie 46 mm): le
  intensità sono smussate.
- `etc_anno` include l'evaporazione potenziale del suolo nudo.
- La forma Y × f_caldo approssima l'eq. A.8 di Deryng.

## Giudizio complessivo

I bilanci di massa sono corretti e chiusi alla precisione di macchina. Le equazioni FAO-56, CN, FAO-33,
gradi-giorno e Deryng sono implementate fedelmente, lo stato non si azzera mai e non c'è taratura nascosta.
Le fasi 3 e 4 si possono chiudere a quattro condizioni:
1. correggere l'incoerenza tra Kc singolo e suolo nudo (errori 1-2);
2. adottare, o almeno affiancare come variante principale, il CN di AquaCrop (E1), poi rimisurare
   ruscellamento, percolazione e l'effetto della cover;
3. aggiungere i test di `rotation.py` (errore 3);
4. aggiornare i testi dei parametri (errori 4-5) e dichiarare i limiti elencati.
