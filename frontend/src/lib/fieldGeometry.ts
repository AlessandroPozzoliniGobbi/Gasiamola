import type { Map as MapLibreMap } from "maplibre-gl";
import polylabel from "polylabel";
import type { FieldItem } from "../types/field";
import { MAP_CONFIG } from "./mapConfig";

type LngLatTuple = [number, number];
export type FieldBounds = [LngLatTuple, LngLatTuple];

export function getFieldBounds(fields: FieldItem[]): FieldBounds | null {
  const coordinates = fields.flatMap((field) => field.coordinates.flat());
  if (!coordinates.length) return null;

  const lngs = coordinates.map((coordinate) => coordinate[0]);
  const lats = coordinates.map((coordinate) => coordinate[1]);

  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ];
}

// A differenza del centro del rettangolo, questo punto cade dentro il poligono.
export function getLabelPosition(field: FieldItem): LngLatTuple {
  const rings = field.coordinates.map((ring) =>
    ring.map((coordinate) => [coordinate[0], coordinate[1]] as LngLatTuple)
  );

  if (!rings[0] || rings[0].length < 4) {
    const first = field.coordinates[0]?.[0];
    return first ? [first[0], first[1]] : MAP_CONFIG.center;
  }

  const result = polylabel(rings, 0.000001);
  return [result[0], result[1]];
}

export function getFieldPixelSize(map: MapLibreMap, field: FieldItem) {
  const positions = field.coordinates[0] ?? [];
  if (!positions.length) return { width: 0, height: 0 };

  const points = positions.map(([lng, lat]) => map.project([lng, lat]));
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);

  return {
    width: Math.max(...xs) - Math.min(...xs),
    height: Math.max(...ys) - Math.min(...ys),
  };
}

// Nella modalita' Modifica il lato maggiore del campo rimane >= 80 px.
// La soglia e' un compromesso, modificabile in futuro.
export function getSmartMinZoom(map: MapLibreMap, field: FieldItem): number {
  const { width, height } = getFieldPixelSize(map, field);
  const currentSize = Math.max(width, height, 1);
  const minForField = map.getZoom() + Math.log2(80 / currentSize);

  return Math.min(
    MAP_CONFIG.maxZoom - 0.5,
    Math.max(MAP_CONFIG.minZoom, minForField)
  );
}
