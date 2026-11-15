/** A Markdown document is the canonical source for FIELDWISE exports.
 *  The PDF export renders this same document on the API side.
 *  This exports the FULL completed browser snapshot, not untransmitted raw model series.
 */
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS, FUTURE_SSP_LABELS } from "./analysisStorage";
import { translateFutureNotice, translateFutureCompliance } from "./futureNotices";
import {
  REPORT_METRICS, alternativeTitle, formatMetric, getRecommendation, labelRotation, marginDefinition,
  recommendationHeadline, sourceModeText, visibleStatements,
  type CompletedReport, type RotationResult, type RotationMetrics,
} from "./reportTypes";

export function includesEconomics(report: CompletedReport): boolean {
  return !("advancedEconomics" in report.inputs) || report.inputs.advancedEconomics === true;
}

export function includesFuture(report: CompletedReport): boolean {
  return report.inputs.includeFuture === true || Boolean(report.results.future);
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

function notesSection(title: string, outcome: RotationResult, isCurrent: boolean, economics: boolean): string {
  const evidence = visibleStatements(outcome.evidence, outcome.evidenceTopics, economics);
  const risks = visibleStatements(outcome.risks, outcome.riskTopics, economics);
  const list = (items: string[]) => items.map((x) => `- ${x.trim()}`).join("\n");
  const position = finite(outcome.position ?? null) ? ` It ranks ${outcome.position} in the compared set.` : "";
  return `### ${title} — ${labelRotation(outcome.label)}\n\n` +
    `The relative ranking score is ${finite(outcome.score) ? outcome.score.toFixed(3) : "not available"}.${position} This value only ranks the rotations within the analyzed set; it does not represent a probability of success or a confidence level.\n\n` +
    `**Evidence reported by the engine**\n\n` +
    (evidence.length ? list(evidence) : isCurrent
      ? "The current rotation is the baseline: the engine reports evidence for the alternatives relative to it."
      : "No difference above the engine's reporting thresholds.") +
    `\n\n**Risks reported by the engine**\n\n` +
    (risks.length ? list(risks) : "The engine reported no risk for this rotation. This does not establish that the strategy is risk-free: see the model limitations.");
}

export function renderReportMarkdown(report: CompletedReport, demo = false): string {
  const economics = includesEconomics(report);
  const outcomes = [report.results.current, ...report.results.alternatives];
  const recommendation = getRecommendation(report);
  const rows = REPORT_METRICS.filter((metric) => economics || metric.key !== "grossMarginEurHa").map((m) => {
    const baseline = report.results.current.metrics[m.key];
    const a = report.results.alternatives[0]?.metrics[m.key] ?? null;
    const b = report.results.alternatives[1]?.metrics[m.key] ?? null;
    return `| ${mdCell(m.label)} | ${mdCell(formatMetric(m.key, baseline))} | ${mdCell(formatMetric(m.key, a))} | ${mdCell(formatMetric(m.key, b))} | ${mdCell(delta(m.key, a, baseline))} | ${mdCell(delta(m.key, b, baseline))} |`;
  }).join("\n");
  const soil = report.engine.localData;
  const rotationText = report.inputs.rotation.map((r) => `${CROP_LABELS[r.crop]}${r.coverAfter ? " + rye cover" : ""}`).join(" > ");
  const priorities = PRIORITY_KEYS.filter((k) => economics || k !== "profitto").map((key) => `| ${PRIORITY_LABELS[key]} | ${report.inputs.priorities[key] ?? "Not supplied"} / 10 |`).join("\n");
  const notes = visibleStatements(report.results.notes, undefined, economics);
  const modelNotes = notes.length ? notes.map((n) => `- ${n}`).join("\n") : "- No additional notes supplied.";
  const limitations = report.engine.limitations?.statements ?? [];
  const geometry = report.field.polygonCoordinates?.flatMap((ring, ri) => ring.map((coord, ci) => `| ${ri + 1} | ${ci + 1} | ${finite(coord[0]) ? coord[0].toFixed(7) : "N/A"} | ${finite(coord[1]) ? coord[1].toFixed(7) : "N/A"} |`)).join("\n");
  const modeText = sourceModeText(report);
  const alt = (i: number) => alternativeTitle(report, i);
  const components = (r: RotationResult) => r.marginComponents;
  let n = 5;
  const next = () => n++;
  const summaryText = recommendation.status === "current_not_compliant"
    ? "The current rotation fails the selected rule set. The proposed alternative is compliant under the engine's encoded rules; compliance takes precedence over its weighted score. Verify the actual applicable regulations independently."
    : recommendation.recommended
    ? "The recommended alternative scores higher than the current rotation under the recorded priorities and irrigation scenario, but it should not be interpreted as universally optimal. Differences between rotations can reflect trade-offs: for example, a change that improves relative yield can also raise water or fertilizer demand. The comparison is conditional on model assumptions, data coverage, scenario definitions and the alternatives that were actually evaluated."
    : "No alternative is recommended over the current rotation. The alternatives in this report are shown for comparison only: the first is the best-scoring non-dominated rotation other than the current one, the second the best in the worst year among the others.";
  const md = [
    `# FIELDWISE | Field Analysis Report\n\n` +
    `**${demo ? "DEMONSTRATION ONLY — FICTIONAL VALUES, NOT SCIENTIFIC RESULTS" : "Completed FIELDWISE analysis"}**\n\n` +
    `**Field:** ${report.field.name} (#${report.field.number})\n\n` +
    `**Created:** ${report.createdAt}\n\n` +
    `**Report ID:** ${report.id}\n\n` +
    `**Data scope:** ${modeText}`,
    `## 1. Executive summary\n\n` +
    `**Current rotation:** ${labelRotation(report.results.current.label)}${report.results.rotationOrderNote ? ` (${report.results.rotationOrderNote})` : ""}\n\n` +
    `**Recommendation:** ${recommendationHeadline(report)}\n\n` +
    `${recommendation.message}${recommendation.priorityWarning ? ` ${recommendation.priorityWarning}` : ""}\n\n` +
    `**Irrigation scenario:** ${IRRIGATION_LABELS[report.inputs.irrigation]}\n\n` +
    `**Regional rules:** ${mdCell(report.engine.regulatoryRegimeLabel ?? report.inputs.regulatoryRegime ?? "Lombardy (five-year default)")}\n\n` +
    `**Rotations compared:** ${report.results.comparedRotations ?? "Not supplied"}\n\n` +
    `The purpose of this analysis is to support a comparison of management strategies using a consistent set of historical climate scenarios. The model evaluates the current crop rotation against alternative sequences and ranks the resulting outcomes according to the priorities recorded below.\n\n` +
    summaryText,
    `## 2. Field, assumptions and input configuration\n\n` +
    `| Parameter | Value |\n| --- | --- |\n` +
    `| Field name | ${mdCell(report.field.name)} |\n| Field number | ${report.field.number} |\n` +
    `| Area (estimated) | ${finite(report.field.areaHectares) ? report.field.areaHectares.toFixed(3) + " ha" : "Not available"} |\n` +
    `| Field representative point | ${fmtPoint(report.field.representativePoint)} |\n` +
    `| Model input point | ${fmtPoint(report.engine.modelPoint)} |\n` +
    `| Irrigation scenario | ${IRRIGATION_LABELS[report.inputs.irrigation]} |\n` +
    `| Regulatory filter | ${mdCell(report.engine.regulatoryRegimeLabel ?? report.inputs.regulatoryRegime ?? "Lombardy (five-year default)")} |\n` +
    `| Crop sequence (as entered) | ${mdCell(rotationText)} |\n` +
    `| Analysis reference mode | ${mdCell(modeText)} |\n\n` +
    `### Priority weights\n\n| Criterion | Weight |\n| --- | --- |\n${priorities}`,
    `## 3. Quantitative comparison (all saved indicators)\n\n` +
    `The full table reports every quantitative indicator retained in the browser report snapshot. Each column refers to a simulation-based property of the stated rotation and irrigation scenario, aggregated over historical weather conditions. These are modeled comparisons, not directly measured field outcomes.\n\n` +
    `Columns: ${mdCell(alt(0))}; ${mdCell(alt(1))}.\n\n` +
    `Deltas are calculated as **alternative minus current rotation**. A positive delta means an increase, not necessarily an improvement: higher relative yield and higher humus change can be favorable, whereas higher nitrogen leaching and irrigation demand usually represent a larger environmental or resource burden.\n\n` +
    `| Indicator | Current | Alternative 1 | Alternative 2 | Delta A1 | Delta A2 |\n| --- | --- | --- | --- | --- | --- |\n${rows}\n\n` +
    `### Comparative figures\n\n` +
    `The bar charts visualize the saved summary indicators. They complement, rather than replace, the numerical table: read both the scale and the unit of each metric before comparing options.\n\n` +
    `<!-- FIELDWISE_CHARTS -->\n\n` +
    `### Change across historical rotation cycles\n\n` +
    (report.results.historicalWindows?.series?.length ?
      (report.results.historicalWindows.series.some((s) => s.points.some((p) => p.evaluatedYear !== undefined))
        ? `The following line charts describe variation across **overlapping simulated rotation cycles**, indexed by the first year of the evaluated cycle (spin-up years excluded). Each point is the median across available cyclic shifts, not the observation of a single farm in that calendar year. Adjacent points share weather years and are not independent.`
        : `The following line charts describe variation across overlapping simulated rotation cycles. This saved report predates the corrected axis: the x-axis shows the simulation start year, which includes the spin-up cycle.`) +
      `\n\n<!-- FIELDWISE_HISTORICAL_CHARTS -->` :
      `A year-indexed simulation series was not supplied with this saved report. It would be inappropriate to reconstruct or interpolate that sequence from aggregated summary values.`),
    `## 4. Evidence, risks and interpretations\n\n` +
    `For each rotation, the statements below are the evidence and risks returned by the FIELDWISE engine, with its own thresholds and numbers. A favorable result for one variable does not remove uncertainty in others.\n\n` +
    [notesSection("Current rotation", outcomes[0], true, economics), ...report.results.alternatives.map((r, i) => notesSection(alt(i), r, false, economics))].join("\n\n"),
    ...(economics ? [`## ${next()}. Economics: difference from the current rotation\n\n` +
      `${marginDefinition(report)}\n\n` +
      `| Rotation | Margin (EUR/ha/year) | Delta vs current (EUR/ha/year) | Revenue | Fertilizer | Irrigation | Other crop costs |\n| --- | --- | --- | --- | --- | --- | --- |\n` +
      outcomes.map((r, i) => {
        const c = components(r);
        const eur = (v: number | null | undefined) => finite(v ?? null) ? (v as number).toFixed(0) : "Not available";
        return `| ${mdCell(i === 0 ? "Current" : `Alternative ${i}`)} | ${finite(r.metrics.grossMarginEurHa) ? r.metrics.grossMarginEurHa.toFixed(1) : "Not available"} | ${i === 0 ? "0 (baseline)" : delta("grossMarginEurHa", r.metrics.grossMarginEurHa, outcomes[0].metrics.grossMarginEurHa)} | ${eur(c?.revenueEurHa)} | ${eur(c?.fertilizerCostEurHa)} | ${eur(c?.irrigationCostEurHa)} | ${eur(c?.otherCropCostsEurHa)} |`;
      }).join("\n")] : []),
    ...(includesFuture(report) && report.results.future ? [(() => {
      const f = report.results.future;
      return `## ${next()}. Future climate projections (CMIP6 Delta Change)\n\n` +
        `**Scenario:** ${FUTURE_SSP_LABELS[f.ssp_code].title} · **Horizon:** +${f.horizon_years} years\n\n` +
        `${FUTURE_SSP_LABELS[f.ssp_code].description}\n\n` +
        `### ${f.referenceMatchesRequestedRotation === false ? "Archived reference rotation" : "Current rotation"} under climate change\n\n` +
        `| Indicator | Historical baseline | Future projected | Delta |\n| --- | --- | --- | --- |\n` +
        `| Relative yield (%) | ${f.baseline_resa_rel_pct.toFixed(1)}% | ${f.future_resa_rel_pct.toFixed(1)}% | ${f.delta_resa_rel_pct >= 0 ? "+" : ""}${f.delta_resa_rel_pct.toFixed(1)} pp |\n` +
        `| Average yield (t/ha) | ${f.baseline_resa_t_ha.toFixed(2)} t/ha | ${f.future_resa_t_ha.toFixed(2)} t/ha | ${(f.future_resa_t_ha - f.baseline_resa_t_ha).toFixed(2)} t/ha |\n` +
        `| Net margin (EUR/ha/year) | ${f.baseline_margine_eur_ha.toFixed(0)} EUR/ha | ${f.future_margine_eur_ha.toFixed(0)} EUR/ha | ${f.delta_margine_eur_ha >= 0 ? "+" : ""}${f.delta_margine_eur_ha.toFixed(0)} EUR/ha |\n` +
        `| Variable costs (EUR/ha/year) | ${f.baseline_costo_eur_ha.toFixed(0)} EUR/ha | ${f.future_costo_eur_ha.toFixed(0)} EUR/ha | ${f.delta_costo_eur_ha >= 0 ? "+" : ""}${f.delta_costo_eur_ha.toFixed(0)} EUR/ha |\n` +
        `| Irrigation demand (mm/year) | ${f.baseline_irrigazione_mm.toFixed(0)} mm | ${f.future_irrigazione_mm.toFixed(0)} mm | ${(f.future_irrigazione_mm - f.baseline_irrigazione_mm).toFixed(0)} mm |\n` +
        `| Extreme heat days (Tmax > 35°C) | Historical baseline | ${f.future_hot_days_ann.toFixed(1)} days/year | Heat stress increase |\n` +
        `| Reference ET0 (mm/year) | ${f.baseline_et0_ann_mm.toFixed(0)} mm | ${f.future_et0_ann_mm.toFixed(0)} mm | +${(f.future_et0_ann_mm - f.baseline_et0_ann_mm).toFixed(0)} mm |\n\n` +
        `### Climate adaptation opportunity\n\n` +
        (f.best_rotation ? `**Illustrative compliant adaptation candidate:** ${labelRotation(f.best_rotation)}\n\n${f.adaptationNotice ?? ""}\n\n` :
          `${f.adaptationNotice ?? "No verifiably compliant candidate can be proposed."}\n\n`) +
        (f.best_rotation ? `- Additional margin vs current rotation: ${f.delta_guadagno_eur_ha >= 0 ? "+" : ""}${f.delta_guadagno_eur_ha.toFixed(1)} EUR/ha/year\n` +
        `- Yield boost vs current rotation: ${f.delta_resa_best_pct >= 0 ? "+" : ""}${f.delta_resa_best_pct.toFixed(1)} pp (projected: ${f.best_resa_rel_pct.toFixed(1)}%, ${f.best_resa_t_ha.toFixed(1)} t/ha)\n` +
        `- Future irrigation demand: ${f.best_irrigazione_mm.toFixed(0)} mm/year\n` +
        `- Nitrogen fertilizer demand: ${f.best_concime_kg_n_ha.toFixed(0)} kg N/ha\n` +
        `- Regulatory compliance: ${translateFutureCompliance(f.best_conformita)}\n` +
        (f.best_rischi && f.best_rischi.length ? `\n**Adaptation notices and risks:**\n\n` + f.best_rischi.map((r) => `- ${translateFutureNotice(r)}`).join("\n") : "") : "") +
        `\n\n### Other simulated future rotations\n\n` +
        `${f.candidateRotationsNote ?? "No additional future ranking was included in this saved report."}\n\n` +
        (f.candidateRotations?.length ?
          `| Precomputed rank | Rotation | Relative yield (%) | Margin (EUR/ha/year) | Delta vs reference (EUR/ha/year) | Irrigation (mm/year) | Fertilizer (kg N/ha/year) | N leaching (kg N/ha/year) | Humus change (t/ha/year) |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- |\n` +
          f.candidateRotations.map(c => {
            const n = (v: number | null | undefined, digits = 1) => v === null || v === undefined || !Number.isFinite(v) ? "N/A" : v.toFixed(digits);
            return `| ${c.precomputedRank ?? "N/A"} | ${mdCell(labelRotation(c.rotation))} | ${n(c.relativeYieldPct)} | ${n(c.marginEurHa, 0)} | ${n(c.marginDeltaVsCurrentEurHa, 0)} | ${n(c.irrigationMm, 0)} | ${n(c.fertilizerKgN, 0)} | ${n(c.nitrogenLeachingKgN)} | ${n(c.humusChangeTonsHa, 3)} |`;
          }).join("\n") : "No additional verifiably compliant rotations were available.");
    })()] : []),
    `## ${next()}. Soil and geographic data\n\n` +
    (soil ? `| Parameter | Model input |\n| --- | --- |\n` +
      `| Soil processing method | ${mdCell(soil.soilDataMethod)} |\n` +
      `| Soil pixel displacement | ${soil.soilPixelShiftMeters.toFixed(1)} m |\n` +
      `| Surface texture | ${mdCell(soil.surfaceTexture)} |\n` +
      `| Curve Number | ${soil.curveNumber.toFixed(2)} |\n` +
      `| Runoff group | ${soil.aquaCropRunoffGroup} |\n` +
      `| Surface available water | ${soil.surfaceAvailableWaterMm.toFixed(2)} mm |\n` +
      `| Profile available water | ${soil.profileAvailableWaterMm.toFixed(2)} mm |` : "The saved report does not include a local soil-properties snapshot."),
    `## ${next()}. Model limitations, ranking stability and validation\n\n` +
    (limitations.length ? limitations.map((s) => `- ${s}`).join("\n")
      : "This saved report predates the transmission of the sensitivity and validation results; run the analysis again to include them."),
    `## ${next()}. Model notes\n\n${modelNotes}`,
    `## ${next()}. Data provenance and reproducibility\n\n` +
    `| Item | Value |\n| --- | --- |\n` +
    `| Engine version | ${mdCell(report.engine.version)} |\n` +
    `| Data period | ${mdCell(report.engine.dataPeriod)} |\n` +
    `| Ensemble calculated at | ${mdCell(report.engine.ensembleCalculatedAt)} |\n` +
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
    `Ranking scores are relative to the compared rotations and selected priorities, and they are not confidence or sustainability percentages. Ranking stability and validation results are listed in the limitations section above.` +
    (economics ? ` The economic margin uses ${report.engine.economics?.farmerAdjusted ? "farmer-adjusted crop expenses and default unit prices" : "default prices and costs"}; it is not net farm profit.` : "") + `\n\n` +
    `Only fields transmitted to the browser are included here. Daily simulation states, raw satellite imagery and other unpublished diagnostics have not been inferred. For professional use, verify assumptions, local regulatory compliance and field measurements independently.`,
  ];
  return md.join("\n\n") + "\n";
}
