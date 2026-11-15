"use client";

import { useState } from "react";
import Link from "next/link";
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS, FUTURE_SSP_LABELS } from "../../lib/analysisStorage";
import { REPORT_METRICS, formatMetric, getRecommendation, labelRotation, marginDefinition,
  sourceModeText, visibleStatements, type CompletedReport, type RotationMetrics, type RotationResult } from "../../lib/reportTypes";
import styles from "../../styles/reports.module.css";
import { downloadPdfReport } from "../../lib/reportPrint";
import { downloadExcelReport } from "../../lib/reportExcel";
import HistoricalWindowPlot from "./HistoricalWindowPlot";
import { translateFutureNotice } from "../../lib/futureNotices";

type Tab = "overview" | "compare" | "insights" | "economics" | "future" | "details";
const TABS: { id: Tab; title: string }[] = [
  { id: "overview", title: "Overview" }, { id: "compare", title: "Compare" },
  { id: "insights", title: "Insights" }, { id: "economics", title: "Economics" },
  { id: "future", title: "Future Projections" },
  { id: "details", title: "Details" },
];
// Keep Overview focused: other measures remain available in Compare and Insights.
const SHOW_METRICS: (keyof RotationMetrics)[] = [
  "relativeYieldMedian", "irrigationMm", "nitrogenLeachingKgN",
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
          <span className={styles.mutedTiny}>Model estimate</span>
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

function ComparisonPlot({ report, showEconomics }: { report: CompletedReport; showEconomics: boolean }) {
  const [metric, setMetric] = useState<keyof RotationMetrics>("relativeYieldMedian");
  const available = REPORT_METRICS.filter((m) => showEconomics || m.key !== "grossMarginEurHa");
  const selected = available.find((m) => m.key === metric) ?? available[0];
  const entries = [
    { label: "Current", result: report.results.current },
    ...report.results.alternatives.slice(0, 2).map((result, index) => ({
      label: result === getRecommendation(report).recommended ? "Recommended" : `Alternative ${index + 1}`, result,
    })),
  ];
  const values = entries.map((e) => e.result.metrics[selected.key]).filter((n): n is number => n !== null && Number.isFinite(n));
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
          <select value={selected.key} onChange={(e) => setMetric(e.target.value as keyof RotationMetrics)}>
            {available.map((m) => <option value={m.key} key={m.key}>{m.shortLabel}</option>)}
          </select>
        </label>
      </div>
      <div className={styles.plot} role="group" aria-label={`${selected.label} by crop rotation`}>
        {entries.map((entry, index) => {
          const value = entry.result.metrics[selected.key];
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
            <strong className={styles.plotValue}>{formatMetric(selected.key, value)}</strong>
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
    <span className={styles.economicComparison}>{direction} margin versus the current rotation</span>
  </>;
}

function BulletSection({ title, items, fallback, tone }: {
  title: string; items: string[]; fallback: string; tone?: "evidence" | "risk";
}) {
  return <div className={`${styles.bulletBox} ${tone === "risk" ? styles.riskBox : tone === "evidence" ? styles.evidenceBox : ""}`}>
    <h3>{title}</h3>
    {items.length ? <ul>{items.map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}</ul>
      : <p className={styles.muted}>{fallback}</p>}
  </div>;
}

export default function ReportDashboard({ report, demo = false }: { report: CompletedReport; demo?: boolean }) {
  const [selectedTab, setTab] = useState<Tab>("overview");
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
  const showFuture = report.inputs.includeFuture === true || Boolean(report.results.future);
  const visibleTabs = TABS.filter((item) => {
    if (item.id === "economics") return showEconomics;
    if (item.id === "future") return showFuture;
    return true;
  });
  const tab: Tab = (selectedTab === "economics" && !showEconomics) || (selectedTab === "future" && !showFuture)
    ? "overview" : selectedTab;
  const futureNum = showEconomics ? "05" : "04";
  const detailsNum = (3 + (showEconomics ? 1 : 0) + (showFuture ? 1 : 0) + 1).toString().padStart(2, "0");
  const tabIndex = visibleTabs.findIndex((item) => item.id === tab);
  const previousTab = visibleTabs[tabIndex - 1];
  const nextTab = visibleTabs[tabIndex + 1];
  const changeTab = (next: Tab) => {
    setTab(next);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "auto" });
  };
  const recommendation = getRecommendation(report);
  const current = report.results.current;
  // The rotation the overview talks about: the recommended alternative, otherwise the current rotation.
  const focus: RotationResult = recommendation.recommended ?? current;
  const statements = (item: RotationResult, kind: "evidence" | "risks") => visibleStatements(
    item[kind], kind === "evidence" ? item.evidenceTopics : item.riskTopics, showEconomics);
  const visibleNotes = (notes: string[]) => visibleStatements(notes, undefined, showEconomics);
  const outcomes = [current, ...report.results.alternatives.slice(0, 2)];
  const outcomeTitle = (index: number) => index === 0 ? "Current" :
    outcomes[index] === recommendation.recommended ? "Recommended" : `Alternative ${index}`;
  const limitations = report.engine.limitations;
  const recommendationTitle = recommendation.recommended ? "Recommended rotation" :
    recommendation.status === "priorities_do_not_discriminate" ? "No clear winner" :
    recommendation.status === "no_alternative" ? "No alternative available" : "Keep your current rotation";
  const recommendationSummary = recommendation.recommended
    ? "This option scores higher under your selected priorities. Check its risks before making a decision."
    : recommendation.status === "priorities_do_not_discriminate"
      ? "These priorities do not distinguish between the compared rotations. Review the comparison before deciding."
      : recommendation.status === "no_alternative"
        ? "There is no alternative to recommend in this analysis."
        : "No available alternative scores higher under your selected priorities.";
  const focusEvidence = statements(focus, "evidence");
  // Surface legal and regulatory warnings in the short Overview, without removing
  // or reordering any original engine statements from the full Insights page.
  const focusRisks = [...statements(focus, "risks")].sort((a, b) => {
    const priority = (value: string) => /not compliant|non-compliant|legal nitrogen limit|regulatory|exceeds the legal|derogation|not validated/i.test(value) ? 1 : 0;
    return priority(b) - priority(a);
  });
  const tabTheme = {
    overview: styles.themeOverview, compare: styles.themeCompare, insights: styles.themeInsights,
    economics: styles.themeEconomics, future: styles.themeFuture, details: styles.themeDetails,
  }[tab];
  const date = new Date(report.createdAt);
  const dateLabel = Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" });

  return (
    <main className={`${styles.page} ${tabTheme} ${tab === "overview" ? styles.overviewPage : ""}`}>
      <div className={styles.container}>
        <div className={styles.topbar}>
          <Link className={styles.backLink} href="/reports">← All reports</Link>
          <span className={styles.eyebrow}>FIELDWISE / ANALYSIS REPORT</span>
        </div>
        {report.engine.sourceMode === "pilot_reference" && <div role="note" className={styles.demoBanner}>
          <strong>DATA OF THE CREMONA PILOT POINT, NOT OF YOUR FIELD.</strong> Local climate and soil data were not available,
          and this comparison was run explicitly with the pilot reference data. Results are not location-specific.
        </div>}
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

        {tab === "overview" && <div className={`${styles.content} ${styles.overviewContent}`}>
          <section className={styles.recommendation} aria-labelledby="report-recommendation">
            <div>
              <span className={styles.smallCaps}>01 / YOUR RESULT</span>
              <h2 id="report-recommendation">{recommendationTitle}</h2>
              <p className={styles.rotationSequence}>{labelRotation(focus.label)}</p>
              <p className={styles.recommendationSummary}>{recommendationSummary}</p>
              <div className={styles.inlineTags}>
                <span>{IRRIGATION_LABELS[report.inputs.irrigation]}</span>
                <span>Historical climate simulations</span>
              </div>
            </div>
          </section>
          {recommendation.priorityWarning && <p className={styles.priorityNotice} role="note">{recommendation.priorityWarning}</p>}
          <h2 className={styles.sectionTitle}>Key indicators <span>{recommendation.recommended ? "Recommended option" : "Current rotation"}</span></h2>
          <MetricCards outcome={focus} />
          <div className={`${styles.splitPanels} ${styles.overviewHighlights}`}>
            <BulletSection title="Main advantages" items={focusEvidence.slice(0, 2)} tone="evidence"
              fallback="No significant advantage was reported for this option." />
            <BulletSection title="Risks to review" items={focusRisks.slice(0, 2)} tone="risk"
              fallback="No specific risk exceeded the model thresholds. See Details for limitations." />
          </div>
          <div className={styles.overviewActions}>
            <button type="button" className={styles.primaryButton} onClick={() => changeTab("compare")}>Compare rotations →</button>
            <button type="button" className={styles.secondaryButton} onClick={() => changeTab("insights")}>Explore all insights</button>
            <button type="button" className={styles.textButton} onClick={() => changeTab("details")}>Assumptions &amp; limitations →</button>
          </div>
        </div>}

        {tab === "compare" && <div className={styles.content}>
          <div className={styles.sectionIntro}><span className={styles.smallCaps}>02 / ROTATION COMPARISON</span><h2>Different paths, clearer trade-offs.</h2>
            <p>Compare your current rotation with the model&apos;s alternatives. The highlighted option is recommended only when it scores higher.</p></div>
          <div className={styles.outcomeGrid}>
            {outcomes.map((item, index) => <OutcomeCard key={`${item.label}-${index}`} result={item}
              title={outcomeTitle(index)} highlight={index > 0 && item === recommendation.recommended} />)}
          </div>
          <ComparisonPlot report={report} showEconomics={showEconomics} />
          <details className={styles.explainer}>
            <summary>How were the alternatives selected?</summary>
            <p>Alternative 1 is selected from the highest-scoring options; Alternative 2 is the best for worst-year yield among the remaining choices. A recommendation is made only if it outscores your current rotation.</p>
            <p>{recommendation.message}</p>
            {report.results.rotationOrderNote && <p>{report.results.rotationOrderNote}</p>}
          </details>
          <p className={styles.footnote}>Ranking scores are relative to the compared rotation set. They are not probabilities, sustainability percentages or predictions of future yields.</p>
        </div>}

        {tab === "insights" && <div className={`${styles.content} ${styles.insightsContent}`}>
          <div className={styles.sectionIntro}>
            <span className={styles.smallCaps}>03 / MODEL INSIGHTS</span>
            <h2>Key risks, backed by evidence.</h2>
            <p>Focus on outcomes in difficult historical years, then inspect the supporting observations below. These are simulated conditions, not next season&apos;s forecast.</p>
          </div>
          <h3 className={styles.sectionTitle}>Performance in difficult years</h3>
          <div className={styles.insightGrid}>
            {outcomes.map((item, index) => <article key={`${item.label}-${index}`} className={`${styles.panel} ${item === recommendation.recommended ? styles.insightRecommended : ""}`}>
              <span className={styles.smallCaps}>{outcomeTitle(index)}</span>
              <h3 className={styles.insightRotation}>{labelRotation(item.label)}</h3>
              <div className={`${styles.insightFigure} ${styles.insightPrimaryFigure}`}>
                <span>Worst-year yield</span>
                <strong><Value name="relativeYieldWorst" value={item.metrics.relativeYieldWorst} /></strong>
              </div>
              <div className={styles.insightFigure}>
                <span>10th-percentile yield</span>
                <strong><Value name="relativeYieldP10" value={item.metrics.relativeYieldP10} /></strong>
              </div>
            </article>)}
          </div>
          {report.results.historicalWindows && <HistoricalWindowPlot history={report.results.historicalWindows} showEconomics={showEconomics} />}
          <div className={styles.sectionIntro}>
            <h2>Evidence and trade-offs</h2>
            <p>All reported findings are retained below. The amber panels highlight risks, while the green panels explain supporting evidence.</p>
          </div>
          {outcomes.map((item, index) => <section className={styles.insightSection} key={`notes-${index}`}>
            <h3>{outcomeTitle(index)} <span>{labelRotation(item.label)}</span></h3>
            <div className={styles.splitPanels}>
              <BulletSection title="Evidence" tone="evidence" items={statements(item, "evidence")}
                fallback={index === 0 ? "Baseline: alternatives are compared with this rotation." : "No difference exceeded the model thresholds."} />
              <BulletSection title="Risks &amp; trade-offs" tone="risk" items={statements(item, "risks")}
                fallback="The engine reported no specific risk for this rotation. Model uncertainty still applies." />
            </div>
          </section>)}
          {visibleNotes(report.results.notes).length > 0 && <details className={styles.explainer}>
            <summary>Additional model notes ({visibleNotes(report.results.notes).length})</summary>
            <ul className={styles.noteList}>{visibleNotes(report.results.notes).map((n, i) => <li key={i}>{n}</li>)}</ul>
          </details>}
        </div>}

        {tab === "economics" && showEconomics && <div className={styles.content}>
          {report.results.current.metrics.grossMarginEurHa == null ? (
            <section className={styles.comingSoon}>
              <span className={styles.economicsIcon} aria-hidden="true">€</span>
              <span className={styles.smallCaps}>04 / ECONOMIC OUTLOOK</span>
              <h2>Economic analysis is on its way.</h2>
              <p>This report does not contain economic estimates.</p>
              <span className={styles.softPill}>Coming soon</span>
            </section>
          ) : <>
            <div className={styles.sectionIntro}><span className={styles.smallCaps}>04 / ECONOMIC OUTLOOK</span>
              <h2>Economic difference versus today.</h2>
              <p>Each alternative shows the change in annual margin relative to your current rotation, not the total revenue.</p>
            </div>
            <div className={styles.outcomeGrid}>
              {outcomes.map((item, index) => <article className={styles.outcomeCard} key={index}>
                <span className={styles.smallCaps}>{index === 0 ? "Current rotation" : `Alternative ${index}`}</span>
                <h3>{labelRotation(item.label)}</h3>
                <MarginDifference value={item.metrics.grossMarginEurHa} baseline={report.results.current.metrics.grossMarginEurHa} isCurrent={index === 0} />
              </article>)}
            </div>
            <div className={styles.panel}><h3>How to read these differences</h3>
              <p>Δ margin = alternative margin − current-rotation margin.</p>
              <p>{marginDefinition(report)}</p>
            </div>
          </>}
        </div>}

        {tab === "future" && showFuture && <div className={styles.content}>
          {!report.results.future ? (
            <section className={styles.comingSoon}>
              <span className={styles.economicsIcon} aria-hidden="true">🌱</span>
              <span className={styles.smallCaps}>{futureNum} / CLIMATE PROJECTIONS (CMIP6)</span>
              <h2>Climate simulation is not available for this report.</h2>
              <p>Run the analysis again with climate projections enabled to view CMIP6 future scenarios.</p>
              <span className={styles.softPill}>Not included</span>
            </section>
          ) : (() => {
            const f = report.results.future;
            const futureScenario = FUTURE_SSP_LABELS[f.ssp_code];
            return (
              <>
                <div className={styles.sectionIntro}>
                  <span className={styles.smallCaps}>{futureNum} / FUTURE CLIMATE PROJECTIONS (CMIP6)</span>
                  <h2>{futureScenario.title} · Horizon +{f.horizon_years} years</h2>
                  <p>{futureScenario.description}</p>
                </div>

                <div className={styles.outcomeGrid}>
                  <article className={styles.outcomeCard}>
                    <span className={styles.smallCaps}>Yield impact (Current rotation)</span>
                    <h3>{labelRotation(f.current_rotation)}</h3>
                    <span className={`${styles.economicDifference} ${f.delta_resa_rel_pct >= 0 ? styles.economicPositive : styles.economicNegative}`}>
                      {f.delta_resa_rel_pct >= 0 ? "+" : ""}{f.delta_resa_rel_pct.toFixed(1)} pp
                    </span>
                    <span className={styles.economicComparison}>
                      Historical: {f.baseline_resa_rel_pct.toFixed(1)}% ({f.baseline_resa_t_ha.toFixed(1)} t/ha) → Future: {f.future_resa_rel_pct.toFixed(1)}% ({f.future_resa_t_ha.toFixed(1)} t/ha)
                    </span>
                  </article>

                  <article className={styles.outcomeCard}>
                    <span className={styles.smallCaps}>Economic impact (Current rotation)</span>
                    <h3>Net margin variation</h3>
                    <span className={`${styles.economicDifference} ${f.delta_margine_eur_ha >= 0 ? styles.economicPositive : styles.economicNegative}`}>
                      {f.delta_margine_eur_ha >= 0 ? "+" : ""}{f.delta_margine_eur_ha.toFixed(1)} €/ha/year
                    </span>
                    <span className={styles.economicComparison}>
                      Margin: {f.baseline_margine_eur_ha.toFixed(0)} € → {f.future_margine_eur_ha.toFixed(0)} €/ha · Cost: {f.future_costo_eur_ha.toFixed(0)} €/ha ({f.delta_costo_eur_ha >= 0 ? "+" : ""}{f.delta_costo_eur_ha.toFixed(1)} €)
                    </span>
                  </article>

                  <article className={styles.outcomeCard}>
                    <span className={styles.smallCaps}>Climate &amp; Heat stress</span>
                    <h3>Extreme heat &amp; Evapotranspiration</h3>
                    <span className={`${styles.economicDifference} ${f.future_hot_days_ann > 10 ? styles.economicNegative : styles.economicBaseline}`}>
                      {f.future_hot_days_ann.toFixed(1)} days/year
                    </span>
                    <span className={styles.economicComparison}>
                      Days with Tmax &gt; 35°C · Annual ET0: {f.future_et0_ann_mm.toFixed(0)} mm (baseline: {f.baseline_et0_ann_mm.toFixed(0)} mm)
                    </span>
                  </article>
                </div>

                <div className={styles.sectionIntro} style={{ marginTop: 32 }}>
                  <span className={styles.smallCaps}>CLIMATE ADAPTATION OPPORTUNITY</span>
                  <h2>Best performing rotation in the future.</h2>
                  <p>Multicriteria ranking under {futureScenario.title} conditions identifies adaptive crop rotations with higher thermal and drought resilience.</p>
                </div>

                <article className={`${styles.outcomeCard} ${styles.outcomeHighlight}`} style={{ marginTop: 12 }}>
                  <span className={styles.smallCaps}>Recommended Adaptation Strategy</span>
                  <h3>{labelRotation(f.best_rotation)}</h3>
                  <p className={styles.footnote}>Rank 1 in the future multicriteria evaluation · Pareto optimal</p>
                  <div className={styles.outcomeFigures}>
                    <span>Additional gain vs current rotation: <strong className={styles.economicPositive}>+{f.delta_guadagno_eur_ha.toFixed(1)} €/ha/year</strong></span>
                    <span>Yield boost: <strong className={f.delta_resa_best_pct >= 0 ? styles.economicPositive : ""}>{f.delta_resa_best_pct >= 0 ? "+" : ""}{f.delta_resa_best_pct.toFixed(1)} pp</strong></span>
                    <span>Future yield: <strong>{f.best_resa_rel_pct.toFixed(1)}% ({f.best_resa_t_ha.toFixed(1)} t/ha)</strong></span>
                    <span>Irrigation requirement: <strong>{f.best_irrigazione_mm.toFixed(0)} mm/year</strong></span>
                    <span>Nitrogen fertilizer: <strong>{f.best_concime_kg_n_ha.toFixed(0)} kg N/ha</strong></span>
                  </div>
                  {f.best_rischi && f.best_rischi.length > 0 && (
                    <div className={styles.bulletBox} style={{ marginTop: 18 }}>
                      <h3>Regulatory &amp; Agronomic notices for adaptation</h3>
                      <ul>
                        {f.best_rischi.map((r, i) => (
                          <li key={i}>{translateFutureNotice(r)}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </article>

                <div className={styles.panel} style={{ marginTop: 24 }}>
                  <h3>CMIP6 Delta Change Scientific Methodology</h3>
                  <p>
                    Projections apply monthly climate anomalies calibrated on the CMIP6 climate model ensemble for the Po Valley to the validated NASA POWER daily series at {f.lat.toFixed(3)}° N, {f.lon.toFixed(3)}° E.
                  </p>
                  <p>
                    Evapotranspiration (ET0) is recalculated using the FAO Penman-Monteith equation post-thermal scaling. Agronomic simulations assess crop phenology acceleration, heat stress days, and soil moisture depletion under the chosen radiative forcing scenario.
                  </p>
                </div>
              </>
            );
          })()}
        </div>}

        {tab === "details" && <div className={`${styles.content} ${styles.detailsCompact}`}>
          <div className={styles.sectionIntro}>
            <span className={styles.smallCaps}>{detailsNum} / ANALYSIS DETAILS</span>
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
                <div><dt>Crop rotation</dt><dd>{report.inputs.rotation.map((r) => `${CROP_LABELS[r.crop]}${r.coverAfter ? " + rye" : ""}`).join(" → ")}{report.results.rotationOrderNote ? ` (${report.results.rotationOrderNote})` : ""}</dd></div>
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
                <div><dt>Source</dt><dd>{report.engine.sourceMode === "local_estimate" ? "Local gridded estimate" : report.engine.sourceMode === "pilot_reference" ? "Cremona pilot data, not this field" : report.engine.sourceMode === "pilot_point" ? "Cremona pilot" : "Not specified"}</dd></div>
                <div><dt>Rotations compared</dt><dd>{report.results.comparedRotations ?? "Not provided"}</dd></div>
                {report.engine.localData && <div><dt>Soil</dt><dd>{report.engine.localData.surfaceTexture} · CN {report.engine.localData.curveNumber}</dd></div>}
              </dl>
            </section>
            <section className={styles.panel}><h3>Important limitations</h3>
              <p className={styles.compactCaveat}>{sourceModeText(report)}</p>
              {report.engine.methodologyNote && <p className={styles.compactCaveat}>{report.engine.methodologyNote}</p>}
              <p className={styles.compactCaveat}>Historical-climate ensemble, not a forecast. Estimates at one representative point may not reflect variations across the field.</p>
              {limitations?.statements.map((n, i) => <p className={styles.compactCaveat} key={i}>{n}</p>)}
              <p className={styles.compactAside}>Full model notes, individual risks, soil parameters and reproducibility data are included in the PDF.</p>
            </section>
          </div>
        </div>}
        <footer className={styles.footer}>FIELDWISE · Science-led decisions for resilient farming.</footer>
      </div>
    </main>
  );
}
