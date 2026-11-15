import type { AnalysisDraft } from "./analysisStorage";
import type { CompletedReport, FieldSnapshot } from "./reportTypes";

/** A report is reusable only if the field geometry, reference point and *all*
 * analysis settings are unchanged. Do not reuse pilot-reference or demo data.
 * The model might still have changed since the original run; the UI gives the
 * user a clear option to force fresh calculations instead. */
export function findReusableFieldReport(
  reports: CompletedReport[], field: FieldSnapshot, draft: AnalysisDraft,
): CompletedReport | null {
  const expectedDraft = JSON.stringify({
    rotation: draft.rotation,
    irrigation: draft.irrigation,
    priorities: draft.priorities,
    advancedEconomics: draft.advancedEconomics === true,
    regulatoryRegime: draft.regulatoryRegime ?? "lombardia_impegno_quinquennale",
    otherCropCostsEurHa: draft.advancedEconomics ? (draft.otherCropCostsEurHa ?? {}) : {},
    includeFuture: draft.includeFuture === true,
    futureHorizon: draft.futureHorizon ?? 10,
    futureSsp: draft.futureSsp ?? "ssp245",
  });
  for (const report of reports) {
    if (report.field.id !== field.id || report.engine.sourceMode !== "local_estimate") continue;
    if (report.field.number !== field.number || report.field.name !== field.name) continue;
    if (report.field.areaHectares === null || field.areaHectares === null) {
      if (report.field.areaHectares !== field.areaHectares) continue;
    } else if (Math.abs(report.field.areaHectares - field.areaHectares) > 0.00001) continue;
    if (JSON.stringify(report.field.polygonCoordinates) !== JSON.stringify(field.polygonCoordinates)) continue;
    if (JSON.stringify(report.field.representativePoint) !== JSON.stringify(field.representativePoint)) continue;
    const savedDraft = report.inputs;
    const actualDraft = JSON.stringify({
      rotation: savedDraft.rotation,
      irrigation: savedDraft.irrigation,
      priorities: savedDraft.priorities,
      advancedEconomics: savedDraft.advancedEconomics === true,
      regulatoryRegime: savedDraft.regulatoryRegime ?? "lombardia_impegno_quinquennale",
      otherCropCostsEurHa: savedDraft.advancedEconomics ? (savedDraft.otherCropCostsEurHa ?? {}) : {},
      includeFuture: savedDraft.includeFuture === true,
      futureHorizon: savedDraft.futureHorizon ?? 10,
      futureSsp: savedDraft.futureSsp ?? "ssp245",
    });
    if (actualDraft === expectedDraft) return report;
  }
  return null;
}
