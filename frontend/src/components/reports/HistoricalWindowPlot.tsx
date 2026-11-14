"use client";

import { useState } from "react";
import { historicalPointYear as pointYear, type HistoricalWindows } from "../../lib/reportTypes";
import styles from "../../styles/reports.module.css";

type Measure = "relativeYield" | "irrigationMm" | "nitrogenLeachingKgN" | "humusChangeTonsHa" | "grossMarginEurHa";
const measures: {id:Measure;label:string;unit:string;factor:number}[] = [
  {id:"relativeYield",label:"Relative yield",unit:"%",factor:100},
  {id:"irrigationMm",label:"Irrigation demand",unit:"mm/year",factor:1},
  {id:"nitrogenLeachingKgN",label:"Nitrogen leaching",unit:"kg N/ha/year",factor:1},
  {id:"humusChangeTonsHa",label:"Annual humus change",unit:"t/ha/year",factor:1},
  {id:"grossMarginEurHa",label:"Economic margin",unit:"EUR/ha/year",factor:1},
];

const colors:Record<string,string>={current:"#8c9c91",alternative1:"#247a4b",alternative2:"#bc843e"};
const names:Record<string,string>={current:"Current",alternative1:"Alternative 1",alternative2:"Alternative 2"};
const isNumber=(n:number|null):n is number=>typeof n==="number"&&Number.isFinite(n);

export default function HistoricalWindowPlot({history,showEconomics}:{history:HistoricalWindows;showEconomics:boolean}) {
  const [metric,setMetric]=useState<Measure>("relativeYield");
  const allowed=measures.filter(m=>showEconomics||m.id!=="grossMarginEurHa");
  const selected=allowed.find(m=>m.id===metric)??allowed[0];
  const legacy=!history.series.some(s=>s.points.some(p=>p.evaluatedYear!==undefined));
  const years=[...new Set(history.series.flatMap(s=>s.points.map(pointYear)).filter((y):y is number=>y!==null))].sort((a,b)=>a-b);
  const vals=history.series.flatMap(s=>s.points.map(p=>p[selected.id])).filter(isNumber).map(v=>v*selected.factor);
  if (years.length<2||vals.length<2) return null;
  const smallest=Math.min(...vals),largest=Math.max(...vals),pad=Math.max((largest-smallest)*0.12,0.01);
  const yMin=smallest-pad,yMax=largest+pad;
  const W=900,H=266,left=80,right=25,top=20,bottom=40;
  const x=(year:number)=>left+(year-years[0])/(years[years.length-1]-years[0]||1)*(W-left-right);
  const y=(value:number)=>top+(yMax-value)/(yMax-yMin)*(H-top-bottom);
  const ticks=Array.from({length:4},(_,i)=>yMin+(yMax-yMin)*i/3);
  return <section className={styles.panel} aria-label="Historical rotation simulation series">
    <div className={styles.panelHeading}>
      <div><span className={styles.smallCaps}>Historical rotation windows</span><h3>How simulated outcomes vary across historical conditions</h3></div>
      <label className={styles.metricSelector}><span className={styles.srOnly}>Time-series indicator</span>
        <select value={selected.id} onChange={e=>setMetric(e.target.value as Measure)}>
          {allowed.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}
        </select>
      </label>
    </div>
    <svg className={styles.historyPlot} viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`${selected.label} by ${legacy?"simulation start year":"first year of the evaluated rotation cycle"}`}>
      {ticks.map((v,i)=><g key={i}><line x1={left} x2={W-right} y1={y(v)} y2={y(v)} stroke="#dce8d9" strokeDasharray="4 5"/>
        <text x={left-10} y={y(v)+4} textAnchor="end" fill="#637d69" fontSize="13">{Math.abs(v)>=100?v.toFixed(0):v.toFixed(1)}</text></g>)}
      {years.filter((_,i)=>i%Math.max(1,Math.ceil(years.length/7))===0||i===years.length-1).map(yr=><text key={yr} x={x(yr)} y={H-15} textAnchor="middle" fontSize="13" fill="#637d69">{yr}</text>)}
      {history.series.map(s=>{
        const points=s.points.filter(p=>isNumber(p[selected.id])&&pointYear(p)!==null).map(p=>({x:x(pointYear(p) as number),y:y((p[selected.id] as number)*selected.factor)}));
        return <g key={s.role}><polyline points={points.map(p=>`${p.x},${p.y}`).join(" ")} fill="none" stroke={colors[s.role]??"#386a4e"} strokeWidth="3" strokeLinejoin="round" strokeLinecap="round"/>
          {points.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r="2.7" fill={colors[s.role]??"#386a4e"}/>)}</g>;
      })}
      <text x={W-25} y={H-15} textAnchor="end" fontSize="12" fill="#637d69">{legacy?"Simulation start year":"Evaluated cycle starts"} · {selected.unit}</text>
    </svg>
    <div className={styles.historyLegend}>{history.series.map(s=><span key={s.role}><i style={{background:colors[s.role]}}/>{names[s.role]??s.role}</span>)}</div>
    <p className={styles.footnote}>{history.method} {legacy
      ? <>This saved report predates the corrected axis: the x-axis shows the <strong>simulation start year, which includes the spin-up cycle</strong>; the evaluated cycle starts later. Run the analysis again for the corrected axis.</>
      : <>The x-axis is the <strong>first year of the evaluated rotation cycle</strong> (spin-up years excluded), not a single-year observation or a future projection.</>}</p>
  </section>;
}
