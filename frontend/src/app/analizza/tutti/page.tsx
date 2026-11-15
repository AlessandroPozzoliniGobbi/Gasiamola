"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FieldItem } from "../../../types/field";
import { loadSavedFields } from "../../../lib/fieldStorage";
import { getSavedAnalysisDraft, type AnalysisDraft } from "../../../lib/analysisStorage";
import { getLabelPosition } from "../../../lib/fieldGeometry";
import { estimateFieldHectares } from "../../../lib/fieldArea";
import { analyzeField, prepareLocalField } from "../../../lib/engineApi";
import { listRecentCompletedReports, saveCompletedReport } from "../../../lib/reportStorage";
import { findReusableFieldReport } from "../../../lib/reuseFieldReport";
import { savePortfolio, type PortfolioFailure, type PortfolioReport } from "../../../lib/portfolioStorage";
import type { CompletedReport, FieldSnapshot } from "../../../lib/reportTypes";
import styles from "../../../styles/portfolio.module.css";

type Screen = {status:"loading"}|{status:"ready";fields:FieldItem[];drafts:Record<string,AnalysisDraft|null>}|{status:"error";message:string};
const MAX_FIELDS_PER_BATCH = 25;
type ItemProgress={id:string;name:string;status:"pending"|"running"|"done"|"failed"|"reused";stage:string};

function fieldSnapshot(field: FieldItem): FieldSnapshot {
  return {
    id:field.id, name:field.name, number:field.number,
    areaHectares:estimateFieldHectares(field),
    polygonCoordinates:field.coordinates,
    representativePoint:getLabelPosition(field),
  };
}
function setupProblem(draft:AnalysisDraft|null):string|null {
  if (!draft) return "Add this field's analysis settings before running a comparison.";
  const active=Object.entries(draft.priorities).filter(([key])=>key!=="profitto"||draft.advancedEconomics===true);
  if (active.every(([,value])=>value===0)) return "Choose at least one priority above zero in this field's analysis settings.";
  return null;
}

export default function AnalyzeAllPage(){
  const router=useRouter();
  const [screen,setScreen]=useState<Screen>({status:"loading"});
  const [selected,setSelected]=useState<string[]>([]);
  const [pastReports,setPastReports]=useState<CompletedReport[]>([]);
  const [reuseReports,setReuseReports]=useState(true);
  const [historyAvailable,setHistoryAvailable]=useState(true);
  const [running,setRunning]=useState(false);
  const [items,setItems]=useState<ItemProgress[]>([]);
  const [message,setMessage]=useState<string|null>(null);
  useEffect(()=>{
    let live=true;
    queueMicrotask(()=>{
      if(!live)return;
      try{
        const fields=loadSavedFields()?.fields??[];
        const drafts:Record<string,AnalysisDraft|null>={};
        fields.forEach(f=>{drafts[f.id]=getSavedAnalysisDraft(f.id)});
        setScreen({status:"ready",fields,drafts});
        // A return from an individual field's settings carries the original
        // selection. Opening this page normally still selects every field.
        const savedSelection = new URLSearchParams(window.location.search).get("selected");
        const selectedIds = savedSelection === null ? null : new Set(savedSelection.split(","));
        setSelected(fields.filter(f=>selectedIds === null || selectedIds.has(f.id)).map(f=>f.id));
      }catch(e){setScreen({status:"error",message:e instanceof Error?e.message:"Cannot load saved fields."});}
    });
    void listRecentCompletedReports().then(reports=>{
      if(live)setPastReports(reports);
    }).catch(()=>{if(live)setHistoryAvailable(false)});
    return()=>{live=false};
  },[]);
  const fields=screen.status==="ready"?screen.fields:[];
  const ready=screen.status==="ready";
  const chosen=fields.filter(f=>selected.includes(f.id));
  const invalid=chosen.filter(f=>setupProblem(ready?screen.drafts[f.id]:null)!==null);
  const cachedById:Record<string,CompletedReport>={};
  if(ready){
    fields.forEach(field=>{
      const draft=screen.drafts[field.id];
      if(!draft||setupProblem(draft))return;
      const cached=findReusableFieldReport(pastReports,fieldSnapshot(field),draft);
      if(cached)cachedById[field.id]=cached;
    });
  }
  const reuseCount=chosen.filter(field=>Boolean(cachedById[field.id])).length;
  const setProgress=(id:string,patch:Partial<ItemProgress>)=>setItems(old=>old.map(x=>x.id===id?{...x,...patch}:x));
  function toggle(id:string){setSelected(old=>old.includes(id)?old.filter(k=>k!==id):[...old,id]);}

  async function start(){
    if(!ready||running||chosen.length<2||chosen.length>MAX_FIELDS_PER_BATCH||invalid.length)return;
    const jobs=chosen.map(f=>({field:f,draft:screen.drafts[f.id]!,snapshot:fieldSnapshot(f)}));
    setMessage(null);setRunning(true);
    setItems(jobs.map(x=>({id:x.field.id,name:x.field.name,status:"pending",stage:"Waiting"})));
    const reports:CompletedReport[]=[];
    const failures:PortfolioFailure[]=[];
    for(const {field,draft,snapshot} of jobs){
      const previous=reuseReports?cachedById[field.id]:null;
      if(previous){
        reports.push(previous);
        setProgress(field.id,{status:"reused",stage:`Saved analysis from ${new Date(previous.createdAt).toLocaleDateString("en-GB")}`});
        continue;
      }
      setProgress(field.id,{status:"running",stage:"Preparing location-specific data..."});
      try{
        await prepareLocalField(snapshot.representativePoint!,stage=>setProgress(field.id,{stage}));
        setProgress(field.id,{stage:"Running the rotation comparison..."});
        const report=await analyzeField(snapshot,draft);
        reports.push(report);
        // The farm report is a snapshot; it must survive even if the separate
        // single-report history is unavailable.
        try{await saveCompletedReport(report)}catch(e){console.warn("Single report history unavailable:",e)}
        setProgress(field.id,{status:"done",stage:"New analysis completed"});
      }catch(e){
        const reason=e instanceof Error?e.message:"Field analysis failed.";
        failures.push({fieldId:field.id,fieldName:field.name,message:reason});
        setProgress(field.id,{status:"failed",stage:reason});
      }
    }
    if(reports.length){
      const portfolio:PortfolioReport={schemaVersion:1,id:crypto.randomUUID(),createdAt:new Date().toISOString(),
        requestedFields:jobs.length,reports,failures};
      try{
        await savePortfolio(portfolio);
        router.push(`/reports/portfolio/${encodeURIComponent(portfolio.id)}`);
        return;
      }catch(e){setMessage(e instanceof Error?e.message:"Portfolio storage is unavailable.");}
    }else setMessage("All selected analyses failed. Check the field errors and try again.");
    setRunning(false);
  }
  return <main className={styles.page}><div className={styles.container}>
    <div className={styles.topbar}><Link href="/mappa" className={styles.back}>← Back to map</Link><span className={styles.eyebrow}>FIELDWISE / FARM ANALYSIS</span></div>
    <header className={`${styles.hero} ${styles.batchHero}`}>
      <div><span className={styles.eyebrow}>MULTIPLE FIELDS</span><h1>Analyze your fields together.</h1>
        <p>Choose at least two fields. Each field is analyzed independently, then the results are brought together in one clear comparison.</p></div>
      <div className={styles.heroSteps} aria-label="How it works"><span><b>1</b>Select fields</span><span><b>2</b>Check settings</span><span><b>3</b>Compare results</span></div>
    </header>
    {screen.status==="loading"&&<section className={styles.panel} role="status">Loading saved fields...</section>}
    {screen.status==="error"&&<section className={styles.panel} role="alert">{screen.message}</section>}
    {ready&&<>
      <section className={styles.panel} aria-labelledby="select-fields-heading">
        <div className={styles.headline}><div><span className={styles.eyebrow}>01 / SELECTION</span><h2 id="select-fields-heading">Select your fields</h2>
          <p>All selected fields need saved analysis settings. You can fix missing settings directly from the field card.</p></div>
          <button type="button" className={styles.ghostButton} disabled={running||!fields.length} onClick={()=>setSelected(selected.length===fields.length?[]:fields.map(f=>f.id))}>
            {selected.length===fields.length?"Deselect all":"Select all"}</button></div>
        {!fields.length?<p className={styles.emptyNotice}>No fields are saved. <Link href="/mappa">Draw a field on the map</Link> first.</p>:
        <div className={styles.fieldGrid}>{fields.map(f=>{
          const draft=screen.drafts[f.id];
          const problem=setupProblem(draft);
          const cached=cachedById[f.id];
          const settingsHref=`/analizza/${encodeURIComponent(f.id)}?from=multiple&selected=${encodeURIComponent(selected.join(","))}`;
          return <div key={f.id} className={`${styles.fieldCard} ${selected.includes(f.id)?styles.selected:""} ${problem?styles.fieldNeedsSetup:""}`}>
            <label className={styles.fieldChoice}>
              <input type="checkbox" checked={selected.includes(f.id)} disabled={running} onChange={()=>toggle(f.id)} aria-label={`Select ${f.name}`}/>
              <span className={styles.fieldDetail}><strong>{f.name}</strong><small>Field #{f.number} · {estimateFieldHectares(f).toLocaleString("en-GB",{maximumFractionDigits:2})} ha</small></span>
            </label>
            <div className={styles.fieldMeta}>
              {problem?<>
                <span className={styles.setupBadge} tabIndex={0} title={problem} aria-label={`Attention: ${problem}`}>
                  <span className={styles.warningIcon} aria-hidden="true">!</span> Needs setup
                  <span className={styles.setupTooltip} role="tooltip">{problem}</span>
                </span>
              </>:<>
                <span className={styles.readyBadge}>✓ Settings ready</span>
                {cached&&<span className={styles.reuseBadge} title={`Saved on ${new Date(cached.createdAt).toLocaleString("en-GB")}`}>Saved report available</span>}
              </>}
              <Link className={styles.configure} href={settingsHref}>{problem?"Configure field →":"Edit settings →"}</Link>
            </div>
          </div>;
        })}</div>}
        <div className={styles.selectionFooter}>
          <div className={styles.selectedSummary}><strong>{chosen.length}</strong><span>fields selected</span></div>
          <button type="button" className={styles.primaryButton} disabled={running||chosen.length<2||chosen.length>MAX_FIELDS_PER_BATCH||invalid.length>0} onClick={()=>void start()}>
            {running?"Analyzing fields...":`Analyze ${chosen.length} fields →`}</button>
        </div>
        {invalid.length>0&&<p className={styles.warning} role="status"><strong>{invalid.length} selected field{invalid.length===1?" needs":"s need"} attention.</strong> Open its settings using the amber indicator to finish setup.</p>}
        {chosen.length>MAX_FIELDS_PER_BATCH&&<p className={styles.warning} role="status">Select no more than {MAX_FIELDS_PER_BATCH} fields per batch.</p>}
        {chosen.length===1&&<p className={styles.hint}>Select at least two fields to compare. To analyze just one, use its individual analysis page.</p>}
      </section>
      <section className={`${styles.panel} ${styles.reusePanel}`} aria-labelledby="reuse-heading">
        <div className={styles.headline}><div><span className={styles.eyebrow}>02 / SAVED RESULTS</span><h2 id="reuse-heading">Save time with previous analyses</h2>
          <p>When the field geometry and every analysis setting match, you can use a previously saved result instead of calculating it again.</p></div>
          <span className={styles.countBadge}>{reuseCount} match{reuseCount===1?"":"es"}</span></div>
        <label className={styles.reuseChoice}>
          <input type="checkbox" checked={reuseReports} disabled={running||!historyAvailable} onChange={e=>setReuseReports(e.target.checked)}/>
          <span><strong>Reuse matching saved reports</strong><small>Turn this off to recalculate every selected field with the current backend.</small></span>
        </label>
        <p className={styles.hint}>Only locally saved, field-specific reports can be reused. Saved snapshots may reflect an earlier engine version; for the latest calculations, turn reuse off. {historyAvailable?"":"Saved report history is unavailable in this browser, so fields will be analyzed again."}</p>
      </section>
      <details className={styles.infoDetails}><summary>How does the farm comparison work?</summary><p>Up to {MAX_FIELDS_PER_BATCH} fields are processed one at a time. The results are field-specific; different priorities, irrigation scenarios or source data can make direct comparisons misleading. FIELDWISE does not optimize a shared rotation for the whole farm.</p></details>
      {items.length>0&&<section className={styles.panel} aria-live="polite"><span className={styles.eyebrow}>ANALYSIS STATUS</span><h2>Field progress</h2>
        <p className={styles.hint}>Keep this tab open until the report opens. Newly calculated fields may take several minutes.</p>
        <div className={styles.progressList}>{items.map(item=><div className={styles.progressRow} key={item.id}>
          <span className={`${styles.progressIcon} ${item.status==="failed"?styles.progressFailed:""}`}>{item.status==="done"||item.status==="reused"?"✓":item.status==="failed"?"!":item.status==="running"?"◌":"·"}</span>
          <div><strong>{item.name}</strong><small>{item.stage}</small></div><span className={styles.progressStatus}>{item.status==="reused"?"Reused":item.status}</span></div>)}</div>
      </section>}
      {message&&<div className={styles.warning} role="alert">{message}</div>}
    </>}
  </div></main>;
}
