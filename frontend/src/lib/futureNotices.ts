/** English display text for the future-simulation payload.
 *  Some older reports contain Italian free-text statements produced by ranking.py.
 *  Translate only known templates, without changing numeric values or assumptions.
 *  Unrecognised statements are left untouched rather than guessed.
 */

export function translateFutureCompliance(value: string): string {
  const states: Record<string, string> = {
    conforme: "Compliant",
    conforme_solo_in_deroga: "Compliant only under derogation",
    non_conforme: "Not compliant",
    non_valutabile: "Not assessable",
  };
  return states[value.trim().toLowerCase()] ?? value;
}

function translateRegime(text: string): string {
  return text
    .replaceAll("Lombardia, impegno quinquennale", "Lombardy, five-year commitment")
    .replaceAll("Lombardia, impegno triennale (SRA01)", "Lombardy, three-year commitment (SRA01)")
    .replaceAll("Emilia-Romagna, impegno quinquennale", "Emilia-Romagna, five-year commitment")
    .replaceAll("Emilia-Romagna, adesione per singola coltura", "Emilia-Romagna, single-crop membership");
}

export function translateFutureNotice(original: string): string {
  const text = original.trim();
  let match: RegExpMatchArray | null;
  if ((match = text.match(/^nell['’]annata peggiore la resa media della rotazione scende a (.+?)(?: \(attuale: (.+?)\))?$/i))) {
    return `In the worst simulated year, average relative yield falls to ${match[1]}${match[2] ? ` (current: ${match[2]})` : ""}.`;
  }
  if ((match = text.match(/^in (\d+(?:[.,]\d+)?)% delle annate almeno una coltura supera il limite normativo di azoto(?: \(attuale: (\d+(?:[.,]\d+)?)%\))?$/i))) {
    return `In ${match[1]}% of simulated years, at least one crop exceeds the legal nitrogen limit${match[2] ? ` (current: ${match[2]}%)` : ""}.`;
  }
  if (/^non conforme al disciplinare di produzione integrata/i.test(text)) {
    return translateRegime(text.replace(/^non conforme al disciplinare di produzione integrata/i, "Does not comply with integrated-production rotation rules"));
  }
  if (/^conforme al disciplinare solo in deroga/i.test(text)) {
    return translateRegime(text.replace(/^conforme al disciplinare solo in deroga/i, "Complies with integrated-production rules only under derogation"));
  }
  if (/^conformita' al disciplinare non valutabile per questa successione/i.test(text)) {
    return "Compliance with integrated-production rules cannot be assessed for this rotation.";
  }
  if ((match = text.match(/^la cover e' praticabile nel (\d+(?:[.,]\d+)?)% dei casi: negli altri l'intervallo resta a suolo nudo$/i))) {
    return `The cover crop is feasible in ${match[1]}% of cases; otherwise the soil remains bare between crops.`;
  }
  if ((match = text.match(/^rispetto all'attuale: (.+)$/i))) {
    const detail = match[1];
    const metrics: Record<string, string> = {
      irrigazione: "irrigation", "concime azotato": "nitrogen fertilizer",
      "azoto lisciviato": "nitrogen leaching", "resa mediana": "median relative yield",
      "resa media della rotazione nell'annata peggiore": "worst-year mean relative yield",
      margine: "margin",
    };
    for (const [it, en] of Object.entries(metrics)) {
      if (detail.toLowerCase().includes(it)) {
        const escaped = it.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
        const translated = detail.replace(new RegExp(`di ${escaped}`, "i"), `change in ${en}`)
          .replace(new RegExp(escaped, "i"), en)
          .replace(/\binvece di\b/gi, "instead of").replace(/\ball'anno\b/gi, "per year");
        return `Compared with the current rotation: ${translated}`;
      }
    }
    if (/^humus:/i.test(detail)) {
      return `Compared with the current rotation: ${detail.replace(/all'anno invece di/gi, "per year instead of")}`;
    }
  }
  return text;
}
