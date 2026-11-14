# Fonti per `params/soil.yaml` e `src/fieldwise/soil.py`

Data di accesso di tutte le fonti: 2026-11-11. Punto pilota: lat 45,2, lon 10,0 (circa 7 km a nord di Cremona).

## 1. Equazioni di Saxton e Rawls (2006)

**Saxton K.E., Rawls W.J. (2006).** Soil water characteristic estimates by texture and organic matter for hydrologic solutions. *Soil Science Society of America Journal* 70:1569–1578. doi:10.2136/sssaj2005.0117.
- URL dell'editore: https://acsess.onlinelibrary.wiley.com/doi/10.2136/sssaj2005.0117
- **Limite di accesso:** l'articolo è a pagamento. L'editore ha risposto 403. Le copie su siti terzi (scispace, ResearchGate, una pagina universitaria archiviata) erano bloccate o non autorizzate, quindi non le ho usate. **Non ho letto l'articolo originale.** I coefficienti vengono dalle due riproduzioni ufficiali USDA qui sotto.

**USDA-ARS, modello WEPP, routine `saxpar.for`** (S. Dun, WSU, verificata da J. Wu, 2008).
- URL: https://infosys.ars.usda.gov/svn/code/weps1/branches/weps.src.wepp/src/lib_wepp/saxpar.for
- Cosa ho letto: il codice sorgente completo, con i coefficienti delle eq. 1, 2, 3, 4, 5, 14, 15 e 16. Ogni formula riporta il numero di equazione dell'articolo. Ksat è in mm/h.

**USDA Ag Data Commons, "Soil - Plant - Atmosphere - Water Field & Pond Hydrology"** (K. Saxton), doi:10.15482/USDA.ADC/1529226. File `Soil Water Characteristics-Equations.xls`, ultima revisione 2007.
- URL: https://agdatacommons.nal.usda.gov/articles/model/Soil_-_Plant_-_Atmosphere_-_Water_Field_Pond_Hydrology/24660957 (file scaricato da https://api.figshare.com/v2/file/download/44357183)
- Cosa ho letto: il foglio "Equations", che contiene le soluzioni passo per passo:
  - righe 40–51: le 12 classi tessiturali con OM 2,5 %, senza correzioni. Sono gli esempi della tabella per classi dell'articolo; i Ksat 108,1, 96,7, 50,3 e 15,5 mm/h coincidono con i valori citati dai motori di ricerca per quella tabella;
  - righe 18–28: le medie per classe di 2149 campioni NRCS dell'orizzonte A;
  - riga 30: un esempio con fattore di densità 1,2;
  - riga 53: un esempio con scheletro.
- Le formule delle celle non si leggono con xlrd; ho letto i valori. Le equazioni di densità (ρN = (1−θS)·2,65; ρDF = ρN·DF; θS,DF = 1−ρDF/2,65; θ33,DF = θ33 − 0,2(θS−θS,DF); θ1500 invariato) le ho ricostruite e verificate numericamente sulla riga 30. Lo stesso controllo è in `tests/test_soil.py`.
- Per lo scheletro la riga 53 mostra solo il caso limite (scheletro al 100 %: acqua disponibile e Ksat pari a 0). La formula generale di Ksat con lo scheletro non l'ho letta, quindi non è implementata.

**Saxton K.E., Willey P.H. — The SPAW model for agricultural field and pond hydrologic simulation** (USDA-ARS / NRCS, manuale utente).
- URL: https://irrigationtoolbox.com/NEH/UserGuides/SPAW%20User%20Guide.pdf
- Cosa ho letto, a p. 22: le equazioni valgono per argilla da 0 a circa 60 % e sabbia da 0 a 95 %; esistono correzioni per densità, scheletro e salinità. Nella sezione Runoff: il Curve Number viene corretto per l'umidità antecedente (ARC I sotto il 60 % della capacità di campo dello strato 2, ARC III sopra la capacità di campo).
- Il limite OM ≤ 8 % non l'ho letto in una fonte primaria. È riportato dalla documentazione di pacchetti che riprendono l'articolo, e il foglio USDA arriva a OM 7,5 %. Nel codice è dichiarato con questa provenienza.

**Pagine USDA archiviate del programma "Soil Water Characteristics"**: http://web.archive.org/web/20220809045619/https://hydrolab.arsusda.gov/soilwater/Index.htm. Le ho usate solo per conferma: il programma considera tessitura, sostanza organica, scheletro, salinità e compattazione.

## 2. SoilGrids 2.0

**Poggio L., de Sousa L.M., Batjes N.H., Heuvelink G.B.M., Kempen B., Ribeiro E., Rossiter D. (2021).** SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. *SOIL* 7:217–240.
- URL: https://soil.copernicus.org/articles/7/217/2021/ (PDF letto)
- Cosa ho letto:
  - tab. 4, validazione globale, MEC delle medie: SOC 0,47, sabbia 0,54, argilla 0,43, bdod 0,74, cfvo 0,31;
  - tab. 5, MEC per profondità: SOC 0,38–0,55 nei primi 30 cm;
  - il testo dice che alla scala locale SoilGrids va confrontato con rilievi di dettaglio.
- Dati del punto: servizio REST https://rest.isric.org/soilgrids/v2.0/properties/query, scaricati il 2026-11-11T16:25:34Z. Provenienza in `data/raw/soilgrids/lat45.200_lon10.000/soilgrids_rest.json.meta.json`.

## 3. Controllo di plausibilità (fonti regionali)

**ERSAF Lombardia (2024). Piano di monitoraggio dei suoli e dei sistemi agricoli 2020-2023 – Rapporto finale.**
- URL: https://www.ersaf.lombardia.it/wp-content/uploads/2024/12/Rapporto-Monitoraggio_suoli_20-23_def.pdf
- Cosa ho letto:
  - tab. 1, suoli prevalenti per Focus Area:
    - Bassa Pianura Centrale: "suoli franchi con substrato sabbioso senza scheletro… limitati dalla falda profonda e/o da orizzonti sabbiosi (mediamente tra 110 e 150 cm)";
    - Media Pianura: "limitati dalla falda (mediamente tra 85 e 170 cm)";
  - tab. 19, carbonio organico 0–30 cm nel 2020–2023:
    - Bassa Pianura Centrale 13,5 ± 4,7 g/kg;
    - Media Pianura 14,7 ± 3,7;
    - pianura totale 15,6 ± 6,6;
  - tab. 13, classi di Costantini (2006): oltre 18 g/kg è "molto elevato";
  - tab. 27, piezometri di falda ipodermica (0–3 m) a Pizzighettone e Pescarolo ed Uniti (Bassa Pianura Centrale) e a Pessina Cremonese (Media Pianura).
- Limite: la Focus Area del punto l'ho dedotta dalla posizione dei comuni campionati, che stanno a est e a ovest del punto. La carta della figura 7 non l'ho consultata.

**ERSAF (2008). Stock di carbonio nei suoli regionali – Relazione tecnica** (Progetto Kyoto Lombardia).
- URL: https://ambiente.regione.emilia-romagna.it/it/geologia/suoli/proprieta-e-qualita-dei-suoli/carbonio-organico/co2/soc-stock-lombardia.pdf/@@download/file/SOC%20Stock%20Lombardia.pdf
- Cosa ho letto:
  - nei seminativi e nelle legnose agrarie lo stock medio è di 57,0 t C/ha in 0–30 cm, con coefficiente di variazione tra 0,4 e 0,5;
  - la pianura centro-meridionale ha i tenori più bassi.

**Regione Lombardia (2009). FERSOIL – Quaderni della ricerca n. 105.**
- URL: https://maclab.it/wp-content/uploads/2024/01/Progetto-FerSoil-compresso.pdf
- Cosa ho letto, sul sito sperimentale di Luignano (CR), a circa 5 km dal punto, carta pedologica ERSAF "I suoli della pianura cremonese centrale" (2000), unità BZG1, Haplic Luvisols:
  - tessitura franco-sabbiosa: sabbia 56 %, limo 34 %, argilla 10 %;
  - carbonio organico 9 g/kg (8,3–10 nelle tesi);
  - "assenza di scheletro";
  - densità assunta 1,4 t/m³.
- Limite: è un singolo appezzamento.

**LUCAS topsoil (JRC ESDAC):** non consultato. I dati puntuali richiedono una registrazione e non ho trovato un riepilogo aperto per i seminativi di Cremona. Sulla sovrastima di SoilGrids nei seminativi europei non ho trovato, in questa ricerca, uno studio specifico da poter aprire.

**Esito**

| grandezza (0–30 cm) | SoilGrids | fonti regionali | effetto |
|---|---|---|---|
| carbonio organico | 20,7 g/kg (q05–q95: 5,7–48,2) | 13,5 ± 4,7 (ERSAF BPC); 9 (Luignano) | SoilGrids è circa 1,5 volte ERSAF |
| sostanza organica | 3,56 % | 2,33 % | fc da 0,3255 a 0,3146; wp da 0,1722 a 0,1662; AW 0–30 da 46,0 a 44,5 mm |
| stock di humus 0–30 (ρ 1,433) | 153 t/ha (C 88,9 t/ha) | 100 t/ha (C 58,0 t/ha, coerente con le 57 t/ha di ERSAF 2008) | −35 % sullo stock iniziale del bilancio dell'humus |
| tessitura | franco (S 33, C 26) | "franchi" (ERSAF); franco-sabbioso a Luignano | classe confermata a scala di Focus Area |
| scheletro | 9–12 % vol | "senza scheletro" | non applicato |
| densità | 1,43 g/cm³ | 1,4 assunta (FerSoil) | plausibile; non usata in Saxton-Rawls |

In `soil.yaml` ho lasciato il valore SoilGrids, con l'alternativa ERSAF in `intervallo` e `sensibilita: true`. La scelta spetta al responsabile.

## 4. Parametri FAO, NRCS e AquaCrop

**Allen R.G., Pereira L.S., Raes D., Smith M. (1998). FAO Irrigation and Drainage Paper 56.**
- Cap. 7, https://www.fao.org/4/x0490e/x0490e0c.htm: tab. 19, riga Loam: θFC 0,20–0,30, θWP 0,07–0,17, REW 8–10 mm, TEW 16–22 mm.
- Cap. 8, https://www.fao.org/4/x0490e/x0490e0e.htm:
  - tab. 22: Maize, Field (grain), Zr 1,0–1,7 m;
  - eq. 85 (bilancio, con il termine CR di risalita capillare) ed eq. 88 (percolazione profonda nello stesso giorno);
  - "Initial depletion" (eq. 87): Dr ≈ 0 dopo piogge abbondanti.

**USDA NRCS, National Engineering Handbook, Part 630 Hydrology** (indice: https://directives.nrcs.usda.gov//sites/default/files2/1712930634/Part%20630%20-%20Hydrology.pdf).
- Cap. 7 Hydrologic Soil Groups (gennaio 2009), https://directives.nrcs.usda.gov/sites/default/files2/1712930597/11905.pdf: definizioni dei gruppi A–D e tabella 7-1 (Ksat dello strato meno permeabile, profondità della falda e dello strato impermeabile).
- Cap. 9 Hydrologic Soil-Cover Complexes (luglio 2004), https://directives.nrcs.usda.gov/sites/default/files2/1712930607/7306.pdf: tab. 9-1, gruppo C:
  - Fallow bare soil 91;
  - Row crops SR Good 85 / Poor 88;
  - Small grain SR Good 83 / Poor 84;
  - valori per ARC II e Ia = 0,2 S.
- Cap. 10 Estimation of Direct Runoff (luglio 2004), https://directives.nrcs.usda.gov/sites/default/files2/1712930608/7300.pdf:
  - tab. 10-1, ARC I e III: 85 → 70/94, 83 → 67/93, 91 → 80/97;
  - nel testo ARC I e III sono gli estremi della variabilità.

**Raes D., Steduto P., Hsiao T.C., Fereres E. (2026). AquaCrop Version 7.3 Reference Manual, Chapter 3** (FAO).
- URL: https://www.fao.org/docs/devbuildingforwardbetterlibraries/default-document-library/chapter3aquacropv73.pdf (il PDF l'aveva già scaricato un altro agent; ho letto le sezioni 3.7.3 e 3.7.4)
- Cosa ho letto:
  - eq. 3.7a–b: drenaggio con τ = 0,0866·Ksat^0,35, Ksat in mm/giorno;
  - eq. 3.7e–i: Curve Number con Ia = 0,05 S; CN di default per il gruppo C pari a 72 (tab. 3.7a); correzione per l'umidità dei primi 0,3 m.

**Soil Science Society of America, Glossary of Soil Science Terms.** Definizioni delle classi tessiturali USDA tratte dal Soil Survey Manual, Handbook 18 (1993).
- URL: https://agronomy.org/files/publications/soils-glossary/table-5.pdf e https://agronomy.org/files/publications/soils-glossary/figure-1.pdf
- Cosa ho letto: i limiti di tutte le 12 classi.

## 5. Falda

L'unica fonte aperta trovata con profondità vicino al punto è ERSAF (2024), tab. 1. Indica falda e/o orizzonti sabbiosi a 110–150 cm nella Bassa Pianura Centrale e falda a 85–170 cm nella Media Pianura. Il rapporto non pubblica le soggiacenze misurate nei piezometri. Le carte piezometriche di ARPA Lombardia e i PGT comunali non li ho consultati. Il motore non modella la falda: le conseguenze sono descritte in `soil.yaml` → `_meta.limiti`.

## 6. Aggiornamento 2026-11-12 – decisione sulla sostanza organica 0–30 cm

Il responsabile ha scelto il valore ERSAF (2024), tab. 19, Bassa Pianura Centrale: carbonio organico 13,5 g/kg, cioè
2,327% di SO (× 1,724), al posto di SoilGrids (3,563%, ora in `intervallo` e in nota). Nessuna fonte nuova letta:
il rapporto ERSAF è quello della sezione 3. Grandezze ricalcolate con `fieldwise.soil` (strato 0–30 e
`profilo.strato_superficiale`): fc 0,3146, wp 0,1662, sat 0,4647, ksat 8,97 mm/h, acqua disponibile 44,5 mm;
acqua disponibile 0–150 cm 213,6 mm; tau AquaCrop dello strato superficiale 0,568; gruppo idrologico invariato (C).
`tests/test_soil.py::test_yaml_inputs_match_soilgrids_cache` è stato adattato: per lo strato 0–30 la SO non deve più
coincidere con la cache SoilGrids, ma il valore SoilGrids deve stare nell'intervallo della voce.

## 7. Aggiornamento 2026-11-12 – verifica del motore (ruscellamento e doppio coefficiente)

**Raes D., Steduto P., Hsiao T.C., Fereres E. (2026). AquaCrop Version 7.3 Reference Manual, Chapter 3**, riletto
(PDF scaricato e convertito in testo), sez. 3.7.4, pp. 3-61/3-63:
- eq. 3.7e-f e frase "The initial abstraction (Ia) in Eq. 3.7e is fixed at 0.05 S" → `ruscellamento.aquacrop.ia_su_s`;
- tab. 3.7a: gruppo C, Ksat 346-36 mm/day, CN default AMC II = 72 → `ruscellamento.aquacrop.cn` (Ksat 0-30 cm = 215 mm/g);
- testo: il CN del suolo non deve considerare uso e copertura (gestione del campo) → `ruscellamento.metodo_cn`;
- eq. 3.7g-h (CN AMC I e III da CN AMC II), usate da `water.cn_amc_aquacrop` con la correzione opzionale per l'umidità.

**Allen et al. (1998), FAO-56 cap. 7**, https://www.fao.org/4/x0490e/x0490e0c.htm, riletto: tab. 20 (fw: pioggia e
aspersione 1,0; goccia 0,3-0,4) → `evaporazione.fw`.
