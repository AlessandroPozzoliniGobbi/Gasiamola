"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getPortfolio, type PortfolioReport } from "../../lib/portfolioStorage";
import { comparisonRows, portfolioCoverage, sumChangeByArea } from "../../lib/portfolioMetrics";
import { downloadPortfolioPdf } from "../../lib/portfolioPdf";
import { REPORT_METRICS, formatMetric, labelRotation, recommendationHeadline, type RotationMetrics } from "../../lib/reportTypes";
import { IRRIGATION_LABELS } from "../../lib/analysisStorage";
import styles from "../../styles/portfolio.module.css";

type Screen={status:"loading"}|{status:"ready";value:PortfolioReport}|{status:"error";message:string}|{status:"missing"};
const fmt=(x:number)=>x.toLocaleString("en-GB",{maximumFractionDigits:1});
function metricDifference(key:keyof RotationMetrics,value:number|null):string {
  if(value===null)return "N/A";
  if(key.startsWith("relativeYield"))return `${value>0?"+":""}${(value*100).toFixed(1)} pp`;
  return `${value>0?"+":""}${formatMetric(key,value)}`;
}
function MetricBreakdown({p,metric}:{p:PortfolioReport;metric:keyof RotationMetrics}){
  const selected=REPORT_METRICS.find(m=>m.key===metric)!;
  const rows=comparisonRows(p,metric);
  const max=Math.max(0.000001,...rows.map(r=>Math.abs(r.delta??0)));
  return <section className={styles.panel}>
    <div className={styles.headline}><div><span className={styles.eyebrow}>COMPARISON BY FIELD</span><h2>{selected.label}</h2></div><span className={styles.legend}>{selected.higherIsBetter?"Higher is generally better":"Lower is generally better"}</span></div>
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
    <p className={styles.caution}>Bars show the signed change from each field&apos;s current rotation to its recommendation (zero where the recommendation is to keep the current rotation), not an estimate of certainty.</p>
    <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Field</th><th>Current</th><th>Recommended</th><th>Difference</th></tr></thead><tbody>
      {rows.map(r=><tr key={r.report.id}><td>{r.report.field.name}</td><td>{formatMetric(metric,r.current)}</td><td>{formatMetric(metric,r.alternative)}</td><td>{metricDifference(metric,r.delta)}</td></tr>)}
    </tbody></table></div>
  </section>;
}
export default function PortfolioViewer({portfolioId}:{portfolioId:string}){
  const router=useRouter();
  const [screen,setScreen]=useState<Screen>({status:"loading"});
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
    <section className={styles.panel}>{screen.status==="loading"?"Opening your portfolio...":screen.status==="missing"?"This portfolio report was not found in this browser.":screen.status==="error"?screen.message:"Portfolio unavailable."}</section>
  </div></main>;
  const metrics=REPORT_METRICS.filter(m=>m.key!=="grossMarginEurHa"||coverage!.economic>0);
  const date=new Date(p.createdAt).toLocaleString("en-GB",{dateStyle:"medium",timeStyle:"short"});
  const irrigation=sumChangeByArea(p,"irrigationMm");
  const fertilizer=sumChangeByArea(p,"fertilizerKgN");
  const financial=coverage!.economic>0?sumChangeByArea(p,"grossMarginEurHa"):null;
  async function exportPdf(){
    if(!p)return;
    setError(null);setExporting(true);
    try{await downloadPortfolioPdf(p)}catch(e){setError(e instanceof Error?e.message:"Portfolio PDF download failed.");}
    finally{setExporting(false)}
  }
  return <main className={styles.page}><div className={styles.container}>
    <div className={styles.topbar}><Link className={styles.back} href="/reports">← All reports</Link><span className={styles.eyebrow}>FIELDWISE / PORTFOLIO REPORT</span></div>
    <header className={styles.hero}><span className={styles.eyebrow}>FARM COMPARISON · {date}</span>
      <h1>One farm. Many field decisions.</h1>
      <p>Compare independently modeled rotations across your fields, inspect the trade-offs and export a consolidated technical report.</p>
      <div className={styles.actions}><button type="button" className={styles.primaryButton} disabled={exporting} onClick={()=>void exportPdf()}>{exporting?"Preparing PDF...":"Export farm PDF"}</button>
        <button type="button" className={styles.ghostButton} onClick={()=>router.push("/analizza/tutti")}>New farm analysis</button></div>
      {error&&<p className={styles.warning} role="alert">{error}</p>}
    </header>
    <div className={styles.summaryGrid}>
      <div className={styles.summaryCard}><span>Fields analyzed</span><strong>{p.reports.length} / {p.requestedFields}</strong><small>{p.failures.length?`${p.failures.length} unsuccessful`:"All completed"}</small></div>
      <div className={styles.summaryCard}><span>Mapped surface</span><strong>{fmt(coverage!.area)} ha</strong><small>Geometry-based area estimate</small></div>
      <div className={styles.summaryCard}><span>Modeled irrigation change</span><strong>{irrigation?`${irrigation.alternative-irrigation.current>=0?"+":""}${fmt((irrigation.alternative-irrigation.current)*10)} m3`:"N/A"}</strong><small>{irrigation?`${irrigation.count} eligible fields`:"No complete area data"}</small></div>
      <div className={styles.summaryCard}><span>Economic assessment</span><strong>{coverage!.economic} / {p.reports.length}</strong><small>Fields with Advanced Analysis enabled</small></div>
    </div>
    <section className={styles.panel}><span className={styles.eyebrow}>01 / ROTATION PLANS</span><h2>Recommended rotations by field</h2>
      <div className={styles.tableWrap}><table className={styles.table}><thead><tr><th>Field</th><th>Area</th><th>Current rotation</th><th>Recommendation</th><th>Scenario</th><th>Data used</th><th>Details</th></tr></thead><tbody>
      {p.reports.map(r=><tr key={r.id}><td><strong>{r.field.name}</strong></td><td>{r.field.areaHectares===null?"N/A":`${fmt(r.field.areaHectares)} ha`}</td>
        <td>{labelRotation(r.results.current.label)}</td><td>{recommendationHeadline(r)}</td>
        <td>{IRRIGATION_LABELS[r.inputs.irrigation]}</td>
        <td>{r.engine.sourceMode==="pilot_reference"?<strong>Pilot data, NOT this field</strong>:r.engine.sourceMode==="local_estimate"?"Local estimate":r.engine.sourceMode==="pilot_point"?"Pilot point":"Not specified"}</td><td><Link className={styles.configure} href={`/reports/portfolio/${encodeURIComponent(p.id)}/field/${encodeURIComponent(r.id)}`}>Field report →</Link></td></tr>)}
      </tbody></table></div>
    </section>
    <div className={styles.metricHeading}><div><span className={styles.eyebrow}>02 / SIDE-BY-SIDE INDICATORS</span><h2>Explore the differences</h2></div>
      <label className={styles.selector}>Indicator <select value={metric} onChange={e=>setMetric(e.target.value as keyof RotationMetrics)}>{metrics.map(m=><option key={m.key} value={m.key}>{m.shortLabel}</option>)}</select></label></div>
    <MetricBreakdown p={p} metric={metric}/>
    <section className={styles.panel}><span className={styles.eyebrow}>03 / FARM-LEVEL INTERPRETATION</span><h2>Operational totals and coverage</h2>
      <p>Area-weighted totals are estimated from modeled indicators. They are meaningful only for the fields with known surface areas and valid model output; missing fields are excluded, not assumed to be zero.</p>
      <div className={styles.summaryGrid}>
        <div className={styles.summaryCard}><span>Recommended irrigation volume</span><strong>{irrigation?`${fmt(irrigation.alternative*10)} m3/year`:"N/A"}</strong><small>{irrigation?.count??0} covered fields</small></div>
        <div className={styles.summaryCard}><span>Recommended fertilizer input</span><strong>{fertilizer?`${fmt(fertilizer.alternative)} kg N/year`:"N/A"}</strong><small>{fertilizer?.count??0} covered fields</small></div>
        {financial&&<div className={styles.summaryCard}><span>Economic margin change</span><strong>{financial.alternative-financial.current>=0?"+":""}{fmt(financial.alternative-financial.current)} EUR/year</strong><small>{financial.count} opt-in fields only</small></div>}
      </div>
      <p className={styles.caution}>A field&apos;s ranking score is relative to the rotations evaluated for that field. Comparing scores across fields is not scientifically justified. This dashboard does not solve shared water, machinery or budget constraints.</p>
    </section>
    {!!p.failures.length&&<section className={styles.panel}><span className={styles.eyebrow}>INCOMPLETE ANALYSES</span><h2>Fields needing attention</h2>
      <ul>{p.failures.map(f=><li key={f.fieldId}><strong>{f.fieldName}:</strong> {f.message}</li>)}</ul></section>}
    <footer className={styles.footer}>FIELDWISE · Modeled historical estimates, not measured field outcomes. See individual field reports for detailed caveats and evidence.</footer>
  </div></main>;
}
