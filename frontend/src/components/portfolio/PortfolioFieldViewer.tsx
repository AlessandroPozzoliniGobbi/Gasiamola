"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import ReportDashboard from "../reports/ReportDashboard";
import { getPortfolio } from "../../lib/portfolioStorage";
import type { CompletedReport } from "../../lib/reportTypes";
import styles from "../../styles/portfolio.module.css";
export default function PortfolioFieldViewer({portfolioId,reportId}:{portfolioId:string;reportId:string}){
  const [state,setState]=useState<{loading:boolean;report:CompletedReport|null}>({loading:true,report:null});
  useEffect(()=>{let active=true;void getPortfolio(portfolioId).then(p=>{
    if(active)setState({loading:false,report:p?.reports.find(r=>r.id===reportId)??null});
  }).catch(()=>{if(active)setState({loading:false,report:null})});return()=>{active=false};},[portfolioId,reportId]);
  if(state.report)return <ReportDashboard report={state.report}/>;
  return <main className={styles.page}><div className={styles.container}>
    <Link href={`/reports/portfolio/${encodeURIComponent(portfolioId)}`} className={styles.back}>← Back to farm comparison</Link>
    <section className={styles.panel}>{state.loading?"Loading the individual field report...":"This field report was not found in the saved farm comparison."}</section>
  </div></main>;
}
