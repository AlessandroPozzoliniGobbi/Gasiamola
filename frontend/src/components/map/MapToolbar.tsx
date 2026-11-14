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
      {mode === "draw" && value === "draw" ? "Annulla disegno" : label}
    </button>
  );

  return (
    <details className={styles.mapAccordion} open>
      <summary className={styles.mapAccordionSummary}>
        <span>Navigazione e strumenti</span>
        <span className={styles.summaryChevron} aria-hidden="true">⌄</span>
      </summary>

      <div className={styles.mapAccordionBody}>
        <div className={styles.toolsColumns}>
          <section className={styles.toolsColumn} aria-label="Navigazione mappa">
            <h2 className={styles.toolsColumnTitle}>Mappa</h2>
            <div className={styles.compactZoomRow}>
              <button type="button" className={styles.compactZoomButton} onClick={onZoomIn} aria-label="Ingrandisci mappa" title="Ingrandisci">+</button>
              <button type="button" className={styles.compactZoomButton} onClick={onZoomOut} aria-label="Riduci mappa" title="Riduci">−</button>
              <button type="button" className={styles.compactZoomButton} onClick={onResetNorth} aria-label="Orientamento nord" title="Rimetti il nord in alto">N↑</button>
            </div>
            <button type="button" className={styles.compactAction} onClick={onResetView}>Torna a Cremona</button>
            <button type="button" className={styles.compactAction} onClick={onShowAll} disabled={fieldCount === 0}>
              Mostra tutti i campi
            </button>
          </section>

          <section className={styles.toolsColumn} aria-label="Disegno appezzamenti">
            <h2 className={styles.toolsColumnTitle}>Appezzamenti</h2>
            {modeButton("navigate", "Naviga")}
            {modeButton("draw", "Disegna")}
            {modeButton("select", "Seleziona / Modifica")}
          </section>
        </div>

        <p className={styles.toolHint} role="status">
          {mode === "draw"
            ? "Clicca per i vertici. Invio completa, Esc annulla."
            : mode === "select"
              ? "Seleziona un campo e trascina i vertici per correggerlo."
              : "Usa gli strumenti a destra per disegnare o modificare."}
        </p>
      </div>
    </details>
  );
}
