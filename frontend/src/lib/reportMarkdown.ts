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
  const bullets = (items: string[], fallback: string) => items.length ? items.map((line) => `- ${line}`).join("\n") : `- ${fallback}`;
  return `### ${role} — ${labelRotation(outcome.label)}\n\n` +
    `Relative ranking score: ${finite(outcome.score) ? outcome.score.toFixed(3) : "Not available"} (relative score, not confidence).\n\n` +
    `**Evidence**\n\n${bullets(outcome.evidence, "No evidence supplied.")}\n\n` +
    `**Risks and trade-offs**\n\n${bullets(outcome.risks, "No risk notes supplied.")}`;
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
    `The recommendation reflects relative ranking among the considered rotations under historical weather conditions and the selected farmer priorities. It is not a prediction of next year's yield or a guarantee of economic benefit.`,
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
    `The full indicator table below supplies the values used by the comparison charts. Deltas are alternative minus current rotation; positive is not necessarily better for consumption and loss indicators.\n\n` +
    `| Indicator | Current | Alternative 1 | Alternative 2 | Delta A1 | Delta A2 |\n| --- | --- | --- | --- | --- | --- |\n${rows}\n\n` +
    `### Comparative figures\n\n<!-- FIELDWISE_CHARTS -->`,
    `## 4. Evidence, risks and interpretations\n\n` +
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
    `## ${economics ? 7 : 6}. Scientific interpretation and limitations\n\n` +
    `${report.engine.methodologyNote ?? "No detailed methodology supplied with this report."}\n\n` +
    `- Historical ensemble results describe sensitivity to past weather variability; they are not weather or harvest forecasts.\n` +
    `- Soil grids describe predicted properties, not direct field measurements. A single point cannot resolve within-field heterogeneity.\n` +
    `- Relative ranking scores are conditional on the alternative set, assumptions and priority weights; they are not confidence or sustainability percentages.\n` +
    `- The saved browser report may omit daily model series and numerical diagnostics not transmitted by the backend.`,
    `## ${economics ? 8 : 7}. Model notes\n\n${modelNotes}`,
    `## ${economics ? 9 : 8}. Data provenance and reproducibility\n\n` +
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
