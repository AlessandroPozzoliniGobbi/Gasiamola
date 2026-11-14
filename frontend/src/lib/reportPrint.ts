/** FIELDWISE print-to-PDF export.
 *  The detailed Markdown is the single narrative source; figures are a projection of
 *  the same browser report numbers into SVG. Print dialog -> Save as PDF.
 */
import { REPORT_METRICS, formatMetric, type CompletedReport, type RotationMetrics } from "./reportTypes";
import { renderReportMarkdown, includesEconomics } from "./reportMarkdown";

const esc=(x:unknown)=>String(x??"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
function rich(s:string):string {
  return esc(s).replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>").replace(/\*(.+?)\*/g,"<em>$1</em>");
}
function chartHtml(report: CompletedReport): string {
  const outcomes=[report.results.current,...report.results.alternatives.slice(0,2)];
  const keys=REPORT_METRICS.filter(m=>includesEconomics(report)||m.key!=="grossMarginEurHa");
  return `<div class="figure-grid">${keys.map((metric,mi)=>{
    const vals=outcomes.map(r=>r.metrics[metric.key]).filter((n):n is number=>typeof n==="number"&&Number.isFinite(n));
    if(!vals.length)return `<section class="figure"><h4>Figure ${mi+1}. ${esc(metric.label)}</h4><p>Data unavailable</p></section>`;
    const min=Math.min(0,...vals),max=Math.max(0,...vals),range=Math.max(1e-9,max-min);
    const left=98,top=34,w=340,rowH=35,height=top+outcomes.length*rowH+22;
    const scale=(n:number)=>(n-min)/range;
    const xzero=left+scale(0)*w;
    const bars=outcomes.map((entry,i)=>{
      const v=entry.metrics[metric.key];const y=top+i*rowH;
      const role=i===0?"Current":`Alt ${i}`;
      const display=formatMetric(metric.key,v);
      const x=v===null?xzero:Math.min(xzero,left+scale(v)*w),barW=v===null?0:Math.max(1,Math.abs(left+scale(v)*w-xzero));
      return `<text x="4" y="${y+14}" class="bar-label">${esc(role)}</text><rect x="${x}" y="${y+2}" width="${barW}" height="15" rx="4" fill="${i===0?'#9cbaa2':'#2b7c50'}"/><text x="${left+w+8}" y="${y+14}" class="bar-value">${esc(display)}</text>`;
    }).join("");
    return `<section class="figure"><h4>Figure ${mi+1}. ${esc(metric.label)}</h4><svg viewBox="0 0 610 ${height}" role="img" aria-label="${esc(metric.label)} comparison"><line x1="${xzero}" y1="${top-8}" x2="${xzero}" y2="${height-10}" stroke="#859e8d" stroke-width="1.2" stroke-dasharray="3 3"/>${bars}</svg><p>${metric.higherIsBetter?"Higher":"Lower"} is preferable, other things equal. Values are historical model indicators.</p></section>`;
  }).join("")}</div>`;
}
function markdownHtml(markdown:string,report:CompletedReport):string {
  const lines=markdown.split(/\r?\n/);
  const out:string[]=[];let inList=false;let inTable=false;let paragraphs:string[]=[];
  const flushParagraph=()=>{if(paragraphs.length){out.push(`<p>${rich(paragraphs.join(" "))}</p>`);paragraphs=[];}};
  const closeList=()=>{if(inList){out.push("</ul>");inList=false;}};
  const closeTable=()=>{if(inTable){out.push("</tbody></table></div>");inTable=false;}};
  for(let i=0;i<lines.length;i++){
    const raw=lines[i];const line=raw.trim();
    if(!line){flushParagraph();closeList();closeTable();continue;}
    if(line==="<!-- FIELDWISE_CHARTS -->") {flushParagraph();closeList();closeTable();out.push(chartHtml(report));continue;}
    const heading=line.match(/^(#{1,4})\s+(.+)$/);
    if(heading){flushParagraph();closeList();closeTable();const level=heading[1].length;out.push(`<h${level}>${rich(heading[2])}</h${level}>`);continue;}
    if(line.startsWith("|")&&line.endsWith("|")){
      flushParagraph();closeList();
      if(/^\|[\s|:\-]+\|$/.test(line))continue;
      const cells=line.slice(1,-1).split(/(?<!\\)\|/).map(s=>s.replace(/\\\|/g,"|").trim());
      if(!inTable){out.push(`<div class="table-wrap"><table><thead><tr>${cells.map(s=>`<th>${rich(s)}</th>`).join("")}</tr></thead><tbody>`);inTable=true;}
      else out.push(`<tr>${cells.map(s=>`<td>${rich(s)}</td>`).join("")}</tr>`);
      continue;
    }
    closeTable();
    if(line.startsWith("- ")){flushParagraph();if(!inList){out.push("<ul>");inList=true;}out.push(`<li>${rich(line.slice(2))}</li>`);continue;}
    closeList();paragraphs.push(line);
  }
  flushParagraph();closeList();closeTable();return out.join("\n");
}
export function renderReportPrintHtml(report:CompletedReport,demo=false):string {
  const content=markdownHtml(renderReportMarkdown(report,demo),report);
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"/><title>FIELDWISE | ${esc(report.field.name)} | Report</title><meta name="viewport" content="width=device-width,initial-scale=1"/><style>
@page{size:A4;margin:15mm 16mm 17mm}*{box-sizing:border-box}html{background:#eaf0e9}body{font-family:Arial,Helvetica,sans-serif;color:#20382c;margin:0;background:#fff;font-size:10.5pt;line-height:1.48}main{max-width:920px;margin:0 auto;padding:40px 48px 70px}header.site-header{border-bottom:3px solid #256a49;padding:0 0 12px;margin-bottom:24px;display:flex;justify-content:space-between;align-items:center}header.site-header strong{letter-spacing:.13em;color:#22583b;font-size:17px}header.site-header span{font-size:10px;color:#668775;text-transform:uppercase;letter-spacing:.11em}
h1{font-size:29px;line-height:1.14;margin:5px 0 16px;color:#173e2c;letter-spacing:-.03em}h2{font-size:16.7px;color:#1e5c3e;margin:25px 0 12px;padding:7px 0 6px;border-bottom:1px solid #c7dbcb;break-after:avoid}h3{font-size:13px;margin:18px 0 8px;color:#225a3d;break-after:avoid}h4{font-size:10px;margin:0 0 9px;color:#1b5d39}p{margin:9px 0 12px}ul{margin:8px 0 14px;padding-left:21px}li{margin:4px 0}strong{color:#1b4b35} .table-wrap{overflow:visible;margin:11px 0 20px}table{border-collapse:collapse;width:100%;font-size:8.5pt;line-height:1.4;table-layout:auto}thead{display:table-header-group}tr{break-inside:avoid}th{background:#e3f0e2;text-align:left;color:#194a30;padding:7px;border-bottom:2px solid #9bbb9f}td{padding:6px 7px;border-bottom:1px solid #e1e9df;vertical-align:top;overflow-wrap:anywhere}tbody tr:nth-child(even){background:#f6faf5} .figure-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:16px 0 18px}.figure{break-inside:avoid;border:1px solid #cfe0cf;border-radius:9px;padding:12px 11px 8px;background:#f9fcf7;min-width:0}.figure svg{width:100%;height:auto}.figure p{font-size:8px;color:#67806c;margin:3px 0 0}.bar-label{font-size:15px;fill:#315944;font-weight:600}.bar-value{font-size:11.5px;fill:#183c29;font-weight:600}.notice{padding:11px 15px;background:#fff5db;border-left:4px solid #ca9d4b;color:#714e20;font-size:11px;margin:17px 0}.actions{padding:12px 18px;background:#eaf1e7;display:flex;justify-content:center;align-items:center;gap:14px;position:sticky;top:0;z-index:30;border-bottom:1px solid #ccdccc;font-family:Arial}.actions button{border:0;border-radius:8px;background:#266b4a;color:white;padding:11px 17px;font-size:14px;cursor:pointer}.actions span{color:#54745c;font-size:13px}footer{margin-top:30px;border-top:1px solid #c9dccb;padding-top:9px;color:#6f8976;font-size:9px} @media print{html{background:white}body{font-size:10pt;-webkit-print-color-adjust:exact;print-color-adjust:exact}.actions{display:none}main{max-width:none;padding:0}h1{font-size:27px}.figure-grid{gap:9px}.figure{padding:9px}.table-wrap{overflow:visible}.figure svg{max-height:105px}} @media (max-width:650px){main{padding:23px 16px}.figure-grid{grid-template-columns:1fr}.actions{flex-wrap:wrap}}
</style></head><body><div class="actions"><button type="button" onclick="window.print()">Print / Save as PDF</button><span>Choose “Save as PDF” in your browser&apos;s print dialog.</span></div><main><header class="site-header"><strong>FIELDWISE</strong><span>Scientific decision-support report</span></header>${demo?'<div class="notice">DEMO ONLY — FICTIONAL VALUES; NOT ENGINE RESULTS.</div>':''}${content}<footer>FIELDWISE · Generated from the completed browser report snapshot. Not a substitute for field measurement or professional agronomic assessment.</footer></main></body></html>`;
}
export function openPdfReport(report:CompletedReport,demo=false):void {
  const tab=window.open("","_blank");
  if(!tab){window.alert("Your browser blocked the PDF preview. Allow pop-ups for this site and try again.");return;}
  tab.document.open();tab.document.write(renderReportPrintHtml(report,demo));tab.document.close();
  tab.focus();
}
