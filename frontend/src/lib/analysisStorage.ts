/** Frontend-only analysis draft. This is not a backend API payload yet. */
export type CropId = "mais" | "soia" | "frumento";
export type IrrigationScenario = "solo_pioggia" | "tetto_irriguo" | "irrigazione_libera";
export type PriorityId = "resa" | "rischio" | "acqua" | "concime" | "suolo" | "profitto";

export type CropStep = {
  crop: CropId;
  coverAfter: boolean;
};

export type RegulatoryRegime =
  | "lombardia_impegno_quinquennale" | "lombardia_impegno_triennale_SRA01_2026"
  | "emilia_romagna_impegno_quinquennale" | "emilia_romagna_adesione_singola_coltura";
export const REGULATORY_REGIMES: Record<RegulatoryRegime, string> = {
  lombardia_impegno_quinquennale: "Lombardy — five-year commitment",
  lombardia_impegno_triennale_SRA01_2026: "Lombardy — three-year commitment (SRA01 2026)",
  emilia_romagna_impegno_quinquennale: "Emilia-Romagna — five-year commitment",
  emilia_romagna_adesione_singola_coltura: "Emilia-Romagna — single-crop membership",
};
export const DEFAULT_REGULATORY_REGIME: RegulatoryRegime = "lombardia_impegno_quinquennale";
export type OtherCropCostOverrides = Partial<Record<CropId, number>>;

export type FutureHorizon = 5 | 10 | 15 | 20;
export type FutureSsp = "ssp126" | "ssp245" | "ssp585";

export const FUTURE_HORIZONS: FutureHorizon[] = [5, 10, 15, 20];
export const FUTURE_SSPS: FutureSsp[] = ["ssp126", "ssp245", "ssp585"];

export const FUTURE_SSP_LABELS: Record<FutureSsp, { title: string; short: string; description: string }> = {
  ssp126: {
    title: "Low emissions (SSP1-2.6)",
    short: "SSP1-2.6",
    description: "Rapid emissions reductions and limited warming under a low-emissions pathway",
  },
  ssp245: {
    title: "Intermediate emissions (SSP2-4.5)",
    short: "SSP2-4.5",
    description: "An intermediate emissions pathway, with warmer and potentially drier summers",
  },
  ssp585: {
    title: "Very high emissions (SSP5-8.5)",
    short: "SSP5-8.5",
    description: "Very high emissions, with stronger heat and drought risks",
  },
};

export type AnalysisDraft = {
  version: 1;
  rotation: [CropStep, CropStep, CropStep];
  irrigation: IrrigationScenario;
  priorities: Record<PriorityId, number>;
  /** Opt-in for the current engine's fixed-assumption economic analysis. */
  advancedEconomics?: boolean;
  regulatoryRegime?: RegulatoryRegime;
  /** EUR per cultivated hectare; omitted entries use values from params/economia.yaml. */
  otherCropCostsEurHa?: OtherCropCostOverrides;
  /** Opt-in for IPCC CMIP6 future climate projections. */
  includeFuture?: boolean;
  futureHorizon?: FutureHorizon;
  futureSsp?: FutureSsp;
};

export const CROP_LABELS: Record<CropId, string> = {
  mais: "Maize",
  soia: "Soybean",
  frumento: "Winter wheat",
};

export const IRRIGATION_LABELS: Record<IrrigationScenario, string> = {
  solo_pioggia: "Rainfed only",
  tetto_irriguo: "Limited irrigation",
  irrigazione_libera: "Unrestricted irrigation",
};

export const PRIORITY_LABELS: Record<PriorityId, string> = {
  resa: "Yield",
  rischio: "Resilience in difficult years",
  acqua: "Water savings",
  concime: "Fertilizer savings",
  suolo: "Soil health",
  profitto: "Economic margin",
};

export const PRIORITY_KEYS: PriorityId[] = ["resa", "rischio", "acqua", "concime", "suolo", "profitto"];
export const CROP_KEYS: CropId[] = ["mais", "soia", "frumento"];
export const IRRIGATION_KEYS: IrrigationScenario[] = ["solo_pioggia", "tetto_irriguo", "irrigazione_libera"];

// Keep the original storage key and draft version, so existing user settings survive.
// Old priority values (0-5) remain valid when the interface changes to 0-10.
const STORAGE_KEY = "fieldwise:analysis-drafts:v1";
export const PRIORITY_MAX = 10;

export function defaultAnalysisDraft(): AnalysisDraft {
  return {
    version: 1,
    rotation: [
      { crop: "mais", coverAfter: false },
      { crop: "soia", coverAfter: false },
      { crop: "frumento", coverAfter: false },
    ],
    irrigation: "tetto_irriguo",
    priorities: { resa: 5, rischio: 5, acqua: 5, concime: 5, suolo: 5, profitto: 5 },
    advancedEconomics: false,
    regulatoryRegime: DEFAULT_REGULATORY_REGIME,
    otherCropCostsEurHa: {},
    includeFuture: false,
    futureHorizon: 10,
    futureSsp: "ssp245",
  };
}

function normalizeAnalysisDraft(draft: AnalysisDraft): AnalysisDraft {
  return {
    ...draft,
    advancedEconomics: draft.advancedEconomics === true,
    regulatoryRegime: draft.regulatoryRegime && draft.regulatoryRegime in REGULATORY_REGIMES
      ? draft.regulatoryRegime : DEFAULT_REGULATORY_REGIME,
    otherCropCostsEurHa: draft.otherCropCostsEurHa ?? {},
    includeFuture: draft.includeFuture === true,
    futureHorizon: (draft.futureHorizon && FUTURE_HORIZONS.includes(draft.futureHorizon)) ? draft.futureHorizon : 10,
    futureSsp: (draft.futureSsp && FUTURE_SSPS.includes(draft.futureSsp)) ? draft.futureSsp : "ssp245",
    priorities: { ...draft.priorities, profitto: draft.priorities.profitto ?? 5 },
  };
}

export function isAnalysisDraft(value: unknown): value is AnalysisDraft {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const draft = value as Partial<AnalysisDraft>;
  const validSteps = Array.isArray(draft.rotation) && draft.rotation.length === 3 &&
    draft.rotation.every((step: unknown) => {
      if (!step || typeof step !== "object") return false;
      const item = step as CropStep;
      return CROP_KEYS.includes(item.crop) && typeof item.coverAfter === "boolean";
    });
  return draft.version === 1 && validSteps &&
    (draft.advancedEconomics === undefined || typeof draft.advancedEconomics === "boolean") &&
    (draft.regulatoryRegime === undefined || Object.hasOwn(REGULATORY_REGIMES, draft.regulatoryRegime)) &&
    (draft.otherCropCostsEurHa === undefined || (
      typeof draft.otherCropCostsEurHa === "object" && draft.otherCropCostsEurHa !== null &&
      !Array.isArray(draft.otherCropCostsEurHa) &&
      Object.entries(draft.otherCropCostsEurHa).every(([crop, value]) =>
        CROP_KEYS.includes(crop as CropId) && typeof value === "number" &&
        Number.isFinite(value) && value >= 0 && value <= 100000)
    )) &&
    (draft.includeFuture === undefined || typeof draft.includeFuture === "boolean") &&
    (draft.futureHorizon === undefined || FUTURE_HORIZONS.includes(draft.futureHorizon as FutureHorizon)) &&
    (draft.futureSsp === undefined || FUTURE_SSPS.includes(draft.futureSsp as FutureSsp)) &&
    IRRIGATION_KEYS.includes(draft.irrigation as IrrigationScenario) &&
    !!draft.priorities && typeof draft.priorities === "object" &&
    PRIORITY_KEYS.filter((key) => key !== "profitto").every((key) => {
      const n = draft.priorities?.[key];
      return typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= PRIORITY_MAX;
    }) && (draft.priorities.profitto === undefined ||
      (Number.isInteger(draft.priorities.profitto) && draft.priorities.profitto >= 0 && draft.priorities.profitto <= PRIORITY_MAX));
}

function readAll(): Record<string, AnalysisDraft> {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return {};
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("Invalid saved analysis drafts.");
  }
  const result: Record<string, AnalysisDraft> = Object.create(null);
  for (const [id, draft] of Object.entries(value)) {
    if (isAnalysisDraft(draft)) result[id] = normalizeAnalysisDraft(draft);
  }
  return result;
}

/** Read the explicitly saved configuration, without inventing a default for exports. */
export function getSavedAnalysisDraft(fieldId: string): AnalysisDraft | null {
  return readAll()[fieldId] ?? null;
}

export function loadAnalysisDraft(fieldId: string): AnalysisDraft {
  return getSavedAnalysisDraft(fieldId) ?? defaultAnalysisDraft();
}

export function saveAnalysisDraft(fieldId: string, draft: AnalysisDraft): void {
  if (!isAnalysisDraft(draft)) throw new Error("Invalid analysis configuration.");
  const all = readAll();
  all[fieldId] = normalizeAnalysisDraft(draft);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

export function deleteAnalysisDraft(fieldId: string): void {
  const all = readAll();
  if (!(fieldId in all)) return;
  delete all[fieldId];
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(all));
}

/** Replace settings along with a complete field-configuration import. */
export function replaceAnalysisDrafts(drafts: Record<string, AnalysisDraft>): void {
  const checked: Record<string, AnalysisDraft> = Object.create(null);
  for (const [id, draft] of Object.entries(drafts)) {
    if (!id || id.length > 128 || !isAnalysisDraft(draft)) {
      throw new Error("The field backup contains invalid analysis settings.");
    }
    checked[id] = normalizeAnalysisDraft(draft);
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(checked));
}

export function snapshotAnalysisDrafts(): Record<string, AnalysisDraft> {
  return readAll();
}

/** Exact string syntax accepted by the existing Python Rotation.from_label(). */
export function rotationBackendLabel(rotation: AnalysisDraft["rotation"]): string {
  return rotation.map(({ crop, coverAfter }) => `${crop}${coverAfter ? "+cover" : ""}`).join(" > ");
}
