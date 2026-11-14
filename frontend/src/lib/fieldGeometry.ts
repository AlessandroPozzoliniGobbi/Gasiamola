import type { Map as MapLibreMap } from "maplibre-gl";
import polylabel from "polylabel";
import type { FieldItem } from "../types/field";
import { MAP_CONFIG } from "./mapConfig";

type LngLatTuple = [number, number];
export type FieldBounds = [LngLatTuple, LngLatTuple];

type PlanarPoint = [number, number];
const EARTH_RADIUS_METERS = 6371008.8;

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

// Centroid of the area, rather than the centre of the bounding box or
// polylabel's "farthest from every edge" point. All calculations use local
// metre coordinates to avoid treating a longitude degree as a latitude degree.
function ringCentroid(ring: PlanarPoint[]): { point: PlanarPoint; area: number } | null {
  const n = ring.length;
  if (n < 3) return null;
  let twiceArea = 0;
  let sumX = 0;
  let sumY = 0;
  for (let i = 0; i < n; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % n];
    const cross = x1 * y2 - x2 * y1;
    twiceArea += cross;
    sumX += (x1 + x2) * cross;
    sumY += (y1 + y2) * cross;
  }
  if (Math.abs(twiceArea) < 1e-8) return null;
  return {
    point: [sumX / (3 * twiceArea), sumY / (3 * twiceArea)],
    area: Math.abs(twiceArea) / 2,
  };
}

function inRing(point: PlanarPoint, ring: PlanarPoint[]): boolean {
  const [px, py] = point;
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [ax, ay] = ring[j];
    const [bx, by] = ring[i];
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const t = len2 > 0 ? ((px - ax) * dx + (py - ay) * dy) / len2 : 0;
    if (t >= 0 && t <= 1 && Math.hypot(px - (ax + t * dx), py - (ay + t * dy)) < 1e-7) {
      return true;
    }
    if ((ay > py) !== (by > py) && px < ax + ((py - ay) * dx) / (by - ay)) {
      inside = !inside;
    }
  }
  return inside;
}

function inPolygon(point: PlanarPoint, rings: PlanarPoint[][]): boolean {
  return !!rings[0] && inRing(point, rings[0]) &&
    !rings.slice(1).some((hole) => inRing(point, hole));
}

function clearanceFromBoundary(point: PlanarPoint, rings: PlanarPoint[][]): number {
  let minDist = Infinity;
  for (const ring of rings) {
    for (let i = 0; i < ring.length; i++) {
      const a = ring[i];
      const b = ring[(i + 1) % ring.length];
      const dx = b[0] - a[0];
      const dy = b[1] - a[1];
      const len2 = dx * dx + dy * dy;
      const t = len2 ? Math.max(0, Math.min(1,
        ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / len2)) : 0;
      minDist = Math.min(minDist,
        Math.hypot(point[0] - a[0] - t * dx, point[1] - a[1] - t * dy));
    }
  }
  return minDist;
}

/**
 * Visually central, guaranteed-inside reference point for both map labels and
 * the single-point Analysis preview. For most fields this is the area centroid.
 * If the centroid falls outside a concave polygon (or into a hole), move from
 * the centroid towards an interior safe point until the label has some margin.
 * This function never alters the actual field geometry.
 */
export function getLabelPosition(field: FieldItem): LngLatTuple {
  const outer = field.coordinates[0];
  if (!outer || outer.length < 4) {
    const first = outer?.[0];
    return first ? [first[0], first[1]] : MAP_CONFIG.center;
  }

  const minLon = Math.min(...outer.map((p) => p[0]));
  const maxLon = Math.max(...outer.map((p) => p[0]));
  const minLat = Math.min(...outer.map((p) => p[1]));
  const maxLat = Math.max(...outer.map((p) => p[1]));
  const originLon = (minLon + maxLon) / 2;
  const originLat = (minLat + maxLat) / 2;
  const metersPerDeg = Math.PI * EARTH_RADIUS_METERS / 180;
  const xScale = metersPerDeg * Math.cos(originLat * Math.PI / 180);
  const yScale = metersPerDeg;
  const project = ([lon, lat]: number[]): PlanarPoint => [
    (lon - originLon) * xScale,
    (lat - originLat) * yScale,
  ];
  const unproject = ([x, y]: PlanarPoint): LngLatTuple => [
    originLon + x / xScale,
    originLat + y / yScale,
  ];
  const rings = field.coordinates.map((ring) => ring.map(project));
  const parts = rings.map(ringCentroid);
  const outerPart = parts[0];
  if (!outerPart) return [outer[0][0], outer[0][1]];

  let totalArea = outerPart.area;
  let weightedX = outerPart.point[0] * totalArea;
  let weightedY = outerPart.point[1] * totalArea;
  for (let i = 1; i < parts.length; i++) {
    const hole = parts[i];
    if (!hole) continue;
    totalArea -= hole.area;
    weightedX -= hole.point[0] * hole.area;
    weightedY -= hole.point[1] * hole.area;
  }
  if (totalArea <= 0) return unproject(outerPart.point);
  const centroid: PlanarPoint = [weightedX / totalArea, weightedY / totalArea];

  // For normal polygons, the centroid is exactly the visually central result.
  if (inPolygon(centroid, rings)) return unproject(centroid);

  // Concave and holed shapes can have centroids outside their actual area.
  // polylabel is used only as an inside anchor, not as the final label position.
  const safe = polylabel(rings, 0.5) as PlanarPoint;
  if (!inPolygon(safe, rings)) return unproject(outerPart.point);
  const minMargin = Math.min(10, clearanceFromBoundary(safe, rings) * 0.15);
  for (let i = 0; i <= 200; i++) {
    const t = i / 200;
    const p: PlanarPoint = [
      centroid[0] * (1 - t) + safe[0] * t,
      centroid[1] * (1 - t) + safe[1] * t,
    ];
    if (inPolygon(p, rings) && clearanceFromBoundary(p, rings) >= minMargin) {
      return unproject(p);
    }
  }
  return unproject(safe);
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

// The long side of a field must remain at least 80 px while editing.
export function getSmartMinZoom(map: MapLibreMap, field: FieldItem): number {
  const { width, height } = getFieldPixelSize(map, field);
  const currentSize = Math.max(width, height, 1);
  const minForField = map.getZoom() + Math.log2(80 / currentSize);

  return Math.min(
    MAP_CONFIG.maxZoom - 0.5,
    Math.max(MAP_CONFIG.minZoom, minForField)
  );
}
