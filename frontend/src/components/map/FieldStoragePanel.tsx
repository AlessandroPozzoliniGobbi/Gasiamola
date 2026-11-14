"use client";

import { useRef, useState } from "react";
import type { ChangeEvent } from "react";
import styles from "../../styles/map.module.css";

type Props = {
  count: number;
  ready: boolean;
  onExport: () => void;
  onImport: (file: File) => Promise<void>;
  importFeedback: { kind: "success" | "error"; message: string } | null;
};

export default function FieldStoragePanel({
  count,
  ready,
  onExport,
  onImport,
  importFeedback,
}: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file || !ready) return;

    setImporting(true);
    try {
      await onImport(file);
    } finally {
      setImporting(false);
    }
  }

  return (
    <details className={styles.mapAccordion}>
      <summary className={styles.mapAccordionSummary}>
        <span>Saved fields and files</span>
        <span className={styles.summaryChevron} aria-hidden="true">⌄</span>
      </summary>
      <div className={styles.mapAccordionBody}>
        <p className={styles.storageHelp}>
          Fields are saved automatically in this browser.
          Export your FIELDWISE configuration as GeoJSON, including each field’s analysis settings.
          Importing a configuration replaces the current fields and settings.
        </p>
        <div className={styles.storageActions}>
          <button
            type="button"
            className={styles.compactAction}
            onClick={onExport}
            disabled={!ready || count === 0 || importing}
          >
            Export configuration
          </button>

          <input
            ref={inputRef}
            type="file"
            accept=".geojson,.json,application/geo+json,application/json"
            onChange={handleFileChange}
            className={styles.visuallyHiddenFileInput}
            aria-label="Choose a GeoJSON file to import"
            tabIndex={-1}
          />
          <button
            type="button"
            className={styles.compactAction}
            onClick={() => inputRef.current?.click()}
            disabled={!ready || importing}
          >
            {importing ? "Importing…" : "Import configuration"}
          </button>
        </div>
        {importFeedback && (
          <p
            className={`${styles.storageFeedback} ${importFeedback.kind === "error" ? styles.importError : styles.importSuccess}`}
            role={importFeedback.kind === "error" ? "alert" : "status"}
          >
            {importFeedback.message}
          </p>
        )}
      </div>
    </details>
  );
}
