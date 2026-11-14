import { rotationBackendLabel, type AnalysisDraft } from "./analysisStorage";
import type { CompletedReport, FieldSnapshot, RotationResult } from "./reportTypes";

// Production deployments must configure a publicly reachable HTTPS Python API.
const configured = process.env.NEXT_PUBLIC_FIELDWISE_API_URL?.replace(/\/+$/, "");
const BASE = configured ?? (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : "");

type EngineResult = {
  schemaVersion: 1;
  engine: CompletedReport["engine"];
  results: {
    scenario: string;
    current: RotationResult;
    alternatives: RotationResult[];
    comparedRotations: number | null;
    notes: string[];
  };
};

export async function analyzeField(field: FieldSnapshot, draft: AnalysisDraft): Promise<CompletedReport> {
  if (!BASE) throw new Error("Analysis API is not configured. Set NEXT_PUBLIC_FIELDWISE_API_URL to your Python backend URL.");
  if (!field.representativePoint) throw new Error("This field does not have a valid reference point.");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  try {
    const response = await fetch(`${BASE}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        point: field.representativePoint,
        rotation: rotationBackendLabel(draft.rotation),
        scenario: draft.irrigation,
        // Standard reports do not opt into economic ranking; the backend's fixed
        // economic model is not modified by this display-level selection.
        priorities: { ...draft.priorities, profitto: draft.advancedEconomics ? draft.priorities.profitto : 0 },
        use_pilot_reference: false,
      }),
      signal: controller.signal,
    });
    const data: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const payload = data as { detail?: string | { message?: string } } | null;
      const detail = payload?.detail;
      throw new Error(typeof detail === "string" ? detail : detail?.message ?? `Analysis request failed (HTTP ${response.status}).`);
    }
    if (!data || typeof data !== "object") throw new Error("The backend returned an invalid response.");
    const result = data as EngineResult;
    if (result.schemaVersion !== 1 || !result.engine || !result.results ||
        !result.results.current || !Array.isArray(result.results.alternatives) ||
        !Array.isArray(result.results.notes)) {
      throw new Error("Unsupported backend report format.");
    }
    return {
      schemaVersion: 1,
      id: crypto.randomUUID(),
      status: "completed",
      createdAt: new Date().toISOString(),
      field: structuredClone(field),
      inputs: structuredClone(draft),
      engine: result.engine,
      results: result.results,
    };
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The backend did not respond within 120 seconds. Please retry.");
    }
    if (error instanceof TypeError) {
      throw new Error("Cannot reach the FIELDWISE Python API. Start it locally or check the configured API URL and CORS settings.");
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}


type PreparationResponse = {
  jobId?: string;
  status: "ready" | "running" | "failed";
  stage: string;
  error?: string;
};

/** Prepare location-conditioned data before requesting the cached ensemble result.
 *  The backend owns the potentially long-running data fetch and simulation job.
 */
export async function prepareLocalField(point: [number, number], onStage: (stage: string) => void): Promise<void> {
  if (!BASE) throw new Error("Analysis API is not configured.");
  const response = await fetch(`${BASE}/api/v1/prepare`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ point }),
  });
  const initial = await response.json() as PreparationResponse & { detail?: { message?: string } };
  if (!response.ok) throw new Error(initial.detail?.message ?? "Local data preparation could not start.");
  if (initial.status === "ready") return;
  if (!initial.jobId) throw new Error("The server did not return a preparation job ID.");
  const deadline = Date.now() + 20 * 60_000;
  while (Date.now() < deadline) {
    onStage(initial.stage);
    // Poll the backend for genuine progress: no fictitious percentage.
    await new Promise((resolve) => setTimeout(resolve, 1700));
    const poll = await fetch(`${BASE}/api/v1/prepare/${encodeURIComponent(initial.jobId)}`, { cache: "no-store" });
    if (!poll.ok) throw new Error("Preparation status is unavailable. The server may have restarted.");
    const step = await poll.json() as PreparationResponse;
    onStage(step.stage);
    if (step.status === "ready") return;
    if (step.status === "failed") throw new Error(step.error ?? "Location-specific preparation failed.");
    initial.stage = step.stage;
  }
  throw new Error("Local preparation is taking longer than expected. The backend may still be processing; retry to check its status.");
}
