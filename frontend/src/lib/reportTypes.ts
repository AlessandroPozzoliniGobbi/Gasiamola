import type { AnalysisDraft } from "./analysisStorage";

/** This is a frontend report snapshot, NOT the Python engine's API response.
 *  A versioned backend adapter will convert validated Python results into it. */
export type RotationMetrics = {
  relativeYieldMedian: number | null; // dimensionless, usually 0..1
  relativeYieldWorst: number | null; // dimensionless, 0..1
  relativeYieldP10: number | null; // dimensionless, 0..1
  irrigationMm: number | null;
  fertilizerKgN: number | null;
  nitrogenLeachingKgN: number | null;
  humusChangeTonsHa: number | null;
  grossMarginEurHa: number | null; // EUR/ha/year: revenue − fertilizer − irrigation − other crop costs
};

export type MarginComponents = {
  revenueEurHa: number | null;
  fertilizerCostEurHa: number | null;
  irrigationCostEurHa: number | null;
  otherCropCostsEurHa: number | null;
};

export type RotationResult = {
  label: string; // for the current rotation: the order entered by the user
  cyclicClass?: string; // engine cyclic class actually compared
  role?: string | null; // engine role (ranking.confronta "ruolo")
  roleLabel?: string | null;
  score: number | null; // relative ranking only, never "confidence"
  position?: number | null; // 1 = first by score in the compared set
  nonDominated?: boolean | null;
  metrics: RotationMetrics;
  marginComponents?: MarginComponents;
  evidence: string[];
  evidenceTopics?: string[]; // engine indicator behind each statement (same order)
  risks: string[];
  riskTopics?: string[];
};

export type RecommendationStatus =
  | "alternative_ranks_higher" | "current_is_best" | "priorities_do_not_discriminate"
  | "no_alternative_ranks_higher" | "no_alternative";

export type Recommendation = {
  status: RecommendationStatus;
  message: string;
  recommendedAlternativeIndex: number | null;
  currentPosition: number | null;
  currentScore: number | null;
  comparedRotations: number | null;
  nonDominatedCount: number | null;
  priorityWarning: string | null;
};

export type EconomicsInfo = {
  source: string;
  marginDefinition: string;
  cropPricesEurT: Record<string, number>;
  nitrogenEurKgN: number;
  irrigationEurMm: number;
  otherCropCostsEurHa: Record<string, number>;
};

export type Limitations = {
  referencePoint: [number, number];
  appliesToThisAnalysisData: boolean;
  rankingStability: {
    scenario: string; samples: number | null; firstStaysFirstShare: number | null;
    top3StayTop3Share: number | null; referenceCurrentRotation: string | null;
    currentInBottomQuarterShare: number | null; generatedAt: string | null; source: string;
  } | null;
  validation: {
    source: string;
    yields: { crop: string; scenario: string; simulation: string; years: [number, number] | null;
      pearson: number; ci95: [number, number]; n: number; verdict: string }[];
    evapotranspiration: { years: [number, number] | null; scenario: string; observedMmDay: number;
      modelMmDay: number; biasMmDay: number; passes: number } | null;
    notValidated: string[];
  } | null;
  statements: string[];
};

export type FieldSnapshot = {
  id: string;
  name: string;
  number: number;
  areaHectares: number | null;
  polygonCoordinates: number[][][] | null; // immutable GeoJSON snapshot, not an ID lookup
  representativePoint: [number, number] | null; // [longitude, latitude]
};

/** Points are overlapping simulated rotation cycles, not measured annual yields.
 *  New reports index them by the first year of the evaluated cycle (evaluatedYear);
 *  older saved reports only carry the simulation start year (startYear, spin-up included). */
export type HistoricalWindowPoint = {
  evaluatedYear?:number;
  simulationStartYears?:[number,number];
  startYear?:number;
  endYear?:number;
  memberCount:number;
  relativeYield:number|null;
  irrigationMm:number|null;
  nitrogenLeachingKgN:number|null;
  humusChangeTonsHa:number|null;
  grossMarginEurHa:number|null;
};
export type HistoricalWindows = {
  axis?:"evaluatedYear";
  method:string;
  series:{role:"current"|"alternative1"|"alternative2";rotation:string;points:HistoricalWindowPoint[]}[];
};

export type CompletedReport = {
  schemaVersion: 1;
  id: string;
  status: "completed";
  createdAt: string; // ISO-8601 UTC
  field: FieldSnapshot;
  inputs: AnalysisDraft;
  engine: {
    version: string | null;
    dataPeriod: string | null;
    methodologyNote: string | null;
    sourceMode?: "pilot_point" | "pilot_reference" | "local_estimate";
    modelPoint?: [number, number]; // [longitude, latitude] for the model inputs
    requestedPoint?: [number, number];
    weatherYears?: [number, number] | null;
    evaluatedCycleStartYears?: [number, number] | null;
    spinUpCycles?: number | null;
    ensembleCalculatedAt?: string | null;
    codeHash?: string;
    cacheCodeVersionRecorded?: boolean;
    economics?: EconomicsInfo;
    limitations?: Limitations;
    localData?: {
      aquaCropRunoffGroup: string;
      curveNumber: number;
      soilPixelShiftMeters: number;
      soilDataMethod: string;
      surfaceTexture: string;
      surfaceAvailableWaterMm: number;
      profileAvailableWaterMm: number;
    } | null;
  };
  results: {
    scenario: string;
    current: RotationResult;
    alternatives: RotationResult[];
    comparedRotations: number | null;
    recommendation?: Recommendation;
    rotationOrderNote?: string | null;
    historicalWindows?: HistoricalWindows | null;
    notes: string[];
  };
};

export type ReportSummary = Pick<CompletedReport, "id" | "createdAt" | "field"> & {
  rotationLabel: string;
  recommendedLabel: string | null;
  recommendationText?: string;
};

export const REPORT_METRICS: {
  key: keyof RotationMetrics;
  label: string;
  shortLabel: string;
  unit: string;
  higherIsBetter: boolean;
}[] = [
  { key: "relativeYieldMedian", label: "Median relative yield", shortLabel: "Relative yield", unit: "%", higherIsBetter: true },
  { key: "relativeYieldWorst", label: "Worst-case relative yield", shortLabel: "Worst-case yield", unit: "%", higherIsBetter: true },
  { key: "relativeYieldP10", label: "10th-percentile relative yield", shortLabel: "10th-percentile yield", unit: "%", higherIsBetter: true },
  { key: "irrigationMm", label: "Irrigation demand", shortLabel: "Irrigation", unit: "mm", higherIsBetter: false },
  { key: "fertilizerKgN", label: "Nitrogen fertilizer", shortLabel: "Fertilizer", unit: "kg N/ha", higherIsBetter: false },
  { key: "nitrogenLeachingKgN", label: "Nitrogen leaching", shortLabel: "Nitrogen leaching", unit: "kg N/ha", higherIsBetter: false },
  { key: "humusChangeTonsHa", label: "Annual humus change", shortLabel: "Humus change", unit: "t/ha/year", higherIsBetter: true },
  { key: "grossMarginEurHa", label: "Economic margin", shortLabel: "Margin", unit: "EUR/ha/year", higherIsBetter: true },
];

export function formatMetric(key: keyof RotationMetrics, value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Not available";
  if (key.startsWith("relativeYield")) return `${(value * 100).toFixed(1)}%`;
  if (key === "grossMarginEurHa") return `${value.toLocaleString("en-GB", { maximumFractionDigits: 0 })} EUR/ha/year`;
  if (key === "humusChangeTonsHa") return `${value > 0 ? "+" : ""}${value.toFixed(2)} t/ha/year`;
  const unit = key === "irrigationMm" ? "mm" : "kg N/ha";
  return `${value.toLocaleString("en-US", { maximumFractionDigits: 1 })} ${unit}`;
}

export function labelRotation(raw: string): string {
  const names: Record<string, string> = { mais: "Maize", soia: "Soybean", frumento: "Winter wheat" };
  return raw.split(/\s*>\s*/).map((item) => {
    const crop = item.trim().replace(/\+cover/g, "").trim();
    return `${names[crop] ?? crop}${item.includes("+cover") ? " + rye" : ""}`;
  }).join(" → ");
}

/** Used only for reports saved before the API described the margin itself. */
export const MARGIN_DEFINITION_FALLBACK =
  "Margin = grain revenue − nitrogen fertilizer − irrigation − other crop costs per cultivated hectare " +
  "(seed, crop protection, field operations, harvest, drying, transport), with the default values of " +
  "params/economia.yaml; land rent, depreciation and CAP payments are not included.";

export function marginDefinition(report: CompletedReport): string {
  return report.engine.economics?.marginDefinition ?? MARGIN_DEFINITION_FALLBACK;
}

export type RecommendationView = {
  status: RecommendationStatus;
  message: string;
  /** The rotation to adopt: an alternative only when it scores higher than the current one. */
  recommended: RotationResult | null;
  keepCurrent: boolean;
  priorityWarning: string | null;
};

/** Single rule for every view and export: an alternative is "recommended" only when the engine
 *  scores it above the current rotation and the priorities discriminate between rotations. */
export function getRecommendation(report: CompletedReport): RecommendationView {
  const r = report.results.recommendation;
  const first = report.results.alternatives[0] ?? null;
  if (r) {
    const recommended = r.recommendedAlternativeIndex === null ? null : report.results.alternatives[r.recommendedAlternativeIndex] ?? null;
    return { status: r.status, message: r.message, recommended,
      keepCurrent: r.status === "current_is_best" || r.status === "no_alternative_ranks_higher",
      priorityWarning: r.priorityWarning };
  }
  // Reports saved before the API returned a recommendation: decide from the saved scores.
  const current = report.results.current;
  if (!first) return { status: "no_alternative", message: "The engine returned no alternative rotation to compare.",
    recommended: null, keepCurrent: false, priorityWarning: null };
  if (first.score !== null && current.score !== null && first.score > current.score) {
    return { status: "alternative_ranks_higher", message: "Alternative 1 scores higher than your current rotation.",
      recommended: first, keepCurrent: false, priorityWarning: null };
  }
  return { status: "no_alternative_ranks_higher", keepCurrent: true, priorityWarning: null, recommended: null,
    message: "No alternative scores higher than your current rotation. The alternatives are shown for comparison only." };
}

/** Short headline used in lists and tables. */
export function recommendationHeadline(report: CompletedReport): string {
  const r = getRecommendation(report);
  if (r.recommended) return labelRotation(r.recommended.label);
  if (r.status === "priorities_do_not_discriminate") return "No rotation stands out for these priorities";
  if (r.status === "no_alternative") return "No alternative available";
  return "Keep the current rotation";
}

/** Card title: only the recommended alternative is called "recommended"; the others are "to compare". */
export function alternativeTitle(report: CompletedReport, index: number): string {
  const alt = report.results.alternatives[index];
  const base = `Alternative ${index + 1}`;
  if (!alt) return base;
  const tag = getRecommendation(report).recommended === alt ? "recommended" : "to compare";
  return alt.roleLabel ? `${base} · ${tag} · ${alt.roleLabel}` : `${base} · ${tag}`;
}

const MARGIN_TEXT = /partial gross margin|economic margin|^margin\b|\bmargin \d/i;

/** Statements to display; margin statements are hidden when the economic analysis is off. */
export function visibleStatements(texts: string[], topics: string[] | undefined, showEconomics: boolean): string[] {
  if (showEconomics) return texts;
  return texts.filter((text, i) => topics && topics.length === texts.length
    ? topics[i] !== "margine_lordo_eur_ha" : !MARGIN_TEXT.test(text));
}

/** Human description of the data used for the analysis. */
export function sourceModeText(report: CompletedReport): string {
  switch (report.engine.sourceMode) {
    case "local_estimate": return "Location-conditioned estimate (gridded NASA POWER climate and SoilGrids soil at the field's reference point); NOT a validated field-scale forecast.";
    case "pilot_reference": return "Cremona pilot-point data, NOT the data of this field: soil and climate are those of the pilot point, chosen explicitly because local data were not available.";
    case "pilot_point": return "Cremona pilot-point dataset (the field lies at the pilot point).";
    default: return "Data provenance not specified in this saved report.";
  }
}

/** x value of a historical point: first year of the evaluated cycle. Reports saved before this
 *  correction only have the simulation start year (spin-up included). */
export function historicalPointYear(point: HistoricalWindowPoint): number | null {
  return point.evaluatedYear ?? point.startYear ?? null;
}
