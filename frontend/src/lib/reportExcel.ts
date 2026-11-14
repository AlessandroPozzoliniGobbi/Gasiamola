/** Dependency-free XLSX/OOXML export of the completed FIELDWISE browser report.
 *  Every numerical value behind the report comparison chart is exported as a number.
 *  Raw simulation time series absent from the saved report cannot be recreated here.
 */
import { CROP_LABELS, IRRIGATION_LABELS, PRIORITY_KEYS, PRIORITY_LABELS } from "./analysisStorage";
import { REPORT_METRICS, labelRotation, type CompletedReport } from "./reportTypes";
import { includesEconomics } from "./reportMarkdown";

type Cell = string | number | null | { formula: string; cached: number | null };
type Sheet = { name: string; rows: Cell[][]; widths?: number[] };
const text = (v: unknown) => v === null || v === undefined ? "Not provided" : String(v);
const good = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);
const coord = (p?: [number,number] | null) => p ? `${p[1]}, ${p[0]}` : "Not supplied";

function sheetsForReport(report: CompletedReport, demo=false): Sheet[] {
  const econ = includesEconomics(report);
  const rotations = [report.results.current, ...report.results.alternatives];
  const labels = rotations.map((r,i) => i === 0 ? "Current" : `Alternative ${i}`);
  const metrics = REPORT_METRICS.filter((m) => econ || m.key !== "grossMarginEurHa");
  const notes: Cell[][] = [["Source / parameter", "Value"],
    ["Report ID", report.id], ["Field ID", report.field.id], ["Engine version", text(report.engine.version)],
    ["Data period", text(report.engine.dataPeriod)], ["Scenario code", report.results.scenario],
    ["Source mode", report.engine.sourceMode ?? "Not stated"], ["Model point [lat, lon]",coord(report.engine.modelPoint)],
    ["Methodology note", text(report.engine.methodologyNote)],
    ["Interpretation", "Historical ensemble, not future forecast. Scores are relative, not confidence."],
    ["Completeness", "Browser report snapshot only: raw daily model outputs are not included unless delivered by API."],
  ];
  if (report.engine.localData) {
    Object.entries(report.engine.localData).forEach(([key,value]) => notes.push([key, typeof value === "number" ? value : String(value)]));
  }
  report.results.notes.forEach((n,i) => notes.push([`Model note ${i+1}`, n]));

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
  const rotationRows:Cell[][] = [["Role", "Crop rotation", "Relative score", ...metrics.map(m=>m.label)]];
  rotations.forEach((r,i) => rotationRows.push([labels[i],labelRotation(r.label),r.score,...metrics.map(m=>r.metrics[m.key])]));
  const evidenceRows:Cell[][] = [["Rotation", "Type", "Statement"]];
  rotations.forEach((r,i) => {r.evidence.forEach(x=>evidenceRows.push([labels[i],"Evidence",x]));r.risks.forEach(x=>evidenceRows.push([labels[i],"Risk",x]));});
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
    ["Leading alternative",report.results.alternatives[0]?labelRotation(report.results.alternatives[0].label):"Not available"],
    ["Irrigation scenario", IRRIGATION_LABELS[report.inputs.irrigation]],
    ["Rotations compared",report.results.comparedRotations],
    ["Economic assessment requested",econ?"Yes":"No"],
    ["Note","Values are historical simulation indicators, not predictions. See provenance sheet."],
  ];
  const polygon:Cell[][] = [["Ring", "Vertex", "Longitude", "Latitude"]];
  report.field.polygonCoordinates?.forEach((ring,ri)=>ring.forEach((xy,vi)=>polygon.push([ri+1,vi+1,good(xy[0])?xy[0]:null,good(xy[1])?xy[1]:null])));
  return [
    {name:"Summary",rows:overview,widths:[42,84]},
    {name:"Indicators",rows:indicators,widths:[35,20,18,18,18,18,18,18,18]},
    {name:"Chart data",rows:chartRows,widths:[35,22,20,22,22]},
    {name:"Rotations",rows:rotationRows,widths:[20,48,20,...metrics.map(()=>18)]},
    {name:"Priorities",rows:priorities,widths:[36,18]},
    {name:"Crop cycle",rows:cycleRows,widths:[16,30,24]},
    {name:"Evidence and risks",rows:evidenceRows,widths:[22,20,105]},
    {name:"Provenance",rows:notes,widths:[43,110]},
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
      const style=ri===0?1:pctCell?4:ri%2===0?3:2;
      if(typeof val === "number") return Number.isFinite(val)?`<c r="${ref}" s="${style}"><v>${val}</v></c>`:"";
      if(typeof val === "object") return `<c r="${ref}" s="${style}"><f>${xml(val.formula)}</f>${val.cached===null?"":`<v>${val.cached}</v>`}</c>`;
      return `<c r="${ref}" s="${style}" t="inlineStr"><is><t xml:space="preserve">${xml(val)}</t></is></c>`;
    }).join("");
    return `<row r="${ri+1}"${ri===0?' ht="27" customHeight="1"':''}>${cells}</row>`;
  }).join("");
  const columns=(sheet.widths??[]).map((width,i)=>`<col min="${i+1}" max="${i+1}" width="${width}" customWidth="1"/>`).join("");
  const last=sheet.rows.reduce((n,r)=>Math.max(n,r.length),1);
  const lastName=`${col(last-1)}${Math.max(sheet.rows.length,1)}`;
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`+
    `<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">`+
    `<dimension ref="A1:${lastName}"/><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>`+
    `<sheetFormatPr defaultRowHeight="20"/><cols>${columns}</cols><sheetData>${rowText}</sheetData>`+
    `<autoFilter ref="A1:${lastName}"/></worksheet>`;
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
export function buildExcelWorkbook(report:CompletedReport, demo=false):Uint8Array {
  const sheets=sheetsForReport(report,demo);
  const fileTypes=sheets.map((_,i)=>`<Override PartName="/xl/worksheets/sheet${i+1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join("");
  const files=[
    {path:"[Content_Types].xml",content:`<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>${fileTypes}</Types>`},
    {path:"_rels/.rels",content:`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`},
    {path:"xl/workbook.xml",content:`<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${sheets.map((s,i)=>`<sheet name="${xml(s.name)}" sheetId="${i+1}" r:id="rId${i+1}"/>`).join("")}</sheets><calcPr calcId="191029" fullCalcOnLoad="1"/></workbook>`},
    {path:"xl/_rels/workbook.xml.rels",content:`<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${sheets.map((_,i)=>`<Relationship Id="rId${i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i+1}.xml"/>`).join("")}<Relationship Id="rId${sheets.length+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>`},
    {path:"xl/styles.xml",content:`<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Aptos"/><color rgb="FF244735"/></font><font><b/><sz val="11"/><name val="Aptos"/><color rgb="FFFFFFFF"/></font></fonts><fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF246B4B"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFEDF5EA"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="10" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>`},
    ...sheets.map((s,i)=>({path:`xl/worksheets/sheet${i+1}.xml`,content:sheetXml(s)})),
  ];
  return zipStore(files);
}
export function downloadExcelReport(report:CompletedReport,demo=false):void {
  const bytes=buildExcelWorkbook(report,demo);
  const blob=new Blob([new Uint8Array(bytes) as BlobPart],{type:"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"});
  const url=URL.createObjectURL(blob);const a=document.createElement("a");
  a.href=url;a.download=`FIELDWISE_${demo?"DEMO_":""}${report.id}.xlsx`;
  document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
