import { MAP_CONFIG } from "./mapConfig";

/**
 * MapTiler TileJSON can succeed even if a raster image is blocked by a key
 * restriction, browser extension or network policy. Test one real tile as
 * well, using the same XYZ template as MapLibre. Never include keys in UI errors.
 */
export async function checkSatelliteAccess(signal?: AbortSignal): Promise<string | null> {
  if (!MAP_CONFIG.satelliteTileJson) {
    return "Satellite unavailable: add NEXT_PUBLIC_MAPTILER_KEY to frontend/.env.local and restart Next.js. For Vercel, add it to the project environment and redeploy.";
  }
  try {
    const response = await fetch(MAP_CONFIG.satelliteTileJson, { signal, cache: "no-store" });
    if (response.status === 401 || response.status === 403) {
      return `MapTiler denied satellite access (HTTP ${response.status}). Check the API key and Allowed HTTP origins: localhost, 127.0.0.1 and your production domain.`;
    }
    if (!response.ok) return `MapTiler satellite metadata returned HTTP ${response.status}.`;
    const tileJson: unknown = await response.json();
    const tiles = tileJson && typeof tileJson === "object"
      ? (tileJson as { tiles?: unknown }).tiles : undefined;
    if (!Array.isArray(tiles) || typeof tiles[0] !== "string") {
      return "MapTiler returned an unexpected satellite tileset response.";
    }

    // Web Mercator tile at the pilot-region center, zoom 10. The map requests
    // raster tiles in exactly this format when Satellite is selected.
    const z = 10;
    const [lng, lat] = MAP_CONFIG.center;
    const n = 2 ** z;
    const x = Math.max(0, Math.min(n - 1, Math.floor(((lng + 180) / 360) * n)));
    const rad = (Math.max(-85.0511, Math.min(85.0511, lat)) * Math.PI) / 180;
    const y = Math.max(0, Math.min(n - 1, Math.floor((1 - Math.asinh(Math.tan(rad)) / Math.PI) * n / 2)));
    const tileUrl = tiles[0].replace("{z}", String(z))
      .replace("{x}", String(x)).replace("{y}", String(y));
    const tileResponse = await fetch(tileUrl, { signal, cache: "no-store" });
    if (tileResponse.status === 401 || tileResponse.status === 403) {
      return `MapTiler blocked satellite imagery (HTTP ${tileResponse.status}). Check your key and the site's Allowed HTTP origin.`;
    }
    if (!tileResponse.ok) return `Satellite imagery could not be loaded (HTTP ${tileResponse.status}).`;
    if (!(tileResponse.headers.get("content-type") ?? "").startsWith("image/")) {
      return "MapTiler did not return a satellite image; verify that the tileset is enabled for your key.";
    }
    return null;
  } catch {
    if (signal?.aborted) return null;
    return "Satellite tiles were blocked or unreachable. Check browser extensions, MapTiler Allowed HTTP origins and the Network tab.";
  }
}
