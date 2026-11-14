/**
 * Valida l'inviluppo di un appezzamento (un solo anello, senza fori).
 * Rifiuta poligoni ad anello aperto, lati degeneri, vertici ripetuti,
 * area nulla e intersezioni tra lati non consecutivi.
 *
 * Le coordinate GeoJSON sono [longitudine, latitudine].
 * Non verifica la sovrapposizione tra appezzamenti differenti.
 */
export function isSimpleFieldPolygon(coordinates: number[][][]): boolean {
  if (!Array.isArray(coordinates) || coordinates.length !== 1) return false;
  const ring = coordinates[0];
  if (!Array.isArray(ring) || ring.length < 4) return false;

  const isPoint = (p: number[]) =>
    Array.isArray(p) && p.length >= 2 &&
    Number.isFinite(p[0]) && Number.isFinite(p[1]);

  if (!ring.every(isPoint)) return false;

  const same = (a: number[], b: number[]) =>
    Math.abs(a[0] - b[0]) < 1e-12 && Math.abs(a[1] - b[1]) < 1e-12;

  if (!same(ring[0], ring[ring.length - 1])) return false;

  const vertices = ring.slice(0, -1);
  const n = vertices.length;
  if (n < 3) return false;

  // Nessun vertice deve essere ripetuto (esclusa la chiusura GeoJSON).
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (same(vertices[i], vertices[j])) return false;
    }
  }

  // Area non nulla (formula del laccio, su coordinate locali per stabilita').
  const base = vertices[0];
  let twiceArea = 0;
  for (let i = 0; i < n; i++) {
    const a = vertices[i];
    const b = vertices[(i + 1) % n];
    twiceArea += (a[0] - base[0]) * (b[1] - base[1]) -
      (b[0] - base[0]) * (a[1] - base[1]);
  }
  if (Math.abs(twiceArea) <= 1e-14) return false;

  const orient = (a: number[], b: number[], c: number[]) =>
    (b[0] - a[0]) * (c[1] - a[1]) -
    (b[1] - a[1]) * (c[0] - a[0]);

  const onSegment = (a: number[], b: number[], p: number[]) =>
    Math.abs(orient(a, b, p)) <= 1e-14 &&
    p[0] >= Math.min(a[0], b[0]) - 1e-12 &&
    p[0] <= Math.max(a[0], b[0]) + 1e-12 &&
    p[1] >= Math.min(a[1], b[1]) - 1e-12 &&
    p[1] <= Math.max(a[1], b[1]) + 1e-12;

  const intersects = (a: number[], b: number[], c: number[], d: number[]) => {
    const o1 = orient(a, b, c);
    const o2 = orient(a, b, d);
    const o3 = orient(c, d, a);
    const o4 = orient(c, d, b);
    const eps = 1e-14;

    if (Math.abs(o1) <= eps && onSegment(a, b, c)) return true;
    if (Math.abs(o2) <= eps && onSegment(a, b, d)) return true;
    if (Math.abs(o3) <= eps && onSegment(c, d, a)) return true;
    if (Math.abs(o4) <= eps && onSegment(c, d, b)) return true;

    return ((o1 > eps && o2 < -eps) || (o1 < -eps && o2 > eps)) &&
      ((o3 > eps && o4 < -eps) || (o3 < -eps && o4 > eps));
  };

  // Due lati adiacenti condividono legittimamente un estremo.
  // Tutte le altre coppie NON devono incrociarsi né toccarsi.
  for (let i = 0; i < n; i++) {
    const a = vertices[i];
    const b = vertices[(i + 1) % n];
    for (let j = i + 1; j < n; j++) {
      if (j === i + 1 || (i === 0 && j === n - 1)) continue;
      const c = vertices[j];
      const d = vertices[(j + 1) % n];
      if (intersects(a, b, c, d)) return false;
    }
  }
  return true;
}
