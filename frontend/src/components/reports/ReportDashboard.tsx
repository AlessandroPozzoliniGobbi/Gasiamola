"use client";

import { useState } from "react";
import Link from "next/link";
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS } from "../../lib/analysisStorage";
import { REPORT_METRICS, formatMetric, labelRotation, type CompletedReport,
  type RotationMetrics, type RotationResult } from "../../lib/reportTypes";
import styles from "../../styles/reports.module.css";
import { downloadMarkdownReport } from "../../lib/reportMarkdown";

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

function BulletSection({ title, items, fallback }: { title: string; items: string[]; fallback: string }) {
  return <div className={styles.bulletBox}>
    <h3>{title}</h3>
    {items.length ? <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
      : <p className={styles.muted}>{fallback}</p>}
  </div>;
}

export default function ReportDashboard({ report, demo = false }: { report: CompletedReport; demo?: boolean }) {
  const [tab, setTab] = useState<Tab>("overview");
  const best = report.results.alternatives[0] ?? null;
  const outcomes = [report.results.current, ...report.results.alternatives.slice(0, 2)];
  const date = new Date(report.createdAt);
  const dateLabel = Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

  return (
    <main className={`${styles.page} ${tab === "overview" ? styles.overviewPage : ""} ${demo ? styles.demoPage : ""}`}>
      <div className={styles.container}>
        <div className={styles.topbar}>
          <Link className={styles.backLink} href="/reports">← All reports</Link>
          <span className={styles.eyebrow}>FIELDWISE / ANALYSIS REPORT</span>
        </div>
        {demo && <div role="status" className={styles.demoBanner}>
          <strong>DEMO PREVIEW — FICTIONAL DATA.</strong> These values are for interface testing only. No FIELDWISE analysis was performed. This report is not saved.
        </div>}
        {report.engine.sourceMode === "pilot_reference" &&
          <div className={styles.demoBanner} role="status"><strong>CREMONA REFERENCE DATASET.</strong> This report uses pilot-point climate and soil data, not measurements for this field. It is an exploratory comparison only.</div>}
        {report.engine.sourceMode === "local_estimate" &&
          <div className={styles.demoBanner} role="status"><strong>LOCATION-CONDITIONED ESTIMATE.</strong> Local NASA POWER and SoilGrids predictions are used at one representative point. This is experimental, not a measured or validated field-scale forecast.</div>}
        <header className={styles.reportHeader}>
          <div>
            <span className={styles.eyebrow}>FIELD REPORT · {dateLabel}</span>
            <h1>{report.field.name}</h1>
            <p>Compare rotations, explore environmental trade-offs and see the evidence behind each result.</p>
          </div>
          <div className={styles.exportArea}>
            <button type="button" disabled title="PDF export will be enabled after backend integration" className={styles.secondaryButton}>Export PDF</button>
            <button type="button" disabled={demo} onClick={() => downloadMarkdownReport(report)}
              title={demo ? "Not available for fictional demo data" : "Download a Markdown copy of this completed report"}
              className={styles.secondaryButton}>Export Markdown</button>
            <small>PDF export is planned; Markdown is available for completed reports.</small>
          </div>
        </header>

        <nav className={styles.tabNavigation} aria-label="Report sections">
          {TABS.map((item) => <button type="button" key={item.id} onClick={() => setTab(item.id)}
            className={`${styles.tabButton} ${tab === item.id ? styles.tabActive : ""}`}
            aria-current={tab === item.id ? "page" : undefined}>
            {item.title}{item.id === "economics" && <span className={styles.tabSoon}>{report.results.current.metrics.grossMarginEurHa == null ? "Soon" : "New"}</span>}
          </button>)}
        </nav>

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
            <BulletSection title="Why this rotation?" items={best?.evidence ?? []} fallback="No evidence supplied by the model." />
            <BulletSection title="What to consider" items={best?.risks ?? []} fallback="No risk notes supplied by the model." />
          </div>
          <button type="button" className={styles.textButton} onClick={() => setTab("compare")}>Explore the full comparison →</button>
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
          <div className={styles.insightGrid}>
            {outcomes.map((item, index) => <article key={`${item.label}-${index}`} className={styles.panel}>
              <span className={styles.smallCaps}>{index === 0 ? "Current rotation" : `Alternative ${index}`}</span>
              <h3>{labelRotation(item.label)}</h3>
              <div className={styles.insightFigure}><span>Worst-case relative yield</span><strong><Value name="relativeYieldWorst" value={item.metrics.relativeYieldWorst} /></strong></div>
              <div className={styles.insightFigure}><span>10th-percentile relative yield</span><strong><Value name="relativeYieldP10" value={item.metrics.relativeYieldP10} /></strong></div>
            </article>)}
          </div>
          <div className={styles.splitPanels}>
            <BulletSection title="Evidence" items={best?.evidence ?? []} fallback="No evidence available." />
            <BulletSection title="Risks and limitations" items={best?.risks ?? []} fallback="No specific risk notes available." />
          </div>
          {report.results.notes.length > 0 && <div className={styles.panel}><h3>Model notes</h3>
            <ul className={styles.noteList}>{report.results.notes.map((n, i) => <li key={i}>{n}</li>)}</ul></div>}
        </div>}

        {tab === "economics" && <div className={styles.content}>
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
              <h2>Evaluate the economic trade-offs.</h2>
              <p>A partial annual gross margin, not a complete farm budget. Based on the engine&apos;s static price assumptions.</p>
            </div>
            <div className={styles.outcomeGrid}>
              {outcomes.map((item, index) => <article className={styles.outcomeCard} key={index}>
                <span className={styles.smallCaps}>{index === 0 ? "Current rotation" : `Alternative ${index}`}</span>
                <h3>{labelRotation(item.label)}</h3>
                <p className={styles.metricValue}>{formatMetric("grossMarginEurHa", item.metrics.grossMarginEurHa ?? null)}</p>
              </article>)}
            </div>
            <div className={styles.panel}><h3>What is included?</h3>
              <p>Crop revenue minus nitrogen fertilizer and irrigation costs, averaged over historical simulation years (EUR/ha/year).</p>
              <p className={styles.footnote}>Excludes seeds, crop protection, machinery, labor and fixed costs. Prices are static; results are not profit forecasts.</p>
            </div>
          </>}
        </div>}

        {tab === "details" && <div className={styles.content}>
          <div className={styles.sectionIntro}><span className={styles.smallCaps}>05 / ANALYSIS DETAILS</span><h2>Traceable by design.</h2>
            <p>Review the field snapshot, inputs, model provenance and limitations for this report.</p></div>
          <div className={styles.detailsGrid}>
            <section className={styles.panel}><h3>Field snapshot</h3>
              <dl className={styles.detailList}>
                <div><dt>Field name</dt><dd>{report.field.name}</dd></div>
                <div><dt>Field number</dt><dd>#{report.field.number}</dd></div>
                <div><dt>Area estimate</dt><dd>{report.field.areaHectares === null ? "Unavailable" : `${report.field.areaHectares.toFixed(2)} ha`}</dd></div>
                <div><dt>Reference point</dt><dd>{report.field.representativePoint ? `${report.field.representativePoint[1].toFixed(5)}° N, ${report.field.representativePoint[0].toFixed(5)}° E` : "Unavailable"}</dd></div>
                <div><dt>Original field ID</dt><dd className={styles.breakText}>{report.field.id}</dd></div>
              </dl>
            </section>
            <section className={styles.panel}><h3>Analysis inputs</h3>
              <dl className={styles.detailList}>
                <div><dt>Rotation</dt><dd>{report.inputs.rotation.map((r) => `${CROP_LABELS[r.crop]}${r.coverAfter ? " + rye" : ""}`).join(" → ")}</dd></div>
                <div><dt>Irrigation</dt><dd>{IRRIGATION_LABELS[report.inputs.irrigation]}</dd></div>
                {PRIORITY_KEYS.map((key) => <div key={key}><dt>{PRIORITY_LABELS[key]}</dt><dd>{report.inputs.priorities[key]} / 10</dd></div>)}
              </dl>
            </section>
            <section className={styles.panel}><h3>Scientific provenance</h3>
              <dl className={styles.detailList}>
                <div><dt>Engine version</dt><dd>{report.engine.version ?? "Not provided"}</dd></div>
                {report.engine.modelPoint && <div><dt>Simulation input point</dt><dd>{report.engine.modelPoint[1].toFixed(3)}° N, {report.engine.modelPoint[0].toFixed(3)}° E</dd></div>}
                {report.engine.localData && <>
                  <div><dt>Soil data source</dt><dd>SoilGrids 250 m ({report.engine.localData.soilDataMethod.toUpperCase()})</dd></div>
                  <div><dt>Soil pixel displacement</dt><dd>{report.engine.localData.soilPixelShiftMeters.toFixed(0)} m</dd></div>
                  <div><dt>Surface texture</dt><dd>{report.engine.localData.surfaceTexture}</dd></div>
                  <div><dt>Runoff Curve Number</dt><dd>{report.engine.localData.curveNumber} (group {report.engine.localData.aquaCropRunoffGroup})</dd></div>
                  <div><dt>Estimated water availability</dt><dd>{report.engine.localData.profileAvailableWaterMm.toFixed(1)} mm (0–150 cm)</dd></div>
                </>}
                <div><dt>Dataset period</dt><dd>{report.engine.dataPeriod ?? "Not provided"}</dd></div>
                <div><dt>Scenario</dt><dd>{report.results.scenario}</dd></div>
                <div><dt>Compared rotations</dt><dd>{report.results.comparedRotations ?? "Not provided"}</dd></div>
                <div><dt>Report ID</dt><dd className={styles.breakText}>{report.id}</dd></div>
              </dl>
            </section>
            <section className={styles.panel}><h3>Important limitations</h3>
              <p>{report.engine.methodologyNote ?? "Detailed methodology notes were not supplied with this report."}</p>
              <p className={styles.footnote}>Simulations describe historical scenarios, not future weather predictions. Indicators may be subject to model and input uncertainty. Interpret results with local agronomic context.</p>
            </section>
          </div>
        </div>}
        <footer className={styles.footer}>FIELDWISE · Science-led decisions for resilient farming.</footer>
      </div>
    </main>
  );
}
