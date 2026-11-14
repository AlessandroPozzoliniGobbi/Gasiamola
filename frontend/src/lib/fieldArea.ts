import type { FieldItem } from "../types/field";

// Small-area estimate in hectares using a local equirectangular projection.
// Not a cadastral survey; the map's geometry is retained unchanged.
const EARTH_RADIUS_M = 6371008.8;

function signedRingArea(ring: number[][]): number {
  if (ring.length < 4) return 0;
  const avgLat = ring.reduce((total, [, lat]) => total + lat, 0) / ring.length;
  const [originLon, originLat] = ring[0];
  const latFactor = (Math.PI / 180) * EARTH_RADIUS_M;
  const lonFactor = latFactor * Math.cos(avgLat * Math.PI / 180);
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [lon1, lat1] = ring[i];
    const [lon2, lat2] = ring[i + 1];
    const x1 = (lon1 - originLon) * lonFactor;
    const y1 = (lat1 - originLat) * latFactor;
    const x2 = (lon2 - originLon) * lonFactor;
    const y2 = (lat2 - originLat) * latFactor;
    sum += x1 * y2 - x2 * y1;
  }
  return sum / 2;
}

export function estimateFieldHectares(field: FieldItem): number {
  const [outer, ...holes] = field.coordinates;
  if (!outer) return 0;
  const area = Math.max(0, Math.abs(signedRingArea(outer)) - holes.reduce(
    (total, ring) => total + Math.abs(signedRingArea(ring)), 0,
  ));
  return area / 10000;
}
