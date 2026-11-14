import type { PortfolioReport } from "./portfolioStorage";
import { portfolioPdfPayload, renderPortfolioMarkdown } from "./portfolioMarkdown";
const configured=process.env.NEXT_PUBLIC_FIELDWISE_API_URL?.replace(/\/+$/,'');
const BASE=configured??(process.env.NODE_ENV==='development'?'http://127.0.0.1:8000':'');

export async function downloadPortfolioPdf(p:PortfolioReport):Promise<void> {
  if(!BASE)throw new Error("PDF service unavailable. Configure the public FIELDWISE API URL.");
  const controller=new AbortController();
  const timeout=setTimeout(()=>controller.abort(),120_000);
  try {
    const response=await fetch(`${BASE}/api/v1/reports/pdf`,{
      method:'POST',headers:{'Content-Type':'application/json'},signal:controller.signal,
      body:JSON.stringify({markdown:renderPortfolioMarkdown(p),report:portfolioPdfPayload(p),demo:false}),
    });
    if(!response.ok){
      const payload=await response.json().catch(()=>null) as {detail?:string|{message?:string}}|null;
      throw new Error(typeof payload?.detail==='string'?payload.detail:payload?.detail?.message??`PDF export failed (${response.status}).`);
    }
    const blob=await response.blob();
    if(!blob.type.startsWith('application/pdf'))throw new Error('The API did not return a PDF document.');
    const url=URL.createObjectURL(blob);
    const a=document.createElement('a');a.href=url;a.download=`FIELDWISE_Portfolio_${p.id}.pdf`;
    document.body.appendChild(a);a.click();
    setTimeout(()=>{a.remove();URL.revokeObjectURL(url);},60_000);
  } catch(e) {
    if(e instanceof DOMException && e.name==='AbortError')throw new Error('Portfolio PDF export timed out.');
    if(e instanceof TypeError)throw new Error('Cannot reach the FIELDWISE PDF service.');
    throw e;
  } finally {clearTimeout(timeout);}
}
