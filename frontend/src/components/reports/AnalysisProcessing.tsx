"use client";

import { useEffect, useState } from "react";
import styles from "../../styles/reports.module.css";

/** Shows backend-reported stages and actual elapsed time, never fake progress. */
export default function AnalysisProcessing({ fieldName, stage }: {
  fieldName: string;
  stage?: string;
}) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const elapsed = `${Math.floor(elapsedSeconds / 60)}:${String(elapsedSeconds % 60).padStart(2, "0")}`;
  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <section className={styles.processingScreen} role="status" aria-live="polite" aria-atomic="false">
          <div className={styles.processingSpinnerWrap} aria-hidden="true">
            <span className={styles.processingSpinner} />
            <span className={styles.processingSpinnerCenter}>FW</span>
          </div>
          <span className={styles.eyebrow}>FIELDWISE / ANALYSIS IN PROGRESS</span>
          <h1>Analyzing your field</h1>
          <p className={styles.processingStage}>{stage ?? "Preparing your field analysis..."}</p>
          <span className={styles.processingField}>{fieldName}</span>
          <div className={styles.processingElapsed}>Elapsed time <strong>{elapsed}</strong></div>
          <small>Preparing local environmental data may take longer on the first run. This is real elapsed time, not an estimated completion time.</small>
        </section>
      </div>
    </main>
  );
}
