import { getRecommendation, type CompletedReport, type RotationMetrics, type RotationResult } from "./reportTypes";
import type { PortfolioReport } from "./portfolioStorage";

export type MetricKey = keyof RotationMetrics;
export type ComparisonRow = {
  report: CompletedReport;
  current: number | null;
  alternative: number | null;
  delta: number | null;
  area: number | null;
};
export function finite(v: number | null | undefined): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
/** The rotation each field would adopt: the recommended alternative, or the current rotation when
 *  no alternative scores higher (then the change is zero, never a lower-scoring alternative). */
export function recommendedRotation(report: CompletedReport): RotationResult {
  return getRecommendation(report).recommended ?? report.results.current;
}
export function canCompareEconomics(report: CompletedReport): boolean {
  // Legacy reports did not store this opt-in. A portfolio conservatively uses
  // economics ONLY when the individual analysis explicitly enabled it.
  return report.inputs.advancedEconomics === true;
}
export function comparisonRows(portfolio: PortfolioReport, key: MetricKey): ComparisonRow[] {
  return portfolio.reports.map(report => {
    const current = finite(report.results.current.metrics[key]);
    const alternative = finite(recommendedRotation(report).metrics[key]);
    const allowed = key !== "grossMarginEurHa" || canCompareEconomics(report);
    return {report, area: finite(report.field.areaHectares),
      current: allowed ? current : null,
      alternative: allowed ? alternative : null,
      delta: allowed && current !== null && alternative !== null ? alternative-current : null};
  });
}
export function sumChangeByArea(portfolio: PortfolioReport, key: MetricKey): {current: number; alternative: number; count: number; area: number} | null {
  const applicable = comparisonRows(portfolio,key).filter(row=>row.area !== null && row.area > 0 && row.current !== null && row.alternative !== null);
  if (applicable.length===0) return null;
  return {current: applicable.reduce((a,r)=>a+r.current!*r.area!,0),
    alternative: applicable.reduce((a,r)=>a+r.alternative!*r.area!,0),
    count: applicable.length,area:applicable.reduce((a,r)=>a+r.area!,0)};
}
export function portfolioCoverage(p:PortfolioReport) {
  return {economic: p.reports.filter(canCompareEconomics).length,
    local: p.reports.filter(r=>r.engine.sourceMode === "local_estimate").length,
    area: p.reports.reduce((a,r)=>a+(finite(r.field.areaHectares)??0),0),
    areaCount:p.reports.filter(r=>finite(r.field.areaHectares)!==null && r.field.areaHectares!>0).length};
}
