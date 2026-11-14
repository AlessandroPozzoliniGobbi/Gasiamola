// La chiave MapTiler rimane nel file frontend/.env.local.
// Non inserire chiavi reali qui: NEXT_PUBLIC_* e' pubblico nel browser.
const mapTilerKey = process.env.NEXT_PUBLIC_MAPTILER_KEY?.trim();

export const MAP_CONFIG = {
  // Centro di Cremona. MapLibre usa [longitudine, latitudine].
  center: [10.024423, 45.133635] as [number, number],
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
  // Cambia qui il raggio se deciderete di restringere/espandere il progetto.
  operationalRadiusKm: 100,
};
