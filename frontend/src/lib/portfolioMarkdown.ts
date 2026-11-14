import type { PortfolioReport } from "./portfolioStorage";
import { comparisonRows, canCompareEconomics, portfolioCoverage, sumChangeByArea } from "./portfolioMetrics";
import { IRRIGATION_LABELS } from "./analysisStorage";
import { REPORT_METRICS, formatMetric, labelRotation, type RotationMetrics } from "./reportTypes";

const safe = (s:unknown) => String(s??"").replace(/\|/g,"\\|").replace(/[\r\n]+/g," ").replace(/\*/g,"");
const fmtNumber = (n:number) => n.toLocaleString("en-GB",{maximumFractionDigits:2});
const fmtMetric = (k:keyof RotationMetrics,n:number|null) => n===null?"N/A":formatMetric(k,n);
export function renderPortfolioMarkdown(p: PortfolioReport):string {
  const cov=portfolioCoverage(p);
  const econ=cov.economic>0;
  const created=new Date(p.createdAt).toLocaleString("en-GB",{dateStyle:"long",timeStyle:"short"});
  const lines:string[]=[
    "# FIELDWISE | Farm Portfolio Analysis",
    "",
    `**Report date:** ${created}`,
    `**Portfolio ID:** ${safe(p.id)}`,
    `**Coverage:** ${p.reports.length} successful of ${p.requestedFields} requested field analyses.`,
    `**Total mapped area:** ${fmtNumber(cov.area)} ha (${cov.areaCount} fields with valid area estimates).`,
    "",
    "## 1. Executive summary",
    "",
    "This portfolio report brings together the results of independent FIELDWISE field analyses. For each field, it contrasts the current crop rotation with the leading alternative under that field's selected irrigation scenario and priority weights. The recommendations are field-specific. A higher ranking score in one field must not be compared directly with the score of another field.",
    "",
    "The analysis uses historical weather scenarios and a numerical agronomic model. It does not predict future harvests or substitute for measured field conditions.",
    "",
    "## 2. Field-level recommendations",
    "",
    "| Field | Area (ha) | Current rotation | Leading alternative | Irrigation |",
    "| --- | ---: | --- | --- | --- |",
    ...p.reports.map(r=>`| ${safe(r.field.name)} | ${r.field.areaHectares!==null?fmtNumber(r.field.areaHectares):"N/A"} | ${safe(labelRotation(r.results.current.label))} | ${safe(r.results.alternatives[0]?labelRotation(r.results.alternatives[0].label):"Unavailable")} | ${safe(IRRIGATION_LABELS[r.inputs.irrigation])} |`),
    "",
    "## 3. Model indicators across fields",
    "",
    "Each line compares a given field with itself. Differences are calculated as recommended minus current. Yield percentages are relative model indicators, not realized yields.",
  ];
  for(const metric of REPORT_METRICS.filter(m=>econ||m.key!=="grossMarginEurHa")) {
    lines.push("",`### ${metric.label}`,"","| Field | Current | Recommended | Difference |","| --- | ---: | ---: | ---: |");
    for(const r of comparisonRows(p,metric.key)){
      const delta=r.delta===null?"N/A":`${r.delta>0?"+":""}${metric.key.startsWith("relativeYield")?(r.delta*100).toFixed(1)+" percentage points":fmtMetric(metric.key,r.delta)}`;
      lines.push(`| ${safe(r.report.field.name)} | ${fmtMetric(metric.key,r.current)} | ${fmtMetric(metric.key,r.alternative)} | ${delta} |`);
    }
    lines.push("",`${metric.higherIsBetter?"Higher":"Lower"} values are generally preferable for this model indicator, all other considerations held constant.`);
  }
  lines.push("","## 4. Field comparison figures","",
    "<!-- FIELDWISE_PORTFOLIO_CHARTS -->","",
    "The figures compare independent modeled field outcomes. They do not rank entire fields by intrinsic quality. Values and uncertainties depend on the local input data, field configurations, and historical scenarios.","",
    "## 5. Area-weighted operational totals","",
    "These totals are simple conversions of modeled per-area indicators, not measured farm resource consumption. Only fields with known area and valid current/recommended values are included; the coverage is shown for every total.",
    "","| Total | Current | Recommended | Change | Fields included |","| --- | ---: | ---: | ---: | ---: |");
  for(const metric of [
    {key:"irrigationMm" as const,label:"Modeled irrigation volume (m3/year)",factor:10},
    {key:"fertilizerKgN" as const,label:"Modeled nitrogen fertilizer (kg N/year)",factor:1},
    {key:"nitrogenLeachingKgN" as const,label:"Modeled nitrogen leaching (kg N/year)",factor:1},
    {key:"humusChangeTonsHa" as const,label:"Modeled humus change (t/year)",factor:1},
    ...(econ?[{key:"grossMarginEurHa" as const,label:"Partial economic margin (EUR/year)",factor:1}]:[])
  ]){
    const data=sumChangeByArea(p,metric.key);
    if(!data)continue;
    const current=data.current*metric.factor,alternative=data.alternative*metric.factor;
    lines.push(`| ${metric.label} | ${fmtNumber(current)} | ${fmtNumber(alternative)} | ${alternative-current>0?"+":""}${fmtNumber(alternative-current)} | ${data.count} of ${p.reports.length} |`);
  }
  if(econ){
    lines.push("","## 6. Optional economic analysis","",
      `Economic analysis was enabled for ${cov.economic} of ${p.reports.length} completed fields. It is excluded for fields that did not explicitly opt into Advanced Analysis.`,
      "","The current backend margin is a partial gross margin: modeled crop revenue less mineral-nitrogen fertilizer and irrigation. It excludes seeds, crop protection, machinery and fixed overheads. Results should not be treated as whole-farm net profit.");
  }
  lines.push("",`## ${econ?7:6}. Field-specific evidence and risks`,"");
  for(const r of p.reports){
    lines.push("",`### ${safe(r.field.name)}`,"",
      `**Current:** ${safe(labelRotation(r.results.current.label))}. **Recommended:** ${safe(r.results.alternatives[0]?labelRotation(r.results.alternatives[0].label):"No alternative available")}.`,
      `**Model source:** ${safe(r.engine.sourceMode??"Not specified")}. **Model version:** ${safe(r.engine.version??"Unknown")}. **Historical period:** ${safe(r.engine.dataPeriod??"Not specified")}.`,
      "","**Recommendation evidence:**", "",
      ...(r.results.alternatives[0]?.evidence.length?r.results.alternatives[0].evidence.map(s=>`- ${safe(s)}`):["- No evidence notes supplied by the engine."]),
      "","**Risks and trade-offs:**", "",
      ...(r.results.alternatives[0]?.risks.length?r.results.alternatives[0].risks.map(s=>`- ${safe(s)}`):["- No specific risk notes supplied; model uncertainty still applies."]),
      "");
  }
  if(p.failures.length) {
    lines.push("",`## ${econ?8:7}. Analyses that could not be completed`,"",
      "The following fields are excluded from numerical comparisons and portfolio totals:","",
      ...p.failures.map(f=>`- **${safe(f.fieldName)}:** ${safe(f.message)}`),"");
  }
  lines.push("","## Disclaimer and interpretation limits","",
    "Each field analysis uses one representative coordinate. SoilGrids predictions and historical NASA POWER forcing are estimates, not a direct survey of the entire polygon. Spatial resolution and model assumptions may not reflect local within-field variability.",
    "","Historical rotation windows overlap and are not independent annual field observations. Yield-related risk and rotation rankings have uncertainty and should not be interpreted as forecasts. Regulations must be checked for the actual field location.",
    "","Different fields may have different priorities, irrigation assumptions, and quality of source data. Reported per-area indicators can be compared descriptively but do not constitute a controlled experimental comparison. Portfolio totals include only eligible fields with known surface area; land area is estimated from geometry.",
    "","This document is an agricultural decision-support aid and does not replace professional agronomic advice, local field measurements, or financial accounting.","");
  return lines.join("\n");
}

/** Serializable chart projection; contains no fabricated values. */
export function portfolioPdfPayload(p:PortfolioReport) {
  return {
    id:p.id,
    portfolio:{
      fields:p.reports.map(r=>({
        name:r.field.name,
        areaHectares:r.field.areaHectares,
        advancedEconomics:canCompareEconomics(r),
        current:r.results.current.metrics,
        recommended:r.results.alternatives[0]?.metrics??null,
      })),
    },
  };
}
