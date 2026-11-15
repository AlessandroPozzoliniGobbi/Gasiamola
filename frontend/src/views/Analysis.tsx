"use client";

import { useEffect, useState, type CSSProperties, type MouseEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { FieldItem } from "../types/field";
import { loadSavedFields } from "../lib/fieldStorage";
import { getLabelPosition } from "../lib/fieldGeometry";
import { estimateFieldHectares } from "../lib/fieldArea";
import {
  CROP_KEYS, CROP_LABELS, IRRIGATION_KEYS, IRRIGATION_LABELS, PRIORITY_KEYS,
  PRIORITY_LABELS, defaultAnalysisDraft, loadAnalysisDraft, saveAnalysisDraft,
  rotationBackendLabel, FUTURE_HORIZONS, FUTURE_SSPS, FUTURE_SSP_LABELS,
  type AnalysisDraft, type CropId, type IrrigationScenario, type PriorityId,
  REGULATORY_REGIMES, DEFAULT_REGULATORY_REGIME, type RegulatoryRegime,
  type FutureHorizon, type FutureSsp,
} from "../lib/analysisStorage";
import AnalysisFieldMap from "../components/map/AnalysisFieldMap";
import AnalysisProcessing from "../components/reports/AnalysisProcessing";
import { analyzeField, canOfferPilotReference, prepareLocalField, loadEconomicDefaults, type EconomicDefaults } from "../lib/engineApi";
import { MAP_CONFIG } from "../lib/mapConfig";
import { listRecentCompletedReports, saveCompletedReport } from "../lib/reportStorage";
import { findReusableFieldReport } from "../lib/reuseFieldReport";
import type { CompletedReport } from "../lib/reportTypes";
import styles from "../styles/analysis.module.css";

type Props = { fieldId: string; returnToMultipleHref?: string };
type LoadState =
  | { status: "loading" }
  | { status: "found"; field: FieldItem }
  | { status: "not-found" }
  | { status: "error" };

type DraftSaveStatus = "saved" | "saving" | "error";

export default function Analysis({ fieldId, returnToMultipleHref }: Props) {
  const router = useRouter();
  const [running, setRunning] = useState(false);
  const [processingStage, setProcessingStage] = useState("Preparing your field analysis...");
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  // Offered only after local preparation failed: never applied without the user's explicit choice.
  const [pilotOffer, setPilotOffer] = useState(false);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [draft, setDraft] = useState<AnalysisDraft | null>(null);
  const [saveStatus, setSaveStatus] = useState<DraftSaveStatus>("saved");
  const [draftLoadWarning, setDraftLoadWarning] = useState<string | null>(null);
  const [economicDefaults, setEconomicDefaults] = useState<EconomicDefaults | null>(null);
  const [costLoadError, setCostLoadError] = useState<string | null>(null);
  const [savedReports, setSavedReports] = useState<CompletedReport[]>([]);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      try {
        const saved = loadSavedFields();
        const field = saved?.fields.find((item) => item.id === fieldId);
        if (!field) {
          setState({ status: "not-found" });
          return;
        }
        setState({ status: "found", field });
        try {
          setDraft(loadAnalysisDraft(fieldId));
        } catch (error) {
          console.warn("Unable to read the saved analysis draft:", error);
          setDraft(defaultAnalysisDraft());
          setDraftLoadWarning("The previous analysis settings could not be loaded. Default values are shown.");
        }
      } catch (error) {
        console.error("Unable to load field data:", error);
        setState({ status: "error" });
      }
    });
    return () => { active = false; };
  }, [fieldId]);

  // Prices and cultivation-cost defaults come directly from the Python engine YAML.
  useEffect(() => {
    let active = true;
    void loadEconomicDefaults().then((defaults) => {
      if (active) { setEconomicDefaults(defaults); setCostLoadError(null); }
    }).catch((error) => {
      if (active) setCostLoadError(error instanceof Error ? error.message : "Cost defaults unavailable");
    });
    return () => { active = false; };
  }, []);

  // A completed local report can be reopened instantly without rerunning the engine.
  // The user must explicitly choose it; Run analysis always requests fresh results.
  useEffect(() => {
    let active = true;
    void listRecentCompletedReports().then((reports) => {
      if (active) setSavedReports(reports);
    }).catch(() => { /* IndexedDB may be unavailable: fresh analysis still works. */ });
    return () => { active = false; };
  }, [fieldId]);

  // Save an independent draft for each field immediately, so navigating away
  // cannot discard edits made just before leaving the page.
  useEffect(() => {
    if (!draft || state.status !== "found") return;
    let active = true;
    try {
      saveAnalysisDraft(fieldId, draft);
      queueMicrotask(() => { if (active) setSaveStatus("saved"); });
    } catch (error) {
      console.error("Unable to save analysis settings:", error);
      queueMicrotask(() => { if (active) setSaveStatus("error"); });
    }
    return () => { active = false; };
  }, [draft, fieldId, state.status]);

  // A direct click on "Back to multiple-field analysis" also commits the
  // current draft synchronously, even if the user navigates immediately after
  // changing a setting. Never navigate silently when local saving fails.
  const saveBeforeReturning = (event: MouseEvent<HTMLAnchorElement>) => {
    if (state.status !== "found" || !draft) return;
    try {
      saveAnalysisDraft(fieldId, draft);
      setSaveStatus("saved");
    } catch (error) {
      event.preventDefault();
      console.error("Unable to save field settings before returning:", error);
      setSaveStatus("error");
    }
  };

  const updateDraft = (next: (old: AnalysisDraft) => AnalysisDraft) => {
    setDraft((old) => old ? next(old) : old);
    setSaveStatus("saving");
  };

  const changeCrop = (index: number, crop: CropId) => {
    updateDraft((old) => ({
      ...old,
      rotation: old.rotation.map((step, i) => i === index ? { ...step, crop } : step) as AnalysisDraft["rotation"],
    }));
  };
  const changeCover = (index: number, coverAfter: boolean) => {
    updateDraft((old) => ({
      ...old,
      rotation: old.rotation.map((step, i) => i === index ? { ...step, coverAfter } : step) as AnalysisDraft["rotation"],
    }));
  };
  const changeIrrigation = (irrigation: IrrigationScenario) => {
    updateDraft((old) => ({ ...old, irrigation }));
  };
  const changeRegulatoryRegime = (regulatoryRegime: RegulatoryRegime) => {
    updateDraft((old) => ({ ...old, regulatoryRegime }));
  };
  const changeOtherCropCost = (crop: CropId, cost: number) => {
    updateDraft((old) => ({
      ...old, advancedEconomics: true,
      otherCropCostsEurHa: { ...(old.otherCropCostsEurHa ?? {}), [crop]: cost },
    }));
  };
  const resetOtherCropCosts = () => {
    updateDraft((old) => ({ ...old, otherCropCostsEurHa: {} }));
  };
  const changeAdvancedEconomics = (enabled: boolean) => {
    updateDraft((old) => ({ ...old, advancedEconomics: enabled }));
  };
  const changeIncludeFuture = (enabled: boolean) => {
    updateDraft((old) => ({ ...old, includeFuture: enabled }));
  };
  const changeFutureHorizon = (horizon: FutureHorizon) => {
    updateDraft((old) => ({ ...old, includeFuture: true, futureHorizon: horizon }));
  };
  const changeFutureSsp = (ssp: FutureSsp) => {
    updateDraft((old) => ({ ...old, includeFuture: true, futureSsp: ssp }));
  };
  const changePriority = (key: PriorityId, value: number) => {
    updateDraft((old) => ({
      ...old,
      advancedEconomics: key === "profitto" ? true : old.advancedEconomics,
      priorities: { ...old.priorities, [key]: value },
    }));
  };

  const field = state.status === "found" ? state.field : null;
  const point = field ? getLabelPosition(field) : null;
  const hectares = field ? estimateFieldHectares(field) : null;
  const reusableReport = field && draft && point ? findReusableFieldReport(savedReports, {
    id: field.id, name: field.name, number: field.number,
    areaHectares: hectares, polygonCoordinates: field.coordinates, representativePoint: point,
  }, draft) : null;
  const weightSum = draft ? PRIORITY_KEYS.filter((key) => key !== "profitto" || draft.advancedEconomics === true)
    .reduce((sum, key) => sum + draft.priorities[key], 0) : 0;

  const runAnalysis = async (usePilotReference = false) => {
    if (!field || !point || !draft || weightSum === 0 || running) return;
    setAnalysisError(null);
    setPilotOffer(false);
    setRunning(true);
    try {
      if (usePilotReference) {
        setProcessingStage("Comparing rotations with the Cremona pilot reference data...");
      } else {
        setProcessingStage("Checking field-specific climate and soil data...");
        await prepareLocalField(point, setProcessingStage);
        setProcessingStage("Comparing rotations and saving your report...");
      }
      const report = await analyzeField({
        id: field.id, name: field.name, number: field.number,
        areaHectares: hectares,
        polygonCoordinates: field.coordinates,
        representativePoint: point,
      }, draft, { usePilotReference });
      await saveCompletedReport(report);
      router.push(`/reports/${encodeURIComponent(report.id)}`);
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : "The analysis could not be completed.");
      setPilotOffer(!usePilotReference && canOfferPilotReference(error));
      setRunning(false);
    }
  };

  if (running && field) return <AnalysisProcessing fieldName={field.name} stage={processingStage} />;

  return (
    <main data-fieldwise-analysis className={styles.page}>
      <div className={styles.container}>
        <div className={styles.pageTop}>
          <nav className={styles.backLinks} aria-label="Return navigation">
            {returnToMultipleHref && <Link href={returnToMultipleHref} onClick={saveBeforeReturning} className={styles.multipleBackLink}>← Back to multiple-field analysis</Link>}
            <Link href="/mappa" className={styles.backLink}>← Back to map</Link>
          </nav>
          <span className={styles.sectionLabel}>FIELDWISE / FIELD ANALYSIS</span>
        </div>
        {state.status === "loading" ? (
          <p role="status" className={styles.loadMessage}>Loading field…</p>
        ) : field && draft && point ? (
          <>
            <div className={styles.hero}>
              <div>
                <h1>Analyze {field.name}</h1>
              </div>
              <span className={styles.draftBadge} role="status" aria-live="polite">
                {saveStatus === "saved" ? "✓ Saved in this browser" : saveStatus === "saving" ? "Saving settings…" : "Could not save settings"}
              </span>
            </div>
            {draftLoadWarning && <p className={styles.alert} role="alert">{draftLoadWarning}</p>}
            <div className={styles.mainGrid}>
              <aside className={styles.leftColumn} aria-label="Selected field map and details">
                <section className={styles.mapCard}>
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>01 / YOUR FIELD</p>
                      <h2>Field location</h2>
                    </div>
                    <span className={styles.subtleTag}>Single-point analysis</span>
                  </div>
                  <AnalysisFieldMap field={field} />
                  <div className={styles.fieldFacts} aria-label="Field details">
                    <div><span>Field</span><strong>#{field.number}</strong></div>
                    <div><span>Area</span><strong>{hectares?.toLocaleString("en-US", { maximumFractionDigits: 2 })} ha</strong></div>
                    <div><span>Reference point</span><strong>{point[1].toFixed(5)}° N, {point[0].toFixed(5)}° E</strong></div>
                  </div>
                </section>
              </aside>
              <div className={styles.rightColumn}>
                <section id="analysis-rotation" className={styles.formCard} aria-labelledby="rotation-heading">
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>02 / AGRICULTURAL HISTORY</p>
                      <h2 id="rotation-heading">Current crop rotation</h2>
                    </div>
                  </div>
                  <p className={styles.helper}>Choose the crops grown in your field over a repeating three-year cycle. The model currently supports maize, soybean, and winter wheat.</p>
                  <div className={styles.rotationGrid}>
                    {draft.rotation.map((step, index) => (
                      <div key={index} className={styles.cropCard}>
                        <label htmlFor={`crop-${index}`} className={styles.inputLabel}>Year {index + 1}</label>
                        <select id={`crop-${index}`} className={styles.select} value={step.crop}
                          onChange={(event) => changeCrop(index, event.target.value as CropId)}>
                          {CROP_KEYS.map((crop) => <option value={crop} key={crop}>{CROP_LABELS[crop]}</option>)}
                        </select>
                        <label className={styles.checkboxLabel}>
                          <input type="checkbox" checked={step.coverAfter} onChange={(event) => changeCover(index, event.target.checked)} />
                          <span>Rye cover crop afterward</span>
                        </label>
                      </div>
                    ))}
                  </div>
                  <p className={styles.helper}>The third year leads back to Year 1. Cover crops are simulated only when the agricultural calendar allows them.</p>
                  <div className={styles.rotationSummary}>
                    <span>Current rotation</span>
                    <strong>{draft.rotation.map((step) => `${CROP_LABELS[step.crop]}${step.coverAfter ? " + rye" : ""}`).join(" → ")}</strong>
                  </div>
                </section>
                <section id="analysis-water" className={styles.formCard} aria-labelledby="water-heading">
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>03 / WATER AVAILABILITY</p>
                      <h2 id="water-heading">Irrigation scenario</h2>
                    </div>
                  </div>
                  <div className={styles.optionList} role="radiogroup" aria-label="Irrigation scenario">
                    {IRRIGATION_KEYS.map((key) => (
                      <label key={key} className={`${styles.optionCard} ${draft.irrigation === key ? styles.optionActive : ""}`}>
                        <input type="radio" name="irrigation" value={key} checked={draft.irrigation === key}
                          onChange={() => changeIrrigation(key)} />
                        <span className={styles.optionContent}>
                          <strong>{IRRIGATION_LABELS[key]}</strong>
                          <span>{key === "solo_pioggia" ? "No irrigation; rainfall only." : key === "tetto_irriguo" ? "Irrigation subject to the model's predefined limits." : "No predefined irrigation volume cap in the scenario."}</span>
                        </span>
                      </label>
                    ))}
                  </div>
                  <p className={styles.helper}>These are model scenarios, not measured water availability at your farm. The exact limits will come from the backend.</p>
                </section>
                <section id="analysis-regulations" className={styles.formCard} aria-labelledby="regulations-heading">
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>04 / COMPLIANCE</p>
                      <h2 id="regulations-heading">Regional crop-rotation rules</h2>
                    </div>
                  </div>
                  <label htmlFor="regional-regime" className={styles.inputLabel}>Apply rules from</label>
                  <select id="regional-regime" className={styles.select}
                    value={draft.regulatoryRegime ?? DEFAULT_REGULATORY_REGIME}
                    onChange={(event) => changeRegulatoryRegime(event.target.value as RegulatoryRegime)}>
                    {Object.entries(REGULATORY_REGIMES).map(([code, label]) =>
                      <option key={code} value={code}>{label}</option>)}
                  </select>
                  <p className={styles.helper}>Only rotations classified as compliant under the selected engine rules can be proposed. Derogations and unassessable rotations are excluded. Your existing rotation stays in the report as a comparison, even if it does not comply.</p>
                  <p className={styles.regulatoryWarning}>Model-based check of the encoded rules, not official certification. Verify the applicable version and your farm&apos;s eligibility.</p>
                </section>
                <section id="analysis-priorities" className={styles.formCard} aria-labelledby="priorities-heading">
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>05 / YOUR GOALS</p>
                      <h2 id="priorities-heading">Set your priorities</h2>
                    </div>
                  </div>
                  <p className={styles.helper}>Priorities change the ranking of crop rotations, not the scientific simulation. A value of 0 means the priority is excluded.</p>
                  <div className={styles.priorityList}>
                    {PRIORITY_KEYS.filter((key) => key !== "profitto").map((key) => (
                      <div className={styles.priorityRow} key={key}>
                        <label htmlFor={`priority-${key}`}><span>{PRIORITY_LABELS[key]}</span><strong>{draft.priorities[key]} / 10</strong></label>
                        <input id={`priority-${key}`} type="range" min="0" max="10" step="1"
                          value={draft.priorities[key]}
                          style={{ "--priority-fill": `${draft.priorities[key] * 10}%` } as CSSProperties}
                          onChange={(event) => changePriority(key, Number(event.target.value))} />
                      </div>
                    ))}
                  </div>
                  {weightSum === 0 && <p className={styles.alert} role="alert">Choose at least one priority above zero before running an analysis.</p>}
                </section>
                <section id="analysis-economics" className={`${styles.formCard} ${styles.optionalFeatureCard}`} aria-labelledby="advanced-economics-heading">
                  <div className={styles.optionalFeatureHeader}>
                    <div className={styles.optionalSummaryMain}>
                      <span className={styles.cardEyebrow}>06 / OPTIONAL</span>
                      <h2 id="advanced-economics-heading">Economic analysis</h2>
                      <p className={styles.optionalSubtitle}>Adjust economic priority · selecting a value enables the analysis</p>
                    </div>
                    <label className={styles.optionalFeatureToggle}>
                      <input type="checkbox" checked={draft.advancedEconomics === true}
                        onChange={(event) => changeAdvancedEconomics(event.target.checked)} />
                      <span>Include</span>
                    </label>
                  </div>
                  <div className={styles.optionalFeatureBody}>
                    {!draft.advancedEconomics && <p className={styles.optionalHintInline}>Move the slider below or select <strong>Include</strong> to add economic margin to the ranking.</p>}
                    <div className={styles.optionalFieldset}>
                      <div className={styles.priorityRow}>
                        <label htmlFor="priority-profitto"><span>{PRIORITY_LABELS.profitto}</span><strong>{draft.priorities.profitto} / 10</strong></label>
                        <input id="priority-profitto" type="range" min="0" max="10" step="1"
                          value={draft.priorities.profitto}
                          style={{ "--priority-fill": `${draft.priorities.profitto * 10}%` } as CSSProperties}
                          onChange={(event) => changePriority("profitto", Number(event.target.value))} />
                      </div>
                    </div>
                    <details className={styles.optionalTechnicalDetails}>
                      <summary>Advanced costs — adjust farm-specific expenses</summary>
                      <p>These costs cover seed, crop protection, machinery and field operations (including sowing and harvest), drying and transport. Enter their <strong>total EUR/ha for each crop</strong>, excluding nitrogen fertilizer and irrigation: those are already calculated separately. Do not add them twice.</p>
                      {economicDefaults ? (
                        <>
                          <div className={styles.costInputGrid}>
                            {CROP_KEYS.map((crop) => {
                              const standard = economicDefaults.otherCropCostsEurHa[crop];
                              const entered = draft.otherCropCostsEurHa?.[crop];
                              return (
                                <div className={styles.costInputGroup} key={crop}>
                                  <label htmlFor={`crop-cost-${crop}`}>{CROP_LABELS[crop]} — €/ha</label>
                                  <input id={`crop-cost-${crop}`} type="number" min="0" max="100000" step="10"
                                    value={entered ?? standard}
                                    onChange={(event) => {
                                      const value = Number(event.target.value);
                                      if (event.target.value !== "" && Number.isFinite(value) && value >= 0 && value <= 100000) {
                                        changeOtherCropCost(crop, value);
                                      }
                                    }} />
                                  <small>Engine default: {standard.toLocaleString("en-GB")} €/ha</small>
                                </div>
                              );
                            })}
                          </div>
                          <div className={styles.costActions}>
                            <span>{Object.keys(draft.otherCropCostsEurHa ?? {}).length ? "Custom farm expenses in use" : "Standard engine expenses in use"}</span>
                            <button type="button" onClick={resetOtherCropCosts} className={styles.resetButton}>Restore standard costs</button>
                          </div>
                        </>
                      ) : <p className={styles.alert} role="status">{costLoadError ?? "Loading standard costs from the engine…"} Custom costs are unavailable until this connection succeeds.</p>}
                    </details>
                  </div>
                </section>
                <section id="analysis-climate" className={`${styles.formCard} ${styles.optionalFeatureCard}`} aria-labelledby="future-projections-heading">
                  <div className={styles.optionalFeatureHeader}>
                    <div className={styles.optionalSummaryMain}>
                      <span className={styles.cardEyebrow}>07 / OPTIONAL</span>
                      <div className={styles.optionalTitleRow}>
                        <h2 id="future-projections-heading">Future climate projections</h2>
                        <span className={styles.experimentalTag} title="Exploratory climate scenarios, not validated field-level forecasts">Experimental</span>
                      </div>
                      <p className={styles.optionalSubtitle}>Choose a scenario and a time horizon · 5–20 years</p>
                    </div>
                    <label className={styles.optionalFeatureToggle}>
                      <input type="checkbox" checked={draft.includeFuture === true}
                        onChange={(event) => changeIncludeFuture(event.target.checked)} />
                      <span>Include</span>
                    </label>
                  </div>
                  <div className={styles.optionalFeatureBody}>
                    {!draft.includeFuture && <p className={styles.optionalHintInline}>Choose a horizon or emissions scenario below, or select <strong>Include</strong>, to add future climate projections.</p>}
                    <div className={styles.optionalFieldset}>
                      <div className={styles.optionalConfigGrid}>
                        <div className={styles.optionalInputGroup}>
                          <label htmlFor="future-horizon">Time horizon</label>
                          <select id="future-horizon" className={styles.futureSelect} value={draft.futureHorizon ?? 10}
                            onChange={(event) => changeFutureHorizon(Number(event.target.value) as FutureHorizon)}>
                            {FUTURE_HORIZONS.map((h) => (
                              <option key={h} value={h}>{h} years {h === 10 ? "· Default" : ""}</option>
                            ))}
                          </select>
                        </div>
                        <div className={styles.optionalInputGroup}>
                          <label htmlFor="future-ssp">Emissions scenario</label>
                          <select id="future-ssp" className={styles.futureSelect} value={draft.futureSsp ?? "ssp245"}
                            onChange={(event) => changeFutureSsp(event.target.value as FutureSsp)}>
                            {FUTURE_SSPS.map((code) => (
                              <option key={code} value={code}>{FUTURE_SSP_LABELS[code].title}</option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                    {draft.includeFuture && <p className={styles.optionalScenarioNote}>{FUTURE_SSP_LABELS[draft.futureSsp ?? "ssp245"]?.description}</p>}
                    <details className={styles.optionalTechnicalDetails}>
                      <summary>About the climate model</summary>
                      <p>Projections use IPCC CMIP6 ensemble delta changes calibrated with historical NASA POWER weather data. These are scenarios, not forecasts for a particular field.</p>
                    </details>
                  </div>
                </section>
                <section id="analysis-run" className={styles.submitCard} aria-labelledby="ready-heading">
                  <div>
                    <p className={styles.cardEyebrow}>08 / RUN ANALYSIS</p>
                    <h2 id="ready-heading">Your configuration is ready</h2>
                    <p>These settings are saved locally for this field. You can edit them anytime.</p>
                  </div>
                  <div className={styles.summaryChips}>
                    <span>3-year rotation</span><span>{IRRIGATION_LABELS[draft.irrigation]}</span><span>{REGULATORY_REGIMES[draft.regulatoryRegime ?? DEFAULT_REGULATORY_REGIME]}</span><span>{draft.advancedEconomics ? "Advanced economics" : "Standard analysis"}</span>
                    {draft.includeFuture && <span>{`Future ${draft.futureHorizon ?? 10}y (${(draft.futureSsp ?? "ssp245").toUpperCase()})`}</span>}
                  </div>
                  {reusableReport && (
                    <div className={styles.savedReportNotice}>
                      <div>
                        <strong>Previous analysis available</strong>
                        <p>Same field and settings · {new Date(reusableReport.createdAt).toLocaleDateString("en-GB")}. Open instantly, or run again to get results from the current model.</p>
                      </div>
                      <Link href={`/reports/${encodeURIComponent(reusableReport.id)}`} className={styles.savedReportLink}>
                        View saved report →
                      </Link>
                    </div>
                  )}
                  <div className={styles.submitActions}>
                    <button className={styles.resetButton} type="button" onClick={() => {
                      if (window.confirm("Reset this field's analysis settings to the defaults?")) updateDraft(() => defaultAnalysisDraft());
                    }}>Reset settings</button>
                    <button type="button" className={styles.runButton} disabled={weightSum === 0 || running} onClick={() => void runAnalysis()}>
                      Run analysis <span>→</span>
                    </button>
                  </div>
                  <p className={styles.helper}>Field-local mode downloads NASA POWER and SoilGrids data for your field&apos;s representative point (within {MAP_CONFIG.operationalRadiusKm} km of the Cremona pilot point). The first preparation can take several minutes and requires an online backend. These are experimental gridded estimates, not field measurements.</p>
                  {analysisError && <p className={styles.alert} role="alert">{analysisError}</p>}
                  {pilotOffer && <div className={styles.alert} role="group" aria-label="Pilot reference option">
                    <p><strong>Local data for this field are not available.</strong> You can still run the comparison with the
                      data of the Cremona pilot point. The report will be labelled &ldquo;Data of the Cremona pilot point, not of your
                      field&rdquo;: its soil and climate are not those of your field.</p>
                    <button type="button" className={styles.resetButton} onClick={() => void runAnalysis(true)}>
                      Run with Cremona pilot data (not my field)
                    </button>
                  </div>}
                  <details className={styles.technicalDetails}>
                    <summary>Backend-ready identifiers (for integration)</summary>
                    <p>Crop rotation: <code>{rotationBackendLabel(draft.rotation)}</code></p>
                    <p>Irrigation scenario: <code>{draft.irrigation}</code></p>
                    <p>Regulatory rules: <code>{draft.regulatoryRegime ?? DEFAULT_REGULATORY_REGIME}</code></p>
                    <p>Field ID: <code>{field.id}</code></p>
                  </details>
                </section>
              </div>
            </div>
          </>
        ) : (
          <div className={styles.missingCard}>
            <h1>Field unavailable</h1>
            <p>{state.status === "error" ? "Your saved fields could not be read in this browser." : "This field was not found among the saved fields in this browser."}</p>
            {returnToMultipleHref && <Link href={returnToMultipleHref} onClick={saveBeforeReturning} className={styles.multipleBackLink}>← Back to multiple-field analysis</Link>}
            <Link href="/mappa" className={styles.backLink}>Return to the map</Link>
          </div>
        )}
      </div>
    </main>
  );
}
