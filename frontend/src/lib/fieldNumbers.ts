import type { ImportedField } from "./fieldStorage";

/** Numero positivo piu' piccolo non ancora utilizzato. */
export function firstAvailableNumber(used: ReadonlySet<number>): number {
  let number = 1;
  while (used.has(number)) number++;
  return number;
}

/** Campo legacy v1: per compatibilita' mantiene nextNumber > massimo. */
export function nextSavedNumber(fields: readonly { number: number }[]): number {
  return fields.reduce((max, field) => Math.max(max, field.number), 0) + 1;
}

/**
 * Preserva tutti i numeri univoci espliciti del GeoJSON, prima di
 * attribuire i numeri mancanti o duplicati. Non dipende dalla mappa attuale.
 */
export function prepareImportedFields(imported: readonly ImportedField[]) {
  const reserved = new Set<number>();
  for (const item of imported) {
    if (item.number !== null) reserved.add(item.number);
  }

  const assigned = new Set<number>();
  return imported.map((item) => {
    let number: number;
    if (item.number !== null && !assigned.has(item.number)) {
      number = item.number;
    } else {
      number = firstAvailableNumber(new Set([...reserved, ...assigned]));
    }
    assigned.add(number);

    // Se il nome era quello generato automaticamente, aggiorniamo il numero
    // anche nel nome; i nomi personalizzati sono conservati intatti.
    const customName = item.name?.trim() || "";
    const name = !customName || /^(?:Appezzamento|Field) \d+$/.test(customName)
      ? `Field ${number}`
      : customName;

    return { number, name, coordinates: item.coordinates, backupId: item.backupId, analysis: item.analysis };
  });
}
