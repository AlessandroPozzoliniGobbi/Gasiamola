import type { ReactNode } from "react";
import type { MapMode } from "../../types/field";
import styles from "../../styles/map.module.css";

type Props = {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetNorth: () => void;
  onResetView: () => void;
  onShowAll: () => void;
  onModeChange: (mode: MapMode) => void;
  mode: MapMode;
  ready: boolean;
  fieldCount: number;
};

function ToolIcon({ kind }: { kind: MapMode | "center" | "bounds" }) {
  const paths: Record<MapMode | "center" | "bounds", ReactNode> = {
    navigate: <><path d="m5 3 13 9-6 1-2.5 6L5 3Z" /></>,
    draw: <><path d="M4 19 18 5l2 2L6 21H4v-2Z" /><path d="m14 9 2 2" /></>,
    select: <><path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5" /><path d="m9 13 3-3 3 3-3 3z" /></>,
    center: <><circle cx="12" cy="12" r="8" /><path d="M12 2v4M12 18v4M2 12h4M18 12h4" /></>,
    bounds: <><path d="M4 10V4h6M14 4h6v6M20 14v6h-6M10 20H4v-6" /></>,
  };
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[kind]}</svg>;
}

export default function MapToolbar({
  onZoomIn,
  onZoomOut,
  onResetNorth,
  onResetView,
  onShowAll,
  onModeChange,
  mode,
  ready,
  fieldCount,
}: Props) {
  const modeButton = (value: MapMode, label: string) => (
    <button
      type="button"
      className={`${styles.compactAction} ${mode === value ? styles.compactActive : ""}`}
      onClick={() =>
        onModeChange(mode === value && value === "draw" ? "navigate" : value)
      }
      disabled={!ready || (value === "select" && fieldCount === 0)}
      aria-pressed={mode === value}
    >
      <ToolIcon kind={value} />
      <span>{mode === "draw" && value === "draw" ? "Cancel drawing" : label}</span>
    </button>
  );

  return (
    <details className={styles.mapAccordion} open>
      <summary className={styles.mapAccordionSummary}>
        <span>Navigation and tools</span>
        <span className={styles.summaryChevron} aria-hidden="true">⌄</span>
      </summary>

      <div className={styles.mapAccordionBody}>
        <div className={styles.toolsColumns}>
          <section className={styles.toolsColumn} aria-label="Map navigation">
            <h2 className={styles.toolsColumnTitle}>Map</h2>
            <div className={styles.compactZoomRow}>
              <button type="button" className={styles.compactZoomButton} onClick={onZoomIn} aria-label="Zoom in on map" title="Zoom in">+</button>
              <button type="button" className={styles.compactZoomButton} onClick={onZoomOut} aria-label="Zoom out on map" title="Zoom out">−</button>
              <button type="button" className={styles.compactZoomButton} onClick={onResetNorth} aria-label="Point north" title="Reset bearing to north">N↑</button>
            </div>
            <button type="button" className={styles.compactAction} onClick={onResetView}><ToolIcon kind="center" /> <span>Back to Cremona</span></button>
            <button type="button" className={styles.compactAction} onClick={onShowAll} disabled={fieldCount === 0}>
              <ToolIcon kind="bounds" /> <span>Show all fields</span>
            </button>
          </section>

          <section className={styles.toolsColumn} aria-label="Field drawing">
            <h2 className={styles.toolsColumnTitle}>Fields</h2>
            {modeButton("navigate", "Navigate")}
            {modeButton("draw", "Draw")}
            {modeButton("select", "Select / Edit")}
          </section>
        </div>

        <p className={styles.toolHint} role="status">
          {mode === "draw"
            ? "Click to add vertices. Press Enter to finish or Esc to cancel."
            : mode === "select"
              ? "Select a field and drag its vertices to edit it."
              : "Use the tools on the right to draw or edit fields."}
        </p>
      </div>
    </details>
  );
}
