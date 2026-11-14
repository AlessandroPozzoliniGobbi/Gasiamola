import type { FieldItem } from "../types/field";

// Versioniamo la chiave: se in futuro cambiamo il formato dei dati,
// potremo migrare quelli precedenti senza interpretarli per errore.
const STORAGE_KEY = "nasa-space-apps-2026:appezzamenti:v1";

export type StorageStatus = "loading" | "saving" | "saved" | "error";

export type SavedFields = {
  version: 1;
  nextNumber: number;
  fields: FieldItem[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isPosition(value: unknown): value is [number, number] {
  return Array.isArray(value) && value.length === 2 &&
    typeof value[0] === "number" && Number.isFinite(value[0]) &&
    value[0] >= -180 && value[0] <= 180 &&
    typeof value[1] === "number" && Number.isFinite(value[1]) &&
    value[1] >= -90 && value[1] <= 90;
}

function isPolygonCoordinates(value: unknown): value is number[][][] {
  if (!Array.isArray(value) || value.length < 1 || value.length > 100) return false;
  return value.every((ring) => {
    if (!Array.isArray(ring) || ring.length < 4 || ring.length > 20000) return false;
    if (!ring.every(isPosition)) return false;
    const first = ring[0] as [number, number];
    const last = ring[ring.length - 1] as [number, number];
    return first[0] === last[0] && first[1] === last[1];
  });
}

function isFieldItem(value: unknown): value is FieldItem {
  if (!isRecord(value)) return false;
  return typeof value.id === "string" &&
    value.id.length > 0 && value.id.length <= 128 &&
    typeof value.number === "number" &&
    Number.isSafeInteger(value.number) && value.number > 0 &&
    typeof value.name === "string" && value.name.length <= 48 &&
    isPolygonCoordinates(value.coordinates);
}

// Leggiamo solo dati compatibili e completi. Se il salvataggio e' corrotto,
// lanciamo un errore invece di sovrascriverlo con un archivio vuoto.
export function loadSavedFields(): SavedFields | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (raw === null) return null;

  const parsed: unknown = JSON.parse(raw);
  if (!isRecord(parsed) || parsed.version !== 1 ||
      !Array.isArray(parsed.fields) || parsed.fields.length > 5000 ||
      !parsed.fields.every(isFieldItem) ||
      typeof parsed.nextNumber !== "number" ||
      !Number.isSafeInteger(parsed.nextNumber) || parsed.nextNumber < 1) {
    throw new Error("Salvataggio locale non valido o incompatibile.");
  }

  const ids = new Set((parsed.fields as FieldItem[]).map((field) => field.id));
  const numbers = new Set((parsed.fields as FieldItem[]).map((field) => field.number));
  const maxNumber = Math.max(0, ...(parsed.fields as FieldItem[]).map((field) => field.number));
  if (ids.size !== parsed.fields.length || numbers.size !== parsed.fields.length ||
      parsed.nextNumber <= maxNumber) {
    throw new Error("Il salvataggio contiene identificativi o numeri duplicati/non validi.");
  }

  return parsed as SavedFields;
}

export function saveFields(fields: FieldItem[], nextNumber: number): void {
  const payload: SavedFields = { version: 1, nextNumber, fields };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}

// GeoJSON di scambio: NON includiamo le proprieta' interne di Terra Draw.
export function buildGeoJSON(fields: FieldItem[]) {
  return {
    type: "FeatureCollection" as const,
    features: fields.map((field) => ({
      type: "Feature" as const,
      id: field.id,
      geometry: {
        type: "Polygon" as const,
        coordinates: field.coordinates,
      },
      properties: {
        number: field.number,
        name: field.name,
      },
    })),
  };
}

// Terra Draw, invece, richiede properties.mode per ricaricare i poligoni.
export function toTerraDrawFeatures(fields: FieldItem[]) {
  return fields.map((field) => ({
    type: "Feature" as const,
    id: field.id,
    geometry: {
      type: "Polygon" as const,
      coordinates: field.coordinates,
    },
    properties: { mode: "polygon" },
  }));
}

export function downloadGeoJSON(fields: FieldItem[]): void {
  const content = JSON.stringify(buildGeoJSON(fields), null, 2);
  const blob = new Blob([content], { type: "application/geo+json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `appezzamenti-${new Date().toISOString().slice(0, 10)}.geojson`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1500);
}

// I file GeoJSON non devono contenere le proprieta' interne di Terra Draw.
// Accettiamo sia i file esportati da questo sito sia normali Polygon GeoJSON.
export type ImportedField = {
  coordinates: number[][][];
  name: string | null;
  number: number | null;
};

export function parseImportedGeoJSON(content: string): ImportedField[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch {
    throw new Error("Il file non contiene JSON valido.");
  }

  if (!isRecord(parsed) || parsed.type !== "FeatureCollection" || !Array.isArray(parsed.features)) {
    throw new Error("Seleziona un GeoJSON di tipo FeatureCollection.");
  }
  if (parsed.features.length === 0) {
    throw new Error("Il file non contiene appezzamenti.");
  }
  if (parsed.features.length > 1000) {
    throw new Error("Il file contiene troppi appezzamenti (massimo 1000 per importazione).");
  }

  return parsed.features.map((item: unknown, index: number) => {
    if (!isRecord(item) || item.type !== "Feature" || !isRecord(item.geometry) ||
        item.geometry.type !== "Polygon" || !isPolygonCoordinates(item.geometry.coordinates)) {
      throw new Error(`Il campo ${index + 1} non e' un poligono GeoJSON valido.`);
    }

    // Una superficie deve avere almeno 3 vertici distinti oltre alla chiusura.
    const ring = item.geometry.coordinates[0];
    const vertices = new Set(ring.slice(0, -1).map((p) => `${p[0]},${p[1]}`));
    if (vertices.size < 3) {
      throw new Error(`Il campo ${index + 1} ha meno di 3 vertici distinti.`);
    }

    const props = isRecord(item.properties) ? item.properties : {};
    const name = typeof props.name === "string" ? props.name.trim().slice(0, 48) || null : null;
    const number = typeof props.number === "number" &&
      Number.isSafeInteger(props.number) && props.number > 0 ? props.number : null;

    return {
      // Cloniamo i dati per non conservare oggetti provenienti dal JSON letto.
      coordinates: item.geometry.coordinates.map((r) => r.map((p) => [...p])),
      name,
      number,
    };
  });
}
