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
};

export type RotationResult = {
  label: string;
  score: number | null; // relative ranking only, never "confidence"
  metrics: RotationMetrics;
  evidence: string[];
  risks: string[];
};

export type FieldSnapshot = {
  id: string;
  name: string;
  number: number;
  areaHectares: number | null;
  polygonCoordinates: number[][][] | null; // immutable GeoJSON snapshot, not an ID lookup
  representativePoint: [number, number] | null; // [longitude, latitude]
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
  };
  results: {
    scenario: string;
    current: RotationResult;
    alternatives: RotationResult[];
    comparedRotations: number | null;
    notes: string[];
  };
};

export type ReportSummary = Pick<CompletedReport, "id" | "createdAt" | "field"> & {
  rotationLabel: string;
  recommendedLabel: string | null;
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
];

export function formatMetric(key: keyof RotationMetrics, value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "Not available";
  if (key.startsWith("relativeYield")) return `${(value * 100).toFixed(1)}%`;
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
