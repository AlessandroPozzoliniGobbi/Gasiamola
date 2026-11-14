# Contratto dei file `params/*.yaml`

Ogni numero usato dal modello è una **voce parametro**: un dizionario YAML con queste chiavi.

| Chiave | Obbligatoria | Significato |
|--------|--------------|-------------|
| `valore` | sì | numero, oppure lista di numeri, oppure stringa (es. una data `"04-10"`) |
| `unita` | sì | unità di misura; `"-"` se adimensionale |
| `fonte` | sì, salvo assunzione | autore, anno, titolo |
| `riferimento` | sì, salvo assunzione | tabella, equazione o pagina nella fonte |
| `url` | sì, salvo assunzione | indirizzo dove la fonte si legge |
| `nota` | sì | come è stato scelto o convertito il valore (anche vuota `""`) |
| `verificato` | sì | `true` solo se il valore è stato **letto dalla fonte** durante il lavoro; `false` se ricordato o preso da una citazione indiretta |
| `assunzione` | no (default `false`) | `true` se non esiste una fonte ufficiale per quel valore |
| `motivazione` | sì se `assunzione: true` | perché quel valore, e da cosa è stato ragionato |
| `derivato` | no (default `false`) | `true` se il valore è stato calcolato dall'autore a partire da altre voci o da regole lette nella fonte; la `nota` dice da cosa e come. In questo caso `verificato` si riferisce agli ingressi del calcolo |
| `sensibilita` | no (default `false`) | `true` per includere il parametro nell'analisi di sensibilità anche se ha una fonte |
| `intervallo` | no | `[min, max]` plausibile, se la fonte lo dà |

Regole:

1. Una voce è valida se ha (`fonte` + `riferimento` + `url`) **oppure** (`assunzione: true` + `motivazione`).
2. Ogni voce con `assunzione: true` entra automaticamente nell'analisi di sensibilità.
3. I valori convertiti (es. da q/ha a t/ha) riportano in `nota` il valore originale e la conversione.
4. Gerarchia delle fonti: manuali FAO (56, 33, 66/AquaCrop) → enti pubblici italiani (disciplinari
   di produzione integrata di Regione Lombardia ed Emilia-Romagna, CREA, ISTAT, ARPA) → articoli
   peer-reviewed → altro solo se dichiarato in `nota`.
5. I file possono avere in testa una chiave `_meta` (descrizione, data di compilazione): non è un parametro.
6. Una voce parametro si riconosce perché contiene la chiave `valore`. Tutto ciò che sta sopra è
   struttura (dizionari annidati per coltura, gruppo, ecc.).
7. Una voce non può avere insieme `verificato: true` e `assunzione: true`: un'assunzione non è letta da una fonte.
8. Le voci calcolate dall'autore si marcano `derivato: true` (vedi tabella).

Esempio:

```yaml
_meta:
  descrizione: "Parametri colturali"
  compilato_il: "2026-11-11"

mais:
  kc:
    mid:
      valore: 1.20
      unita: "-"
      fonte: "Allen, Pereira, Raes, Smith (1998). Crop evapotranspiration. FAO Irrigation and Drainage Paper 56"
      riferimento: "Tabella 12, Maize, Field (grain)"
      url: "https://www.fao.org/4/x0490e/x0490e0b.htm"
      nota: "Valore per clima sub-umido standard (RHmin 45%, u2 2 m/s); correzione climatica eq. 62 applicata nel codice"
      verificato: true
```

Il caricatore è `fieldwise.params` (`load_params()`, `validate_params()`); il test
`tests/test_params.py` fallisce se una voce non rispetta la regola 1.
