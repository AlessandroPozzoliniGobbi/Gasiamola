"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getPortfolio, type PortfolioReport } from "../../lib/portfolioStorage";
import { comparisonRows, portfolioCoverage, sumChangeByArea } from "../../lib/portfolioMetrics";
import { downloadPortfolioPdf } from "../../lib/portfolioPdf";
import { REPORT_METRICS, formatMetric, labelRotation, recommendationHeadline, getRecommendation, type RotationMetrics } from "../../lib/reportTypes";
import { IRRIGATION_LABELS } from "../../lib/analysisStorage";
import styles from "../../styles/portfolio.module.css";

type Screen={status:"loading"}|{status:"ready";value:PortfolioReport}|{status:"error";message:string}|{status:"missing"};
type Tab="overview"|"compare"|"fields"|"details";
const TABS:{key:Tab;label:string}[]=[{key:"overview",label:"Overview"},{key:"compare",label:"Compare"},{key:"fields",label:"Fields"},{key:"details",label:"Details"}];
const fmt=(x:number)=>x.toLocaleString("en-GB",{maximumFractionDigits:1});
function metricDifference(key:keyof RotationMetrics,value:number|null):string {
  if(value===null)return "N/A";
  if(key.startsWith("relativeYield"))return `${value>0?"+":""}${(value*100).toFixed(1)} pp`;
  const formatted = formatMetric(key,value);
  return value>0 && !formatted.startsWith("+") ? `+${formatted}` : formatted;
}
function dataSourceLabel(source:PortfolioReport["reports"][number]["engine"]["sourceMode"]):string {
  if(source==="pilot_reference")return "Pilot reference — not this field";
  if(source==="local_estimate")return "Local estimate";
  if(source==="pilot_point")return "Pilot point";
  return "Not specified";
}
function MetricBreakdown({p,metric}:{p:PortfolioReport;metric:keyof RotationMetrics}){
  const selected=REPORT_METRICS.find(m=>m.key===metric)!;
  const rows=comparisonRows(p,metric);
  const max=Math.max(0.000001,...rows.map(r=>Math.abs(r.delta??0)));
  return <section className={`${styles.panel} ${styles.comparePanel}`}>
    <div className={styles.headline}><div><span className={styles.eyebrow}>FIELD-BY-FIELD CHANGE</span><h2>{selected.label}</h2></div><span className={styles.legend}>{selected.higherIsBetter?"Higher is generally better":"Lower is generally better"}</span></div>
    <div className={styles.chart} role="group" aria-label={`${selected.label}: recommended minus current for each field`}>
      {rows.map(r=>{
        const improved=r.delta!==null && (selected.higherIsBetter?r.delta>=0:r.delta<=0);
        return <div className={styles.chartRow} key={r.report.id}>
          <span className={styles.chartName}>{r.report.field.name}</span>
          <span className={styles.chartTrack}>
            <span className={styles.chartZero}/>
            {r.delta!==null&&<span className={`${styles.chartBar} ${improved?styles.chartImproved:styles.chartWorse}`}
              style={{width:`${Math.abs(r.delta)/max*46}%`,left:r.delta>=0?"50%":`${50-Math.abs(r.delta)/max*46}%`}}/>}
          </span>
          <strong className={styles.chartNumber}>{metricDifference(metric,r.delta)}</strong>
        </div>;
      })}
    </div>
    <p className={styles.hint}>Bars show the change from each current rotation to the recommended choice, not the confidence of the prediction. A zero means no change.</p>
    <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Field</th><th>Current</th><th>Recommended</th><th>Change</th></tr></thead><tbody>
      {rows.map(r=><tr key={r.report.id}><td><strong>{r.report.field.name}</strong></td><td>{formatMetric(metric,r.current)}</td><td>{formatMetric(metric,r.alternative)}</td><td><strong>{metricDifference(metric,r.delta)}</strong></td></tr>)}
    </tbody></table></div>
  </section>;
}
export default function PortfolioViewer({portfolioId}:{portfolioId:string}){
  const router=useRouter();
  const [screen,setScreen]=useState<Screen>({status:"loading"});
  const [tab,setTab]=useState<Tab>("overview");
  const [metric,setMetric]=useState<keyof RotationMetrics>("relativeYieldMedian");
  const [exporting,setExporting]=useState(false);
  const [error,setError]=useState<string|null>(null);
  useEffect(()=>{
    let alive=true;
    void getPortfolio(portfolioId).then(value=>{
      if(alive)setScreen(value?{status:"ready",value}:{status:"missing"});
    }).catch(e=>{if(alive)setScreen({status:"error",message:e instanceof Error?e.message:"Could not read this comparison."});});
    return()=>{alive=false};
  },[portfolioId]);
  const p=screen.status==="ready"?screen.value:null;
  const coverage=useMemo(()=>p?portfolioCoverage(p):null,[p]);
  if(!p)return <main className={styles.page}><div className={styles.container}>
    <Link href="/reports" className={styles.back}>← All reports</Link>
    <section className={styles.panel} role="status">{screen.status==="loading"?"Opening your farm comparison...":screen.status==="missing"?"This farm comparison was not found in this browser.":screen.status==="error"?screen.message:"Farm comparison unavailable."}</section>
  </div></main>;
  const metrics=REPORT_METRICS.filter(m=>m.key!=="grossMarginEurHa"||coverage!.economic>0);
  const date=new Date(p.createdAt).toLocaleString("en-GB",{dateStyle:"medium",timeStyle:"short"});
  const irrigation=sumChangeByArea(p,"irrigationMm");
  const fertilizer=sumChangeByArea(p,"fertilizerKgN");
  const financial=coverage!.economic>0?sumChangeByArea(p,"grossMarginEurHa"):null;
  const volumeChange=irrigation?(irrigation.alternative-irrigation.current)*10:null;
  async function exportPdf(){
    setError(null);setExporting(true);
    try{await downloadPortfolioPdf(p!)}catch(e){setError(e instanceof Error?e.message:"Farm PDF download failed.");}
    finally{setExporting(false)}
  }
  return <main className={styles.page}><div className={styles.container}>
    <div className={styles.topbar}><Link className={styles.back} href="/reports">← All reports</Link><span className={styles.eyebrow}>FIELDWISE / FARM REPORT</span></div>
    <header className={`${styles.hero} ${styles.reportHero}`}><div>
      <span className={styles.eyebrow}>FARM COMPARISON · {date}</span>
      <h1>Your farm, at a glance.</h1>
      <p>{p.reports.length} fields analyzed. Review the recommendations, compare indicators, and open each field&apos;s detailed report.</p></div>
      <div className={styles.actions}><button type="button" className={styles.primaryButton} disabled={exporting} onClick={()=>void exportPdf()}>{exporting?"Preparing PDF...":"Export farm PDF ↓"}</button>
        <button type="button" className={styles.ghostButton} onClick={()=>router.push("/analizza/tutti")}>New comparison</button></div>
      {error&&<p className={styles.warning} role="alert">{error}</p>}
    </header>
    <nav className={styles.reportTabs} aria-label="Farm report sections" role="tablist">
      {TABS.map(item=><button key={item.key} type="button" role="tab" id={`farm-tab-${item.key}`} aria-selected={tab===item.key} aria-controls="farm-tab-content"
        className={`${styles.reportTab} ${tab===item.key?styles.reportTabActive:""}`} onClick={()=>setTab(item.key)}>{item.label}</button>)}
    </nav>
    <div role="tabpanel" id="farm-tab-content" aria-labelledby={`farm-tab-${tab}`} className={`${styles.reportContent} ${styles[`tab-${tab}`]}`}>
      {tab==="overview"&&<>
        <div className={styles.sectionIntro}><div><span className={styles.eyebrow}>01 / OVERVIEW</span><h2>Key numbers</h2></div><p>The essentials, before the details.</p></div>
        <div className={styles.summaryGrid}>
          <div className={`${styles.summaryCard} ${styles.summaryPrimary}`}><span>Fields analyzed</span><strong>{p.reports.length} <em>/ {p.requestedFields}</em></strong><small>{p.failures.length?`${p.failures.length} fields need attention`:"All selected fields completed"}</small></div>
          <div className={styles.summaryCard}><span>Mapped area</span><strong>{fmt(coverage!.area)} <em>ha</em></strong><small>Geometry-based estimate</small></div>
          <div className={`${styles.summaryCard} ${styles.summaryWater}`}><span>Irrigation change</span><strong>{volumeChange!==null?`${volumeChange>0?"+":""}${fmt(volumeChange)} m³`:"N/A"}</strong><small>{irrigation?`${irrigation.count} eligible fields · modeled annual change`:"Insufficient field data"}</small></div>
          <div className={styles.summaryCard}><span>Economics available</span><strong>{coverage!.economic} <em>/ {p.reports.length}</em></strong><small>Fields with economics enabled</small></div>
        </div>
        <section className={styles.panel}><div className={styles.headline}><div><span className={styles.eyebrow}>WHAT TO DO NEXT</span><h2>Recommendations by field</h2></div><button type="button" className={styles.textButton} onClick={()=>setTab("fields")}>View all field details →</button></div>
          <div className={styles.decisionList}>{p.reports.map(report=>{
            const recommended=getRecommendation(report).recommended;
            return <article className={styles.decisionRow} key={report.id}>
              <div className={styles.decisionField}><span className={styles.fieldGlyph} aria-hidden="true">▦</span><div><strong>{report.field.name}</strong><small>{report.field.areaHectares!==null?`${fmt(report.field.areaHectares)} ha`:"Area unavailable"}</small></div></div>
              <div className={styles.decisionText}><span className={`${styles.decisionTag} ${recommended?styles.decisionChange:styles.decisionKeep}`}>{recommended?"Suggested change":"Keep / review"}</span><strong>{recommendationHeadline(report)}</strong></div>
              <Link href={`/reports/portfolio/${encodeURIComponent(p.id)}/field/${encodeURIComponent(report.id)}`} className={styles.configure}>Open report →</Link>
            </article>;
          })}</div>
        </section>
        <div className={styles.actionStrip}><div><strong>Want to see the trade-offs?</strong><span>Compare yield, irrigation, fertilizer and other modeled indicators.</span></div><button type="button" className={styles.ghostButton} onClick={()=>setTab("compare")}>Open comparison →</button></div>
        {!!p.failures.length&&<div className={styles.warning} role="status">{p.failures.length} selected field(s) could not be analyzed. See Details for the reasons.</div>}
      </>}
      {tab==="compare"&&<>
        <div className={styles.sectionIntro}><div><span className={styles.eyebrow}>02 / COMPARE</span><h2>Compare field indicators</h2></div><p>Changes relative to each field&apos;s current rotation.</p></div>
        <div className={styles.metricToolbar}><label className={styles.selector}>Choose an indicator <select value={metric} onChange={e=>setMetric(e.target.value as keyof RotationMetrics)}>{metrics.map(m=><option key={m.key} value={m.key}>{m.shortLabel}</option>)}</select></label><span className={styles.chartLegend}><i className={styles.legendGood}/> Favourable <i className={styles.legendRisk}/> Unfavourable</span></div>
        <MetricBreakdown p={p} metric={metric}/>
      </>}
      {tab==="fields"&&<>
        <div className={styles.sectionIntro}><div><span className={styles.eyebrow}>03 / FIELDS</span><h2>Rotation plans</h2></div><p>Every recommendation in one place.</p></div>
        <div className={styles.fieldReportGrid}>{p.reports.map(report=>{
          const recommendation=getRecommendation(report).recommended;
          return <article className={styles.fieldReportCard} key={report.id}>
            <div className={styles.fieldReportHeader}><div><span className={styles.eyebrow}>FIELD #{report.field.number}</span><h3>{report.field.name}</h3></div><span className={`${styles.decisionTag} ${recommendation?styles.decisionChange:styles.decisionKeep}`}>{recommendation?"Suggested change":"Keep / review"}</span></div>
            <div className={styles.rotationPair}><div><span>Current rotation</span><p>{labelRotation(report.results.current.label)}</p></div><div className={styles.recommendedRotation}><span>{recommendation?"Recommended rotation":"Recommended decision"}</span><p>{recommendationHeadline(report)}</p></div></div>
            <div className={styles.fieldReportMeta}><span><strong>Area</strong> {report.field.areaHectares===null?"N/A":`${fmt(report.field.areaHectares)} ha`}</span><span><strong>Irrigation</strong> {IRRIGATION_LABELS[report.inputs.irrigation]}</span><span><strong>Data</strong> {dataSourceLabel(report.engine.sourceMode)}</span></div>
            <Link className={styles.fieldReportLink} href={`/reports/portfolio/${encodeURIComponent(p.id)}/field/${encodeURIComponent(report.id)}`}>View individual report →</Link>
          </article>;
        })}</div>
      </>}
      {tab==="details"&&<>
        <div className={styles.sectionIntro}><div><span className={styles.eyebrow}>04 / DETAILS</span><h2>Coverage and model notes</h2></div><p>Technical context, totals and qualifications.</p></div>
        <section className={styles.panel}><span className={styles.eyebrow}>FARM-LEVEL ESTIMATES</span><h2>Operational totals</h2>
          <p className={styles.hint}>Area-weighted totals use only fields with an available area and valid model output. Missing fields are excluded, never treated as zero.</p>
          <div className={styles.detailGrid}>
            <div className={styles.summaryCard}><span>Recommended irrigation volume</span><strong>{irrigation?`${fmt(irrigation.alternative*10)} m³/year`:"N/A"}</strong><small>{irrigation?.count??0} covered fields</small></div>
            <div className={styles.summaryCard}><span>Recommended fertilizer input</span><strong>{fertilizer?`${fmt(fertilizer.alternative)} kg N/year`:"N/A"}</strong><small>{fertilizer?.count??0} covered fields</small></div>
            {financial&&<div className={styles.summaryCard}><span>Economic margin change</span><strong>{financial.alternative-financial.current>=0?"+":""}{fmt(financial.alternative-financial.current)} EUR/year</strong><small>{financial.count} eligible fields</small></div>}
          </div>
        </section>
        <section className={styles.panel}><span className={styles.eyebrow}>INTERPRETATION</span><h2>Important limitations</h2>
          <div className={styles.noteList}><p>Each field&apos;s ranking score is relative to the alternatives evaluated for that field. Scores from different fields should not be compared directly.</p>
            <p>The farm comparison does not optimize shared water, machinery or budget constraints. Results are modeled estimates, not measurements of farm outcomes.</p>
            <p>Methods, source data and field-specific uncertainties are described in the individual reports and the exported PDF.</p></div>
        </section>
        {!!p.failures.length&&<section className={styles.panel}><span className={styles.eyebrow}>INCOMPLETE ANALYSES</span><h2>Fields needing attention</h2><ul className={styles.failureList}>{p.failures.map(f=><li key={f.fieldId}><strong>{f.fieldName}:</strong> {f.message}</li>)}</ul></section>}
      </>}
    </div>
    <footer className={styles.footer}>FIELDWISE · Historical model estimates, not measured farm outcomes. See individual reports for full scientific details.</footer>
  </div></main>;
}
