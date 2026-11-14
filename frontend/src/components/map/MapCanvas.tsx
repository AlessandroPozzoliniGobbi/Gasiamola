"use client";

import { useEffect, useRef } from "react";
import { Map, ScaleControl, setWorkerUrl } from "maplibre-gl";
import { TerraDraw, TerraDrawPolygonMode, TerraDrawSelectMode } from "terra-draw";
import { TerraDrawMapLibreGLAdapter } from "terra-draw-maplibre-gl-adapter";
import "maplibre-gl/dist/maplibre-gl.css";
import { MAP_CONFIG } from "../../lib/mapConfig";
import {
  getAreaMaskGeoJSON, getAreaOutlineGeoJSON, getOperationalBounds,
  isPointAllowed, isPolygonAllowed,
} from "../../lib/allowedArea";
import type { FieldGeometry } from "../../types/field";
import { isSimpleFieldPolygon } from "../../lib/polygonValidation";

// Manteniamo il worker che funziona gia' nel tuo progetto Next.js.
setWorkerUrl(
  new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).toString()
);

type Props = {
  onMapReady: (map: Map | null) => void;
  onDrawReady: (draw: TerraDraw | null) => void;
  onFieldsChange: (geometries: FieldGeometry[]) => void;
  onSelectedFieldChange: (id: string | null) => void;
  onDrawingFinished: () => void;
};

export default function MapCanvas({
  onMapReady,
  onDrawReady,
  onFieldsChange,
  onSelectedFieldChange,
  onDrawingFinished,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new Map({
      container: containerRef.current,
      style: MAP_CONFIG.style,
      center: MAP_CONFIG.center,
      zoom: MAP_CONFIG.zoom,
      minZoom: MAP_CONFIG.minZoom,
      maxZoom: MAP_CONFIG.maxZoom,
      maxBounds: MAP_CONFIG.maxBounds,
    });
    mapRef.current = map;
    onMapReady(map);

    map.addControl(new ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

    let draw: TerraDraw | null = null;

    const initialize = () => {
      // Lo stile cartografico e' la vista iniziale; il satellite e' nascosto.
      if (MAP_CONFIG.satelliteTileJson) {
        map.addSource("satellite-source", {
          type: "raster",
          url: MAP_CONFIG.satelliteTileJson,
          tileSize: 512,
        });
        map.addLayer({
          id: "satellite-layer",
          type: "raster",
          source: "satellite-source",
          layout: { visibility: "none" },
        });
      }

      // Maschera geografica, SOTTO i poligoni Terra Draw e SOPRA il satellite.
      map.addSource("cremona-mask-source", {
        type: "geojson",
        data: getAreaMaskGeoJSON(),
      });
      map.addLayer({
        id: "cremona-mask-layer",
        source: "cremona-mask-source",
        type: "fill",
        paint: { "fill-color": "#8A9096", "fill-opacity": 0.72 },
      });
      map.addSource("cremona-boundary-source", {
        type: "geojson",
        data: getAreaOutlineGeoJSON(),
      });
      map.addLayer({
        id: "cremona-boundary-layer",
        source: "cremona-boundary-source",
        type: "line",
        paint: { "line-color": "#45515d", "line-width": 2, "line-dasharray": [3, 2] },
      });

      // Validazione unica per disegno e modifica: limiti di Cremona
      // + poligono semplice (nessun incrocio tra lati).
      const validateArea = (
        feature: {
          geometry: { type: string; coordinates?: unknown };
        },
        context?: { updateType?: string },
      ) => {
        if (feature.geometry.type !== "Polygon") return { valid: true };
        if (context?.updateType === "provisional") return { valid: true };

        const coordinates = feature.geometry.coordinates as number[][][];
        // Terra Draw usa geometrie temporanee nei primissimi clic.
        if (!coordinates?.[0] || coordinates[0].length < 4) {
          return { valid: true };
        }

        const valid = isPolygonAllowed(coordinates) &&
          isSimpleFieldPolygon(coordinates);
        return valid
          ? { valid: true }
          : { valid: false, reason: "outside-area-or-self-intersection" };
      };

      // Compatibile anche con versioni di Terra Draw in cui il tipo TS
      // di coordinates non dichiarava ancora la proprieta' validation.
      const coordinateEditOptions = {
        draggable: true,
        midpoints: true,
        deletable: false,
        validation: validateArea,
      };

      draw = new TerraDraw({
        adapter: new TerraDrawMapLibreGLAdapter({ map }),
        modes: [
          new TerraDrawPolygonMode({
            showCoordinatePoints: false,
            pointerDistance: 10,
            keyEvents: { finish: "Enter", cancel: "Escape" },
            // Durante i click il poligono e' ancora incompleto:
            // validiamo forma e confini soltanto quando viene chiuso.
            // La modalita' Select mantiene invece validateArea per le modifiche.
            validation: (feature, context) =>
              context.updateType === "finish"
                ? validateArea(feature, context)
                : { valid: true },
            // Fuori dal cerchio il click non aggiunge nemmeno un vertice.
            pointerEvents: {
              leftClick: (event) => {
                return isPointAllowed([event.lng, event.lat]);
              },
              rightClick: true,
              contextMenu: false,
              onDragStart: true,
              onDrag: true,
              onDragEnd: true,
            },
            styles: {
              fillColor: "#3B82F6",
              fillOpacity: 0.18,
              outlineColor: "#1D4ED8",
              outlineWidth: 3,
              coordinatePointColor: "#FFFFFF",
              coordinatePointWidth: 5,
              coordinatePointOutlineColor: "#1D4ED8",
              coordinatePointOutlineWidth: 2,
              closingPointColor: "#0E7490",
              closingPointWidth: 6,
              closingPointOutlineColor: "#FFFFFF",
              closingPointOutlineWidth: 2,
            },
          }),
          new TerraDrawSelectMode({
            pointerDistance: 10,
            allowManualDeselection: true,
            flags: {
              polygon: {
                feature: {
                  draggable: true,
                  // Blocca il trascinamento di un intero terreno fuori zona.
                  validation: validateArea,
                  // Blocca anche il movimento dei singoli vertici e midpoints.
                  coordinates: coordinateEditOptions,
                },
              },
            },
            styles: {
              selectedPolygonColor: "#2563EB",
              selectedPolygonFillOpacity: 0.17,
              selectedPolygonOutlineColor: "#075985",
              selectedPolygonOutlineWidth: 4,
              selectionPointColor: "#FFFFFF",
              selectionPointWidth: 6,
              selectionPointOutlineColor: "#075985",
              selectionPointOutlineWidth: 3,
              midPointColor: "#0E7490",
              midPointWidth: 5,
              midPointOutlineColor: "#FFFFFF",
              midPointOutlineWidth: 2,
            },
          }),
        ],
      });

      const drawing = draw;
      drawing.start();
      drawing.setMode("static");

      // All'avvio inquadra l'intera zona operativa, anche su schermi piccoli.
      map.fitBounds(getOperationalBounds(), { padding: 28, duration: 0 });

      const syncFields = () => {
        const geometries: FieldGeometry[] = drawing.getSnapshot()
          .filter(
            (feature) =>
              feature.geometry.type === "Polygon" &&
              feature.properties.mode === "polygon" &&
              feature.properties.currentlyDrawing !== true
          )
          .map((feature) => ({
            id: String(feature.id),
            coordinates: (feature.geometry as { coordinates: number[][][] }).coordinates,
          }));
        onFieldsChange(geometries);
      };

      drawing.on("finish", (id, context) => {
        if (context.action !== "draw") return;
        syncFields();
        drawing.setMode("select");
        // Si vedranno solo i punti dell'appezzamento selezionato.
        drawing.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
          showCoordinatePoints: false,
        });
        drawing.selectFeature(id);
        onDrawingFinished();
      });

      drawing.on("select", (id) => onSelectedFieldChange(String(id)));
      drawing.on("deselect", () => onSelectedFieldChange(null));
      drawing.on("change", (_ids, type) => {
        if (type === "create" || type === "update" || type === "delete") {
          syncFields();
        }
      });

      onDrawReady(drawing);
      syncFields();
    };

    map.once("load", initialize);

    return () => {
      map.off("load", initialize);
      onDrawReady(null);
      onMapReady(null);
      if (draw) draw.stop();
      map.remove();
      mapRef.current = null;
    };
  }, [onMapReady, onDrawReady, onFieldsChange, onSelectedFieldChange, onDrawingFinished]);

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label={`Interactive map: area within ${MAP_CONFIG.operationalRadiusKm} kilometers of Cremona`}
      style={{ width: "100%", height: "100%" }}
    />
  );
}
