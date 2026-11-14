"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { deletePortfolio, listPortfolios, MAX_PORTFOLIOS, type PortfolioSummary } from "../../lib/portfolioStorage";
import styles from "../../styles/reports.module.css";

type State={status:"loading"}|{status:"ready";items:PortfolioSummary[]}|{status:"error";message:string};
export default function PortfolioHistory(){
  const [state,setState]=useState<State>({status:"loading"});
  const [removing,setRemoving]=useState<string|null>(null);
  const refresh=useCallback(async()=>{
    try{setState({status:"ready",items:await listPortfolios()})}
    catch(e){setState({status:"error",message:e instanceof Error?e.message:"Unable to read farm comparisons."})}
  },[]);
  useEffect(()=>{queueMicrotask(()=>{void refresh()})},[refresh]);
  async function remove(item:PortfolioSummary){
    if(!window.confirm(`Delete the farm comparison from ${new Date(item.createdAt).toLocaleDateString("en-GB")}? This cannot be undone.`))return;
    setRemoving(item.id);
    try{await deletePortfolio(item.id);await refresh()}
    catch(e){setState({status:"error",message:e instanceof Error?e.message:"Could not delete comparison."})}
    finally{setRemoving(null)}
  }
  return <section aria-labelledby="portfolio-history-title">
    <div className={styles.historyHeading}>
      <div><h2 id="portfolio-history-title">Farm comparison history</h2><span>Last {MAX_PORTFOLIOS} comparisons · Stored on this browser</span></div>
      <Link className={styles.primaryButton} href="/analizza/tutti">Analyze multiple fields ↗</Link>
    </div>
    {state.status==="loading"&&<p role="status">Loading farm comparisons...</p>}
    {state.status==="error"&&<p role="alert">{state.message} <button type="button" onClick={()=>void refresh()}>Try again</button></p>}
    {state.status==="ready"&&(state.items.length===0?
      <div className={styles.emptyState}><h3>No farm comparisons yet.</h3><p>Analyze two or more fields to create your first portfolio report.</p>
        <Link className={styles.primaryButton} href="/analizza/tutti">Compare your fields ↗</Link></div>:
      <div className={styles.historyList}>{state.items.map(item=><article key={item.id} className={styles.historyRow}>
        <div className={styles.historyGlyph} aria-hidden="true">▦</div>
        <div className={styles.historyInfo}>
          <div className={styles.historyTitle}><h3>Farm comparison · {item.completedFields} fields</h3><span>{new Date(item.createdAt).toLocaleString("en-GB",{dateStyle:"medium",timeStyle:"short"})}</span></div>
          <p>{item.fieldNames.join(" · ")}</p>
          {item.failures>0&&<p>{item.failures} unsuccessful analyses excluded from the comparison.</p>}
        </div>
        <div className={styles.historyActions}>
          <Link className={styles.openReport} href={`/reports/portfolio/${encodeURIComponent(item.id)}`}>Open comparison →</Link>
          <button className={styles.deleteReport} type="button" disabled={removing===item.id} onClick={()=>void remove(item)}>Delete</button>
        </div>
      </article>)}</div>)}
  </section>;
}
