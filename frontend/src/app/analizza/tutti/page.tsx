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
import { saveCompletedReport } from "../../../lib/reportStorage";
import { savePortfolio, type PortfolioFailure, type PortfolioReport } from "../../../lib/portfolioStorage";
import type { CompletedReport } from "../../../lib/reportTypes";
import styles from "../../../styles/portfolio.module.css";

type Screen = {status:"loading"}|{status:"ready";fields:FieldItem[];drafts:Record<string,AnalysisDraft|null>}|{status:"error";message:string};
const MAX_FIELDS_PER_BATCH = 25;
type ItemProgress={id:string;name:string;status:"pending"|"running"|"done"|"failed";stage:string};

export default function AnalyzeAllPage(){
  const router=useRouter();
  const [screen,setScreen]=useState<Screen>({status:"loading"});
  const [selected,setSelected]=useState<string[]>([]);
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
        setSelected(fields.map(f=>f.id));
      }catch(e){setScreen({status:"error",message:e instanceof Error?e.message:"Cannot load saved fields."});}
    });
    return()=>{live=false};
  },[]);
  const fields=screen.status==="ready"?screen.fields:[];
  const ready=screen.status==="ready";
  const chosen=fields.filter(f=>selected.includes(f.id));
  const invalid=chosen.filter(f=>{
    const draft=ready?screen.drafts[f.id]:null;
    if(!draft)return true;
    const active=Object.entries(draft.priorities).filter(([key])=>key!=="profitto"||draft.advancedEconomics===true);
    return active.every(([,value])=>value===0);
  });
  const setProgress=(id:string,patch:Partial<ItemProgress>)=>setItems(old=>old.map(x=>x.id===id?{...x,...patch}:x));
  function toggle(id:string){setSelected(old=>old.includes(id)?old.filter(k=>k!==id):[...old,id]);}

  async function start(){
    if(!ready||running||chosen.length<2||chosen.length>MAX_FIELDS_PER_BATCH||invalid.length)return;
    const jobs=chosen.map(f=>({field:f,draft:screen.drafts[f.id]!}));
    setMessage(null);setRunning(true);
    setItems(jobs.map(x=>({id:x.field.id,name:x.field.name,status:"pending",stage:"Waiting"})));
    const reports:CompletedReport[]=[];
    const failures:PortfolioFailure[]=[];
    for(const {field,draft} of jobs){
      setProgress(field.id,{status:"running",stage:"Preparing location-specific data..."});
      try{
        const point=getLabelPosition(field);
        await prepareLocalField(point,stage=>setProgress(field.id,{stage}));
        setProgress(field.id,{stage:"Running the rotation comparison..."});
        const report=await analyzeField({
          id:field.id,name:field.name,number:field.number,
          areaHectares:estimateFieldHectares(field),
          polygonCoordinates:field.coordinates,
          representativePoint:point,
        },draft);
        reports.push(report);
        // The portfolio contains full immutable report snapshots; a failure to
        // persist one separately must not destroy the comparison itself.
        try{await saveCompletedReport(report)}catch(e){console.warn("Single report history unavailable:",e)}
        setProgress(field.id,{status:"done",stage:"Completed"});
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
    <div className={styles.topbar}><Link href="/mappa" className={styles.back}>← Back to Map</Link><span className={styles.eyebrow}>FIELDWISE / FARM ANALYSIS</span></div>
    <header className={styles.hero}><span className={styles.eyebrow}>BATCH ANALYSIS</span><h1>Analyze your farm, field by field.</h1>
      <p>Run independent scientific analyses for each selected field, then compare the recommendations and export a farm-wide PDF.</p></header>
    {screen.status==="loading"&&<section className={styles.panel} role="status">Loading saved fields...</section>}
    {screen.status==="error"&&<section className={styles.panel} role="alert">{screen.message}</section>}
    {ready&&<>
      <section className={styles.panel}>
        <div className={styles.headline}><div><h2>Select fields</h2><p>All selected fields must have saved Analysis settings. Open each field's Analysis page to configure it first.</p></div>
          <button type="button" className={styles.ghostButton} disabled={running} onClick={()=>setSelected(selected.length===fields.length?[]:fields.map(f=>f.id))}>
            {selected.length===fields.length?"Deselect all":"Select all"}</button></div>
        {!fields.length?<p>No fields are saved. <Link href="/mappa">Draw a field on the map</Link> first.</p>:
        <div className={styles.fieldGrid}>{fields.map(f=>{
          const draft=screen.drafts[f.id];
          const configured=!!draft;
          return <label key={f.id} className={`${styles.fieldCard} ${selected.includes(f.id)?styles.selected:""}`}>
            <input type="checkbox" checked={selected.includes(f.id)} disabled={running} onChange={()=>toggle(f.id)}/>
            <span className={styles.fieldDetail}><strong>{f.name}</strong><small>Field #{f.number} · {estimateFieldHectares(f).toLocaleString("en-GB",{maximumFractionDigits:2})} ha</small>
              <small className={configured?styles.ok:styles.needsSetup}>{configured?"Settings saved":"Setup required"}</small></span>
            {!configured&&<Link className={styles.configure} href={`/analizza/${encodeURIComponent(f.id)}`} onClick={e=>e.stopPropagation()}>Configure →</Link>}
          </label>;
        })}</div>}
        <p className={styles.caution}>Up to {MAX_FIELDS_PER_BATCH} fields can be processed in one batch. Model results remain field-specific; different priorities, irrigation scenarios and source conditions can prevent direct comparisons. No common farm-wide crop-rotation optimization is performed.</p>
        <div className={styles.actions}><strong>{selected.length} selected</strong>
          <button type="button" className={styles.primaryButton} disabled={running||chosen.length<2||chosen.length>MAX_FIELDS_PER_BATCH||invalid.length>0} onClick={()=>void start()}>
            {running?"Analyzing your fields...":`Run ${chosen.length} field analyses`}</button></div>
        {chosen.length>MAX_FIELDS_PER_BATCH&&<p className={styles.warning} role="status">Select no more than {MAX_FIELDS_PER_BATCH} fields per batch to keep server load manageable.</p>}
        {invalid.length>0&&<p className={styles.warning} role="status">{invalid.length} selected field(s) need Analysis settings or at least one priority greater than zero.</p>}
        {chosen.length===1&&<p className={styles.caution}>For one field, use its individual Analyze button instead.</p>}
      </section>
      {items.length>0&&<section className={styles.panel} aria-live="polite"><h2>Analysis progress</h2>
        <p className={styles.caution}>Fields are processed one at a time. Keep this tab open until completion; an API preparation stage may take several minutes.</p>
        <div className={styles.progressList}>{items.map(item=><div className={styles.progressRow} key={item.id}>
          <span className={styles.progressIcon}>{item.status==="done"?"✓":item.status==="failed"?"!":item.status==="running"?"◌":"·"}</span>
          <div><strong>{item.name}</strong><small>{item.stage}</small></div><span className={styles.progressStatus}>{item.status}</span></div>)}</div>
      </section>}
      {message&&<div className={styles.warning} role="alert">{message}</div>}
    </>}
  </div></main>;
}
