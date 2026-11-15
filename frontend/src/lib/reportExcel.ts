import { translateFutureCompliance } from "./futureNotices";
/** Dependency-free XLSX/OOXML export of the completed FIELDWISE browser report.
 *  Every numerical value behind the report comparison chart is exported as a number.
 *  Raw simulation time series absent from the saved report cannot be recreated here.
 */
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS, FUTURE_SSP_LABELS } from "./analysisStorage";
import { REPORT_METRICS, alternativeTitle, getRecommendation, historicalPointYear, labelRotation, marginDefinition,
  recommendationHeadline, sourceModeText, visibleStatements, type CompletedReport } from "./reportTypes";
import { includesEconomics, includesFuture } from "./reportMarkdown";

type Cell = string | number | null | { formula: string; cached: number | null };
type Sheet = { name: string; rows: Cell[][]; widths?: number[]; chart?: {title:string;unit:string} };
const text = (v: unknown) => v === null || v === undefined ? "Not provided" : String(v);
const good = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);
const coord = (p?: [number,number] | null) => p ? `${p[1]}, ${p[0]}` : "Not supplied";

function sheetsForReport(report: CompletedReport, demo=false): Sheet[] {
  const econ = includesEconomics(report);
  const future = includesFuture(report);
  const rotations = [report.results.current, ...report.results.alternatives];
  const futureAlternatives = report.results.future?.candidateRotations ?? [];
  const labels = rotations.map((r,i) => i === 0 ? "Current" : `Alternative ${i}`);
  const recommendation = getRecommendation(report);
  const metrics = REPORT_METRICS.filter((m) => econ || m.key !== "grossMarginEurHa");
  const notes: Cell[][] = [["Source / parameter", "Value"],
    ["Report ID", report.id], ["Field ID", report.field.id], ["Engine version", text(report.engine.version)],
    ["Data period", text(report.engine.dataPeriod)], ["Scenario code", report.results.scenario],
    ["Source mode", report.engine.sourceMode ?? "Not stated"], ["Data scope", sourceModeText(report)],
    ["Model point [lat, lon]",coord(report.engine.modelPoint)],
    ["Ensemble calculated at", text(report.engine.ensembleCalculatedAt)],
    ["Methodology note", text(report.engine.methodologyNote)],
    ["Interpretation", "Historical ensemble, not future forecast. Scores are relative, not confidence."],
    ["Completeness", "Browser report snapshot only: raw daily model outputs are not included unless delivered by API."],
  ];
  if (report.engine.localData) {
    Object.entries(report.engine.localData).forEach(([key,value]) => notes.push([key, typeof value === "number" ? value : String(value)]));
  }
  if (econ) notes.push(["Margin definition", marginDefinition(report)]);
  (report.engine.limitations?.statements ?? []).forEach((n,i) => notes.push([`Limitation ${i+1}`, n]));
  visibleStatements(report.results.notes, undefined, econ).forEach((n,i) => notes.push([`Model note ${i+1}`, n]));

  const indicators: Cell[][] = [["Indicator", "Unit", "Current", "Alternative 1", "Alternative 2", "Delta Alt 1", "Delta Alt 2", "Delta % Alt 1", "Delta % Alt 2"]];
  for (const m of metrics) {
    const values = rotations.slice(0,3).map((r) => good(r.metrics[m.key]) ? r.metrics[m.key] : null);
    const a = values[0] ?? null, b = values[1] ?? null, c = values[2] ?? null;
    const row = indicators.length + 1;
    const f = (col:string, val:number|null): Cell => ({formula:`IF(OR(C${row}="",${col}${row}=""),"",${col}${row}-C${row})`,cached:good(val)&&good(a)?val-a:null});
    const p = (col:string, val:number|null): Cell => ({formula:`IF(OR(C${row}="",C${row}=0,${col}${row}=""),"",(${col}${row}-C${row})/ABS(C${row}))`,cached:good(val)&&good(a)&&a!==0?(val-a)/Math.abs(a):null});
    indicators.push([m.label, m.unit, a,b,c,f("D",b),f("E",c),p("D",b),p("E",c)]);
  }

  const chartRows:Cell[][] = [["Indicator", "Rotation", "Value (raw)", "Unit", "Better direction"]];
  metrics.forEach((m) => rotations.forEach((r,i) => chartRows.push([m.label,labels[i],r.metrics[m.key],m.unit,m.higherIsBetter?"Higher":"Lower"])));
  const rotationRows:Cell[][] = [["Role", "Engine role", "Crop rotation", "Relative score", "Position in compared set", ...metrics.map(m=>m.label)]];
  rotations.forEach((r,i) => rotationRows.push([labels[i], i === 0 ? "Current rotation (baseline)" : alternativeTitle(report, i-1),
    labelRotation(r.label),r.score,r.position ?? null,...metrics.map(m=>r.metrics[m.key])]));
  const evidenceRows:Cell[][] = [["Rotation", "Type", "Statement"]];
  rotations.forEach((r,i) => {
    visibleStatements(r.evidence, r.evidenceTopics, econ).forEach(x=>evidenceRows.push([labels[i],"Evidence",x]));
    visibleStatements(r.risks, r.riskTopics, econ).forEach(x=>evidenceRows.push([labels[i],"Risk",x]));
  });
  const priorities:Cell[][] = [["Priority", "Weight (0-10)"]];
  PRIORITY_KEYS.filter(k=>econ || k!=="profitto").forEach(k=>priorities.push([PRIORITY_LABELS[k],report.inputs.priorities[k] ?? 0]));
  const cycleRows:Cell[][] = [["Year", "Crop", "Rye cover afterwards"]];
  report.inputs.rotation.forEach((s,i)=>cycleRows.push([i+1,CROP_LABELS[s.crop],s.coverAfter?"Yes":"No"]));
  const overview:Cell[][] = [["FIELDWISE / REPORT SUMMARY", "Value"],
    ["Data status",demo?"DEMONSTRATION: FICTIONAL DATA — NOT ENGINE RESULTS":"Completed browser report snapshot"],
    ["Field",report.field.name], ["Field number",report.field.number], ["Area (ha)",report.field.areaHectares],
    ["Created UTC",report.createdAt], ["Report ID",report.id], ["Representative point [lat,lon]",coord(report.field.representativePoint)],
    ["Model point [lat,lon]",coord(report.engine.modelPoint)],
    ["Reference data mode",report.engine.sourceMode ?? "Not stated"],
    ["Current rotation",labelRotation(report.results.current.label)],
    ["Rotation order note",report.results.rotationOrderNote ?? "Same order as entered"],
    ["Recommendation",recommendationHeadline(report)],
    ["Recommendation note",`${recommendation.message}${recommendation.priorityWarning ? ` ${recommendation.priorityWarning}` : ""}`],
    ["Irrigation scenario", IRRIGATION_LABELS[report.inputs.irrigation]],
    ["Rotations compared",report.results.comparedRotations],
    ["Economic assessment requested",econ?"Yes":"No"],
    ["Climate projections requested",future?"Yes":"No"],
    ...(future && report.results.future ? [
      ["Future scenario", `${FUTURE_SSP_LABELS[report.results.future.ssp_code].title} (+${report.results.future.horizon_years} years)`],
      ["Future adaptation candidate", report.results.future.best_rotation ? labelRotation(report.results.future.best_rotation) : "No compliant candidate available"],
    ] : []),
    ["Note","Values are historical simulation indicators, not predictions. See provenance sheet."],
  ];
  const polygon:Cell[][] = [["Ring", "Vertex", "Longitude", "Latitude"]];
  report.field.polygonCoordinates?.forEach((ring,ri)=>ring.forEach((xy,vi)=>polygon.push([ri+1,vi+1,good(xy[0])?xy[0]:null,good(xy[1])?xy[1]:null])));
  const windows = report.results.historicalWindows;
  const legacyAxis = !windows?.series.some(series => series.points.some(point => point.evaluatedYear !== undefined));
  const yearLabel = legacyAxis ? "Simulation start year (legacy, includes spin-up)" : "First year of evaluated cycle";
  const historicalRaw:Cell[][] = [["Rotation", yearLabel, "Cyclic members", "Relative yield", "Irrigation (mm/year)", "Nitrogen leaching (kg N/ha/year)", "Humus change (t/ha/year)", "Margin (EUR/ha/year)"]];
  const historicalPlots: Sheet[] = [];
  if (windows?.series.length) {
    windows.series.forEach(series => series.points.forEach(point => historicalRaw.push([
      series.role,historicalPointYear(point),point.memberCount,point.relativeYield,point.irrigationMm,
      point.nitrogenLeachingKgN,point.humusChangeTonsHa,econ?point.grossMarginEurHa:null
    ])));
    const years=[...new Set(windows.series.flatMap(item=>item.points.map(historicalPointYear)).filter((y):y is number=>y!==null))].sort((a,b)=>a-b);
    const specs: {name:string;key:"relativeYield"|"irrigationMm"|"humusChangeTonsHa"|"grossMarginEurHa";unit:string;scale:number}[]=[
      {name:"Historical yield",key:"relativeYield",unit:"%",scale:100},
      {name:"Historical water",key:"irrigationMm",unit:"mm/year",scale:1},
      {name:"Historical humus",key:"humusChangeTonsHa",unit:"t/ha/year",scale:1},
      ...(econ?[{name:"Historical margin",key:"grossMarginEurHa" as const,unit:"EUR/ha/year",scale:1}]:[]),
    ];
    specs.forEach(spec=>{
      const rows:Cell[][]=[[yearLabel, "Current", "Alternative 1", "Alternative 2"]];
      for(const year of years) {
        const row:Cell[]=[year];
        for(const role of ["current","alternative1","alternative2"]){
          const point=windows.series.find(s=>s.role===role)?.points.find(p=>historicalPointYear(p)===year);
          const value=point?.[spec.key];
          row.push(good(value)?value*spec.scale:null);
        }
        rows.push(row);
      }
      historicalPlots.push({name:spec.name,rows,widths:[25,24,24,24],chart:{title:spec.name.replace("Historical", "Evaluated rotation cycles —"),unit:spec.unit}});
    });
  }
  return [
    {name:"Summary",rows:overview,widths:[42,84]},
    {name:"Indicators",rows:indicators,widths:[35,20,18,18,18,18,18,18,18]},
    {name:"Chart data",rows:chartRows,widths:[35,22,20,22,22]},
    {name:"Rotations",rows:rotationRows,widths:[20,48,20,...metrics.map(()=>18)]},
    {name:"Priorities",rows:priorities,widths:[36,18]},
    {name:"Crop cycle",rows:cycleRows,widths:[16,30,24]},
    {name:"Evidence and risks",rows:evidenceRows,widths:[22,20,105]},
    ...(future && report.results.future ? [{
      name: "Climate Projections",
      widths: [38, 28, 20, 65],
      rows: [
        ["Parameter / Projection", "Value", "Unit", "Interpretation"],
        ["IPCC Scenario", FUTURE_SSP_LABELS[report.results.future.ssp_code].title, report.results.future.ssp_code.toUpperCase(), FUTURE_SSP_LABELS[report.results.future.ssp_code].description],
        ["Time horizon", report.results.future.horizon_years, "years", "CMIP6 linear scaled delta-change"],
        ["Future reference rotation", labelRotation(report.results.future.current_rotation), "", report.results.future.referenceMatchesRequestedRotation === false ? "Archived reference differs from the selected current rotation" : "Current rotation under evaluation"],
        ["Historical baseline relative yield", report.results.future.baseline_resa_rel_pct, "%", "Historical median yield index"],
        ["Future projected relative yield", report.results.future.future_resa_rel_pct, "%", "Future median yield under scenario"],
        ["Yield delta", report.results.future.delta_resa_rel_pct, "pp", "Future minus baseline yield"],
        ["Historical baseline yield", report.results.future.baseline_resa_t_ha, "t/ha", "Historical average yield"],
        ["Future projected yield", report.results.future.future_resa_t_ha, "t/ha", "Future average yield"],
        ["Historical baseline margin", report.results.future.baseline_margine_eur_ha, "EUR/ha/year", "Historical gross margin"],
        ["Future projected margin", report.results.future.future_margine_eur_ha, "EUR/ha/year", "Future gross margin"],
        ["Margin delta", report.results.future.delta_margine_eur_ha, "EUR/ha/year", "Future minus baseline margin"],
        ["Future variable costs", report.results.future.future_costo_eur_ha, "EUR/ha/year", "Projected water, fertilizer and other crop costs"],
        ["Cost delta", report.results.future.delta_costo_eur_ha, "EUR/ha/year", "Future minus baseline costs"],
        ["Future extreme heat days (Tmax > 35°C)", report.results.future.future_hot_days_ann, "days/year", "Extreme thermal stress frequency"],
        ["Future reference ET0", report.results.future.future_et0_ann_mm, "mm/year", "Recalculated Penman-Monteith ET0"],
        ["Precomputed adaptation candidate", report.results.future.best_rotation ? labelRotation(report.results.future.best_rotation) : "None compliant/verified", "", report.results.future.adaptationNotice ?? "Candidate is not optimized for custom priorities"],
        ...(report.results.future.best_rotation ? ([
        ["Additional gain vs current", report.results.future.delta_guadagno_eur_ha, "EUR/ha/year", "Extra margin by switching to adaptation strategy"],
        ["Adaptation yield boost", report.results.future.delta_resa_best_pct, "pp", "Yield increase vs future current rotation"],
        ["Adaptation projected yield", report.results.future.best_resa_rel_pct, "%", "Relative yield index of best rotation"],
        ["Adaptation average yield", report.results.future.best_resa_t_ha, "t/ha", "Average yield of best rotation"],
        ["Adaptation irrigation demand", report.results.future.best_irrigazione_mm, "mm/year", "Annual water requirement"],
        ["Adaptation nitrogen fertilizer", report.results.future.best_concime_kg_n_ha, "kg N/ha", "Annual fertilizer application"],
        ["Regulatory compliance", translateFutureCompliance(report.results.future.best_conformita), "", "Regional integrated production rules"],
        ] as Cell[][]) : []),
      ] as Cell[][],
    }] : []),
    ...(future && futureAlternatives.length ? [{
      name: "Future alternatives",
      widths: [18, 46, 22, 22, 26, 21, 24, 27, 25],
      rows: [
        ["Rank (archived)", "Crop rotation", "Relative yield (%)", "Margin (EUR/ha/year)",
         "Delta vs reference (EUR/ha/year)", "Irrigation (mm/year)", "Fertilizer (kg N/ha/year)",
         "N leaching (kg N/ha/year)", "Humus change (t/ha/year)"],
        ...futureAlternatives.map(c => [
          c.precomputedRank, labelRotation(c.rotation), c.relativeYieldPct, c.marginEurHa,
          c.marginDeltaVsCurrentEurHa, c.irrigationMm, c.fertilizerKgN,
          c.nitrogenLeachingKgN, c.humusChangeTonsHa,
        ]),
        ["Methodology", report.results.future?.candidateRotationsNote ?? "Future scenario subset; no personalized reranking"],
      ] as Cell[][],
    }] : []),
    {name:"Provenance",rows:notes,widths:[43,110]},
    ...(historicalRaw.length>1?[{name:"Historical windows",rows:historicalRaw,widths:[24,18,18,20,20,24,30,28,31]}]:[]),
    ...historicalPlots,
    ...(polygon.length>1?[{name:"Polygon vertices",rows:polygon,widths:[15,17,24,24]}]:[]),
  ];
}

const xml = (str:string): string => str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&apos;").replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/g,"");
const col = (idx:number):string => {let out=""; for(let x=idx+1;x>0;x=Math.floor((x-1)/26))out=String.fromCharCode(65+(x-1)%26)+out;return out;};
function sheetXml(sheet:Sheet):string {
  const rowText = sheet.rows.map((row,ri)=>{
    const cells = row.map((val,ci)=>{
      if(val===null || val===undefined) return "";
      const ref=`${col(ci)}${ri+1}`;
      const isRelative=sheet.name==="Indicators" && ri>=1 && ri<=3;
      const pctCell=(isRelative && ci>=2) || (sheet.name==="Indicators" && ri>=1 && (ci===7 || ci===8)) ||
        (sheet.name==="Rotations" && ri>=1 && ci>=3 && ci<=5) ||
        (sheet.name==="Chart data" && ri>=1 && ci===2 && /relative yield/i.test(String(row[0])));
      const wrapped = ri>0 && (sheet.name==="Provenance" && ci===1 || sheet.name==="Summary" && ci===1 || sheet.name==="Evidence and risks" && ci===2);
      const style=ri===0?1:wrapped?5:pctCell?4:ri%2===0?3:2;
      if(typeof val === "number") return Number.isFinite(val)?`<c r="${ref}" s="${style}"><v>${val}</v></c>`:"";
      if(typeof val === "object") return `<c r="${ref}" s="${style}"><f>${xml(val.formula)}</f>${val.cached===null?"":`<v>${val.cached}</v>`}</c>`;
      return `<c r="${ref}" s="${style}" t="inlineStr"><is><t xml:space="preserve">${xml(val)}</t></is></c>`;
    }).join("");
    const noteColumn = sheet.name==="Evidence and risks" ? 2 : 1;
    const note = row[noteColumn];
    const colWidth = sheet.widths?.[noteColumn] ?? 60;
    const lines = typeof note === "string" ? note.split("\n").reduce((n,part)=>n+Math.max(1,Math.ceil(part.length/Math.max(18,colWidth-8))),0) : 1;
    const height = ri===0 ? 27 : (lines > 1 ? Math.min(180,Math.max(22,lines*18+7)) : 20);
    return `<row r="${ri+1}" ht="${height}" customHeight="1">${cells}</row>`;
  }).join("");
  const columns=(sheet.widths??[]).map((width,i)=>`<col min="${i+1}" max="${i+1}" width="${width}" customWidth="1"/>`).join("");
  const last=sheet.rows.reduce((n,r)=>Math.max(n,r.length),1);
  const lastName=`${col(last-1)}${Math.max(sheet.rows.length,1)}`;
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`+
    `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">`+
    `<dimension ref="A1:${lastName}"/><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>`+
    `<sheetFormatPr defaultRowHeight="20"/><cols>${columns}</cols><sheetData>${rowText}</sheetData>`+
    `<autoFilter ref="A1:${lastName}"/>${sheet.chart?'<drawing r:id="rId1"/>':''}</worksheet>`;
}

// Well-formed ZIP files with uncompressed entries (method 0); Excel needs no external ZIP library.
const enc = new TextEncoder();
const u16=(n:number):number[]=>[n&255,(n>>>8)&255];
const u32=(n:number):number[]=>[n&255,(n>>>8)&255,(n>>>16)&255,(n>>>24)&255];
const crcTable=Array.from({length:256},(_,i)=>{let c=i;for(let j=0;j<8;j++)c=(c&1)?0xedb88320^(c>>>1):c>>>1;return c>>>0;});
function crc32(data:Uint8Array):number {let c=0xffffffff;for(const b of data)c=crcTable[(c^b)&255]^(c>>>8);return (c^0xffffffff)>>>0;}
function zipStore(files: {path:string;content:string}[]):Uint8Array {
  const parts: Uint8Array[]=[];const central:Uint8Array[]=[];let offset=0;
  for(const f of files){
    const name=enc.encode(f.path),data=enc.encode(f.content),crc=crc32(data);
    const local=new Uint8Array([...u32(0x04034b50),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(name.length),...u16(0),...name]);
    parts.push(local,data);
    central.push(new Uint8Array([...u32(0x02014b50),...u16(20),...u16(20),...u16(0),...u16(0),...u16(0),...u16(0),...u32(crc),...u32(data.length),...u32(data.length),...u16(name.length),...u16(0),...u16(0),...u16(0),...u16(0),...u32(0),...u32(offset),...name]));
    offset+=local.length+data.length;
  }
  const centralSize=central.reduce((n,p)=>n+p.length,0);
  const end=new Uint8Array([...u32(0x06054b50),...u16(0),...u16(0),...u16(files.length),...u16(files.length),...u32(centralSize),...u32(offset),...u16(0)]);
  const total=offset+centralSize+end.length;
  const bytes=new Uint8Array(total);let index=0;
  for(const p of [...parts,...central,end]) {bytes.set(p,index);index+=p.length;}
  return bytes;
}
function excelLineChart(sheet:Sheet, index:number):string {
  const ns="http://schemas.openxmlformats.org/drawingml/2006/chart";
  const last=sheet.rows.length;
  const series=[1,2,3].map((ci,ix)=>{
    const letter=col(ci);const data=sheet.rows.slice(1).map((r,i)=>({i,v:r[ci]})).filter(x=>typeof x.v==="number"&&Number.isFinite(x.v));
    return `<c:ser><c:idx val="${ix}"/><c:order val="${ix}"/><c:tx><c:v>${xml(String(sheet.rows[0][ci]))}</c:v></c:tx>`+
      `<c:spPr><a:ln w="28575"><a:solidFill><a:srgbClr val="${["93A69B","267549","BD8442"][ix]}"/></a:solidFill></a:ln></c:spPr><c:marker><c:symbol val="circle"/><c:size val="4"/></c:marker>`+
      `<c:cat><c:numRef><c:f>'${xml(sheet.name)}'!$A$2:$A$${last}</c:f><c:numCache><c:formatCode>0</c:formatCode><c:ptCount val="${last-1}"/>${sheet.rows.slice(1).map((r,i)=>`<c:pt idx="${i}"><c:v>${r[0]}</c:v></c:pt>`).join("")}</c:numCache></c:numRef></c:cat>`+
      `<c:val><c:numRef><c:f>'${xml(sheet.name)}'!$${letter}$2:$${letter}$${last}</c:f><c:numCache><c:formatCode>General</c:formatCode><c:ptCount val="${last-1}"/>${data.map(({i,v})=>`<c:pt idx="${i}"><c:v>${v}</c:v></c:pt>`).join("")}</c:numCache></c:numRef></c:val></c:ser>`;
  }).join("");
  const cat=7000+index*2,val=cat+1;
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><c:chartSpace xmlns:c="${ns}" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><c:chart>`+
    `<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="en-US"/><a:t>${xml(sheet.chart?.title??sheet.name)} (${xml(sheet.chart?.unit??"")})</a:t></a:r></a:p></c:rich></c:tx></c:title>`+
    `<c:plotArea><c:layout/><c:lineChart><c:grouping val="standard"/>${series}<c:axId val="${cat}"/><c:axId val="${val}"/></c:lineChart>`+
    `<c:catAx><c:axId val="${cat}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="b"/><c:tickLblPos val="nextTo"/><c:crossAx val="${val}"/><c:crosses val="autoZero"/></c:catAx>`+
    `<c:valAx><c:axId val="${val}"/><c:scaling><c:orientation val="minMax"/></c:scaling><c:axPos val="l"/><c:majorGridlines/><c:numFmt formatCode="General" sourceLinked="1"/><c:tickLblPos val="nextTo"/><c:crossAx val="${cat}"/><c:crosses val="autoZero"/></c:valAx></c:plotArea>`+
    `<c:legend><c:legendPos val="b"/><c:layout/></c:legend><c:plotVisOnly val="1"/></c:chart></c:chartSpace>`;
}
function excelDrawing(index:number):string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`+
    `<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">`+
    `<xdr:twoCellAnchor editAs="oneCell"><xdr:from><xdr:col>5</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>1</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from>`+
    `<xdr:to><xdr:col>17</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>22</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to>`+
    `<xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="${index+2}" name="FIELDWISE historical chart"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr>`+
    `<xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">`+
    `<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:id="rId1"/>`+
    `</a:graphicData></a:graphic></xdr:graphicFrame><xdr:clientData/></xdr:twoCellAnchor></xdr:wsDr>`;
}
export function buildExcelWorkbook(report:CompletedReport, demo=false):Uint8Array {
  const sheets=sheetsForReport(report,demo);
  const fileTypes=sheets.map((_,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("");
  const charts=sheets.map((sheet,sheetIndex)=>({sheet,sheetIndex})).filter(x=>x.sheet.chart);
  const extraContent=charts.map((_,i)=>`<Override PartName="/xl/charts/chart${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/><Override PartName="/xl/drawings/drawing${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.drawing+xml"/>`).join("");
  const files=[
    {path:"[Content_Types].xml",content:`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${fileTypes}${extraContent}</Types>`},
    {path:"_rels/.rels",content:`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`},
    {path:"xl/workbook.xml",content:`<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map((s,i)=>`<sheet name="${xml(s.name)}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join("")}</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>`},
    {path:"xl/_rels/workbook.xml.rels",content:`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_,i)=>`<Relationship Id="rId${i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join("")}<Relationship Id="rId${sheets.length+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`},
    {path:"xl/styles.xml",content:`<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Aptos"/><color rgb="FF244735"/></font><font><b/><sz val="11"/><name val="Aptos"/><color rgb="FFFFFFFF"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF246B4B"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEDF5EA"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="6"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="10" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>`},
    ...sheets.map((s,i)=>({path:`xl/worksheets/sheet${i+1}.xml`,content:sheetXml(s)})),
    ...charts.flatMap(({sheet,sheetIndex},i)=>[
      {path:`xl/worksheets/_rels/sheet${sheetIndex+1}.xml.rels`,content:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing" Target="../drawings/drawing${i+1}.xml"/></Relationships>`},
      {path:`xl/drawings/drawing${i+1}.xml`,content:excelDrawing(i)},
      {path:`xl/drawings/_rels/drawing${i+1}.xml.rels`,content:`<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" Target="../charts/chart${i+1}.xml"/></Relationships>`},
      {path:`xl/charts/chart${i+1}.xml`,content:excelLineChart(sheet,i)},
    ]),
  ];
  return zipStore(files);
}
export function downloadExcelReport(report:CompletedReport,demo=false):void {
  const bytes=buildExcelWorkbook(report,demo);
  const blob=new Blob([new Uint8Array(bytes) as BlobPart],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"});
  const url=URL.createObjectURL(blob);const a=document.createElement("a");
  a.href=url;a.download=`FIELDWISE_${demo?"DEMO_":""}${report.id}.xlsx`;
  a.style.display="none";document.body.appendChild(a);a.click();
  // Some browsers cancel object-URL downloads if revoked immediately.
  setTimeout(()=>{a.remove();URL.revokeObjectURL(url);},60_000);
}
