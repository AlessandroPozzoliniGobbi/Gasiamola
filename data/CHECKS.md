# Controlli di qualita' dei dati

<!-- qc:auto:start -->

## Controlli automatici di qualita' dei dati

Eseguito il 2026-11-12 23:17 con `python -m fieldwise.qc --lat 45.2 --lon 10`. 42 controlli: 31 OK, 11 ATTENZIONE, 0 ERRORE, 0 NON DISPONIBILE. Questa parte e' rigenerata a ogni esecuzione: non modificarla a mano (le decisioni vanno nella sezione Decisioni, in fondo al file).

### Esiti

| Dataset | Controllo | Esito | Dettaglio |
|---|---|---|---|
| POWER | Completezza giornaliera | OK | 9497 righe su 9497 attese (2000-01-01..2025-12-31); giorni mancanti 0; duplicati 0; fuori periodo 0; buco piu' lungo 0 giorni |
| POWER | Valori mancanti | OK | nessun NaN in nessuna variabile |
| POWER | Sentinelle | OK | nessun valore <= -900 su 66479 letture |
| POWER | Intervallo tmax | OK | tmax: min -3.73, max 40.92 degC; attesi [-30, 50]; fuori: 0 |
| POWER | Intervallo tmin | OK | tmin: min -10.04, max 26.53 degC; attesi [-40, 40]; fuori: 0 |
| POWER | Intervallo pioggia | ATTENZIONE | rain: min 0.00, max 261.53 mm/g; attesi [0, 300]; fuori: 0; 5 giorni piu' piovosi: 2024-05-18 261.5, 2024-06-21 165.3, 2024-01-02 144.9, 2025-11-02 122.0, 2025-12-01 74.7 (ATTENZIONE oltre 150 mm) |
| POWER | Intervallo radiazione | OK | srad: min 0.59, max 31.25 MJ/m2/g; attesi [0, 35]; fuori: 0 |
| POWER | Radiazione / cielo sereno | OK | Rs/Rso: max 1.017 il 2006-11-02, mediana 0.715; oltre 1.1: 0 giorni (Rso a quota 170.78 m, FAO-56 eq. 37) |
| POWER | Intervallo umidita' | OK | rh: min 27.61, max 99.98 %; attesi [0, 100]; fuori: 0 |
| POWER | Intervallo vento | OK | wind: min 0.33, max 6.24 m/s; attesi [0, 20]; fuori: 0 |
| POWER | Coerenza tmin <= tmean <= tmax | OK | 0 giorni incoerenti (tolleranza 0.05 degC): tmin > tmean 0, tmean > tmax 0, tmin > tmax 0 |
| ARPA pioggia | Completezza per anno | ATTENZIONE | giorni completi per anno: min 75% (2003), media 94%, 9497 giorni, 8974 completi; anni sotto 90%: 2002 90%, 2003 75%, 2004 81%, 2008 89%, 2010 80%, 2016 84% |
| POWER vs ARPA pioggia | Pioggia annua | ATTENZIONE | 24 anni confrontabili (>= 80% giorni completi), 2 non confrontabili; scarto relativo (POWER-ARPA)/ARPA sui giorni comuni: mediano +2.0%, min -18.1%, max +68.2%; anni oltre +-25%: 2004 +34%, 2023 +33%, 2024 +37%, 2025 +68%; non confrontabili: 2003 (75.1%), 2010 (79.7%) |
| POWER vs ARPA pioggia | Correlazione dei totali mensili | OK | r di Pearson tra totali mensili POWER e ARPA = 0.769 su 271 mesi (anni confrontabili, mesi con >= 80% di giorni completi); informativo, nessuna soglia |
| POWER vs ARPA pioggia | Giorni piovosi (>= 1 mm) | OK | frequenza media POWER 31.0% contro ARPA 21.2% dei giorni comuni (differenza +9.9 punti); per anno nella tabella; informativo |
| POWER vs ARPA pioggia | Rapporto annuo nel tempo | ATTENZIONE | rapporto POWER/ARPA medio: fino al 2022 1.02 (21 anni), dopo 1.46 (3 anni); variazione +43% (ATTENZIONE oltre +-25%) |
| IMERG | Completezza giornaliera | OK | 9253 giorni con valore su 9253 attesi (2000-06-01..2025-09-30); mancanti 0 |
| IMERG | Intervallo valori | OK | min 0.00, max 88.89 mm/g; attesi [0, 400]; fuori: 0 |
| IMERG | Ultimo giorno disponibile | ATTENZIONE | ultimo giorno 2025-09-30 (fine periodo meteo 2025-12-31) |
| POWER vs IMERG | Pioggia annua | ATTENZIONE | 24 anni confrontabili (>= 80% giorni completi), 2 non confrontabili; scarto relativo (POWER-IMERG)/IMERG sui giorni comuni: mediano -16.5%, min -28.7%, max +23.1%; anni oltre +-25%: 2016 -28%, 2017 -26%, 2023 -29%; non confrontabili: 2000 (58.5%), 2025 (74.8%) |
| POWER vs IMERG | Correlazione dei totali mensili | OK | r di Pearson tra totali mensili POWER e IMERG = 0.865 su 288 mesi (anni confrontabili, mesi con >= 80% di giorni completi); informativo, nessuna soglia |
| POWER vs IMERG | Giorni piovosi (>= 1 mm) | OK | frequenza media POWER 30.4% contro IMERG 25.9% dei giorni comuni (differenza +4.6 punti); per anno nella tabella; informativo |
| POWER vs IMERG | Rapporto annuo nel tempo | OK | rapporto POWER/IMERG medio: fino al 2022 0.84 (22 anni), dopo 0.97 (2 anni); variazione +16% (ATTENZIONE oltre +-25%) |
| POWER ET0 | Penman-Monteith vs Hargreaves | OK | totali annui medi su 26 anni: Penman-Monteith 887 mm, Hargreaves 1036 mm; rapporto medio HG/PM 1.170 (annuo min 1.122, max 1.219); correlazione giornaliera 0.975; mese con lo scarto maggiore: dicembre (+65%, +7.0 mm); nessun anno con rapporto fuori [0.85, 1.30] |
| ARPA temperature | Completezza per anno | ATTENZIONE | giorni completi per anno: min 72% (2010), media 94%, 9497 giorni, 8971 completi; anni sotto 90%: 2002 85%, 2003 75%, 2004 89%, 2008 89%, 2010 72%, 2016 84% |
| POWER vs ARPA temperature | Differenza tmax/tmin | ATTENZIONE | POWER - ARPA su 8971 giorni completi: tmax -0.79 degC, tmin +0.70 degC (anno); giugno-agosto (2254 giorni): tmax -1.32, tmin +1.18 degC (ATTENZIONE se /tmax estiva/ > 1) |
| POWER vs ARPA temperature | Giorni con tmax > 35 degC | OK | giorni con tmax > 35 degC nei giorni comuni: POWER 320, ARPA 465; per anno nella tabella; informativo |
| MODIS NDVI | Date per anno | OK | 26 anni su 26 con le date attese (23; 20 nel 2000); nessun anno con meno di 20 date |
| MODIS NDVI | Intervallo NDVI | OK | 1767 valori NDVI (centro e finestra): min -0.035, max 0.889; attesi [-0.2, 1]; fuori: 0 |
| MODIS NDVI | Pixel centrale buono/marginale | OK | 95.0% delle 595 date ha il pixel centrale buono o marginale (affidabilita' 0/1); informativo |
| MODIS NDVI | Finestra con almeno meta' pixel buoni | OK | 95.8% delle date ha almeno il 50% dei pixel della finestra buoni; informativo |
| MODIS NDVI | Date utilizzabili in estate | OK | date estive (giugno-agosto) con pixel centrale utilizzabile: min 83%, media 99% su 26 anni; nessun anno sotto 60% |
| MODIS NDVI | NDVI medio luglio-agosto | OK | media di luglio-agosto (finestra) su 26 anni: min 0.601 (2003), max 0.763 (2014); per anno nella tabella |
| SoilGrids | Sabbia + argilla + limo | OK | somma per strato: 0-30cm 100.02%, 30-100cm 100.00%, 100-200cm 99.90%; attesa 100 +-2; fuori: 0 |
| SoilGrids | Densita' apparente | OK | media per strato: 0-30cm 1.43, 30-100cm 1.51, 100-200cm 1.53 g/cm3; attesa [1, 1.8]; fuori: 0 |
| SoilGrids | Sostanza organica 0-30 cm | ATTENZIONE | media 3.56%, intervallo q05-q95 0.99-8.31%; ATTENZIONE oltre 3% (valore alto per un seminativo di pianura) |
| ISTAT | Anni presenti per coltura | OK | mais 2006-2026 (21 anni); soia 2006-2026 (21 anni); frumento 2006-2026 (21 anni) |
| ISTAT | Rese in intervalli plausibili | OK | tutte le rese in intervallo (t/ha: mais 5-16; soia 1.5-6; frumento 3-9) |
| ISTAT | Anni successivi all'ultimo anno di meteo | ATTENZIONE | anni oltre l'ultimo anno di meteo (2025) da escludere dalla validazione (stime provvisorie): frumento 2026, mais 2026, soia 2026 |
| ISTAT | Salti annui > 30% | ATTENZIONE | 6 variazioni oltre +-30% rispetto all'anno precedente: frumento 2013 -38.5%, frumento 2014 +37.5%, frumento 2016 +30.0%, mais 2016 +47.4%, mais 2023 +36.8%, soia 2020 +50.0% |
| SMAP | Giorni con passaggio di qualita' raccomandata | OK | 2323 giorni su 3845 (60.4%) con almeno un passaggio con flag [0, 8]; informativo |
| SMAP | Intervallo valori | OK | 3620 valori di qualita' raccomandata: min 0.038, max 0.468 m3/m3; attesi [0.02, 0.6]; fuori: 0 |

### Pioggia annua: POWER contro riferimento

Totali `*_mm` sull'anno intero; colonne `*_common_mm`, scarto e rapporto ricalcolati solo sui giorni in cui il riferimento e' completo (ARPA `complete`) o presente (IMERG). Scarto = (POWER - rif) / rif. Anno confrontabile solo con almeno 80% di giorni completi.

| reference | year | power_total_mm | ref_total_mm | ref_complete_pct | power_common_mm | ref_common_mm | n_common_days | rel_diff | ratio | wet_freq_power_pct | wet_freq_ref_pct | esito |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ARPA | 2000 | 967 | 775 | 94.5 | 955 | 773 | 346 | +23.5% | 1.23 | 32.9 | 20.5 | OK |
| ARPA | 2001 | 793 | 661 | 98.1 | 774 | 658 | 358 | +17.6% | 1.18 | 32.1 | 19.8 | OK |
| ARPA | 2002 | 1099 | 949 | 89.6 | 947 | 943 | 327 | +0.5% | 1.00 | 33.6 | 24.2 | OK |
| ARPA | 2003 | 587 | 436 | 75.1 | 480 | 435 | 274 | +10.4% | 1.10 | 27.0 | 17.9 | non confrontabile |
| ARPA | 2004 | 795 | 511 | 81.1 | 670 | 500 | 297 | +34.1% | 1.34 | 32.7 | 21.9 | ATTENZIONE |
| ARPA | 2005 | 702 | 809 | 94.5 | 676 | 779 | 345 | -13.1% | 0.87 | 28.1 | 21.2 | OK |
| ARPA | 2006 | 618 | 519 | 98.4 | 599 | 515 | 359 | +16.3% | 1.16 | 29.0 | 18.9 | OK |
| ARPA | 2007 | 654 | 637 | 96.7 | 625 | 612 | 353 | +2.1% | 1.02 | 21.5 | 14.4 | OK |
| ARPA | 2008 | 904 | 875 | 88.5 | 837 | 861 | 324 | -2.8% | 0.97 | 35.8 | 21.6 | OK |
| ARPA | 2009 | 862 | 1004 | 94.5 | 812 | 984 | 345 | -17.5% | 0.82 | 32.5 | 23.5 | OK |
| ARPA | 2010 | 1123 | 1362 | 79.7 | 956 | 1352 | 291 | -29.3% | 0.71 | 35.1 | 30.9 | non confrontabile |
| ARPA | 2011 | 661 | 618 | 97.5 | 643 | 567 | 356 | +13.5% | 1.13 | 25.3 | 17.1 | OK |
| ARPA | 2012 | 749 | 709 | 90.4 | 719 | 709 | 331 | +1.3% | 1.01 | 27.2 | 20.2 | OK |
| ARPA | 2013 | 944 | 1121 | 100.0 | 944 | 1121 | 365 | -15.8% | 0.84 | 37.3 | 27.9 | OK |
| ARPA | 2014 | 1110 | 1143 | 99.7 | 1110 | 1143 | 364 | -3.0% | 0.97 | 44.2 | 31.6 | OK |
| ARPA | 2015 | 586 | 700 | 98.4 | 566 | 692 | 359 | -18.1% | 0.82 | 22.8 | 17.3 | OK |
| ARPA | 2016 | 724 | 526 | 84.2 | 578 | 485 | 308 | +19.1% | 1.19 | 31.8 | 18.8 | OK |
| ARPA | 2017 | 526 | 517 | 100.0 | 526 | 517 | 365 | +1.8% | 1.02 | 24.7 | 15.9 | OK |
| ARPA | 2018 | 810 | 969 | 100.0 | 810 | 969 | 365 | -16.4% | 0.84 | 35.3 | 24.9 | OK |
| ARPA | 2019 | 931 | 884 | 100.0 | 931 | 884 | 365 | +5.3% | 1.05 | 31.5 | 24.4 | OK |
| ARPA | 2020 | 784 | 802 | 100.0 | 784 | 802 | 366 | -2.2% | 0.98 | 29.2 | 21.6 | OK |
| ARPA | 2021 | 682 | 640 | 100.0 | 682 | 640 | 365 | +6.6% | 1.07 | 24.7 | 19.2 | OK |
| ARPA | 2022 | 529 | 572 | 100.0 | 529 | 572 | 365 | -7.6% | 0.92 | 26.3 | 15.6 | OK |
| ARPA | 2023 | 660 | 496 | 100.0 | 660 | 496 | 365 | +33.1% | 1.33 | 31.8 | 19.2 | ATTENZIONE |
| ARPA | 2024 | 1719 | 1241 | 96.2 | 1704 | 1241 | 352 | +37.3% | 1.37 | 36.1 | 25.6 | ATTENZIONE |
| ARPA | 2025 | 1487 | 884 | 99.7 | 1485 | 883 | 364 | +68.2% | 1.68 | 38.7 | 22.8 | ATTENZIONE |
| IMERG | 2000 | 967 | 890 | 58.5 | 742 | 890 | 214 | -16.6% | 0.83 | 36.4 | 39.3 | non confrontabile |
| IMERG | 2001 | 793 | 891 | 100.0 | 793 | 891 | 365 | -11.1% | 0.89 | 32.1 | 29.0 | OK |
| IMERG | 2002 | 1099 | 1233 | 100.0 | 1099 | 1233 | 365 | -10.9% | 0.89 | 34.8 | 33.7 | OK |
| IMERG | 2003 | 587 | 655 | 100.0 | 587 | 655 | 365 | -10.4% | 0.90 | 24.9 | 21.6 | OK |
| IMERG | 2004 | 795 | 790 | 100.0 | 795 | 790 | 366 | +0.6% | 1.01 | 31.7 | 26.5 | OK |
| IMERG | 2005 | 702 | 761 | 100.0 | 702 | 761 | 365 | -7.8% | 0.92 | 27.4 | 24.7 | OK |
| IMERG | 2006 | 618 | 659 | 100.0 | 618 | 659 | 365 | -6.3% | 0.94 | 29.0 | 21.6 | OK |
| IMERG | 2007 | 654 | 762 | 100.0 | 654 | 762 | 365 | -14.2% | 0.86 | 21.6 | 22.5 | OK |
| IMERG | 2008 | 904 | 1022 | 100.0 | 904 | 1022 | 366 | -11.6% | 0.88 | 35.0 | 32.0 | OK |
| IMERG | 2009 | 862 | 1004 | 100.0 | 862 | 1004 | 365 | -14.2% | 0.86 | 32.1 | 25.8 | OK |
| IMERG | 2010 | 1123 | 1338 | 100.0 | 1123 | 1338 | 365 | -16.0% | 0.84 | 34.0 | 32.6 | OK |
| IMERG | 2011 | 661 | 829 | 100.0 | 661 | 829 | 365 | -20.3% | 0.80 | 25.2 | 23.0 | OK |
| IMERG | 2012 | 749 | 921 | 100.0 | 749 | 921 | 366 | -18.7% | 0.81 | 26.0 | 25.1 | OK |
| IMERG | 2013 | 944 | 1138 | 100.0 | 944 | 1138 | 365 | -17.0% | 0.83 | 37.3 | 30.4 | OK |
| IMERG | 2014 | 1110 | 1365 | 100.0 | 1110 | 1365 | 365 | -18.7% | 0.81 | 44.1 | 36.7 | OK |
| IMERG | 2015 | 586 | 770 | 100.0 | 586 | 770 | 365 | -24.0% | 0.76 | 23.6 | 20.5 | OK |
| IMERG | 2016 | 724 | 1003 | 100.0 | 724 | 1003 | 366 | -27.8% | 0.72 | 32.5 | 23.2 | ATTENZIONE |
| IMERG | 2017 | 526 | 710 | 100.0 | 526 | 710 | 365 | -25.9% | 0.74 | 24.7 | 18.1 | ATTENZIONE |
| IMERG | 2018 | 810 | 1006 | 100.0 | 810 | 1006 | 365 | -19.5% | 0.81 | 35.3 | 27.7 | OK |
| IMERG | 2019 | 931 | 1099 | 100.0 | 931 | 1099 | 365 | -15.3% | 0.85 | 31.5 | 25.8 | OK |
| IMERG | 2020 | 784 | 1017 | 100.0 | 784 | 1017 | 366 | -22.9% | 0.77 | 29.2 | 24.0 | OK |
| IMERG | 2021 | 682 | 885 | 100.0 | 682 | 885 | 365 | -22.9% | 0.77 | 24.7 | 23.0 | OK |
| IMERG | 2022 | 529 | 663 | 100.0 | 529 | 663 | 365 | -20.2% | 0.80 | 26.3 | 18.9 | OK |
| IMERG | 2023 | 660 | 927 | 100.0 | 660 | 927 | 365 | -28.7% | 0.71 | 31.8 | 23.0 | ATTENZIONE |
| IMERG | 2024 | 1719 | 1397 | 100.0 | 1719 | 1397 | 366 | +23.1% | 1.23 | 35.8 | 31.7 | OK |
| IMERG | 2025 | 1487 | 970 | 74.8 | 879 | 970 | 273 | -9.4% | 0.91 | 39.9 | 30.4 | non confrontabile |

### ET0: Penman-Monteith contro Hargreaves

_lat 45.2, quota 170.78 m (cella POWER), G = 0, ea da UR media (FAO-56 eq. 19)_

Totali annui (mm) sui giorni con entrambi i metodi.

| year | n_days | et0_pm | et0_hargreaves | ratio |
|---|---|---|---|---|
| 2000 | 366 | 859 | 1035 | 1.204 |
| 2001 | 365 | 852 | 1013 | 1.189 |
| 2002 | 365 | 826 | 975 | 1.181 |
| 2003 | 365 | 969 | 1088 | 1.122 |
| 2004 | 366 | 843 | 1005 | 1.193 |
| 2005 | 365 | 854 | 1012 | 1.184 |
| 2006 | 365 | 879 | 1041 | 1.184 |
| 2007 | 365 | 941 | 1079 | 1.146 |
| 2008 | 366 | 857 | 1009 | 1.177 |
| 2009 | 365 | 901 | 1030 | 1.142 |
| 2010 | 365 | 815 | 955 | 1.173 |
| 2011 | 365 | 899 | 1034 | 1.150 |
| 2012 | 366 | 966 | 1103 | 1.142 |
| 2013 | 365 | 814 | 974 | 1.197 |
| 2014 | 365 | 805 | 976 | 1.212 |
| 2015 | 365 | 902 | 1056 | 1.170 |
| 2016 | 366 | 888 | 1042 | 1.173 |
| 2017 | 365 | 1003 | 1145 | 1.142 |
| 2018 | 365 | 874 | 1014 | 1.160 |
| 2019 | 365 | 909 | 1067 | 1.174 |
| 2020 | 366 | 900 | 1043 | 1.158 |
| 2021 | 365 | 913 | 1056 | 1.157 |
| 2022 | 365 | 1006 | 1130 | 1.123 |
| 2023 | 365 | 948 | 1088 | 1.148 |
| 2024 | 366 | 797 | 971 | 1.219 |
| 2025 | 365 | 848 | 1009 | 1.190 |

Medie mensili climatologiche (mm/mese).

| month | mese | et0_pm | et0_hargreaves | diff_mm | rel_diff |
|---|---|---|---|---|---|
| 1 | gennaio | 14.0 | 20.6 | +6.7 | +47.6% |
| 2 | febbraio | 24.1 | 31.7 | +7.6 | +31.5% |
| 3 | marzo | 52.0 | 63.2 | +11.2 | +21.6% |
| 4 | aprile | 76.9 | 93.3 | +16.5 | +21.4% |
| 5 | maggio | 110.7 | 130.9 | +20.1 | +18.2% |
| 6 | giugno | 142.9 | 159.9 | +17.0 | +11.9% |
| 7 | luglio | 164.0 | 178.6 | +14.6 | +8.9% |
| 8 | agosto | 140.4 | 154.2 | +13.8 | +9.8% |
| 9 | settembre | 87.4 | 99.3 | +11.9 | +13.7% |
| 10 | ottobre | 45.4 | 58.7 | +13.3 | +29.3% |
| 11 | novembre | 18.8 | 28.2 | +9.5 | +50.4% |
| 12 | dicembre | 10.8 | 17.9 | +7.0 | +65.1% |

### Temperature: POWER contro ARPA

Differenze medie POWER - ARPA (degC) sui giorni ARPA completi; `jja` = giugno-agosto; giorni con tmax > 35 degC contati sugli stessi giorni.

| year | n_days | d_tmax | d_tmin | d_tmax_jja | d_tmin_jja | n_jja | hot_days_power | hot_days_arpa |
|---|---|---|---|---|---|---|---|---|
| 2000 | 331 | +0.72 | +0.96 | +0.54 | +1.54 | 86 | 6 | 1 |
| 2001 | 336 | +0.61 | +0.90 | +0.50 | +1.69 | 92 | 9 | 0 |
| 2002 | 310 | +0.50 | +1.09 | +0.14 | +1.17 | 46 | 4 | 2 |
| 2003 | 272 | +1.06 | +1.63 | +1.04 | +2.46 | 91 | 32 | 15 |
| 2004 | 324 | -0.20 | +1.21 | -0.92 | +1.64 | 92 | 2 | 2 |
| 2005 | 345 | -0.98 | +1.05 | +0.22 | +2.06 | 89 | 9 | 7 |
| 2006 | 363 | -1.27 | +1.12 | -1.80 | +1.78 | 90 | 14 | 23 |
| 2007 | 353 | -1.21 | +1.37 | -1.88 | +1.87 | 89 | 9 | 23 |
| 2008 | 324 | -1.55 | +0.72 | -2.92 | +1.18 | 68 | 0 | 20 |
| 2009 | 345 | -1.63 | +0.90 | -2.87 | +1.79 | 87 | 11 | 31 |
| 2010 | 262 | -1.98 | +0.01 | -4.46 | -0.10 | 48 | 4 | 18 |
| 2011 | 363 | -1.11 | +0.76 | -1.54 | +1.01 | 92 | 10 | 12 |
| 2012 | 366 | -0.31 | +1.23 | -0.50 | +2.10 | 92 | 31 | 32 |
| 2013 | 365 | -0.94 | +0.22 | -3.34 | +0.77 | 92 | 9 | 25 |
| 2014 | 364 | -1.44 | +0.27 | -2.31 | +0.72 | 92 | 0 | 7 |
| 2015 | 360 | -0.94 | +0.91 | -1.37 | +1.23 | 88 | 27 | 32 |
| 2016 | 308 | -0.81 | +0.78 | -1.97 | +0.99 | 92 | 4 | 8 |
| 2017 | 364 | -0.20 | +1.20 | -0.05 | +1.72 | 92 | 25 | 24 |
| 2018 | 365 | -1.50 | +0.26 | -2.43 | +0.96 | 92 | 3 | 29 |
| 2019 | 365 | -1.27 | +0.54 | -2.49 | +0.62 | 92 | 18 | 40 |
| 2020 | 366 | -1.53 | +0.58 | -2.21 | +0.97 | 92 | 9 | 21 |
| 2021 | 362 | -1.24 | +0.21 | -0.91 | +0.62 | 92 | 13 | 15 |
| 2022 | 365 | +0.47 | +1.00 | +1.19 | +1.89 | 92 | 31 | 12 |
| 2023 | 365 | -0.36 | +0.58 | -0.73 | +0.73 | 92 | 23 | 26 |
| 2024 | 366 | -1.16 | -0.37 | -2.13 | -0.32 | 92 | 5 | 13 |
| 2025 | 362 | -1.81 | -0.68 | -2.11 | -0.88 | 92 | 12 | 27 |

### MODIS NDVI per anno

`center_ok` = pixel centrale con affidabilita' 0 o 1; `window_ok` = date con almeno meta' dei pixel della finestra buoni; `summer_usable` = date di giugno-agosto con pixel centrale utilizzabile; NDVI di luglio-agosto = media della finestra (`ndvi_window_mean_good`).

| year | n_dates | expected | ndvi_min | ndvi_max | center_ok_pct | window_ok_pct | ndvi_julaug_mean | summer_usable_pct | esito |
|---|---|---|---|---|---|---|---|---|---|
| 2000 | 20 | 20 | 0.421 | 0.835 | 95 | 95 | 0.689 | 100 | OK |
| 2001 | 23 | 23 | 0.336 | 0.850 | 96 | 100 | 0.708 | 83 | OK |
| 2002 | 23 | 23 | 0.357 | 0.793 | 96 | 96 | 0.706 | 100 | OK |
| 2003 | 23 | 23 | 0.290 | 0.809 | 96 | 96 | 0.601 | 100 | OK |
| 2004 | 23 | 23 | 0.326 | 0.843 | 96 | 96 | 0.726 | 100 | OK |
| 2005 | 23 | 23 | 0.324 | 0.850 | 87 | 91 | 0.741 | 100 | OK |
| 2006 | 23 | 23 | 0.028 | 0.842 | 96 | 91 | 0.712 | 100 | OK |
| 2007 | 23 | 23 | 0.409 | 0.796 | 91 | 91 | 0.652 | 100 | OK |
| 2008 | 23 | 23 | 0.291 | 0.823 | 87 | 91 | 0.688 | 100 | OK |
| 2009 | 23 | 23 | -0.035 | 0.750 | 91 | 91 | 0.687 | 100 | OK |
| 2010 | 23 | 23 | 0.325 | 0.837 | 96 | 96 | 0.710 | 100 | OK |
| 2011 | 23 | 23 | 0.383 | 0.807 | 91 | 91 | 0.697 | 100 | OK |
| 2012 | 23 | 23 | 0.468 | 0.859 | 100 | 100 | 0.644 | 100 | OK |
| 2013 | 23 | 23 | 0.330 | 0.836 | 91 | 96 | 0.753 | 100 | OK |
| 2014 | 23 | 23 | 0.147 | 0.847 | 91 | 87 | 0.763 | 100 | OK |
| 2015 | 23 | 23 | 0.310 | 0.812 | 100 | 100 | 0.644 | 100 | OK |
| 2016 | 23 | 23 | 0.358 | 0.831 | 100 | 100 | 0.682 | 100 | OK |
| 2017 | 23 | 23 | 0.443 | 0.839 | 100 | 100 | 0.677 | 100 | OK |
| 2018 | 23 | 23 | 0.228 | 0.788 | 96 | 96 | 0.687 | 100 | OK |
| 2019 | 23 | 23 | 0.367 | 0.833 | 96 | 100 | 0.688 | 100 | OK |
| 2020 | 23 | 23 | 0.421 | 0.889 | 96 | 96 | 0.701 | 100 | OK |
| 2021 | 23 | 23 | 0.370 | 0.833 | 100 | 100 | 0.670 | 100 | OK |
| 2022 | 23 | 23 | 0.101 | 0.840 | 96 | 96 | 0.609 | 100 | OK |
| 2023 | 23 | 23 | 0.386 | 0.822 | 96 | 100 | 0.654 | 100 | OK |
| 2024 | 23 | 23 | 0.300 | 0.828 | 96 | 96 | 0.665 | 100 | OK |
| 2025 | 23 | 23 | 0.384 | 0.862 | 96 | 100 | 0.688 | 100 | OK |

### ISTAT: rese provinciali

_ultimo anno di meteo: 2025_ (rese calcolate come produzione raccolta / superficie totale). Sintesi per coltura e righe con almeno una segnalazione.

| crop | n_years | first | last | yield_min | yield_max | yield_mean |
|---|---|---|---|---|---|---|
| frumento | 21 | 2006 | 2026 | 4.0 | 7.5 | 6.1 |
| mais | 21 | 2006 | 2026 | 9.5 | 14.0 | 11.6 |
| soia | 21 | 2006 | 2026 | 3.0 | 4.8 | 4.0 |

| crop | year | yield_t_ha | change | segnalazioni |
|---|---|---|---|---|
| frumento | 2013 | 4.00 | -38.5% | salto |
| frumento | 2014 | 5.50 | +37.5% | salto |
| frumento | 2016 | 6.50 | +30.0% | salto |
| frumento | 2026 | 6.80 | -4.2% | provvisorio |
| mais | 2016 | 14.00 | +47.4% | salto |
| mais | 2023 | 13.00 | +36.8% | salto |
| mais | 2026 | 11.80 | +0.0% | provvisorio |
| soia | 2020 | 4.50 | +50.0% | salto |
| soia | 2026 | 3.80 | +0.0% | provvisorio |

<!-- qc:auto:end -->

## Decisioni

Compilate il 2026-11-12. Codice: `src/fieldwise/weather.py` (D1, D2). Script di analisi usa-e-getta, non nel repository.

### D1 — Pioggia del motore e anni 2023–2025

**Decisione.** Pioggia NASA POWER (PRECTOTCORR) senza correzioni; l'ensemble delle annate usa solo il 2000–2022 (`POWER_RAIN_LAST_RELIABLE_YEAR = 2022`). Gli anni 2023–2025 restano nella tabella con `rain_trusted = False` e sono esclusi da `available_years`. L'eccesso di giorni piovosi di POWER non si corregge: si dichiara come limite.

**Motivo.** (a) La sovrastima recente è confermata da altri quattro pluviometri ARPA (richiesta SODA aggregata per mese, solo mesi con almeno 90% di misure valide). Totali annui (mm):

| anno | POWER | Persico D. (4 km) | Casalbuttano (7 km) | Cremona Fatebenefratelli (7 km) | Pieve S. Giacomo (18 km) | Gambara (24 km) | POWER / media rete |
|---|---|---|---|---|---|---|---|
| 2020 | 784 | 802 | 842 | 554 | 713 | 761 | 1,02 |
| 2021 | 682 | 640 | 640 | 406 | 534 | 553 | 1,17 |
| 2022 | 529 | 572 | 478 | 626 | 503 | 418 | 1,02 |
| 2023 | 660 | 496 | 611 | 492 | 569 | 563* | 1,17 |
| 2024 | 1719 | 1241 | 1232 | 1494 | 1110 | 1110 | 1,38 |
| 2025 | 1487 | 884 | 847 | 918 | 842 | 758 | 1,72 |

(* Gambara 2023: 88% di misure valide.) Rapporto POWER/stazione 2019–2022 contro 2023–2025: Casalbuttano 1,03 → 1,41; Cremona 1,09 → 1,32; Pieve 1,14 → 1,53; Gambara 1,31 → 1,59; Persico 1,01 → 1,47. Il salto è comune a tutte le stazioni, quindi è di POWER e non del pluviometro di Persico. Il 2024–2025 è chiaramente anomalo (secondo semestre 2025: rapporto 2,06). Il 2023 contro la rete vale 1,17, come il 2019 e il 2021: è al limite. Lo si esclude lo stesso, perché l'errore non è simmetrico: un anno buono perso toglie 1/24 dei campioni, un anno sbagliato falsa la distribuzione. (b) Documentazione: nella pagina "Data Sources" di POWER (power.larc.nasa.gov/docs/methodology/data/sources/, letta tramite i risultati di ricerca; l'URL diretto risponde 404) si legge che la serie meteo giornaliera è MERRA-2 con GEOS-IT accodato per il quasi tempo reale, che i valori MERRA-2 si aggiornano "every several months" e che i trend vanno chiusi circa due mesi prima del tempo reale. In due ricerche non ho trovato alcun avviso di POWER o di GMAO su un cambio di sorgente o su un problema noto di PRECTOTCORR dal 2023. La correzione di MERRA-2 si basa sull'analisi di pluviometri CPCU: piena sotto 42,5° N e ridotta in modo lineare fino a 62,5° N, quindi a 45,2° N vale circa l'87% (questo da una scheda secondaria, Univ. Toronto NORDATA). La causa del salto resta non documentata. Il file in cache dichiara `sources: MERRA2, SRB, SYN1DEG, POWER`. (c) I vincoli: osservazione NASA applicabile a un campo qualsiasi, demo offline e nessuna correzione non dichiarata.

**Alternative scartate.** POWER con 2023–2025 sostituiti dal pluviometro: si può fare solo dove esiste un pluviometro (non vale per un campo qualsiasi) e mescola nella stessa serie fonti con frequenza e intensità diverse. Resta selezionabile come `rain_source="power_arpa"`, solo per la sensibilità. Pluviometro ovunque con buchi riempiti: non è un'osservazione NASA, ci sono anni incompleti (2003, 2004, 2010, 2016 sotto il 90%) e non è trasferibile. Correzione di scala dichiarata (es. ÷1,46): il fattore varia da stazione a stazione (1,32–1,59) e da semestre a semestre (1,15–2,06), quindi sarebbe una taratura locale e instabile. POWER puro: falsa l'ensemble con due annate (2024, 2025) del 40–70% troppo piovose. Resta selezionabile come `rain_source="power"`.

**Giorni piovosi.** POWER nel 2000–2022 ha 31% di giorni con almeno 1 mm contro 21%; i giorni con 0,1–1 mm sono il 22% contro il 17%, ma portano solo il 4,3% della pioggia. Gli eventi forti sono pochi: 6,7 giorni all'anno con almeno 20 mm contro 10,1, e il 99° percentile dei giorni piovosi è 32 mm contro 57. La correlazione giornaliera è 0,74. È il comportamento tipico di un campo su cella da 50 km. Non si corregge con soglie, che sarebbero arbitrarie. Si dichiara come limite: sovrastima dell'evaporazione dal suolo bagnato e sottostima di ruscellamento e percolazione negli eventi intensi.

**Con IMERG.** Si rifà il confronto con la rete (POWER, IMERG, pluviometri, 2001–2024). Se IMERG non mostra il salto del 2023 e ha uno scarto mediano annuo non peggiore di POWER, diventa la pioggia di default (`rain_source="imerg"`, anni interamente coperti: 2001–2024). L'anno 2025 non è coperto (Final fino al 2025-09-30), quindi resterebbe escluso.

### D2 — Temperature, ET0 e quota

**Decisione.** Per fenologia (GDD da T2M), ET0 Penman-Monteith (Tmax e Tmin, eq. 9) e caldo in fioritura si usano POWER T2M_MAX, T2M_MIN e T2M. L'ET0 si calcola alla quota della cella POWER (`power_site.json`, 171 m), con `elev_m` sovrascrivibile. Le stazioni ARPA Casalbuttano (9031) e Gambara (6823) si possono selezionare solo per la sensibilità (`temp_source="arpa_9031"` o `"arpa_6823"`).

**Motivo.** POWER è l'unica fonte valida ovunque e coerente con radiazione, umidità e vento. Contro le due stazioni coerenti la massima media di giugno–agosto ha scarto −0,3 °C e correlazione 0,74. Gli estremi invece sono deboli: i giorni sopra 35 °C hanno correlazione 0,46 ed errore medio assoluto di 7 giorni. Lo scarto POWER−stazione della Tmax di giugno–luglio va da −3,6 a +1,1 °C a seconda dell'anno (2022: +1,0; 2024: −3,6 e −2,8). Persico Dosimo (2485) è escluso per la discontinuità del 2005–2006, Cremona città per l'effetto urbano. Quota: 45 m contro 171 m cambia l'ET0 dello 0,3% (circa 3 mm/anno). La quota della cella è sempre disponibile ed è coerente con la pressione implicita nei dati POWER, mentre la quota del campo richiederebbe un altro dato. ET0 media 2000–2022: 890 mm/anno.

**Alternative scartate.** Stazioni ARPA come default: non esistono per un campo qualsiasi, partono dal 2005 e hanno buchi e un `n_expected` inaffidabile negli anni con passo di misura misto. Quota del campo: effetto trascurabile, dato non sempre disponibile.

**Con IMERG.** Nessun effetto: IMERG non fornisce temperature.

### D3 — Funzione del caldo in fioritura (mais)

**Esito dell'analisi.** Si è usata la funzione di Deryng così com'è scritta in `heat.yaml` (Teff = (T2M+Tmax)/2, Tcr 32, Tlim 45, finestra 0,45–0,70 della somma termica dalla semina, GDD con t_base 8 e t_upper 30 di `crops.yaml` e la temperatura della stessa fonte). Fattore f_caldo, 2005–2025: con POWER la media è 0,984 e il minimo 0,912 (2015), il 2022 vale 0,942. Con Casalbuttano la media è 0,995 e il 2022 vale 0,991; con Gambara 0,991 e 0,990. Finestra del 2022: 24/6–17/7 con POWER, 22/6–18/7 con Casalbuttano, 24/6–19/7 con Gambara. Tmax media nella finestra: 35,1, 33,3 e 33,6 °C. Il valore 0,94 del 2022 viene quindi dalle temperature POWER: nel giugno–luglio 2022 POWER è più caldo delle stazioni di circa 1 °C, mentre di solito è più freddo. Non dipende dalla finestra: sull'intero giugno–agosto lo stesso indice vale 0,957 con POWER e 0,987 con le stazioni. La funzione stessa è mite per la pianura padana: Teff ≥ 32 richiede una Tmax di circa 35 °C. Alternative di `heat.yaml` con POWER: AquaCrop (Ks_pol,h logistico su Tmax, eq. 3.2c, soglia 40 °C) dà 1,000 in tutti gli anni e con tutte le fonti. Teixeira (35/45) su Teff dà almeno 0,995; su Tmax dà in media 0,967, minimo 0,860 (2015) e 0,889 nel 2022 (stazioni 0,96–0,97). Con Tcr 30, il limite basso dell'intervallo di sensibilità, si ottiene 0,875 nel 2022.

**Finestra: giorni o gradi-giorno.** Fedele alla fonte è la frazione dei giorni tra emergenza e maturità (GPL di Deryng, App. A.3). La frazione dei GDD dalla semina usata in `heat.yaml` è un adattamento. Con l'emergenza a 100 GDD (la componente "emergence" di `gdd_maturita` = 100 + 1850) la versione in giorni cambia f_caldo di +0,001 in media e al massimo di 0,018. Valori con POWER: 2022 0,958, 2015 0,930, 2019 0,956. Con le stazioni 2022 0,99. Il risultato non cambia.

**Raccomandazione per `params/heat.yaml` (da applicare a cura del responsabile).** (1) Tenere Deryng come funzione principale. (2) Adottare la finestra in frazione di giorni da emergenza a maturità come default, fedele alla fonte, e lasciare la variante in GDD per il frumento autunnale, dove la pausa invernale la giustifica, dichiarandola come adattamento solo lì. Serve una voce `gdd_emergenza` (100, AquaCrop Annex I.2) in `crops.yaml`. (3) Correggere `_meta.limiti`: con POWER lo stress non è sempre sottostimato, perché nel 2022 POWER è più caldo delle stazioni. (4) Dichiarare che il caldo in fioritura spiega poco della resa del 2022 a Cremona: la perdita va cercata nel bilancio idrico.

**Opzioni per il responsabile (non decidibili sui dati; la validazione arriva in fase 6):**
- A, Deryng su POWER (default attuale). A favore: pubblicata, forma completa e moltiplicativa, nessuna taratura. Contro: effetto piccolo (≥ 0,91) e valore 2022 guidato da un anno caldo di POWER.
- B, AquaCrop. A favore: fonte FAO, gerarchicamente preferita. Contro: soglie "Estimate" e uso fuori dal suo modello di HI; in questo clima vale sempre 1, cioè nessun effetto del caldo.
- C, Teixeira su Tmax. A favore: effetto più marcato (2022 0,89). Contro: articolo non letto (`verificato: false`), temperatura di applicazione incerta; sceglierla perché "dà il 2022 basso" sarebbe una taratura sul risultato.
- In ogni caso B e C, più Tcr 30–35, vanno nell'analisi di sensibilità.

**Confronto orientativo (ISTAT, NDVI).** Gli anni peggiori per POWER sono il 2015 (0,912), il 2022 (0,942) e il 2023 (0,959). Le rese del mais sono 9,5, 9,5 e 13,0 t/ha. L'NDVI di luglio–agosto (finestra) vale 0,644, 0,609 (il minimo) e 0,654. Il 2015 e il 2022 coincidono con i minimi di resa e di NDVI, ma sono anche anni di siccità; il 2023 no. Il 2012 e il 2013 (9,6 e 9,5 t/ha) hanno f_caldo di circa 0,99. Correlazione di f_caldo con lo scarto di resa dal trend lineare: 0,43 con POWER, 0,47 con Casalbuttano, 0,35 con Gambara.

**Con IMERG.** Nessun effetto diretto.

### D4 — Rese ISTAT in validazione

**Decisione.** Validazione sul 2006–2022, cioè 17 anni coerenti con D1. Il 2023–2025 si mostra a parte, solo con `rain_source="power"` o `"power_arpa"` ed etichettato come tale. Il 2026 (provvisorio e oltre il meteo) è escluso. I salti annui (mais 2016 +47%, 2023 +37%, soia 2020 +50%, frumento 2013–2014) si tengono: seguono annate cattive (2015, 2022) e non sono errori evidenti, quindi toglierli sarebbe scegliere i dati. Il confronto si fa sulle anomalie rispetto al trend lineare e sull'ordine degli anni peggiori, non sui valori assoluti. Le rese sono provinciali, calcolate come produzione su superficie totale, con irriguo e asciutto mescolati e umidità di riferimento ignota.

**Alternative scartate.** Rese assolute contro la resa simulata: confondono il trend tecnologico e la media provinciale con il campo. Escludere i salti: nessun motivo documentale.

**Con IMERG.** Se IMERG diventa la pioggia di default, la validazione si estende al 2023–2024.

### D5 — NDVI MODIS

**Decisione.** Per la validazione si usa la media della finestra 9×9 (circa 2 km, `ndvi_window_mean_good`). Valgono solo i pixel con affidabilità 0 o 1 e le date con almeno metà dei pixel buoni (filtro già nel client); indicatore: media di luglio–agosto.

**Motivo.** Il pixel centrale da 250 m dipende dalla coltura dell'anno su quell'appezzamento, che non conosciamo. Correlazione con lo scarto di resa ISTAT: −0,01 per il pixel centrale, 0,29 per la finestra. La finestra rappresenta lo stato medio dei seminativi attorno al punto, come le rese provinciali. Limite: la finestra mescola colture diverse, quindi l'NDVI si confronta con l'ordine delle annate e non con una coltura precisa. Il pixel centrale si usa solo se l'utente dichiara la coltura dell'anno sul proprio campo.

**Con IMERG.** Nessun effetto.

### D6 — IMERG e SMAP quando saranno disponibili

**IMERG.** Il punto pilota cade su un vertice di quattro celle. La regola generale è l'interpolazione bilineare dai quattro centri cella più vicini: su un vertice equivale alla media delle quattro celle, al centro di una cella alla cella stessa. Così si elimina la scelta convenzionale della cella a nord-est fatta dal client attuale, che scarica una sola cella: va esteso (non da me, il client non va toccato). Da rifare: `python -m fieldwise.qc` (sezioni IMERG), il confronto di D1 con la rete di pluviometri sul 2001–2024 (i giorni IMERG sono UTC, POWER usa l'ora solare locale: circa 40 minuti, trascurabile), la scelta del default di D1, `available_years` e la validazione D4.

**SMAP.** Si usa la cella EASE-Grid che contiene il punto e solo i passaggi con qualità raccomandata. Il confronto riguarda le anomalie dell'umidità superficiale (0–5 cm) contro lo strato superficiale del bilancio, dal 2015-04 al 2022, oppure al 2024 se la pioggia passa a IMERG. Da rifare: controlli SMAP del QC e validazione dell'acqua della fase 6.

### D7 — Limiti dei dati da dichiarare nel report finale

1. Pioggia POWER 2023–2025 sovrastimata del 17–72% rispetto a cinque pluviometri, causa non documentata da NASA. L'ensemble usa solo il 2000–2022.
2. POWER ha troppi giorni di pioggerella (31% contro 21%) e pochi eventi intensi (p99 32 contro 57 mm): pesa su evaporazione, ruscellamento e percolazione.
3. Le temperature POWER sono buone in media estiva ma deboli negli estremi (giorni sopra 35 °C: r 0,46; scarto annuo della Tmax estiva fino a ±3 °C). Lo stress da caldo è incerto in entrambe le direzioni.
4. Cella POWER di circa 50 km a 171 m di quota contro un campo a 45 m: effetto sull'ET0 dello 0,3%.
5. Il caldo in fioritura del mais incide poco (f ≥ 0,91), e il valore 2022 dipende dalla fonte di temperatura (0,94 POWER, 0,99 stazioni).
6. Le rese ISTAT sono provinciali e calcolate (produzione / superficie totale), solo dal 2006; il 2026 è provvisorio.
7. L'NDVI della finestra da 2 km mescola colture; il pixel centrale non è legato alla coltura del campo.
8. Senza credenziali Earthdata IMERG e SMAP mancano, quindi nessuna validazione dell'umidità del suolo.
9. Il pluviometro di Persico Dosimo ha anni incompleti (2003, 2004, 2008, 2010, 2016) e il sensore di temperatura 2485 non è omogeneo.

## Aggiornamento delle decisioni dopo l'arrivo di IMERG e SMAP (2026-11-12)

Dati: GPM IMERG Final Daily V07, interpolazione bilineare delle quattro celle attorno al punto,
2000-06-01 → 2025-09-30, 9253 giorni tutti validi. SMAP SPL3SMP_E V006, 2015-03-31 → 2025-12-31,
3845 giorni, 2323 con almeno un passaggio di qualità raccomandata (umidità tra 0,038 e 0,458 m³/m³).

Confronto delle piogge con il pluviometro ARPA di Persico Dosimo (solo giorni completi, anni con almeno
l'80% di giorni completi, 22 anni dal 2001):

| Misura | NASA POWER | IMERG |
|---|---|---|
| Rapporto medio dei totali annui con ARPA, 2001–2022 | 1,01 | 1,21 |
| Errore assoluto medio annuo, 2001–2022 | 11% | 22% |
| Rapporto medio con ARPA, 2023–2024 | 1,35 | 1,49 |
| Correlazione dei totali mensili | 0,80 | 0,80 |
| Correlazione giornaliera | 0,59 | 0,73 |
| Giorni piovosi (≥ 1 mm; ARPA 21%) | 31% | 26% |

D8. La decisione D1 è confermata: la pioggia del motore resta NASA POWER 2000–2022. IMERG non la
sostituisce: sui totali annui sovrastima il pluviometro del 21% in media, contro l'1% di POWER, e il
bilancio idrico stagionale dipende dai totali. IMERG è però migliore nel collocare la pioggia nel giorno
giusto (correlazione giornaliera 0,73 contro 0,59) e ha meno giorni di pioviggine: resta disponibile
come forzante alternativa (`rain_source="imerg"`) per l'analisi di sensibilità.
D9. Anche IMERG è sopra il pluviometro nel 2023 (927 contro 496 mm) e nel 2024 (1386 contro 1241 mm):
gli anni dal 2023 restano esclusi dall'ensemble; il confronto con una sola stazione in quegli anni va
letto con cautela (la rete di cinque pluviometri dava per POWER 1,17 nel 2023).
D10. La differenza tra interpolazione bilineare e cella più vicina è trascurabile (−0,02 mm/giorno).
D11. SMAP è utilizzabile per la validazione dell'umidità (fase 6) sui 2323 giorni di qualità raccomandata.
