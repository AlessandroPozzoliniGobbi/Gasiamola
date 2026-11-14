"use client";

import styles from "../../styles/reports.module.css";

/** Ready for future API job polling; no simulated progress or fake time estimate. */
export default function AnalysisProcessing({ fieldName, stage }: {
  fieldName: string;
  stage?: string;
}) {
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <section className={styles.processingScreen} role="status" aria-live="polite">
          <span className={styles.processingSpinner} aria-hidden="true" />
          <span className={styles.eyebrow}>FIELDWISE / ANALYSIS IN PROGRESS</span>
          <h1>Analyzing your field...</h1>
          <p>{stage ?? "We're turning environmental data into informed farming decisions."}</p>
          <span className={styles.processingField}>{fieldName}</span>
          <small>This screen will update when the simulation has finished.</small>
        </section>
      </div>
    </main>
  );
}
