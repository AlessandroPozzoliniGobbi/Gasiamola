import type { AnalysisDraft, CropId } from "./analysisStorage";

const API_BASE = (process.env.NEXT_PUBLIC_FIELDWISE_API_URL?.trim().replace(/\/$/, "") ||
  (process.env.NODE_ENV === "development" ? "http://127.0.0.1:8000" : ""));

export type BeamObjective = "resa" | "guadagno" | "costo";
export type BeamClimateMode = "storico" | "cmip6";
export type BeamCrop = {
  coltura: CropId; semina: string; raccolta: string;
  resa_t_ha: number; resa_relativa: number;
  irrigazione_mm: number; concime_kg_n_ha: number;
};
export type BeamPeriod = {
  numero: number; obiettivo: BeamObjective; rotazione_label: string;
  anno_partenza: number; anno_valutato: number; inizio: string; fine: string;
  stato_conformita: string | null; colture: BeamCrop[];
  resa_t_ha: number; resa_rel_pct: number;
  costo_totale_eur_ha: number; guadagno_eur_ha: number;
  best_sim_resa_t_ha: number | null;
  best_sim_costo_eur_ha: number | null;
  best_sim_guadagno_eur_ha: number | null;
  fallback_siccita: boolean;
};
export type BeamInheritance = {
  da_triennio: number; a_triennio: number;
  acqua_totale_mm: number; n_min_kg_n_ha: number;
  humus_t_ha: number;
};
export type BeamResult = {
  lat: number; lon: number; climate_mode: BeamClimateMode;
  irrigation_regime: string; regime_normativo: string;
  solo_conformi: boolean; beam_width: number;
  ssp_code: string | null; horizon_years: number | null;
  objectives: BeamObjective[];
  trienni: BeamPeriod[]; eredita_suolo: BeamInheritance[];
  performance: { tempo_beam_s: number; tempo_bruteforce_stimato_s: number; combinazioni_bruteforce: number };
  note: string[];
};

type JobState = { jobId?: string; status: "running" | "ready" | "failed";
  stage: string; error?: string; result?: BeamResult; sourceMode?: string };

function describeError(data: unknown, fallback: string): string {
  if (data && typeof data === "object" && "detail" in data) {
    const detail = (data as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    if (Array.isArray(detail)) return detail.map((item) => (item as { msg?: string }).msg ?? "Invalid input").join("; ");
  }
  return fallback;
}

async function parse(response: Response): Promise<unknown> {
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) throw new Error(describeError(data, `Backend error: HTTP ${response.status}`));
  return data;
}

export async function runBeamSearch(
  point: [number, number], draft: AnalysisDraft,
  objectives: [BeamObjective, BeamObjective, BeamObjective],
  climateMode: BeamClimateMode,
  onProgress: (stage: string) => void,
  signal?: AbortSignal,
): Promise<{ result: BeamResult; sourceMode: string }> {
  if (!API_BASE) throw new Error("Configure NEXT_PUBLIC_FIELDWISE_API_URL before running the optimizer.");
  const started = await fetch(`${API_BASE}/api/v1/beam-search`, {
    method: "POST", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({
      point, objectives, use_pilot_reference: false,
      irrigation_regime: draft.irrigation,
      regime_normativo: draft.regulatoryRegime ?? "lombardia_impegno_quinquennale",
      climate_mode: climateMode, ssp_code: draft.futureSsp ?? "ssp245",
      horizon_years: draft.futureHorizon ?? 10,
      other_crop_costs_eur_ha: draft.advancedEconomics ? (draft.otherCropCostsEurHa ?? {}) : {},
      beam_width: 8,
    }),
  });
  const start = await parse(started) as JobState;
  if (!start.jobId) throw new Error("The backend did not return an optimizer job ID.");
  const sourceMode = start.sourceMode ?? "pilot_point";
  const deadline = Date.now() + 12 * 60 * 1000;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new DOMException("Cancelled", "AbortError");
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => { signal?.removeEventListener("abort", cancel); resolve(); }, 1500);
      const cancel = () => { clearTimeout(timer); reject(new DOMException("Cancelled", "AbortError")); };
      signal?.addEventListener("abort", cancel, { once: true });
    });
    const response = await fetch(`${API_BASE}/api/v1/beam-search/${encodeURIComponent(start.jobId)}`, { cache: "no-store", signal });
    const job = await parse(response) as JobState;
    onProgress(job.stage || "Optimization running...");
    if (job.status === "failed") throw new Error(job.error ?? "The optimizer failed.");
    if (job.status === "ready") {
      if (!job.result || job.result.trienni?.length !== 3 || job.result.eredita_suolo?.length !== 2) {
        throw new Error("The backend returned an incomplete nine-year result.");
      }
      return { result: job.result, sourceMode };
    }
  }
  throw new Error("Optimization exceeded 12 minutes. The backend may still be working; check its logs.");
}
