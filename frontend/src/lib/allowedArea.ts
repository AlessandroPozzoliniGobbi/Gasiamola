import { MAP_CONFIG } from "./mapConfig";

export type LngLat = [number, number];
const EARTH_RADIUS_KM = 6371.0088;
const TO_RAD = Math.PI / 180;
const TO_DEG = 180 / Math.PI;

/** Distanza geodetica (approssimazione sferica), in chilometri. */
export function distanceFromCremonaKm(position: readonly number[]): number {
  if (position.length < 2 || !Number.isFinite(position[0]) || !Number.isFinite(position[1])) {
    return Infinity;
  }
  const [lng, lat] = position;
  const [centerLng, centerLat] = MAP_CONFIG.center;
  const deltaLat = (lat - centerLat) * TO_RAD;
  const deltaLng = (lng - centerLng) * TO_RAD;
  const a = Math.sin(deltaLat / 2) ** 2 +
    Math.cos(centerLat * TO_RAD) * Math.cos(lat * TO_RAD) * Math.sin(deltaLng / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

export function isPointAllowed(position: readonly number[]): boolean {
  return distanceFromCremonaKm(position) <= MAP_CONFIG.operationalRadiusKm + 0.001;
}

/**
 * L'intero poligono deve rimanere nel cerchio, non solo il suo centro.
 * Campioniamo anche i bordi tra vertici per coprire segmenti lunghi.
 */
export function isPolygonAllowed(coordinates: number[][][]): boolean {
  if (!Array.isArray(coordinates) || coordinates.length === 0) return false;
  return coordinates.every((ring) => {
    if (!Array.isArray(ring) || ring.length < 4) return false;
    for (let index = 0; index < ring.length; index++) {
      const a = ring[index];
      const b = ring[(index + 1) % ring.length];
      if (!isPointAllowed(a) || !isPointAllowed(b)) return false;
      const segmentLength = Math.max(
        Math.abs(a[0] - b[0]) * 78,
        Math.abs(a[1] - b[1]) * 111
      );
      const steps = Math.min(300, Math.max(1, Math.ceil(segmentLength / 2)));
      for (let step = 1; step < steps; step++) {
        const fraction = step / steps;
        if (!isPointAllowed([
          a[0] + (b[0] - a[0]) * fraction,
          a[1] + (b[1] - a[1]) * fraction,
        ])) return false;
      }
    }
    return true;
  });
}

/** Cerchio geodetico: 256 segmenti per una linea visivamente fluida. */
export function getOperationalCircle(): LngLat[] {
  const [lng, lat] = MAP_CONFIG.center;
  const lat1 = lat * TO_RAD;
  const lng1 = lng * TO_RAD;
  const distance = MAP_CONFIG.operationalRadiusKm / EARTH_RADIUS_KM;
  const points: LngLat[] = [];

  for (let i = 0; i < 256; i++) {
    const bearing = (i / 256) * 2 * Math.PI;
    const lat2 = Math.asin(
      Math.sin(lat1) * Math.cos(distance) +
      Math.cos(lat1) * Math.sin(distance) * Math.cos(bearing)
    );
    const lng2 = lng1 + Math.atan2(
      Math.sin(bearing) * Math.sin(distance) * Math.cos(lat1),
      Math.cos(distance) - Math.sin(lat1) * Math.sin(lat2)
    );
    points.push([lng2 * TO_DEG, lat2 * TO_DEG]);
  }
  points.push([...points[0]] as LngLat);
  return points;
}

export function getOperationalBounds(): [LngLat, LngLat] {
  const circle = getOperationalCircle();
  return [
    [Math.min(...circle.map((p) => p[0])), Math.min(...circle.map((p) => p[1]))],
    [Math.max(...circle.map((p) => p[0])), Math.max(...circle.map((p) => p[1]))],
  ];
}

/**
 * Polygon con foro: tutta la zona esterna viene oscurata.
 * Rettangolo esterno antiorario, anello interno (cerchio) orario.
 */
export function getAreaMaskGeoJSON() {
  const outer: LngLat[] = [
    [-10, 20], [30, 20], [30, 65], [-10, 65], [-10, 20],
  ];
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "Polygon" as const,
      coordinates: [outer, getOperationalCircle()],
    },
  };
}

export function getAreaOutlineGeoJSON() {
  return {
    type: "Feature" as const,
    properties: {},
    geometry: {
      type: "LineString" as const,
      coordinates: getOperationalCircle(),
    },
  };
}
