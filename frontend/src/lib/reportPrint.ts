/** FIELDWISE PDF export: the API renders the same Markdown used by the browser report
 *  (reportMarkdown.ts) and the saved report values into a PDF.
 */
import type { CompletedReport } from "./reportTypes";
import { renderReportMarkdown } from "./reportMarkdown";

/** Download a real, searchable PDF directly from the Python API (no print tab). */
export async function downloadPdfReport(report:CompletedReport,demo=false):Promise<void> {
  const configured = process.env.NEXT_PUBLIC_FIELDWISE_API_URL?.replace(/\/+$/, "");
  const base = configured ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "");
  if (!base) throw new Error("The PDF service is not configured. Set NEXT_PUBLIC_FIELDWISE_API_URL to the Python API URL.");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  try {
    const response = await fetch(`${base}/api/v1/reports/pdf`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ markdown: renderReportMarkdown(report,demo), report, demo }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null) as {detail?:string|{message?:string}}|null;
      const detail = data?.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message ?? `PDF generation failed (HTTP ${response.status}).`);
    }
    const blob = await response.blob();
    if (blob.type !== "application/pdf" && !blob.type.startsWith("application/pdf;")) {
      throw new Error("The PDF service returned an unexpected file type.");
    }
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `FIELDWISE_${demo?"DEMO_":""}${report.id}.pdf`;
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    setTimeout(() => { anchor.remove(); URL.revokeObjectURL(url); }, 60_000);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw new Error("PDF export took too long. Please try again.");
    if (error instanceof TypeError) throw new Error("Cannot reach the PDF service. Verify that the Python API is running.");
    throw error;
  } finally { clearTimeout(timeout); }
}
