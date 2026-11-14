"use client";

import { useEffect, useRef, useState } from "react";
import { Map, setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FieldItem } from "../../types/field";
import { getFieldBounds, getLabelPosition } from "../../lib/fieldGeometry";
import { MAP_CONFIG } from "../../lib/mapConfig";
import styles from "../../styles/analysis.module.css";

setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString());

type Basemap = "cartographic" | "satellite";

export default function AnalysisFieldMap({ field }: { field: FieldItem }) {
  const elementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("cartographic");
  const [satelliteReady, setSatelliteReady] = useState(false);
  const [mapLoaded, setMapLoaded] = useState(false);

  useEffect(() => {
    const node = elementRef.current;
    if (!node) return;
    const point = getLabelPosition(field);
    const map = new Map({
      container: node,
      style: MAP_CONFIG.style,
      center: point,
      zoom: 15,
      pitch: 0,
      bearing: 0,
      // This is a read-only preview. Only the explicit basemap button works.
      interactive: false,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    const fitField = () => {
      const bounds = getFieldBounds([field]);
      if (bounds) map.fitBounds(bounds, { padding: 34, maxZoom: 17, duration: 0 });
    };

    const onLoad = () => {
      const polygon = {
        type: "Feature" as const,
        properties: { name: field.name },
        geometry: { type: "Polygon" as const, coordinates: field.coordinates },
      };
      if (MAP_CONFIG.satelliteTileJson) {
        map.addSource("analysis-satellite", {
          type: "raster",
          url: MAP_CONFIG.satelliteTileJson,
          tileSize: 512,
        });
        map.addLayer({
          id: "analysis-satellite",
          type: "raster",
          source: "analysis-satellite",
          layout: { visibility: "none" }, // Street map is always the initial view.
        });
        setSatelliteReady(true);
      }
      map.addSource("selected-field", { type: "geojson", data: polygon });
      map.addLayer({
        id: "selected-field-fill",
        type: "fill",
        source: "selected-field",
        paint: { "fill-color": "#4fb4e3", "fill-opacity": 0.10 },
      });
      map.addLayer({
        id: "selected-field-outline",
        type: "line",
        source: "selected-field",
        paint: { "line-color": "#0781a5", "line-width": 3 },
      });
      map.addSource("analysis-point", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: point },
        },
      });
      map.addLayer({
        id: "analysis-point-layer",
        type: "circle",
        source: "analysis-point",
        paint: {
          "circle-radius": 5,
          "circle-color": "#fff",
          "circle-stroke-color": "#176b4b",
          "circle-stroke-width": 2.5,
        },
      });
      map.resize();
      fitField();
      setMapLoaded(true);
    };
    const onError = () => {
      if (!map.isStyleLoaded()) setError("The map could not be loaded. Check your connection.");
    };
    map.on("load", onLoad);
    map.on("error", onError);
    const observer = new ResizeObserver(() => {
      map.resize();
      if (map.isStyleLoaded()) fitField();
    });
    observer.observe(node);
    return () => {
      observer.disconnect();
      map.off("load", onLoad);
      map.off("error", onError);
      mapRef.current = null;
      map.remove();
    };
  }, [field]);

  function chooseBasemap(next: Basemap) {
    const map = mapRef.current;
    if (!map || !mapLoaded || next === basemap) return;
    if (next === "satellite" && !satelliteReady) return;
    if (map.getLayer("analysis-satellite")) {
      map.setLayoutProperty("analysis-satellite", "visibility", next === "satellite" ? "visible" : "none");
    }
    setBasemap(next);
  }

  return (
    <div className={styles.mapPreview}>
      {/* The basemap controls sit ABOVE the map, rather than covering the field. */}
      <div className={styles.mapViewToolbar}>
        <span className={styles.mapViewTitle}>MAP VIEW</span>
        <div className={styles.mapViewOptions} role="group" aria-label="Map background">
          <button type="button" aria-pressed={basemap === "cartographic"}
            className={`${styles.mapViewButton} ${basemap === "cartographic" ? styles.mapViewActive : ""}`}
            onClick={() => chooseBasemap("cartographic")} disabled={!mapLoaded}>
            Street
          </button>
          <button type="button" aria-pressed={basemap === "satellite"}
            className={`${styles.mapViewButton} ${basemap === "satellite" ? styles.mapViewActive : ""}`}
            onClick={() => chooseBasemap("satellite")} disabled={!mapLoaded || !satelliteReady}
            title={!MAP_CONFIG.satelliteTileJson ? "Satellite imagery requires the MapTiler key" : undefined}>
            Satellite
          </button>
        </div>
      </div>
      <div className={styles.mapShell}>
        <div ref={elementRef} className={styles.mapCanvas}
          aria-label={`Read-only map showing the boundaries of ${field.name}`} role="region" />
        {error && <div className={styles.mapError} role="alert">{error}</div>}
        {!mapLoaded && !error && <span className={styles.mapLoading} role="status">Loading map…</span>}
      </div>
    </div>
  );
}
