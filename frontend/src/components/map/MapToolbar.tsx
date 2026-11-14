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
      {mode === "draw" && value === "draw" ? "Cancel drawing" : label}
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
            <button type="button" className={styles.compactAction} onClick={onResetView}>Back to Cremona</button>
            <button type="button" className={styles.compactAction} onClick={onShowAll} disabled={fieldCount === 0}>
              Show all fields
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
