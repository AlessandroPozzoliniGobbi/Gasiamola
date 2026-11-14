"use client";

import { useEffect, useRef } from "react";
import { Marker } from "maplibre-gl";
import type { Map as MapLibreMap } from "maplibre-gl";
import type { FieldItem } from "../../types/field";
import { getFieldPixelSize, getLabelPosition } from "../../lib/fieldGeometry";
import styles from "../../styles/map.module.css";

type Props = {
  map: MapLibreMap | null;
  fields: FieldItem[];
  selectedFieldId: string | null;
};

export default function FieldLabels({ map, fields, selectedFieldId }: Props) {
  const markersRef = useRef(new Map<string, Marker>());

  useEffect(() => {
    if (!map) return;

    const markers = markersRef.current;
    const existingIds = new Set(fields.map((field) => field.id));

    // Rimuove solo le etichette di campi cancellati.
    for (const [id, marker] of markers) {
      if (!existingIds.has(id)) {
        marker.remove();
        markers.delete(id);
      }
    }

    for (const field of fields) {
      let marker = markers.get(field.id);
      if (!marker) {
        const element = document.createElement("div");
        element.style.pointerEvents = "none"; // I clic raggiungono Terra Draw.
        marker = new Marker({ element, anchor: "center" })
          .setLngLat(getLabelPosition(field))
          .addTo(map);
        markers.set(field.id, marker);
      } else {
        marker.setLngLat(getLabelPosition(field));
      }
    }

    const updateLabels = () => {
      for (const field of fields) {
        const marker = markers.get(field.id);
        if (!marker) continue;

        const { width, height } = getFieldPixelSize(map, field);
        const requiredWidth = Math.max(110, 42 + field.name.length * 7);
        const showName = width >= requiredWidth && height >= 40;
        const element = marker.getElement();

        // textContent evita interpretazioni HTML dei nomi scelti dall'utente.
        element.textContent = showName
          ? `${field.number} · ${field.name}`
          : String(field.number);

        // Non sovrascriviamo className: MapLibre aggiunge una classe
        // necessaria per posizionare correttamente il Marker.
        element.classList.add(styles.fieldLabel);
        element.classList.toggle(styles.fieldLabelExpanded, showName);
        element.classList.toggle(styles.fieldLabelCompact, !showName);
        element.classList.toggle(styles.fieldLabelSelected, selectedFieldId === field.id);
      }
    };

    updateLabels();
    map.on("zoom", updateLabels);
    map.on("resize", updateLabels);
    map.on("rotate", updateLabels);
    map.on("pitch", updateLabels);

    return () => {
      map.off("zoom", updateLabels);
      map.off("resize", updateLabels);
      map.off("rotate", updateLabels);
      map.off("pitch", updateLabels);
    };
  }, [map, fields, selectedFieldId]);

  // Elimina i marker quando si abbandona la pagina o cambia la mappa.
  useEffect(() => {
    const markers = markersRef.current; // the same Map for the component's lifetime
    return () => {
      for (const marker of markers.values()) marker.remove();
      markers.clear();
    };
  }, [map]);

  return null;
}
