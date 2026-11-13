# Analisi di sensibilita' (fase 7)

Generato da `python -m fieldwise.sensitivity` il 2026-11-13. Domanda: quali parametri incerti cambiano la DECISIONE (classifica delle rotazioni e alternative proposte) e quali no. Nessuna taratura: si riporta cio' che esce.

## Conclusione in una frase

Cambiano la prima rotazione nel tetto irriguo 29 dei 173 parametri presi uno alla volta (soprattutto `crops.mais.kcb.mid`, `crops.soia.kcb.mid`, `nitrogen.mais.n_assorbito`, `scenarios.scenari.tetto_irriguo.tetto_irriguo.mais`, `crops.frumento.kcb.mid`) e, tra le scelte strutturali, evapotraspirazione a kc singolo; curve number per copertura; riparto dell'azoto assorbito su eta; riparto dell'azoto assorbito su eta/et0; penalita' di rotazione azzerate; non cambiano la decisione 107 parametri (82 senza alcun effetto); con l'incertezza congiunta la prima resta prima solo nel 33% dei campioni (tau mediano 0.59) ma il mais continuo resta nell'ultimo quarto nel 92%: e' robusto il giudizio sulla rotazione attuale, non la scelta fine tra le prime alternative.

## Metodo

- **Versione del codice**: commit 2f8776d con modifiche locali in src/ o params/ non registrate, hash dei parametri 2b8a878cc8612e8aed5f97bdedcfa4ba77096eed4b2ddc1be0826954cd891329, ensemble calcolato il 2026-11-13T13:10:26+00:00.
- **Sottoinsieme fisso**: tutti i membri (125 rotazioni) delle 45 classi cicliche non equivalenti dell'ensemble di base, tutte le annate, i tre scenari d'acqua, rotazione attuale "mais". Le equivalenze sono fissate sul caso di base.
- **Verifica del sottoinsieme** (classifica di base, pesi uguali, contro l'ensemble completo di 216 rotazioni): solo pioggia tau 1.000, stessa prima si, stesse prime tre si; tetto irriguo tau 1.000, stessa prima si, stesse prime tre si; irrigazione libera tau 1.000, stessa prima si, stesse prime tre si.
- **Indicatore principale**: punteggio a pesi uguali di `ranking.score` nello scenario tetto irriguo; in subordine solo pioggia e irrigazione libera. Il punteggio e' relativo all'insieme confrontato (0-1).
- **Una alla volta**: 173 voci di `params.sensitivity_entries` a x0,7 e x1,3 del valore. Limiti: l'`intervallo` della voce se piu' stretto; 1 per frazioni, quote ed efficienze; soglie ordinate (GDD delle fasi, zr iniziale < massima, t critica < t limite, finestre del caldo, soglie di pioggia) con la successiva >= precedente x1.01. Valori interi arrotondati. Escluse 6 voci: `crops.mais.irrigabile` (interruttore 0/1, non una grandezza continua); `crops.soia.irrigabile` (interruttore 0/1, non una grandezza continua); `crops.frumento.t_base` (valore nullo: +/-30% non lo cambia); `nitrogen.soia.credito_precessione` (valore nullo: +/-30% non lo cambia); `scenarios.scenari.solo_pioggia.tetto_irriguo.mais` (valore nullo: +/-30% non lo cambia); `scenarios.scenari.solo_pioggia.tetto_irriguo.soia` (valore nullo: +/-30% non lo cambia).
- **Soglie 'non conta'**: in nessuno dei tre scenari cambia la prima, l'insieme delle prime tre o le alternative; |variazione del punteggio della prima| < 0.01; tau >= 0.95.
- **Funzione del caldo alternativa**: si seleziona con l'argomento `metodo_caldo` di `ensemble.run_ensemble` e `rotation.simulate` (`yield_model.heat_factor` con `metodo` diverso).
- **Monte Carlo**: 256 campioni a ipercubo latino (`scipy.stats.qmc.LatinHypercube`, seme 20261113) su tutte le 173 voci, uniformi tra gli stessi limiti dell'OAT; 206 campioni corretti per le soglie ordinate; 30 non eseguibili (ValueError: finestra sensibile vuota). Con 173 parametri e 256 campioni l'influenza si stima con correlazioni di rango parziali (PRCC, gradi di liberta' residui 51): indicativa, non un indice di Sobol.
- **Tempo di calcolo**: OAT + strutturali 217 s (323 calcoli), Monte Carlo 148 s, totale 376 s con 8 processi.

## Caso di base

- solo pioggia: prime tre `frumento > frumento+cover > soia`, `frumento > frumento > soia`, `frumento+cover > soia+cover > soia`; attuale `mais > mais > mais` 45a su 45; alternative `frumento > frumento+cover > soia`, `frumento > frumento > soia`
- tetto irriguo: prime tre `frumento+cover > soia+cover > mais`, `frumento > frumento+cover > soia`, `frumento+cover > soia > mais`; attuale `mais > mais > mais` 30a su 45; alternative `frumento+cover > soia+cover > mais`, `frumento+cover > mais > mais`
- irrigazione libera: prime tre `frumento+cover > soia+cover > mais`, `frumento+cover > mais+cover > soia`, `frumento+cover > soia > mais`; attuale `mais > mais > mais` 43a su 45; alternative `frumento+cover > soia+cover > mais`, `mais+cover > mais+cover > soia`

## I 20 parametri piu' influenti (una alla volta, tetto irriguo)

Effetto = variazione del punteggio della prima rotazione di base; tau = minimo sui due lati; 'prima'/'top3'/'alt' = cambia la prima, l'insieme delle prime tre, le alternative (T = tetto irriguo, S = solo pioggia, L = irrigazione libera).

Ord. | Parametro | Base | Valore -30% | Valore +30% | Effetto -30% | Effetto +30% | Attuale -/+ | tau | prima | top3 | alt | limiti
---|---|---|---|---|---|---|---|---|---|---|---|---
1 | `rotation_rules.f_rotazione.mais_dopo_mais.irriguo` | 0.983 | 0.862 | 0.983 | +0.049 | +0.000 | -0.21/+0.00 | 0.69 | - | - | TL | intervallo
2 | `crops.mais.kcb.mid` | 1.15 | 0.805 | 1.495 | -0.047 | -0.030 | +0.02/-0.36 | 0.46 | T | TSL | TL | -
3 | `crops.soia.kcb.mid` | 1.1 | 0.77 | 1.43 | +0.044 | -0.035 | -0.04/+0.01 | 0.51 | TL | TSL | TL | -
4 | `crops.mais.gdd_maturita` | 1950 | 1515 | 1950 | -0.040 | +0.000 | +0.02/+0.00 | 0.86 | - | TS | TL | intervallo,ordine(meno)
5 | `nitrogen.mais.n_assorbito` | 22.7 | 15.89 | 29.51 | +0.039 | +0.008 | -0.03/-0.00 | 0.84 | TL | TL | TL | -
6 | `scenarios.scenari.tetto_irriguo.tetto_irriguo.mais` | 200 | 140 | 260 | +0.009 | -0.032 | -0.19/+0.02 | 0.67 | T | T | T | -
7 | `nitrogen.mais.n_asportato` | 15.6 | 10.92 | 20.28 | -0.009 | +0.030 | +0.00/+0.03 | 0.90 | L | TL | L | -
8 | `crops.frumento.kcb.mid` | 1.1 | 0.77 | 1.43 | -0.014 | -0.028 | -0.04/+0.02 | 0.78 | T | TL | TL | -
9 | `crops.soia.gdd_maturita` | 2470 | 2150 | 3211 | +0.023 | -0.006 | +0.00/+0.02 | 0.82 | TL | TSL | TL | intervallo
10 | `heat.colture.soia.t_limite` | 40 | 35.35 | 52 | -0.020 | +0.000 | +0.00/-0.00 | 0.94 | T | T | TL | ordine(meno)
11 | `crops.mais.gdd_fine_mid` | 1500 | 1210 | 1600 | -0.019 | +0.009 | +0.01/-0.01 | 0.95 | - | TL | TL | intervallo
12 | `crops.mais.gdd_fine_sviluppo` | 670 | 469 | 871 | +0.016 | -0.019 | -0.02/+0.01 | 0.93 | T | - | TL | -
13 | `crops.frumento.gdd_maturita` | 2395 | 1762 | 3114 | -0.011 | -0.019 | -0.02/+0.02 | 0.69 | TSL | TSL | TSL | ordine(meno)
14 | `cover_crop.biomassa_e_azoto.n_assorbito` | 51 | 51 | 66 | +0.000 | +0.016 | +0.00/+0.00 | 0.97 | - | TL | - | intervallo
15 | `crops.soia.t_base` | 5 | 3.5 | 6.5 | +0.015 | +0.002 | +0.00/-0.00 | 0.93 | T | TL | TL | -
16 | `heat.colture.mais.t_critica` | 32 | 30 | 35 | +0.012 | -0.015 | -0.03/+0.01 | 0.89 | T | TL | T | intervallo
17 | `scenarios.scenari.tetto_irriguo.tetto_irriguo.soia` | 100 | 70 | 130 | -0.005 | +0.015 | +0.00/-0.00 | 0.95 | T | T | T | -
18 | `crops.frumento.gdd_fine_mid` | 1745 | 1222 | 2250 | -0.004 | -0.015 | -0.02/+0.01 | 0.90 | T | T | T | intervallo
19 | `nitrogen.efficienza_concime.recupero_apparente.mais` | 0.84 | 0.588 | 0.91 | +0.013 | -0.004 | +0.00/+0.00 | 0.95 | T | T | T | intervallo
20 | `heat.colture.mais.finestra_fine_frazione` | 0.7 | 0.49 | 0.91 | -0.013 | -0.006 | +0.00/+0.00 | 0.93 | TL | TL | TL | -

Fuori dai primi 20 per effetto ma con tau < 0.95 nel tetto irriguo: `crops.soia.gdd_fine_mid` (0.95), `nitrogen.efficienza_concime.recupero_apparente.frumento` (0.93), `cover_crop.calendario_agronomico.durata_minima_giorni` (0.91), `soil.ruscellamento.aquacrop.cn` (0.94), `nitrogen.soia.n_assorbito` (0.94), `crops.suolo_nudo.ze` (0.94), `heat.colture.frumento.finestra_fine_frazione` (0.92), `crops.frumento.gdd_fine_sviluppo` (0.94).

Variazioni non eseguibili: nessuna.

![Tornado sul punteggio](figure/sensibilita_tornado_punteggio.png)

![Tornado sul tau di Kendall](figure/sensibilita_tornado_tau.png)

## Incertezza strutturale (una alla volta)

Scelta | Esito | tau T / S / L | Effetto sulla prima (T) | Prima nel tetto irriguo | Cambia prima T/S/L | Cambiano top3 T/S/L | Cambiano alternative T/S/L
---|---|---|---|---|---|---|---
Funzione del caldo AquaCrop (Ks logistico su Tmax) | ok | 0.98 / 0.95 / 0.89 | -0.011 | `frumento+cover > soia+cover > mais` | no/no/no | no/si/no | no/no/no
Funzione del caldo con soglie di Teixeira et al. (2013) | ok | 0.97 / 0.95 / 0.88 | -0.010 | `frumento+cover > soia+cover > mais` | no/no/no | no/si/no | no/no/no
Evapotraspirazione a Kc singolo | ok | 0.91 / 0.89 / 0.90 | -0.046 | `frumento > frumento+cover > soia` | no/si/no | no/si/si | no/si/si
Curve Number per copertura (NEH) al posto di AquaCrop | ok | 0.90 / 0.86 / 0.84 | -0.020 | `frumento > frumento+cover > soia` | no/si/si | no/si/si | no/si/si
Riparto dell'azoto assorbito su ETa | ok | 0.96 / 0.94 / 0.92 | +0.000 | `frumento > frumento+cover > soia` | no/si/no | no/no/si | no/si/si
Riparto dell'azoto assorbito su ETa/ET0 | ok | 0.94 / 0.92 / 0.85 | +0.004 | `frumento > frumento+cover > soia` | no/si/si | no/si/si | no/si/si
Zero cicli di avviamento | ok | 0.83 / 0.86 / 0.75 | +0.006 | `frumento+cover > soia+cover > mais` | no/no/no | no/si/no | no/si/si
Pioggia IMERG al posto di NASA POWER | ok | 0.86 / 0.83 / 0.91 | +0.002 | `frumento+cover > soia+cover > mais` | no/no/no | no/si/si | no/si/si
Penalita' di rotazione azzerate (tutti i fattori = 1) | ok | 0.87 / 0.71 / 0.08 | -0.103 | `frumento > frumento > frumento` | si/si/si | si/si/si | si/si/si
Sostanza organica 0-30 cm al valore SoilGrids (3,563%) | ok | 0.97 / 0.99 / 0.98 | +0.002 | `frumento+cover > soia+cover > mais` | no/no/no | no/no/no | no/no/no

## Monte Carlo (incertezza congiunta dei parametri)

Scenario | campioni validi | tau mediana | tau 5° perc. | prima resta prima | prime tre restano | attuale nell'ultimo quarto | alternative restano
---|---|---|---|---|---|---|---
solo pioggia | 226 | 0.756 | 0.383 | 61.5% | 15.0% | 99.1% | 45.6%
tetto irriguo | 226 | 0.590 | 0.021 | 32.7% | 2.2% | 92.0% | 4.0%
irrigazione libera | 226 | 0.509 | 0.176 | 36.3% | 11.5% | 98.7% | 1.8%

Frequenza con cui le rotazioni compaiono tra le prime tre (le prime 6 per scenario):

- solo pioggia: `frumento > frumento+cover > soia` 80%; `frumento > frumento > soia` 42%; `frumento+cover > soia+cover > soia` 41%; `frumento+cover > soia > soia` 27%; `frumento > frumento+cover > mais` 22%; `frumento+cover > soia+cover > mais` 15%
- tetto irriguo: `frumento+cover > soia+cover > mais` 55%; `frumento+cover > soia > mais` 39%; `frumento > frumento+cover > soia` 37%; `frumento > frumento+cover > mais` 36%; `frumento+cover > mais+cover > soia` 32%; `frumento > frumento > mais` 19%
- irrigazione libera: `frumento+cover > soia+cover > mais` 56%; `frumento+cover > soia > mais` 38%; `frumento+cover > mais+cover > soia` 31%; `mais+cover > soia+cover > soia+cover` 21%; `frumento+cover > soia+cover > soia` 20%; `frumento > soia+cover > mais` 16%

Parametri con le correlazioni di rango parziali piu' forti (tetto irriguo; |PRCC| piu' alto su punteggio della prima e tau):

- `crops.soia.gdd_maturita`: PRCC punteggio della prima -0.23, PRCC tau -0.48
- `crops.soia.kcb.mid`: PRCC punteggio della prima -0.45, PRCC tau +0.41
- `nitrogen.frumento.n_assorbito`: PRCC punteggio della prima -0.35, PRCC tau -0.09
- `soil.profilo.strato_superficiale.ksat`: PRCC punteggio della prima +0.34, PRCC tau -0.14
- `nitrogen.lisciviazione.metodo_disciplinare.soglie_pioggia_autunno_inverno[1]`: PRCC punteggio della prima -0.34, PRCC tau +0.15
- `rotation_rules.f_rotazione.mais_dopo_mais.irriguo`: PRCC punteggio della prima -0.33, PRCC tau +0.33
- `crops.mais.kcb.ini`: PRCC punteggio della prima +0.04, PRCC tau +0.31
- `crops.mais.kcb.mid`: PRCC punteggio della prima +0.22, PRCC tau -0.29
- `nitrogen.frumento.n_asportato`: PRCC punteggio della prima +0.29, PRCC tau +0.02
- `soil.strati_soilgrids.s0_30.densita_apparente`: PRCC punteggio della prima -0.28, PRCC tau -0.04

![Distribuzione del tau nel Monte Carlo](figure/sensibilita_montecarlo_tau.png)

## Sensibilita' ai pesi dell'utente (non e' incertezza del modello)

Parametri di base; 5 casi estremi (tutto il peso su una priorita') e 200 pesi casuali (Dirichlet uniforme sul simplesso, stesso seme).

- solo pioggia: 9 rotazioni diverse arrivano prime (5 con i pesi casuali). Estremi: resa -> `frumento > frumento > soia`; rischio -> `frumento > frumento > soia`; acqua -> `frumento > frumento > frumento` (avviso: le rotazioni non si distinguono); concime -> `soia > soia > soia`; suolo -> `frumento+cover > mais+cover > mais`. Piu' frequenti: `frumento > frumento+cover > soia` 57%; `soia+cover > soia+cover > soia` 22%; `frumento > frumento+cover > mais` 19%
- tetto irriguo: 12 rotazioni diverse arrivano prime (10 con i pesi casuali). Estremi: resa -> `frumento > mais > mais`; rischio -> `frumento+cover > mais > mais`; acqua -> `frumento > frumento > frumento`; concime -> `soia > soia > soia`; suolo -> `frumento+cover > mais+cover > mais`. Piu' frequenti: `frumento > frumento+cover > soia` 26%; `frumento+cover > mais+cover > mais` 24%; `frumento+cover > soia+cover > mais` 20%
- irrigazione libera: 16 rotazioni diverse arrivano prime (13 con i pesi casuali). Estremi: resa -> `frumento > mais > soia`; rischio -> `mais > mais > soia`; acqua -> `frumento > frumento > frumento`; concime -> `soia > soia > soia`; suolo -> `mais+cover > mais+cover > mais+cover`. Piu' frequenti: `frumento+cover > mais+cover > soia` 16%; `frumento > frumento+cover > soia` 15%; `mais+cover > mais+cover > soia` 13%

## Parametri che NON contano

**Senza alcun effetto sul risultato** (82; voci non usate dal motore nella configurazione di base, per esempio i parametri delle sole alternative strutturali): `nitrogen.soia.nhi`, `rotation_rules.f_rotazione.mais_dopo_mais.asciutto.primo_ristoppio`, `cover_crop.humus.incremento_c_suolo_medio`, `crops.mais.kc.ini`, `rotation_rules.precessione_favorevole.cereale_dopo_leguminosa_vs_monosuccessione`, `crops.mais.kc.end`, `crops.mais.gdd_fioritura`, `rotation_rules.f_rotazione.mais_dopo_mais.asciutto.monosuccessione_continua`, `crops.soia.gdd_fioritura`, `crops.soia.kc.ini`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_argilloso[1]`, `crops.frumento.kc.ini`, `nitrogen.lisciviazione.metodo_disciplinare.perdita_uscita_inverno`, `nitrogen.lisciviazione.metodo_disciplinare.soglie_pioggia_autunno_inverno[1]`, `nitrogen.lisciviazione.metodo_disciplinare.soglie_pioggia_autunno_inverno[0]`, `crops.frumento.gdd_fioritura`, `crops.frumento.gdd_emergenza`, `cover_crop.biomassa_e_azoto.efficienza_campo`, `soil.strati_soilgrids.s0_30.sabbia`, `soil.strati_soilgrids.s0_30.argilla`, `soil.strati_soilgrids.s0_30.carbonio_organico`, `soil.drenaggio.tau_alternativa.strato_profondo`, `soil.drenaggio.tau_alternativa.strato_superficiale`, `soil.ruscellamento.neh.ia_su_s`, `cover_crop.acqua.kcb.mid`, `cover_crop.acqua.kcb.end`, `soil.profilo.acqua_disponibile_totale`, `soil.profilo.strato_profondo.ksat`, `soil.profilo.strato_superficiale.ksat`, `soil.profilo.profondita_profilo`, `soil.strati_soilgrids.s100_200.ksat`, `soil.strati_soilgrids.s100_200.frammenti_grossolani`, `soil.strati_soilgrids.s30_100.ksat`, `soil.strati_soilgrids.s30_100.frammenti_grossolani`, `soil.strati_soilgrids.s0_30.ksat`, `soil.strati_soilgrids.s0_30.frammenti_grossolani`, `cover_crop.biomassa_e_azoto.riduzione_lisciviazione`, `cover_crop.biomassa_e_azoto.quota_n_che_torna_alla_coltura_successiva`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_argilloso[2]`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_argilloso[0]`, `nitrogen.mais.credito_precessione.stocchi_asportati`, `nitrogen.suolo.k2.per_tessitura.tendenzialmente_argilloso`, `nitrogen.suolo.k2.formula_machet.coeff_temperatura[0]`, `nitrogen.suolo.k2.formula_machet.coeff_numeratore`, `nitrogen.suolo.k2.cn_alto.tendenzialmente_argilloso`, `nitrogen.suolo.k2.cn_alto.franco`, `nitrogen.suolo.k2.cn_alto.tendenzialmente_sabbioso`, `nitrogen.suolo.k2.cn_basso.tendenzialmente_argilloso`, `nitrogen.suolo.k2.cn_basso.franco`, `nitrogen.suolo.k2.cn_basso.tendenzialmente_sabbioso`, `heat.alternative.teixeira_2013.t_critica_mais`, `heat.alternative.aquacrop.delta_zero`, `nitrogen.suolo.k2.per_tessitura.tendenzialmente_sabbioso`, `nitrogen.frumento.credito_precessione.paglia_asportata`, `heat.alternative.teixeira_2013.t_limite_mais`, `heat.alternative.teixeira_2013.t_critica_frumento`, `heat.alternative.teixeira_2013.t_limite_frumento`, `heat.alternative.teixeira_2013.t_critica_soia`, `nitrogen.soia.fissazione.coeff_inibizione_n`, `heat.alternative.teixeira_2013.t_limite_soia`, `nitrogen.suolo.k2.formula_machet.coeff_temperatura[1]`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_sabbioso[0]`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_sabbioso[1]`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_sabbioso[2]`, `nitrogen.suolo.fattore_dispersione.franco[1]`, `nitrogen.suolo.fattore_dispersione.franco[0]`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_sabbioso[2]`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_sabbioso[1]`, `nitrogen.suolo.fattore_dispersione.tendenzialmente_sabbioso[0]`, `nitrogen.suolo.n_pronto.tendenzialmente_argilloso`, `nitrogen.suolo.n_pronto.franco`, `nitrogen.suolo.n_pronto.tendenzialmente_sabbioso`, `heat.alternative.aquacrop.tx_heat_mais`, `heat.alternative.aquacrop.tx_heat_soia`, `heat.alternative.aquacrop.tx_heat_frumento`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_argilloso[2]`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_argilloso[1]`, `nitrogen.suolo.n_mineralizzato_disciplinare.tendenzialmente_argilloso[0]`, `nitrogen.suolo.n_mineralizzato_disciplinare.franco[2]`, `nitrogen.suolo.n_mineralizzato_disciplinare.franco[1]`, `nitrogen.suolo.n_mineralizzato_disciplinare.franco[0]`, `cover_crop.acqua.kc`.

**Con effetto ma senza conseguenze sulla decisione** (25; nessun cambio di prima, prime tre o alternative in alcuno scenario, |effetto| < 0.01, tau >= 0.95): `nitrogen.suolo.n_humus`, `soil.strati_soilgrids.s0_30.sostanza_organica`, `nitrogen.suolo.profondita_humus`, `cover_crop.biomassa_e_azoto.biomassa_secca`, `crops.soia.resa_potenziale`, `rotation_rules.f_rotazione.soia_dopo_soia`, `heat.colture.frumento.t_limite`, `crops.mais.gdd_emergenza`, `cover_crop.humus.coefficiente_isoumico`, `cover_crop.biomassa_e_azoto.frazione_carbonio_sostanza_secca`, `crops.frumento.gdd_fine_ini`, `cover_crop.acqua.kcb.ini`, `heat.colture.soia.finestra_fine_frazione`, `crops.soia.gdd_emergenza`, `cover_crop.biomassa_e_azoto.npd_per_t_ss`, `rotation_rules.calendario_rotazione.giorni_minimi_raccolta_semina`, `crops.frumento.kcb.end`, `cover_crop.acqua.profondita_radicale_max`, `rotation_rules.f_rotazione.frumento_dopo_frumento.monosuccessione_continua`, `cover_crop.acqua.profondita_radicale_iniziale`, `crops.frumento.kcb.ini`, `cover_crop.acqua.altezza`, `soil.umidita_iniziale.frazione_acqua_disponibile`, `crops.frumento.zr_ini`, `crops.frumento.zr_max`.

