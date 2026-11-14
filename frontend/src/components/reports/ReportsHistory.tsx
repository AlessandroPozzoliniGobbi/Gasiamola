"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { deleteCompletedReport, listRecentReports, MAX_SAVED_REPORTS } from "../../lib/reportStorage";
import { labelRotation, type ReportSummary } from "../../lib/reportTypes";
import styles from "../../styles/reports.module.css";
import PortfolioHistory from "../portfolio/PortfolioHistory";

type HistoryState = { status: "loading" } | { status: "ready"; items: ReportSummary[] } | { status: "error"; message: string };

export default function ReportsHistory() {
  const [state, setState] = useState<HistoryState>({ status: "loading" });
  const [removingId, setRemovingId] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      setState({ status: "ready", items: await listRecentReports() });
    } catch (error) {
      setState({ status: "error", message: error instanceof Error ? error.message : "Unable to read saved reports." });
    }
  }, []);
  useEffect(() => {
    queueMicrotask(() => { void refresh(); });
  }, [refresh]);

  async function removeReport(report: ReportSummary) {
    if (!window.confirm(`Permanently delete the saved report for “${report.field.name}”? This cannot be undone.`)) return;
    setRemovingId(report.id);
    try { await deleteCompletedReport(report.id); await refresh(); }
    catch (error) { setState({ status: "error", message: error instanceof Error ? error.message : "Unable to delete this report." }); }
    finally { setRemovingId(null); }
  }

  return <main className={`${styles.page} ${styles.historyPage}`}>
    <div className={styles.container}>
      <div className={styles.historyIntro}>
        <span className={styles.eyebrow}>FIELDWISE / SAVED REPORTS</span>
        <h1>Your Analysis History</h1>
        <p>Revisit completed analyses, explore past decisions and compare your fields over time.</p>
      </div>
      <PortfolioHistory />
      <div className={styles.historyHeading}>
        <div><h2>Recent analyses</h2><span>Saved on this browser only · Maximum {MAX_SAVED_REPORTS}</span></div>
        <Link className={styles.primaryButton} href="/mappa">Analyze a field ↗</Link>
      </div>
      {state.status === "loading" && <section className={styles.emptyState} role="status">Loading saved reports…</section>}
      {state.status === "error" && <section className={styles.emptyState} role="alert"><h2>Reports unavailable</h2><p>{state.message}</p><button className={styles.secondaryButton} onClick={() => void refresh()}>Try again</button></section>}
      {state.status === "ready" && (state.items.length === 0 ?
        <section className={styles.emptyState}>
          <span className={styles.emptyIcon} aria-hidden="true">▤</span>
          <h2>No analyses yet.</h2>
          <p>Your completed field reports will appear here automatically after you complete an analysis.</p>
          <Link className={styles.primaryButton} href="/mappa">Explore your fields ↗</Link>
        </section>
        : <div className={styles.historyList}>
          {state.items.map((r) => <article key={r.id} className={styles.historyRow}>
            <div className={styles.historyGlyph} aria-hidden="true">▤</div>
            <div className={styles.historyInfo}>
              <div className={styles.historyTitle}><h3>{r.field.name}</h3><span>{new Date(r.createdAt).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}</span></div>
              <p>Current: {labelRotation(r.rotationLabel)}</p>
              <p>Recommendation: {r.recommendationText ?? (r.recommendedLabel ? labelRotation(r.recommendedLabel) : "Keep the current rotation")}</p>
            </div>
            <div className={styles.historyActions}>
              <Link className={styles.openReport} href={`/reports/${encodeURIComponent(r.id)}`}>Open report →</Link>
              <button className={styles.deleteReport} type="button" onClick={() => void removeReport(r)} disabled={removingId === r.id} aria-label={`Delete report for ${r.field.name}`}>Delete</button>
            </div>
          </article>)}
        </div>)}
      <p className={styles.storageNote}>Reports stay on this browser and device. Clearing site data or using another browser can remove access to them. Keep a local PDF or Excel copy for long-term archiving.</p>
    </div>
  </main>;
}
