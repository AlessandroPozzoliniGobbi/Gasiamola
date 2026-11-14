"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS } from "../../lib/analysisStorage";
import { REPORT_METRICS, formatMetric, labelRotation, type CompletedReport,
  type RotationMetrics, type RotationResult } from "../../lib/reportTypes";
import styles from "../../styles/reports.module.css";
import { downloadPdfReport } from "../../lib/reportPrint";
import { downloadExcelReport } from "../../lib/reportExcel";
import HistoricalWindowPlot from "./HistoricalWindowPlot";

type Tab = "overview" | "compare" | "insights" | "economics" | "details";
const TABS: { id: Tab; title: string }[] = [
  { id: "overview", title: "Overview" }, { id: "compare", title: "Compare" },
  { id: "insights", title: "Insights" }, { id: "economics", title: "Economics" },
  { id: "details", title: "Details" },
];
const SHOW_METRICS: (keyof RotationMetrics)[] = [
  "relativeYieldMedian", "irrigationMm", "nitrogenLeachingKgN", "humusChangeTonsHa",
];

function Value({ value, name }: { value: number | null; name: keyof RotationMetrics }) {
  return <span>{formatMetric(name, value)}</span>;
}

function MetricCards({ outcome }: { outcome: RotationResult }) {
  return (
    <div className={styles.metricsGrid}>
      {SHOW_METRICS.map((key) => (
        <div className={styles.metricCard} key={key}>
          <span className={styles.smallCaps}>{REPORT_METRICS.find((m) => m.key === key)?.shortLabel}</span>
          <strong className={styles.metricValue}><Value value={outcome.metrics[key]} name={key} /></strong>
          <span className={styles.mutedTiny}>Model indicator</span>
        </div>
      ))}
    </div>
  );
}

function OutcomeCard({ result, title, highlight = false }: {
  result: RotationResult; title: string; highlight?: boolean;
}) {
  return (
    <article className={`${styles.outcomeCard} ${highlight ? styles.outcomeHighlight : ""}`}>
      <span className={styles.smallCaps}>{title}</span>
      <h3>{labelRotation(result.label)}</h3>
      <p className={styles.footnote}>Relative ranking score: {result.score === null ? "Unavailable" : result.score.toFixed(2)}</p>
      <div className={styles.outcomeFigures}>
        <span>Median relative yield <strong><Value name="relativeYieldMedian" value={result.metrics.relativeYieldMedian} /></strong></span>
        <span>Irrigation <strong><Value name="irrigationMm" value={result.metrics.irrigationMm} /></strong></span>
      </div>
    </article>
  );
}

function ComparisonPlot({ report }: { report: CompletedReport }) {
  const [metric, setMetric] = useState<keyof RotationMetrics>("relativeYieldMedian");
  const selected = REPORT_METRICS.find((m) => m.key === metric)!;
  const entries = [
    { label: "Current", result: report.results.current },
    ...report.results.alternatives.slice(0, 2).map((result, index) => ({ label: `Alternative ${index + 1}`, result })),
  ];
  const values = entries.map((e) => e.result.metrics[metric]).filter((n): n is number => n !== null && Number.isFinite(n));
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const range = Math.max(0.00001, max - min);
  const zeroOffset = ((0 - min) / range) * 100;
  return (
    <section className={styles.panel}>
      <div className={styles.panelHeading}>
        <div>
          <span className={styles.smallCaps}>Comparison chart</span>
          <h3>{selected.label}</h3>
        </div>
        <label className={styles.metricSelector}>
          <span className={styles.srOnly}>Metric to compare</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value as keyof RotationMetrics)}>
            {REPORT_METRICS.map((m) => <option value={m.key} key={m.key}>{m.shortLabel}</option>)}
          </select>
        </label>
      </div>
      <div className={styles.plot} role="group" aria-label={`${selected.label} by crop rotation`}>
        {entries.map((entry, index) => {
          const value = entry.result.metrics[metric];
          const v = value !== null && Number.isFinite(value) ? value : null;
          const start = v === null ? 0 : Math.min(zeroOffset, ((v - min) / range) * 100);
          const width = v === null ? 0 : Math.abs(((v - min) / range) * 100 - zeroOffset);
          return <div className={styles.plotRow} key={index}>
            <div className={styles.plotName}><strong>{entry.label}</strong><span>{labelRotation(entry.result.label)}</span></div>
            <div className={styles.plotTrack}>
              <span className={styles.zeroLine} style={{ left: `${zeroOffset}%` }} />
              {v !== null && <span className={`${styles.plotBar} ${index === 0 ? styles.plotBarCurrent : ""}`}
                style={{ left: `${start}%`, width: `${width}%` }} />}
            </div>
            <strong className={styles.plotValue}>{formatMetric(metric, value)}</strong>
          </div>;
        })}
      </div>
      <p className={styles.footnote}>
        {selected.higherIsBetter ? "Higher values are generally preferable for this indicator." : "Lower values are generally preferable for this indicator."}
        {" "}Chart scale is relative to the values displayed, not a measure of confidence.
      </p>
    </section>
  );
}

function MarginDifference({ value, baseline, isCurrent }: {
  value: number | null; baseline: number | null; isCurrent: boolean;
}) {
  if (isCurrent) {
    return <><strong className={styles.economicBaseline}>Baseline</strong><span className={styles.economicComparison}>Reference rotation · Δ 0 EUR/ha/year</span></>;
  }
  if (value === null || baseline === null || !Number.isFinite(value) || !Number.isFinite(baseline)) {
    return <><strong className={styles.economicUnknown}>Not available</strong><span className={styles.economicComparison}>A comparable margin was not supplied.</span></>;
  }
  const difference = value - baseline;
  const rounded = Math.abs(difference) < 1 ? Math.round(difference * 10) / 10 : Math.round(difference);
  const sign = rounded > 0 ? "+" : rounded < 0 ? "−" : "±";
  const direction = rounded > 0 ? "Higher" : rounded < 0 ? "Lower" : "Unchanged";
  return <>
    <strong className={`${styles.economicDifference} ${difference >= 0 ? styles.economicPositive : styles.economicNegative}`}>
      Δ {sign}{Math.abs(rounded).toLocaleString("en-GB")} <small>EUR/ha/year</small>
    </strong>
    <span className={styles.economicComparison}>{direction} partial margin versus the current rotation</span>
  </>;
}

function BulletSection({ title, items, fallback }: { title: string; items: string[]; fallback: string }) {
  return <div className={styles.bulletBox}>
    <h3>{title}</h3>
    {items.length ? <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
      : <p className={styles.muted}>{fallback}</p>}
  </div>;
}

export default function ReportDashboard({ report, demo = false }: { report: CompletedReport; demo?: boolean }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [pdfExporting, setPdfExporting] = useState(false);
  const [pdfError, setPdfError] = useState<string | null>(null);
  const savePdf = async () => {
    setPdfError(null);
    setPdfExporting(true);
    try { await downloadPdfReport(report, demo); }
    catch (error) { setPdfError(error instanceof Error ? error.message : "PDF export failed."); }
    finally { setPdfExporting(false); }
  };
  // Legacy reports predate the optional advanced-analysis input; preserve their Economics tab.
  const showEconomics = !("advancedEconomics" in report.inputs) || report.inputs.advancedEconomics === true;
  const visibleTabs = TABS.filter((item) => showEconomics || item.id !== "economics");
  useEffect(() => {
    if (tab === "economics" && !showEconomics) setTab("overview");
  }, [tab, showEconomics]);
  const tabIndex = visibleTabs.findIndex((item) => item.id === tab);
  const previousTab = visibleTabs[tabIndex - 1];
  const nextTab = visibleTabs[tabIndex + 1];
  const changeTab = (next: Tab) => {
    setTab(next);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "auto" });
  };
  const best = report.results.alternatives[0] ?? null;
  const visibleNotes = (notes: string[]) => showEconomics ? notes : notes.filter((item) => !/partial gross margin|economic margin/i.test(item));
  const outcomes = [report.results.current, ...report.results.alternatives.slice(0, 2)];
  const date = new Date(report.createdAt);
  const dateLabel = Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

  return (
    <main className={`${styles.page} ${tab === "overview" ? styles.overviewPage : ""}`}>
      <div className={styles.container}>
        <div className={styles.topbar}>
          <Link className={styles.backLink} href="/reports">← All reports</Link>
          <span className={styles.eyebrow}>FIELDWISE / ANALYSIS REPORT</span>
        </div>
        {demo && <div role="status" className={styles.demoBanner}>
          <strong>DEMO PREVIEW — FICTIONAL DATA.</strong> These values are for interface testing only. No FIELDWISE analysis was performed. This report is not saved.
        </div>}
        <header className={styles.reportHeader}>
          <div>
            <span className={styles.eyebrow}>FIELD REPORT · {dateLabel}</span>
            <h1>{report.field.name}</h1>
            <p>Compare rotations, explore environmental trade-offs and see the evidence behind each result.</p>
          </div>
          <div className={styles.exportArea}>
            <button type="button" onClick={savePdf} disabled={pdfExporting}
              title="Download the complete PDF report directly"
              className={styles.secondaryButton}>{pdfExporting ? "Preparing PDF…" : "Export PDF"}</button>
            <button type="button" onClick={() => downloadExcelReport(report, demo)}
              title="Download the tabular data used by all comparison charts"
              className={styles.secondaryButton}>Export Excel</button>
            <small>Download the full PDF or an Excel workbook with the underlying tables.</small>
            {pdfError && <small role="alert" style={{color:"#9b4c22"}}>{pdfError}</small>}
          </div>
        </header>

        <nav className={styles.tabNavigation} aria-label="Report sections">
          {visibleTabs.map((item) => <button type="button" key={item.id} onClick={() => changeTab(item.id)}
            className={`${styles.tabButton} ${tab === item.id ? styles.tabActive : ""}`}
            aria-current={tab === item.id ? "page" : undefined}>
            {item.title}
          </button>)}
        </nav>

        <div className={styles.reportSideNavigation} role="group" aria-label="Navigate report sections">
          {previousTab && <button type="button" className={`${styles.sideArrow} ${styles.sideArrowPrevious}`}
            onClick={() => changeTab(previousTab.id)} aria-label={`Previous section: ${previousTab.title}`}
            title={`Previous: ${previousTab.title}`}><span aria-hidden="true">←</span></button>}
          {nextTab && <button type="button" className={`${styles.sideArrow} ${styles.sideArrowNext}`}
            onClick={() => changeTab(nextTab.id)} aria-label={`Next section: ${nextTab.title}`}
            title={`Next: ${nextTab.title}`}><span aria-hidden="true">→</span></button>}
        </div>

        {tab === "overview" && <div className={styles.content}>
          <section className={styles.recommendation}>
            <div>
              <span className={styles.smallCaps}>01 / ROTATION RECOMMENDATION</span>
              <h2>{best ? labelRotation(best.label) : "No alternative available"}</h2>
              <p>{best ? "Leading alternative for the selected farming priorities. Explore the comparison and its risks below." : "The analysis did not return a viable alternative rotation."}</p>
              <div className={styles.inlineTags}><span>{IRRIGATION_LABELS[report.inputs.irrigation]}</span><span>Historical climate ensemble</span></div>
            </div>
            <div className={styles.recommendationIcon} aria-hidden="true">✳</div>
          </section>
          <h2 className={styles.sectionTitle}>At a glance <span>Recommended alternative</span></h2>
          {best ? <MetricCards outcome={best} /> : <p className={styles.muted}>No alternative metrics available.</p>}
          <div className={styles.splitPanels}>
            <BulletSection title="Why this rotation?" items={visibleNotes(best?.evidence ?? [])} fallback="No evidence supplied by the model." />
            <BulletSection title="What to consider" items={visibleNotes(best?.risks ?? [])} fallback="No risk notes supplied by the model." />
          </div>
        </div>}

        {tab === "compare" && <div className={styles.content}>
          <div className={styles.sectionIntro}><span className={styles.smallCaps}>02 / ROTATION COMPARISON</span><h2>Different paths, clearer trade-offs.</h2>
            <p>Your current strategy and the alternatives selected by the ranking model.</p></div>
          <div className={styles.outcomeGrid}>
            {outcomes.map((item, index) => <OutcomeCard key={`${item.label}-${index}`} result={item}
              title={index === 0 ? "Current rotation" : `Alternative ${index}`} highlight={index === 1} />)}
          </div>
          <ComparisonPlot report={report} />
          <p className={styles.footnote}>Ranking scores are relative to the compared rotation set. They are not probabilities, sustainability percentages or predictions of future yields.</p>
        </div>}

        {tab === "insights" && <div className={styles.content}>
          <div className={styles.sectionIntro}><span className={styles.smallCaps}>03 / MODEL INSIGHTS</span><h2>Understand the uncertainty.</h2>
            <p>Results summarize historical climate scenarios, not a weather forecast for next season.</p></div>
          {report.results.historicalWindows && <HistoricalWindowPlot history={report.results.historicalWindows} showEconomics={showEconomics} />}
          <div className={styles.insightGrid}>
            {outcomes.map((item, index) => <article key={`${item.label}-${index}`} className={styles.panel}>
              <span className={styles.smallCaps}>{index === 0 ? "Current rotation" : `Alternative ${index}`}</span>
              <h3>{labelRotation(item.label)}</h3>
              <div className={styles.insightFigure}><span>Worst-case relative yield</span><strong><Value name="relativeYieldWorst" value={item.metrics.relativeYieldWorst} /></strong></div>
              <div className={styles.insightFigure}><span>10th-percentile relative yield</span><strong><Value name="relativeYieldP10" value={item.metrics.relativeYieldP10} /></strong></div>
            </article>)}
          </div>
          <div className={styles.splitPanels}>
            <BulletSection title="Evidence" items={visibleNotes(best?.evidence ?? [])} fallback="No evidence available." />
            <BulletSection title="Risks and limitations" items={visibleNotes(best?.risks ?? [])} fallback="No specific risk notes available." />
          </div>
          {visibleNotes(report.results.notes).length > 0 && <div className={styles.panel}><h3>Model notes</h3>
            <ul className={styles.noteList}>{visibleNotes(report.results.notes).map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
        </div>}

        {tab === "economics" && showEconomics && <div className={styles.content}>
          {report.results.current.metrics.grossMarginEurHa == null ? (
            <section className={styles.comingSoon}>
              <span className={styles.economicsIcon} aria-hidden="true">€</span>
              <span className={styles.smallCaps}>04 / ECONOMIC OUTLOOK</span>
              <h2>Economic analysis is on its way.</h2>
              <p>The demo preview does not contain economic estimates. Real reports show the engine&apos;s partial gross margin.</p>
              <span className={styles.softPill}>Coming soon</span>
            </section>
          ) : <>
            <div className={styles.sectionIntro}><span className={styles.smallCaps}>04 / ECONOMIC OUTLOOK</span>
              <h2>Economic difference versus today.</h2>
              <p>Each alternative shows the change in annual partial margin relative to your current rotation, not the total revenue.</p>
            </div>
            <div className={styles.outcomeGrid}>
              {outcomes.map((item, index) => <article className={styles.outcomeCard} key={index}>
                <span className={styles.smallCaps}>{index === 0 ? "Current rotation" : `Alternative ${index}`}</span>
                <h3>{labelRotation(item.label)}</h3>
                <MarginDifference value={item.metrics.grossMarginEurHa} baseline={report.results.current.metrics.grossMarginEurHa} isCurrent={index === 0} />
              </article>)}
            </div>
            <div className={styles.panel}><h3>How to read these differences</h3>
              <p>Δ partial margin = alternative margin − current-rotation margin. Each margin is crop revenue minus nitrogen fertilizer and irrigation costs, averaged over historical simulation years (EUR/ha/year).</p>
              <p className={styles.footnote}>Excludes seeds, crop protection, machinery, labor and fixed costs. Prices are static; results are not profit forecasts.</p>
            </div>
          </>}
        </div>}

        {tab === "details" && <div className={`${styles.content} ${styles.detailsCompact}`}>
          <div className={styles.sectionIntro}>
            <span className={styles.smallCaps}>{showEconomics ? "05" : "04"} / ANALYSIS DETAILS</span>
            <h2>Traceable by design.</h2>
            <p>The essentials at a glance. Export PDF for the full technical record, interpretation and charts.</p>
          </div>
          <div className={styles.detailsCompactGrid}>
            <section className={styles.panel}><h3>Field</h3>
              <dl className={styles.compactList}>
                <div><dt>Field</dt><dd>{report.field.name} · #{report.field.number}</dd></div>
                <div><dt>Area</dt><dd>{report.field.areaHectares === null ? "Not available" : `${report.field.areaHectares.toFixed(2)} ha`}</dd></div>
                <div><dt>Reference point</dt><dd>{report.field.representativePoint ? `${report.field.representativePoint[1].toFixed(4)}° N, ${report.field.representativePoint[0].toFixed(4)}° E` : "Not available"}</dd></div>
              </dl>
            </section>
            <section className={styles.panel}><h3>Analysis setup</h3>
              <dl className={styles.compactList}>
                <div><dt>Crop rotation</dt><dd>{report.inputs.rotation.map((r) => `${CROP_LABELS[r.crop]}${r.coverAfter ? " + rye" : ""}`).join(" → ")}</dd></div>
                <div><dt>Irrigation</dt><dd>{IRRIGATION_LABELS[report.inputs.irrigation]}</dd></div>
                <div><dt>Priorities</dt><dd className={styles.compactPriorityText}>
                  {PRIORITY_KEYS.filter((k) => showEconomics || k !== "profitto")
                    .map((k) => `${PRIORITY_LABELS[k]} ${report.inputs.priorities[k] ?? "—"}`).join(" · ")}
                </dd></div>
              </dl>
            </section>
            <section className={styles.panel}><h3>Model &amp; provenance</h3>
              <dl className={styles.compactList}>
                <div><dt>Engine</dt><dd>{report.engine.version ?? "Not provided"}</dd></div>
                <div><dt>Data period</dt><dd>{report.engine.dataPeriod ?? "Not provided"}</dd></div>
                <div><dt>Source</dt><dd>{report.engine.sourceMode === "local_estimate" ? "Local gridded estimate" : report.engine.sourceMode === "pilot_reference" ? "Cremona reference" : report.engine.sourceMode === "pilot_point" ? "Cremona pilot" : "Not specified"}</dd></div>
                <div><dt>Rotations compared</dt><dd>{report.results.comparedRotations ?? "Not provided"}</dd></div>
                {report.engine.localData && <div><dt>Soil</dt><dd>{report.engine.localData.surfaceTexture} · CN {report.engine.localData.curveNumber}</dd></div>}
              </dl>
            </section>
            <section className={styles.panel}><h3>Important limitations</h3>
              <p className={styles.compactCaveat}>{report.engine.sourceMode === "local_estimate" ? "Location-conditioned estimate: gridded NASA POWER climate and SoilGrids soil at one point, not a field-scale measurement or validated forecast." : report.engine.sourceMode === "pilot_reference" ? "Cremona reference dataset: results are based on pilot-point conditions, not this field’s local soil and climate." : "Pilot-point historical comparison; not a forecast for the next growing season."}</p>
              <p className={styles.compactCaveat}>Historical-climate ensemble, not a forecast. Estimates at one representative point may not reflect variations across the field.</p>
              <p className={styles.compactCaveat}>Scores depend on the compared rotations and your priorities. Economic margins exclude several farm costs.</p>
              <p className={styles.compactAside}>Full model notes, individual risks, soil parameters and reproducibility data are included in the PDF.</p>
            </section>
          </div>
        </div>}
        <footer className={styles.footer}>FIELDWISE · Science-led decisions for resilient farming.</footer>
      </div>
    </main>
  );
}
