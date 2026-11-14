"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getCompletedReport } from "../../lib/reportStorage";
import type { CompletedReport } from "../../lib/reportTypes";
import ReportDashboard from "./ReportDashboard";
import styles from "../../styles/reports.module.css";

type State = { state: "loading" } | { state: "missing" } | { state: "error"; message: string } | { state: "ready"; report: CompletedReport };
export default function ReportViewer({ reportId }: { reportId: string }) {
  const [status, setStatus] = useState<State>({ state: "loading" });
  useEffect(() => {
    let active = true;
    getCompletedReport(reportId).then((report) => {
      if (active) setStatus(report ? { state: "ready", report } : { state: "missing" });
    }).catch((error: unknown) => {
      if (active) setStatus({ state: "error", message: error instanceof Error ? error.message : "Unable to open report." });
    });
    return () => { active = false; };
  }, [reportId]);
  if (status.state === "ready") return <ReportDashboard report={status.report} />;
  return <main className={styles.page}><div className={styles.container}><div className={styles.emptyState}>
    <span className={styles.emptyIcon} aria-hidden="true">▤</span>
    {status.state === "loading" ? <h1 role="status">Opening your report…</h1> : status.state === "missing" ? <>
      <h1>Report not found</h1><p>This report has not been saved in this browser, or it was deleted.</p>
    </> : <><h1>Could not open report</h1><p role="alert">{status.message}</p></>}
    <Link href="/reports" className={styles.primaryButton}>Back to reports</Link>
  </div></div></main>;
}
