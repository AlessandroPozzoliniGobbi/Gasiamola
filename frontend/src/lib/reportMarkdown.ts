/** A Markdown document is the canonical source for FIELDWISE exports.
 *  The print view turns this same document into a professional PDF-ready layout.
 *  This exports the FULL completed browser snapshot, not untransmitted raw model series.
 */
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS } from "./analysisStorage";
import { REPORT_METRICS, formatMetric, labelRotation, type CompletedReport, type RotationResult, type RotationMetrics } from "./reportTypes";

export function includesEconomics(report: CompletedReport): boolean {
  return !("advancedEconomics" in report.inputs) || report.inputs.advancedEconomics === true;
}

const finite = (n: number | null | undefined): n is number => typeof n === "number" && Number.isFinite(n);
const mdCell = (s: unknown) => String(s ?? "Not available").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
const fmtPoint = (point?: [number, number] | null) => point ? `${point[1].toFixed(5)} N, ${point[0].toFixed(5)} E` : "Not provided";
const delta = (key: keyof RotationMetrics, value: number | null, baseline: number | null) => {
  if (!finite(value) || !finite(baseline)) return "Not available";
  const difference = value - baseline;
  if (key.startsWith("relativeYield")) return `${difference >= 0 ? "+" : ""}${(difference * 100).toFixed(1)} pp`;
  if (key === "grossMarginEurHa") return `${difference >= 0 ? "+" : ""}${difference.toFixed(1)} EUR/ha/year`;
  if (key === "humusChangeTonsHa") return `${difference >= 0 ? "+" : ""}${difference.toFixed(3)} t/ha/year`;
  return `${difference >= 0 ? "+" : ""}${difference.toFixed(1)} ${key === "irrigationMm" ? "mm" : "kg N/ha"}`;
};

function notesSection(role: string, outcome: RotationResult): string {
  const modelText = (items: string[]) => items.map(x => x.trim()).filter(Boolean).join(" ");
  const isCurrent = role === "Current rotation";
  const evidence = modelText(outcome.evidence);
  const risks = modelText(outcome.risks);
  const evidenceIntro = isCurrent ?
    "This is the farmer's starting strategy and serves as the numerical baseline for all differences in the report." :
    "Compared with the current rotation, the model identifies several changes in the selected performance indicators. These findings should be interpreted together rather than as a guarantee that one option is superior in every respect.";
  const riskIntro = "A useful recommendation must also describe its potential disadvantages and unresolved uncertainties, including any production-rule caveats returned by the model.";
  return `### ${role} — ${labelRotation(outcome.label)}\n\n` +
    `The relative ranking score is ${finite(outcome.score) ? outcome.score.toFixed(3) : "not available"}. This value only ranks the alternatives within the analyzed set; it does not represent a probability of success or a confidence level.\n\n` +
    `**Interpretation of the evidence**\n\n${evidenceIntro} ${evidence || "No additional quantitative evidence was supplied for this rotation."}\n\n` +
    `**Risks and trade-offs**\n\n${riskIntro} ${risks || "No specific risk note was supplied; this does not establish that the strategy is risk-free."}`;
}

export function renderReportMarkdown(report: CompletedReport, demo = false): string {
  const economics = includesEconomics(report);
  const outcomes = [report.results.current, ...report.results.alternatives];
  const best = report.results.alternatives[0];
  const rows = REPORT_METRICS.filter((metric) => economics || metric.key !== "grossMarginEurHa").map((m) => {
    const baseline = report.results.current.metrics[m.key];
    const a = report.results.alternatives[0]?.metrics[m.key] ?? null;
    const b = report.results.alternatives[1]?.metrics[m.key] ?? null;
    return `| ${mdCell(m.label)} | ${mdCell(formatMetric(m.key, baseline))} | ${mdCell(formatMetric(m.key, a))} | ${mdCell(formatMetric(m.key, b))} | ${mdCell(delta(m.key, a, baseline))} | ${mdCell(delta(m.key, b, baseline))} |`;
  }).join("\n");
  const mode: Record<string,string> = {
    pilot_reference: "Cremona pilot-reference dataset, NOT field-local input data.",
    pilot_point: "Cremona pilot-point dataset.",
    local_estimate: "Location-conditioned model estimate using gridded climate and predicted soil data at one representative point; NOT a validated field-scale forecast.",
  };
  const soil = report.engine.localData;
  const rotationText = report.inputs.rotation.map((r) => `${CROP_LABELS[r.crop]}${r.coverAfter ? " + rye cover" : ""}`).join(" > ");
  const priorities = PRIORITY_KEYS.filter((k) => economics || k !== "profitto").map((key) => `| ${PRIORITY_LABELS[key]} | ${report.inputs.priorities[key] ?? "Not supplied"} / 10 |`).join("\n");
  const modelNotes = report.results.notes.length ? report.results.notes.map((n) => `- ${n}`).join("\n") : "- No additional notes supplied.";
  const geometry = report.field.polygonCoordinates?.flatMap((ring, ri) => ring.map((coord, ci) => `| ${ri + 1} | ${ci + 1} | ${finite(coord[0]) ? coord[0].toFixed(7) : "N/A"} | ${finite(coord[1]) ? coord[1].toFixed(7) : "N/A"} |`)).join("\n");
  const modeText = mode[report.engine.sourceMode ?? ""] ?? "Data provenance not specified in this saved report.";
  const md = [
    `# FIELDWISE | Field Analysis Report\n\n` +
    `**${demo ? "DEMONSTRATION ONLY — FICTIONAL VALUES, NOT SCIENTIFIC RESULTS" : "Completed FIELDWISE analysis"}**\n\n` +
    `**Field:** ${report.field.name} (#${report.field.number})\n\n` +
    `**Created:** ${report.createdAt}\n\n` +
    `**Report ID:** ${report.id}\n\n` +
    `**Data scope:** ${modeText}`,
    `## 1. Executive summary\n\n` +
    `**Current rotation:** ${labelRotation(report.results.current.label)}\n\n` +
    `**Leading alternative:** ${best ? labelRotation(best.label) : "No feasible alternative returned"}\n\n` +
    `**Irrigation scenario:** ${IRRIGATION_LABELS[report.inputs.irrigation]}\n\n` +
    `**Rotations compared:** ${report.results.comparedRotations ?? "Not supplied"}\n\n` +
    `The purpose of this analysis is to support a comparison of management strategies using a consistent set of historical climate scenarios. The model evaluates the current crop rotation against alternative sequences and ranks the resulting outcomes according to the priorities recorded above.\n\n` +
    `The leading alternative is the highest-ranked eligible recommendation under those conditions, but it should not be interpreted as universally optimal. Differences between the scenarios can reflect trade-offs: for example, a change that improves relative yield can also raise water or fertilizer demand. The comparison is conditional on model assumptions, data coverage, scenario definitions and the alternatives that were actually evaluated.`,
    `## 2. Field, assumptions and input configuration\n\n` +
    `| Parameter | Value |\n| --- | --- |\n` +
    `| Field name | ${mdCell(report.field.name)} |\n| Field number | ${report.field.number} |\n` +
    `| Area (estimated) | ${finite(report.field.areaHectares) ? report.field.areaHectares.toFixed(3) + " ha" : "Not available"} |\n` +
    `| Field representative point | ${fmtPoint(report.field.representativePoint)} |\n` +
    `| Model input point | ${fmtPoint(report.engine.modelPoint)} |\n` +
    `| Irrigation scenario | ${IRRIGATION_LABELS[report.inputs.irrigation]} |\n` +
    `| Crop sequence | ${mdCell(rotationText)} |\n` +
    `| Analysis reference mode | ${mdCell(modeText)} |\n\n` +
    `### Priority weights\n\n| Criterion | Weight |\n| --- | --- |\n${priorities}`,
    `## 3. Quantitative comparison (all saved indicators)\n\n` +
    `The full table reports every quantitative indicator retained in the browser report snapshot. Each column refers to a simulation-based property of the stated rotation and irrigation scenario, aggregated over historical weather conditions. These are modeled comparisons, not directly measured field outcomes.\n\n` +
    `Deltas are calculated as **alternative minus current rotation**. A positive delta means an increase, not necessarily an improvement: higher relative yield and higher humus change can be favorable, whereas higher nitrogen leaching and irrigation demand usually represent a larger environmental or resource burden.\n\n` +
    `| Indicator | Current | Alternative 1 | Alternative 2 | Delta A1 | Delta A2 |\n| --- | --- | --- | --- | --- | --- |\n${rows}\n\n` +
    `### Comparative figures\n\n` +
    `The bar charts visualize the saved summary indicators. They complement, rather than replace, the numerical table: read both the scale and the unit of each metric before comparing options.\n\n` +
    `<!-- FIELDWISE_CHARTS -->\n\n` +
    `### Change across historical simulation windows\n\n` +
    (report.results.historicalWindows?.series?.length ?
      `The following line charts describe variation across **overlapping multi-year rotation simulations** indexed by their historical start year. Each point is the median across available cyclic shifts in that window, not the observation of a single farm in that calendar year. Adjacent points can share weather years and are not independent.\n\n<!-- FIELDWISE_HISTORICAL_CHARTS -->` :
      `A year-indexed simulation series was not supplied with this saved report. It would be inappropriate to reconstruct or interpolate that sequence from aggregated summary values.`),
    `## 4. Evidence, risks and interpretations\n\n` +
    `For each rotation, the following interpretation relates the ranking output to the differences in the indicator table. A favorable result for one variable does not remove uncertainty in others. The evidence and risk statements preserve the comparisons returned by the FIELDWISE API, rather than introducing unobserved measurements.\n\n` +
    [notesSection("Current rotation", outcomes[0]), ...report.results.alternatives.map((r,i) => notesSection(`Alternative ${i+1}`, r))].join("\n\n"),
    ...(economics ? [`## 5. Economics: difference from the current rotation\n\n` +
      `The economic indicator is a **partial gross margin**, not net profit: crop revenue minus nitrogen fertiliser and irrigation costs, using the model's fixed price and cost assumptions. It excludes seeds, crop protection, machinery, labour and fixed costs.\n\n` +
      `| Rotation | Margin (EUR/ha/year) | Delta vs current (EUR/ha/year) |\n| --- | --- | --- |\n` +
      outcomes.map((r, i) => `| ${mdCell(i === 0 ? "Current" : `Alternative ${i}`)} | ${finite(r.metrics.grossMarginEurHa) ? r.metrics.grossMarginEurHa.toFixed(1) : "Not available"} | ${i === 0 ? "0 (baseline)" : delta("grossMarginEurHa",r.metrics.grossMarginEurHa, outcomes[0].metrics.grossMarginEurHa)} |`).join("\n")]: []),
    `## ${economics ? 6 : 5}. Soil and geographic data\n\n` +
    (soil ? `| Parameter | Model input |\n| --- | --- |\n` +
      `| Soil processing method | ${mdCell(soil.soilDataMethod)} |\n` +
      `| Soil pixel displacement | ${soil.soilPixelShiftMeters.toFixed(1)} m |\n` +
      `| Surface texture | ${mdCell(soil.surfaceTexture)} |\n` +
      `| Curve Number | ${soil.curveNumber.toFixed(2)} |\n` +
      `| Runoff group | ${soil.aquaCropRunoffGroup} |\n` +
      `| Surface available water | ${soil.surfaceAvailableWaterMm.toFixed(2)} mm |\n` +
      `| Profile available water | ${soil.profileAvailableWaterMm.toFixed(2)} mm |` : "The saved report does not include a local soil-properties snapshot."),
    `## ${economics ? 7 : 6}. Model notes\n\n${modelNotes}`,
    `## ${economics ? 8 : 7}. Data provenance and reproducibility\n\n` +
    `| Item | Value |\n| --- | --- |\n` +
    `| Engine version | ${mdCell(report.engine.version)} |\n` +
    `| Data period | ${mdCell(report.engine.dataPeriod)} |\n` +
    `| Scenario code | ${mdCell(report.results.scenario)} |\n` +
    `| Report ID | ${mdCell(report.id)} |\n` +
    `| Original field ID | ${mdCell(report.field.id)} |\n` +
    `| Snapshot schema | ${report.schemaVersion} |\n` +
    `| Model input point | ${fmtPoint(report.engine.modelPoint)} |\n\n` +
    `Scientific references, dataset product versions, transformation details and raw model series should be attached through the backend when available. Do not infer missing information from the displayed values.`,
    ...(geometry ? [`## Appendix. Field polygon vertices (GeoJSON order)\n\n| Ring | Vertex | Longitude | Latitude |\n| --- | --- | --- | --- |\n${geometry}`] : []),
    `## Final disclaimer — scope and model limitations\n\n` +
    `This document is a decision-support report produced from a historical simulation ensemble. It is **not** a field measurement, harvest forecast, yield guarantee, financial projection or substitute for site-specific agronomic advice.\n\n` +
    `${modeText} ${report.engine.methodologyNote ?? "Detailed methodological notes were not provided."}\n\n` +
    `The analysis uses a representative geographic point; it does not resolve spatial variability throughout the entire polygon. NASA POWER and SoilGrids represent gridded climate data and modeled soil properties rather than direct measurements on this field. The effect of groundwater and local management may not be fully represented.\n\n` +
    `Ranking scores are relative to the compared rotations and selected priorities, and they are not confidence or sustainability percentages. The model has important validation limitations, including reported uncertainty in wheat yields, soil nitrogen and humus processes. Any economic margin, when included, covers selected variable costs only and is not net farm profit.\n\n` +
    `Only fields transmitted to the browser are included here. Daily simulation states, raw satellite imagery and other unpublished diagnostics have not been inferred. For professional use, verify assumptions, local regulatory compliance and field measurements independently.`,
  ];
  return md.join("\n\n") + "\n";
}

/** Kept available for technical audits even though the main UI now offers PDF + XLSX. */
export function downloadMarkdownReport(report: CompletedReport): void {
  const blob = new Blob([renderReportMarkdown(report)], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = `FIELDWISE_${report.id}.md`;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
