"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Map as MapLibreMap } from "maplibre-gl";
import { TerraDrawPolygonMode } from "terra-draw";
import type { TerraDraw } from "terra-draw";
import MapCanvas from "../components/map/MapCanvas";
import MapToolbar from "../components/map/MapToolbar";
import FieldPanel from "../components/map/FieldPanel";
import FloatingFieldWindow from "../components/map/FloatingFieldWindow";
import FieldStoragePanel from "../components/map/FieldStoragePanel";
import FieldLabels from "../components/map/FieldLabels";
import MapStyleSwitcher from "../components/map/MapStyleSwitcher";
import { MAP_CONFIG } from "../lib/mapConfig";
import { getOperationalBounds, isPolygonAllowed } from "../lib/allowedArea";
import { isSimpleFieldPolygon } from "../lib/polygonValidation";
import { getFieldBounds, getSmartMinZoom } from "../lib/fieldGeometry";
import { firstAvailableNumber, nextSavedNumber, prepareImportedFields } from "../lib/fieldNumbers";
import {
  downloadGeoJSON,
  loadSavedFields,
  parseImportedGeoJSON,
  saveFields,
  toTerraDrawFeatures,
  type StorageStatus,
} from "../lib/fieldStorage";
import type { FieldGeometry, FieldItem, MapMode } from "../types/field";
import { deleteAnalysisDraft, replaceAnalysisDrafts, snapshotAnalysisDrafts, type AnalysisDraft } from "../lib/analysisStorage";
import styles from "../styles/map.module.css";

type Basemap = "cartographic" | "satellite";
type FieldMetadata = Pick<FieldItem, "number" | "name">;

export default function MapPage() {
  const router = useRouter();
  const frameRef = useRef<HTMLElement | null>(null);
  const mapAreaRef = useRef<HTMLElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const drawRef = useRef<TerraDraw | null>(null);
  const fieldMetaRef = useRef(new Map<string, FieldMetadata>());
  // Blocca gli eventi Terra Draw durante una sostituzione in corso.
  const replacingRef = useRef(false);
  // Conserviamo l'ultima versione dello stato per il salvataggio in uscita.
  const fieldsRef = useRef<FieldItem[]>([]);
  // Backup dei campi precedenti alla restrizione di Cremona.
  const legacyBackupRef = useRef<FieldItem[] | null>(null);

  const [mapInstance, setMapInstance] = useState<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [mode, setMode] = useState<MapMode>("navigate");
  const [fields, setFields] = useState<FieldItem[]>([]);
  const [selectedFieldId, setSelectedFieldId] = useState<string | null>(null);
  const [basemap, setBasemap] = useState<Basemap>("cartographic");
  const [hydrated, setHydrated] = useState(false);
  const [storageStatus, setStorageStatus] = useState<StorageStatus>("loading");
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [outsideSavedCount, setOutsideSavedCount] = useState(0);
  const [areaWarning, setAreaWarning] = useState<string | null>(null);
  const [fieldWindowOpen, setFieldWindowOpen] = useState(false);
  const previousCountRef = useRef(0);
  const [importFeedback, setImportFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  useEffect(() => {
    fieldsRef.current = fields;
  }, [fields]);

  // Adatta la pagina all'altezza rimasta sotto la navbar effettiva.
  // Evita di indovinare l'altezza della navbar e la striscia vuota in basso.
  useEffect(() => {
    const frame = frameRef.current;
    const mapArea = mapAreaRef.current;
    if (!frame || !mapArea) return;

    const updateLayout = () => {
      const top = Math.max(0, frame.getBoundingClientRect().top);
      frame.style.setProperty("--map-top-offset", `${top}px`);
      mapRef.current?.resize();
    };

    updateLayout();
    const resizeObserver = new ResizeObserver(() => mapRef.current?.resize());
    resizeObserver.observe(mapArea);
    window.addEventListener("resize", updateLayout);
    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("resize", updateLayout);
    };
  }, []);

  // Il pannello appare soltanto quando esistono appezzamenti.
  // Nuovi campi / importazione lo aprono; eliminare tutto lo chiude.
  useEffect(() => {
    if (!ready || !hydrated) return;
    let active = true;
    const nextCount = fields.length;
    const shouldOpen = nextCount > previousCountRef.current;
    previousCountRef.current = nextCount;
    queueMicrotask(() => {
      if (!active) return;
      if (nextCount === 0) setFieldWindowOpen(false);
      else if (shouldOpen) setFieldWindowOpen(true);
    });
    return () => { active = false; };
  }, [fields.length, ready, hydrated]);

  // La pagina /mappa e' una vista applicativa senza scroll desktop.
  // Ripristina l'overflow originale quando si lascia questa pagina.
  useEffect(() => {
    const media = window.matchMedia('(min-width: 769px)');
    const oldBodyOverflow = document.body.style.overflow;
    const oldHtmlOverflow = document.documentElement.style.overflow;
    const apply = () => {
      document.body.style.overflow = media.matches ? 'hidden' : oldBodyOverflow;
      document.documentElement.style.overflow = media.matches ? 'hidden' : oldHtmlOverflow;
    };
    apply();
    media.addEventListener('change', apply);
    return () => {
      media.removeEventListener('change', apply);
      document.body.style.overflow = oldBodyOverflow;
      document.documentElement.style.overflow = oldHtmlOverflow;
    };
  }, []);

  const handleMapReady = useCallback((map: MapLibreMap | null) => {
    mapRef.current = map;
    setMapInstance(map);
  }, []);

  const handleDrawReady = useCallback((draw: TerraDraw | null) => {
    drawRef.current = draw;

    if (!draw) {
      setReady(false);
      setHydrated(false);
      setMode("navigate");
      setSelectedFieldId(null);
      setFields([]);
      setSavedAt(null);
      setOutsideSavedCount(0);
      legacyBackupRef.current = null;
      return;
    }

    try {
      // La lettura avviene SOLO quando Terra Draw e' pronto, e prima
      // che il salvataggio automatico possa sovrascrivere l'archivio.
      const saved = loadSavedFields();
      // Durante il ripristino, gli eventi 'change' possono essere parziali.
      replacingRef.current = true;
      fieldMetaRef.current.clear();

      if (saved) {
        // I campi storici esterni al nuovo raggio NON vengono cancellati
        // dal salvataggio locale: occorre prima una decisione esplicita.
        const inside = saved.fields.filter((field) => isPolygonAllowed(field.coordinates) && isSimpleFieldPolygon(field.coordinates));
        const outside = saved.fields.filter((field) => !isPolygonAllowed(field.coordinates) || !isSimpleFieldPolygon(field.coordinates));
        if (outside.length > 0) {
          legacyBackupRef.current = saved.fields;
          setOutsideSavedCount(outside.length);
        } else {
          legacyBackupRef.current = null;
          setOutsideSavedCount(0);
        }

        inside.forEach((field) => {
          fieldMetaRef.current.set(field.id, {
            number: field.number,
            name: field.name,
          });
        });

        const results = draw.addFeatures(toTerraDrawFeatures(inside));
        if (results.some((result) => !result.valid)) {
          // Evita un ripristino parziale se uno dei poligoni non e' valido.
          const validIds = results.flatMap((result) =>
            result.valid && result.id !== undefined ? [result.id] : []
          );
          if (validIds.length) draw.removeFeatures(validIds);
          throw new Error("Terra Draw rejected one or more saved polygons.");
        }

      }

      // Non attiviamo il salvataggio finche' l'utente non ha gestito
      // i vecchi campi esterni al cerchio (evita perdite di dati).
      if (legacyBackupRef.current) {
        setStorageStatus("error");
        setHydrated(false);
      } else {
        setStorageStatus("saved");
        setHydrated(true);
      }
    } catch (error) {
      console.error("Could not restore saved fields:", error);
      // Non salviamo dati nuovi sopra un archivio che non riusciamo a leggere.
      setStorageStatus("error");
      setHydrated(false);
    } finally {
      replacingRef.current = false;
    }

    setReady(true);
  }, []);

  const handleFieldsChange = useCallback((geometries: FieldGeometry[]) => {
    // Gli eventi di clear() / addFeatures() non devono produrre stati intermedi.
    if (replacingRef.current) return;

    // Seconda barriera di sicurezza: anche se un comportamento di editing
    // scavalcasse la validazione di Terra Draw, non salviamo geometrie esterne.
    const invalid = geometries.filter((field) =>
      !isPolygonAllowed(field.coordinates) || !isSimpleFieldPolygon(field.coordinates)
    );
    if (invalid.length) {
      const draw = drawRef.current;
      if (draw) {
        replacingRef.current = true;
        try {
          for (const geometry of invalid) {
            const previous = fieldsRef.current.find((field) => field.id === geometry.id);
            if (previous) {
              draw.updateFeatureGeometry(geometry.id, {
                type: "Polygon", coordinates: previous.coordinates,
              });
            } else if (draw.hasFeature(geometry.id)) {
              draw.removeFeatures([geometry.id]);
            }
          }
        } finally {
          replacingRef.current = false;
        }
      }
      setAreaWarning("Change canceled: the field crossed the permitted boundary or contained intersecting edges.");
      return;
    }

    const activeIds = new Set(geometries.map((geometry) => geometry.id));
    // Also clean up configurations if Terra Draw deletes a field by keyboard
    // or another route, instead of the explicit Delete button.
    const removedIds = fieldsRef.current.map((field) => field.id).filter((id) => !activeIds.has(id));
    if (removedIds.length) {
      try {
        const remainingDrafts = snapshotAnalysisDrafts();
        for (const id of removedIds) delete remainingDrafts[id];
        replaceAnalysisDrafts(remainingDrafts);
      } catch (error) {
        console.error("Unable to clear settings for removed fields:", error);
        setStorageStatus("error");
      }
    }
    // Scartiamo i metadati degli appezzamenti che non esistono piu'.
    for (const id of fieldMetaRef.current.keys()) {
      if (!activeIds.has(id)) fieldMetaRef.current.delete(id);
    }

    const usedNumbers = new Set(
      [...fieldMetaRef.current.values()].map((field) => field.number)
    );

    const updated = geometries.map((geometry) => {
      let meta = fieldMetaRef.current.get(geometry.id);
      if (!meta) {
        // Primo numero LIBERO: 1, 2, 3, 5 -> 4.
        const number = firstAvailableNumber(usedNumbers);
        usedNumbers.add(number);
        meta = { number, name: `Field ${number}` };
        fieldMetaRef.current.set(geometry.id, meta);
      }
      return { ...geometry, ...meta };
    });

    fieldsRef.current = updated;
    setFields(updated);
  }, []);

  const handleSelectedFieldChange = useCallback((id: string | null) => {
    setSelectedFieldId(id);
  }, []);

  const handleDrawingFinished = useCallback(() => {
    setAreaWarning(null);
    setMode("select");
  }, []);

  // Salva nome, numerazione e geometrie dopo ogni modifica completata.
  // Un breve debounce evita scritture ripetute durante il trascinamento.
  useEffect(() => {
    if (!ready || !hydrated) return;

    let active = true;
    queueMicrotask(() => { if (active) setStorageStatus("saving"); });
    const timer = window.setTimeout(() => {
      try {
        saveFields(fields, nextSavedNumber(fields));
        setSavedAt(new Date().toLocaleTimeString("en-GB", {
          hour: "2-digit", minute: "2-digit", second: "2-digit",
        }));
        setStorageStatus("saved");
      } catch (error) {
        console.error("Could not save fields:", error);
        setStorageStatus("error");
      }
    }, 350);

    return () => { active = false; window.clearTimeout(timer); };
  }, [fields, ready, hydrated]);

  // Se si chiude la scheda subito dopo una modifica, salviamo lo stato
  // piu' recente prima che il browser abbandoni la pagina.
  useEffect(() => {
    if (!ready || !hydrated) return;

    const flush = () => {
      try {
        saveFields(fieldsRef.current, nextSavedNumber(fieldsRef.current));
      } catch (error) {
        console.error("Could not save fields before leaving:", error);
      }
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "hidden") flush();
    };

    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      // Copre anche la navigazione tra le pagine all'interno di Next.js.
      flush();
    };
  }, [ready, hydrated]);

  // Gestione esplicita del backup creato prima del cambio zona.
  const handleLegacyBackup = () => {
    if (legacyBackupRef.current) downloadGeoJSON(legacyBackupRef.current);
  };

  const handleAcceptArea = () => {
    const previous = legacyBackupRef.current;
    if (!previous) return;
    const removed = previous.filter((field) =>
      !isPolygonAllowed(field.coordinates) || !isSimpleFieldPolygon(field.coordinates)
    ).length;
    if (!window.confirm(
      `Remove ${removed} out-of-area or invalid fields from saved data?\n` +
      "Download the full backup first if you want to keep them."
    )) return;
    try {
      const kept = new Set(fieldsRef.current.map((field) => field.id));
      const previousDrafts = snapshotAnalysisDrafts();
      replaceAnalysisDrafts(Object.fromEntries(
        Object.entries(previousDrafts).filter(([id]) => kept.has(id))
      ));
    } catch (error) {
      console.error("Unable to remove analysis settings for excluded fields:", error);
      window.alert("Could not update saved analysis settings. Your fields have not been changed.");
      return;
    }
    legacyBackupRef.current = null;
    setOutsideSavedCount(0);
    setHydrated(true);
    setStorageStatus("saving");
    setAreaWarning(null);
  };

  const handleExportFields = () => {
    if (fields.length === 0) return;
    try {
      downloadGeoJSON(fields);
    } catch (error) {
      console.error("GeoJSON export failed:", error);
      window.alert("Could not export GeoJSON. Please try again.");
    }
  };

  // L'importazione SOSTITUISCE la configurazione corrente, dopo conferma.
  // Il salvataggio automatico vede solo lo stato finale, mai una mappa vuota.
  const handleImportFields = async (file: File) => {
    setImportFeedback(null);
    const draw = drawRef.current;

    if (!draw || !ready || !hydrated || replacingRef.current) {
      setImportFeedback({
        kind: "error",
        message: "Wait until the map is ready before importing.",
      });
      return;
    }

    // Conserviamo una copia per un eventuale rollback.
    const previousFields = fields.map((field) => ({
      ...field,
      coordinates: field.coordinates.map((ring) =>
        ring.map((point) => [...point])
      ),
    }));

    try {
      if (file.size > 3_000_000) {
        throw new Error("The file exceeds the 3 MB limit.");
      }

      // PRIMA validiamo completamente il file: nessun campo viene modificato.
      const imported = parseImportedGeoJSON(await file.text());
      // Controlliamo PRIMA di chiedere conferma o cancellare i campi attuali.
      const invalidIndex = imported.findIndex((item) =>
        !isPolygonAllowed(item.coordinates) || !isSimpleFieldPolygon(item.coordinates)
      );
      if (invalidIndex !== -1) {
        throw new Error(
          `Field ${invalidIndex + 1} is outside the permitted area or has intersecting edges. ` +
          "The current fields have not been changed."
        );
      }
      const prepared = prepareImportedFields(imported);
      const replacement: FieldItem[] = prepared.map((item) => ({
        number: item.number,
        name: item.name,
        coordinates: item.coordinates,
        // Restoring a FIELDWISE backup preserves identity. Generic GeoJSON
        // always creates new fields (even at the same location with the same name).
        id: item.backupId ?? String(draw.getFeatureId()),
      }));
      const restoredDrafts: Record<string, AnalysisDraft> = Object.create(null);
      replacement.forEach((field, i) => {
        if (prepared[i].analysis) restoredDrafts[field.id] = prepared[i].analysis;
      });

      if (fields.length > 0) {
        const confirmed = window.confirm(
          `Import ${replacement.length} fields and REPLACE the current ${fields.length}?\n\n` +
          "Your current fields AND their analysis settings will be replaced. " +
          "Export your FIELDWISE configuration first if you want to keep them."
        );
        if (!confirmed) return;
      }

      // Keep the previous configurations for rollback if import fails.
      const previousDrafts = snapshotAnalysisDrafts();
      // Gli eventi generati dalla rimozione non devono assegnare altri numeri
      // o provocare un salvataggio dello stato intermedio vuoto.
      replacingRef.current = true;
      try {
        draw.setMode("static");
        draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
          showCoordinatePoints: false,
        });
        draw.clear();

        const results = draw.addFeatures(toTerraDrawFeatures(replacement));
        if (results.some((result) => !result.valid)) {
          throw new Error("Terra Draw rejected one or more fields.");
        }

        // Replace field-associated analysis settings together with the map.
        // Never match configurations by field name, number or geometry.
        replaceAnalysisDrafts(restoredDrafts);
        saveFields(replacement, nextSavedNumber(replacement));

        // Sincronizziamo una sola volta Terra Draw, metadati e React.
        fieldMetaRef.current = new Map(replacement.map((field) => [
          field.id, { number: field.number, name: field.name },
        ]));
        fieldsRef.current = replacement;
        setFields(replacement);
        setSelectedFieldId(null);
        setMode("navigate");
        mapRef.current?.setMinZoom(MAP_CONFIG.minZoom);

        setImportFeedback({
          kind: "success",
          message: `Configuration restored: ${replacement.length} fields and their saved analysis settings.`,
        });
      } catch (importError) {
        // Ripristiniamo gli appezzamenti precedenti se l'aggiunta fallisce.
        try {
          draw.clear();
          const restored = draw.addFeatures(toTerraDrawFeatures(previousFields));
          if (restored.some((result) => !result.valid)) {
            throw new Error("Some existing fields could not be restored.");
          }
          fieldMetaRef.current = new Map(previousFields.map((field) => [
            field.id, { number: field.number, name: field.name },
          ]));
          replaceAnalysisDrafts(previousDrafts);
          saveFields(previousFields, nextSavedNumber(previousFields));
          fieldsRef.current = previousFields;
          setFields(previousFields);
        } catch (rollbackError) {
          console.error("Restore failed after import:", rollbackError);
          // Inibiamo i salvataggi, per non perdere il backup locale valido.
          setHydrated(false);
          setStorageStatus("error");
          throw new Error(
            "Import failed and the previous fields could not all be restored. " +
            "Do not reload or edit fields. Restore your GeoJSON backup."
          );
        }
        throw importError;
      } finally {
        replacingRef.current = false;
      }
    } catch (error) {
      setImportFeedback({
        kind: "error",
        message: error instanceof Error
          ? error.message
          : "Could not import the GeoJSON file.",
      });
    }
  };

  // Lo zoom-out segue le dimensioni del campo selezionato.
  // In modalita' Naviga ritorna al limite base della Pianura Padana.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const selected = mode === "select"
      ? fields.find((field) => field.id === selectedFieldId)
      : undefined;
    const minimum = selected ? getSmartMinZoom(map, selected) : MAP_CONFIG.minZoom;
    if (Math.abs(map.getMinZoom() - minimum) > 0.01) map.setMinZoom(minimum);
  }, [mode, selectedFieldId, fields]);

  const handleModeChange = (newMode: MapMode) => {
    const draw = drawRef.current;
    if (!draw) return;
    setAreaWarning(null);

    if (newMode === "draw") {
      draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
        showCoordinatePoints: true,
      });
      draw.setMode("polygon");
      setSelectedFieldId(null);
    } else {
      draw.setMode(newMode === "select" ? "select" : "static");
      draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
        showCoordinatePoints: false,
      });
      if (newMode === "navigate") setSelectedFieldId(null);
    }
    setMode(newMode);
  };

  // Escape termina il disegno parziale e restituisce la navigazione.
  useEffect(() => {
    if (mode !== "draw") return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const draw = drawRef.current;
      if (!draw) return;
      draw.setMode("static");
      draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
        showCoordinatePoints: false,
      });
      setMode("navigate");
      setSelectedFieldId(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [mode]);

  const handleSelectField = (id: string) => {
    const draw = drawRef.current;
    const map = mapRef.current;
    const field = fields.find((item) => item.id === id);
    if (!draw || !map || !field) return;

    draw.setMode("select");
    draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
      showCoordinatePoints: false,
    });
    draw.selectFeature(id);
    setMode("select");
    setSelectedFieldId(id);

    const bounds = getFieldBounds([field]);
    if (bounds) {
      map.fitBounds(bounds, { padding: 72, maxZoom: 17.5, duration: 650 });
    }
  };

  const handleAnalyzeField = (id: string) => {
    if (!ready || !hydrated || !fieldsRef.current.some((field) => field.id === id)) return;

    // Il salvataggio della mappa e' normalmente posticipato di 350 ms.
    // Forziamolo prima di cambiare pagina, altrimenti Analizza potrebbe
    // leggere dal localStorage una versione precedente del terreno.
    try {
      saveFields(fieldsRef.current, nextSavedNumber(fieldsRef.current));
      setStorageStatus("saved");
    } catch (error) {
      console.error("Could not save the field before analysis:", error);
      setStorageStatus("error");
      window.alert("Could not save the field. Check your browser settings and try again.");
      return;
    }

    router.push(`/analizza/${encodeURIComponent(id)}`);
  };

  const handleRenameField = (id: string, name: string) => {
    const trimmed = name.trim().slice(0, 48);
    const meta = fieldMetaRef.current.get(id);
    if (!meta) return;
    const finalName = trimmed || `Field ${meta.number}`;
    fieldMetaRef.current.set(id, { ...meta, name: finalName });
    setFields((previous) => previous.map((field) =>
      field.id === id ? { ...field, name: finalName } : field
    ));
  };

  const handleShowAll = () => {
    const map = mapRef.current;
    const draw = drawRef.current;
    if (!map || fields.length === 0) return;

    if (draw) {
      draw.setMode("static");
      draw.updateModeOptions<typeof TerraDrawPolygonMode>("polygon", {
        showCoordinatePoints: false,
      });
    }
    setSelectedFieldId(null);
    setMode("navigate");
    map.setMinZoom(MAP_CONFIG.minZoom);

    const bounds = getFieldBounds(fields);
    if (bounds) map.fitBounds(bounds, { padding: 65, maxZoom: 16, duration: 750 });
  };

  const handleDeleteField = (id: string) => {
    const draw = drawRef.current;
    const field = fields.find((item) => item.id === id);
    if (!draw || !field) return;
    if (!window.confirm(`Delete ${field.name} (#${field.number})?`)) return;

    try {
      // Deleted identities must never leave settings that could be reused.
      deleteAnalysisDraft(id);
    } catch (error) {
      console.error("Unable to delete field analysis settings:", error);
      window.alert("Could not update saved analysis settings. The field was not deleted.");
      return;
    }
    draw.removeFeatures([id]);
    fieldMetaRef.current.delete(id);
    setFields((previous) => previous.filter((item) => item.id !== id));
    if (selectedFieldId === id) setSelectedFieldId(null);
  };

  const handleClearFields = () => {
    const draw = drawRef.current;
    if (!draw || fields.length === 0) return;
    if (!window.confirm("Delete all fields?")) return;

    try {
      replaceAnalysisDrafts({});
    } catch (error) {
      console.error("Unable to delete saved analysis settings:", error);
      window.alert("Could not update saved analysis settings. Fields were not deleted.");
      return;
    }
    draw.setMode("static");
    draw.clear();
    fieldMetaRef.current.clear();
    setFields([]);
    setSelectedFieldId(null);
    setMode("navigate");
    mapRef.current?.setMinZoom(MAP_CONFIG.minZoom);
  };

  const handleToggleBasemap = () => {
    const map = mapRef.current;
    if (!map?.getLayer("satellite-layer")) return;
    const next: Basemap = basemap === "satellite" ? "cartographic" : "satellite";
    map.setLayoutProperty("satellite-layer", "visibility", next === "satellite" ? "visible" : "none");
    setBasemap(next);
  };

  const handleResetView = () => {
    handleModeChange("navigate");
    const map = mapRef.current;
    if (!map) return;
    map.setMinZoom(MAP_CONFIG.minZoom);
    map.resetNorth({ duration: 0 });
    map.fitBounds(getOperationalBounds(), { padding: 28, duration: 700 });
  };

  return (
    <main ref={frameRef} className={styles.mapFrame}>
      <aside className={styles.sidebar} aria-label="Map tools">
        <div className={styles.sidebarIntro}>
          <h1 className={styles.title}>Cremona field map</h1>
          <p className={styles.description}>
            Explore and outline fields within {MAP_CONFIG.operationalRadiusKm} km of Cremona.
          </p>
          <div
            className={[
              styles.storageIndicator,
              storageStatus === "saving" ? styles.storageIndicatorSaving : "",
              storageStatus === "error" ? styles.storageIndicatorError : "",
            ].join(" ")}
            role="status"
            aria-live="polite"
          >
            {outsideSavedCount > 0
              ? "Saving paused: some field geometries need review."
              : storageStatus === "loading"
                ? "Loading fields…"
                : storageStatus === "saving"
                  ? "Saving…"
                  : storageStatus === "error"
                    ? "Saving unavailable."
                    : savedAt
                      ? `Automatically saved at ${savedAt}`
                      : "Autosave is active"}
          </div>
        </div>

        {outsideSavedCount > 0 && (
          <div role="alert" className={styles.areaNotice}>
            <strong>{outsideSavedCount} saved fields are incompatible</strong>
            <p>Download the full backup first, then you can keep only valid field geometries.</p>
            <button type="button" className={styles.compactAction} onClick={handleLegacyBackup}>Download backup</button>
            <button type="button" className={styles.compactAction} onClick={handleAcceptArea}>Keep only valid fields</button>
          </div>
        )}

        {areaWarning && (
          <p className={styles.areaNotice} role="status" aria-live="polite">{areaWarning}</p>
        )}

        <MapToolbar
          onZoomIn={() => mapRef.current?.zoomIn({ duration: 300 })}
          onZoomOut={() => mapRef.current?.zoomOut({ duration: 300 })}
          onResetNorth={() => mapRef.current?.resetNorth({ duration: 400 })}
          onResetView={handleResetView}
          onShowAll={handleShowAll}
          onModeChange={handleModeChange}
          mode={mode}
          ready={ready && hydrated}
          fieldCount={fields.length}
        />

        <FieldStoragePanel
          count={fields.length}
          ready={ready && hydrated}
          onExport={handleExportFields}
          onImport={handleImportFields}
          importFeedback={importFeedback}
        />

        {/* Tendina presente solo se esistono campi. Si apre da sola
            alla creazione/importazione, e si puo' richiudere/riaprire. */}
        {fields.length > 0 && (
          <>
            <button
              type="button"
              className={styles.fieldsDropdownTrigger}
              onClick={() => setFieldWindowOpen((opened) => !opened)}
              aria-expanded={fieldWindowOpen}
              aria-controls="fields-floating-panel"
            >
              <span>Fields <span className={styles.fieldCountBadge}>{fields.length}</span></span>
              <span className={styles.summaryChevron} aria-hidden="true">{fieldWindowOpen ? '⌃' : '⌄'}</span>
            </button>
            {fieldWindowOpen && (
              <FloatingFieldWindow
                count={fields.length}
                onClose={() => setFieldWindowOpen(false)}
              >
                <FieldPanel
                  fields={fields}
                  selectedFieldId={selectedFieldId}
                  onSelectField={handleSelectField}
                  onAnalyzeField={handleAnalyzeField}
                  onRenameField={handleRenameField}
                  onDeleteField={handleDeleteField}
                  onClearFields={handleClearFields}
                  ready={ready && hydrated}
                />
              </FloatingFieldWindow>
            )}
          </>
        )}
      </aside>

      <section ref={mapAreaRef} className={styles.mapArea} aria-label="Geographical view">
        <MapCanvas
          onMapReady={handleMapReady}
          onDrawReady={handleDrawReady}
          onFieldsChange={handleFieldsChange}
          onSelectedFieldChange={handleSelectedFieldChange}
          onDrawingFinished={handleDrawingFinished}
        />
        <FieldLabels map={mapInstance} fields={fields} selectedFieldId={selectedFieldId} />
        <MapStyleSwitcher
          basemap={basemap}
          onToggle={handleToggleBasemap}
          disabled={!ready || !MAP_CONFIG.satelliteTileJson}
        />

      </section>

    </main>
  );
}
