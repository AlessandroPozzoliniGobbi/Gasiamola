import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS } from "./analysisStorage";
import { REPORT_METRICS, formatMetric, labelRotation, type CompletedReport, type RotationResult } from "./reportTypes";

function outcomeMd(title: string, outcome: RotationResult): string {
  const rows = REPORT_METRICS.map((metric) =>
    `| ${metric.label} | ${formatMetric(metric.key, outcome.metrics[metric.key] ?? null)} |`).join("\n");
  const evidence = outcome.evidence.map((s) => `- ${s}`).join("\n") || "- Not available";
  const risks = outcome.risks.map((s) => `- ${s}`).join("\n") || "- Not available";
  return `## ${title}: ${labelRotation(outcome.label)}\n\n` +
    `Relative ranking score: ${outcome.score?.toFixed(3) ?? "Not available"} (not a confidence estimate).\n\n` +
    `| Indicator | Result |\n| --- | --- |\n${rows}\n\n` +
    `### Evidence\n${evidence}\n\n### Risks and trade-offs\n${risks}\n`;
}

export function renderReportMarkdown(report: CompletedReport): string {
  const mode = report.engine.sourceMode === "pilot_reference"
    ? "**PILOT REFERENCE ONLY:** This simulation uses Cremona soil and weather, not this field's local conditions."
    : "Simulation of the Cremona pilot-point ensemble.";
  const point = report.field.representativePoint;
  const priorities = PRIORITY_KEYS.map((key) => `- ${PRIORITY_LABELS[key]}: ${report.inputs.priorities[key]} / 10`).join("\n");
  const sections = [
    `# FIELDWISE — Analysis Report\n\n**Field:** ${report.field.name} (#${report.field.number})\n\n` +
    `**Created:** ${report.createdAt}\n\n**Report ID:** ${report.id}\n\n${mode}\n`,
    `## Field & configuration\n\n- Area: ${report.field.areaHectares?.toFixed(2) ?? "Unavailable"} ha\n` +
    `- Field reference coordinates: ${point ? `${point[1].toFixed(5)} N, ${point[0].toFixed(5)} E` : "Unavailable"}\n` +
    `- Model input coordinates: ${report.engine.modelPoint ? `${report.engine.modelPoint[1]} N, ${report.engine.modelPoint[0]} E` : "Not supplied"}\n` +
    `- Irrigation scenario: ${IRRIGATION_LABELS[report.inputs.irrigation]}\n` +
    `- Crop cycle: ${report.inputs.rotation.map((r) => CROP_LABELS[r.crop] + (r.coverAfter ? " + rye" : "")).join(" → ")}\n` +
    `- Compared rotations: ${report.results.comparedRotations ?? "Not available"}\n\n` +
    `### Priorities\n${priorities}\n`,
    outcomeMd("Current rotation", report.results.current),
    ...report.results.alternatives.map((r, i) => outcomeMd(`Alternative ${i + 1}`, r)),
    `## Scientific context and limitations\n\n${report.engine.methodologyNote ?? "Not provided"}\n\n` +
    `The indicators compare historical climate years; they are not a forecast. Ranking scores depend on the compared rotations, irrigation scenario and chosen priorities.\n\n` +
    `Economic margin is partial: crop revenue minus nitrogen fertilizer and irrigation. It excludes seeds, crop protection, machinery, labor and fixed costs.\n`,
    `## Model notes\n\n${report.results.notes.map((s) => `- ${s}`).join("\n")}\n`,
    `## Reproducibility\n\n- Engine version: ${report.engine.version ?? "Not provided"}\n` +
    `- Dataset period: ${report.engine.dataPeriod ?? "Not provided"}\n` +
    `- Scenario code: ${report.results.scenario}\n\n` +
    `Generated from the FIELDWISE browser report snapshot. Source publications and full model methodology are documented in the project resources.\n`,
  ];
  return sections.join("\n\n") + "\n";
}

export function downloadMarkdownReport(report: CompletedReport): void {
  const content = renderReportMarkdown(report);
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `FIELDWISE_${report.id}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
