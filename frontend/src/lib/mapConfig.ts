import demoArea from "./demoArea.json";

// La chiave MapTiler rimane nel file frontend/.env.local.
// Non inserire chiavi reali qui: NEXT_PUBLIC_* e' pubblico nel browser.
const mapTilerKey = process.env.NEXT_PUBLIC_MAPTILER_KEY?.trim();

// Area di analisi: un solo centro (il punto pilota del motore) e un solo raggio, nel file
// condiviso con l'API (api.py lo legge e verifica che coincida con il pilota del motore).
export const DEMO_AREA = {
  center: [demoArea.pilotPoint[0], demoArea.pilotPoint[1]] as [number, number],
  radiusKm: demoArea.maxDistanceKm,
};

export const MAP_CONFIG = {
  // Centro della mappa = punto pilota (centro dell'area). MapLibre usa [longitudine, latitudine].
  center: DEMO_AREA.center,
  // I limiti sono un rettangolo di navigazione, non l'area selezionabile.
  zoom: 8,
  minZoom: 6.2,
  maxZoom: 19,
  maxBounds: [
    [7.55, 43.3],
    [12.5, 46.9],
  ] as [[number, number], [number, number]],
  style: "https://tiles.openfreemap.org/styles/liberty",
  satelliteTileJson: mapTilerKey
    ? `https://api.maptiler.com/tiles/satellite-v2/tiles.json?key=${encodeURIComponent(mapTilerKey)}`
    : null,
  // Raggio definito solo in demoArea.json (condiviso con l'API).
  operationalRadiusKm: DEMO_AREA.radiusKm,
};
