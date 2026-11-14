# Fonti di `params/crops.yaml`

Data di accesso per tutte le fonti: 2026-11-11. "Letto" = pagina o PDF aperto e testo estratto durante il lavoro.

## Manuali FAO

1. **Allen R.G., Pereira L.S., Raes D., Smith M. (1998). Crop evapotranspiration — Guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56. FAO, Roma.**
   - Cap. 6 (Kc singolo): https://www.fao.org/4/x0490e/x0490e0b.htm — letti tab. 11 (righe Soybeans, Winter Wheat, Maize (grain) e nota 2 su date di semina), tab. 12 (gruppi Legumes e Cereals per Kc ini, righe Soybeans, Winter Wheat frozen/non-frozen, Maize Field (grain), note 1, 10, 11), testo delle eq. 59, 62, 65 e Box 14.
   - Cap. 6, definizioni delle fasi: https://www.fao.org/4/x0490e/x0490e0a.htm — letto il testo su fase iniziale (~10% copertura), sviluppo (fino a copertura effettiva, spesso all'inizio della fioritura), piena stagione (fino all'inizio della senescenza).
   - Cap. 7 (Kc duale): https://www.fao.org/4/x0490e/x0490e0c.htm — letti eq. 72 (Kc max), eq. 73 (TEW, Ze 0.10-0.15 m), tab. 19 (REW/TEW per tessitura), esempio di suolo nudo (Kcb 0.15, Kc max 1.20).
   - Cap. 8 (stress idrico): https://www.fao.org/4/x0490e/x0490e0e.htm — letti tab. 22 (Zr e p, note 1 e 2) e tab. 24 (Ky stagionali di FAO-33).
   - Cap. 11 (periodi senza coltura): https://www.fao.org/4/x0490e/x0490e0h.htm — letto il paragrafo Bare soil (Kc = Kc ini) e la nota sul Kc ≈ 0.4 del frumento invernale su suolo gelato.
   - Limiti: le fig. 29-30 (Kc ini in funzione dell'intervallo tra le bagnature) sono immagini; non ne sono stati letti valori numerici.

2. **Doorenbos J., Kassam A.H. (1979). Yield response to water. FAO Irrigation and Drainage Paper 33.** Non aperto: i Ky sono letti nella tab. 24 di FAO-56, che li riporta.

3. **Raes D., Steduto P., Hsiao T.C., Fereres E. (2026). AquaCrop Reference Manual, Annex I — Crop parameters, Version 7.3 (luglio 2026). FAO, Roma.**
   https://www.fao.org/docs/devbuildingforwardbetterlibraries/default-document-library/annexesaquacropv73.pdf — lette le schede I.2 Maize, I.6 Soybean, I.10 Wheat (Tbase, Tupper, GDD a emergenza, fioritura, inizio senescenza, maturità, Zn, Zx, HIo, note sulla taratura del frumento invernale e sull'umidità della resa).
   Riletta il 2026-11-12 per `gdd_emergenza` ("Time from sowing to emergence", sezione 1.2 di ogni scheda): mais 60–100, soia 150–300, frumento 100–250 GDD. Valori adottati: mais 100 (massimo, come la componente di emergenza di `gdd_maturita` = 100 + 1850); soia 190 e frumento 175 (derivati, stessa posizione relativa di `gdd_maturita` nel suo intervallo AquaCrop, come `gdd_fioritura`).
   Confronto con la v7.1 (agosto 2023), https://www.fao.org/3/BR244E/br244e.pdf: stesse righe identiche per Tbase, Tupper, ciclo, fioritura, senescenza, HIo.

4. **Raes D. et al. (2026). AquaCrop Reference Manual, Chapter 3 — Calculation procedures, Version 7.3.**
   https://www.fao.org/docs/devbuildingforwardbetterlibraries/default-document-library/chapter3aquacropv73.pdf — letto il par. 3.3 Growing Degree Days (metodi 1, 2, 3). Il motore usa il metodo 1. Il Chapter 2 v7.3 (chapter2aquacropv73_compresso.pdf) indica "Method 3" come metodo predefinito del programma.
   - Limite: la variante "chapter3aquacropv73_compresso.pdf" restituisce una pagina HTML, non il PDF.

5. **Steduto P., Hsiao T.C., Fereres E., Raes D. (2012). Crop yield response to water. FAO Irrigation and Drainage Paper 66. Sez. 3.4 Herbaceous crops.**
   https://fao.org/4/i2800e/i2800e07.pdf — letti i capitoli Wheat (Tbase 0 / Tupper 26 in AquaCrop, crescita misurabile da ~5 °C, dormienza sotto 5 °C, tab. 1 durate in giorni, Italia S-maturità 100-213 gg), Maize (Tbase 8 / Tupper 30, HI ≈ 0.50), Soybean (durata del ciclo 70-140 gg, ruolo del fotoperiodo).

## Enti pubblici italiani

6. **Regione Lombardia (2026). Disciplinari di produzione integrata 2026, Norme tecniche agronomiche, All. 3 Colture erbacee (D.d.s. n. 3864 del 25/3/2026).**
   https://www.fitosanitario.regione.lombardia.it/wps/wcm/connect/3e3f7971-e8cc-4d7a-a72f-b20298107b5b/All++3_Colture+Erbacee_2026.pdf?MOD=AJPERES — lette le schede di concimazione 3.8 Frumento tenero (produzione normale 5-7 t/ha), 3.13 Mais da granella alta produzione (10-14 t/ha), 3.18 Soia (2,8-4,2 t/ha).
   Parte generale: https://www.fitosanitario.regione.lombardia.it/wps/wcm/connect/5ad93ff9-f46f-45fb-89d7-b0c0524e1f6c/Tecniche+agronomiche+2026+PARTE+GENERALE.pdf?MOD=AJPERES — letto il cap. 14 Irrigazione (nessuna indicazione per coltura).
   - Limite: le schede lombarde 2026 non indicano date di semina né classi FAO; l'umidità di riferimento delle rese non è dichiarata.

7. **Regione Emilia-Romagna (2022). Disciplinari di produzione integrata 2022, Norme tecniche di coltura, Colture erbacee.**
   https://agricoltura.regione.emilia-romagna.it/produzioni-agroalimentari/agricoltura-sostenibile/agricoltura-integrata/Collezione-dpi/dpi_2022/norme/erbacee.pdf/@@download/file — letti la scheda Mais (Irrigazione, Allegato Classi di precocità: aprile FAO 600 sabbiosi / 500 argillosi), la scheda Frumento tenero e duro ("Di norma non è ammessa l'irrigazione").
   - Limiti: la raccolta 2022 non contiene una scheda della soia e non dà date di semina; la versione 2023 della scheda frumento (URL `.../dpi_2023/norme/erbacee/norme-tecniche-frumento-tenero-e-duro-2023.pdf`) restituisce HTML, non il PDF.

## Articoli peer-reviewed e atti

8. **Capo L., Sopegno A., Reyneri A., Ujvári G., Agnolucci M., Blandino M. (2023). Agronomic strategies to enhance the early vigor and yield of maize part II: the role of seed applied biostimulant, hybrid, and starter fertilization on crop performance. Frontiers in Plant Science 14, doi:10.3389/fpls.2023.1240313.**
   https://www.frontiersin.org/journals/plant-science/articles/10.3389/fpls.2023.1240313/full — letti tab. 2 (semine, GDD base 10 semina-raccolta) e tab. 7 (rese al 14%). Limite: letti i primi 100 000 caratteri della pagina.

9. **Danuso F., Patat I., Signor M., Valdevit F., Ceccon P., Baldini M. (2017). Analysis of grain yield in thirty years of soybean cultivation in North-East Italy. Atti XX Convegno AIAM e XLVI Convegno SIA, Milano, doi:10.6092/unibo/amsacta/5692.**
   https://air.uniud.it/retrieve/e27ce0c5-8164-055e-e053-6605fe0a7873/SIA2017.pdf — letti Materials and methods (date di semina 24/4-12/6, per lo più maggio; raccolte per lo più in ottobre; irrigazione di soccorso 2-3 volte; gruppi 0+-I+; rese al 13%). Limite: le rese assolute sono solo in figura.

## Altro (dichiarato, non ufficiale)

10. **Mazzoleni M. (2020). Tecniche di coltivazione del Grano Lombardo, campagna cerealicola 2020-2021. Filiera "Il pane lombardo per la qualità della vita".**
    https://quivicino.genuineway.io/wp-content/uploads/2021/10/tecniche_GRANO_LOMBARDO_2020-21-.pdf — letta la sezione Epoca di semina (non prima del 15/10 o 20/10 secondo la varietà; consigliato fine ottobre - inizio novembre) e la produzione media 50-60 q/ha. Disciplinare di filiera privato: usato solo per la data di semina del frumento, in mancanza di una fonte pubblica.

## Dati usati solo per conversioni e controlli

11. **NASA POWER, API daily point, T2M, lat 45.2 lon 10.0, 2001-2024 (community AG).** https://power.larc.nasa.gov/api/temporal/daily/point — usata per convertire le durate di tab. 11 in gradi-giorno, applicare le regole di semina di FAO-56 e stimare le durate dei cicli. Copia temporanea solo nello scratchpad (non in `data/`).

12. **FAO/IIASA GAEZ v4, Theme 5 "Actual yields and yield gaps" (res05), 1981-2010, CRUTS32 storico, input alto, con fertilizzazione da CO2, cella da 5 minuti d'arco (circa 9 km).** Variabili "Average attainable yield of current cropland" (ycH*) e "of best occurring suitability class in grid cell" (yxH*), mais (`mze`), soia (`soy`), frumento (`whe`); raster `https://s3.eu-west-1.amazonaws.com/data.gaezdev.aws.fao.org/res05/CRUTS32/Hist/8110H/<variabile>_<coltura>.tif`, valori letti dal servizio https://gaez-services.fao.org/server/rest/services/res05/ImageServer il 2026-11-14 per le due celle a cavallo del punto pilota (45,2; 10,0). Conversione da peso secco (kg DW/ha) a peso alla raccolta con i fattori della tab. 9-1, p. 142 di Fischer G. et al. (2021), *Global Agro-Ecological Zones v4 – Model documentation*, FAO e IIASA, Roma, doi:10.4060/cb4744en (frumento 0,87, mais 0,86, soia 0,90). **Usata solo come riscontro indipendente delle `resa_potenziale`, mai come origine di un valore**: nessun `valore`, `intervallo` o stato (`verificato`, `assunzione`) di `crops.yaml` è cambiato; il confronto sta nel campo `nota`. Esito: mais 16,2-16,3 t/ha (irriguo a pioggia) contro 15,8, coerente; soia in asciutto 4,28-4,42 t/ha (4,43-4,57 al 13%) contro 4,5, coerente e dentro l'intervallo ISTAT (a sostegno), soia irrigua 6,7 fuori scala rispetto a ISTAT (massimo 4,8); frumento 11,9-12,1 contro un massimo ISTAT di 7,5, **non usato** (GAEZ non è coerente con le rese provinciali: modello a 9 km, input alto, clima 1981-2010). Dati e tabella: `data/processed/esperimenti/gaez_rese.csv`, `prova_f_tabella.csv`; metodo e giudizio: `reports/esperimenti_dati_nuovi.md`, sez. F. Non letti qui: le mappe di idoneità, né il resto della documentazione oltre alla tab. 9-1.

13. **NASA/JPL ECOSTRESS Collection 2, ECO_L3T_JET.002 (ET giornaliera, 70 m), via AppEEARS (LP DAAC), 2018-07-01 → 2022-12-31, 31 punti sui seminativi del Cremonese.** Usata **solo per verificare l'evapotraspirazione simulata**, mai come input del modello (`fieldwise.data.ecostress`, `fieldwise.validation.validate_ecostress`, `reports/validation.md` sez. E). Unità di `ETdaily`: mm/giorno, da Halverson G., *ECOSTRESS Collection 2 Level-1-2-3-4 Gridded and Tiled Data Products User Guide*, versione 2 (4 aprile 2023), LP DAAC, par. 5.4, p. 16 ("upscaled to a daily ET estimate in millimeters per day"; "integrated ET between sunrise and sunset"); la tabella 10 della stessa guida e il catalogo .002 raggruppano invece `ETdaily` sotto W m⁻²: la documentazione è incoerente, vale il testo (valori 0-5,8 con ciclo stagionale). ETdaily è la mediana di quattro modelli (par. 5.4), non una misura. Non letto in questa sessione: l'errore dichiarato in letteratura (ordine di 1,5 mm/giorno sui valori giornalieri) e la descrizione dei quattro modelli oltre al par. 5.4.

## Fonti cercate ma non leggibili

- Rotundo et al. (2024), Sci. Rep. 14, "European soybean to benefit people and the environment" (testo completo da Europe PMC): nessun valore specifico per il Nord Italia.
- Articoli Terra e Vita / Il Contoterzista / Edagricole sulle reti varietali di soia e frumento: il download restituisce HTML (bloccato).
- core.ac.uk (Danuso et al.) e ScienceDirect S1161030126001966 (mais nel Nord Italia): HTTP 403.
- Schede della Provincia di Vicenza (soia, frumento, mais): HTTP 404.

## Aggiornamento 2026-11-12 – doppio coefficiente nel motore

**Allen et al. (1998), FAO-56 cap. 7**, https://www.fao.org/4/x0490e/x0490e0c.htm, riletto per il metodo a doppio
coefficiente (eq. 69, 71, 72, 74, 75, 76, 77-78): "Kc min the minimum Kc for dry bare soil with no ground cover
[≈ 0.15 - 0.20]", "Kc min ordinarily has the same value as the Kcb ini used for annual crops", es. 32 con
Kc min = 0,15 → `suolo_nudo.kc_min`; Kr con De,i-1 (eq. 74); h dell'eq. 72 = "mean maximum plant height during the
period of calculation". `suolo_nudo.kcb_suolo_nudo` (0,15) ora è usato dal motore.
La legge di crescita dell'altezza (lineare fino a fine sviluppo) e l'altezza della segale da cover
(`cover_crop.acqua.altezza`, 0,3 m) sono assunzioni dichiarate.

## Aggiornamento 2026-11-14 – GAEZ come riscontro, ECOSTRESS come verifica

- Fonti 12 (GAEZ v4) e 13 (ECOSTRESS ET) aggiunte sopra. Nessun parametro di `params/crops.yaml` è cambiato di valore: le tre `resa_potenziale` (mais 15,8, soia 4,5, frumento 8,0) hanno solo una `nota` più lunga con il confronto GAEZ.
- Il mais resta una voce `verificato: true` (prove sperimentali di Capo et al. 2023, fonte 8); soia e frumento restano assunzioni. GAEZ non è mai citato come origine: per la soia coincide col valore scelto (asciutto) ed è dentro l'intervallo ISTAT, ma 4,5 era stato scelto prima e col disciplinare lombardo.
- Per il frumento GAEZ non è usato nemmeno come estremo alto dell'intervallo di sensibilità (11,9-12,1 contro un massimo ISTAT di 7,5).
- Modifica di `crops.yaml` => cambiano l'impronta dei parametri (`hash_parametri`) e il `sha256` di `crops.yaml` in `ensemble_meta.json`: un ensemble calcolato prima di questa modifica ha impronte diverse (stessi valori numerici).
