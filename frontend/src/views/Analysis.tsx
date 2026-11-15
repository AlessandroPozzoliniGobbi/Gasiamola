"use client";

import { useEffect, useState, type CSSProperties } from "react";
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
  type FutureHorizon, type FutureSsp,
} from "../lib/analysisStorage";
import AnalysisFieldMap from "../components/map/AnalysisFieldMap";
import AnalysisProcessing from "../components/reports/AnalysisProcessing";
import { analyzeField, canOfferPilotReference, prepareLocalField } from "../lib/engineApi";
import { MAP_CONFIG } from "../lib/mapConfig";
import { saveCompletedReport } from "../lib/reportStorage";
import styles from "../styles/analysis.module.css";

type Props = { fieldId: string };
type LoadState =
  | { status: "loading" }
  | { status: "found"; field: FieldItem }
  | { status: "not-found" }
  | { status: "error" };

type DraftSaveStatus = "saved" | "saving" | "error";

export default function Analysis({ fieldId }: Props) {
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
  const changeAdvancedEconomics = (enabled: boolean) => {
    updateDraft((old) => ({ ...old, advancedEconomics: enabled }));
  };
  const changeIncludeFuture = (enabled: boolean) => {
    updateDraft((old) => ({ ...old, includeFuture: enabled }));
  };
  const changeFutureHorizon = (horizon: FutureHorizon) => {
    updateDraft((old) => ({ ...old, futureHorizon: horizon }));
  };
  const changeFutureSsp = (ssp: FutureSsp) => {
    updateDraft((old) => ({ ...old, futureSsp: ssp }));
  };
  const changePriority = (key: PriorityId, value: number) => {
    updateDraft((old) => ({ ...old, priorities: { ...old.priorities, [key]: value } }));
  };

  const field = state.status === "found" ? state.field : null;
  const point = field ? getLabelPosition(field) : null;
  const hectares = field ? estimateFieldHectares(field) : null;
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
          <Link href="/mappa" className={styles.backLink}>← Back to map</Link>
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
                <section className={styles.formCard} aria-labelledby="rotation-heading">
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
                <section className={styles.formCard} aria-labelledby="water-heading">
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
                <section className={styles.formCard} aria-labelledby="priorities-heading">
                  <div className={styles.cardHeading}>
                    <div>
                      <p className={styles.cardEyebrow}>04 / YOUR GOALS</p>
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
                <section className={styles.formCard} aria-label="Advanced analysis settings">
                  <details className={styles.advancedSection}>
                    <summary className={styles.advancedSummary}>
                      <span><span className={styles.cardEyebrow}>05 / OPTIONAL FEATURES</span><strong>Advanced Analysis</strong></span>
                      <span className={`${styles.advancedIndicator} ${draft.advancedEconomics ? styles.advancedIndicatorActive : ""}`} role="img" aria-label={draft.advancedEconomics ? "Advanced analysis enabled" : "Advanced analysis disabled"} />
                    </summary>
                    <div className={styles.advancedBody}>
                      <p className={styles.helper}>Economic analysis is optional. The margin is grain revenue minus nitrogen fertilizer, irrigation and other crop costs (seed, crop protection, field operations, harvest, drying, transport), using the engine&apos;s default prices and costs.</p>
                      <label className={styles.advancedToggle}>
                        <input type="checkbox" checked={draft.advancedEconomics === true}
                          onChange={(event) => changeAdvancedEconomics(event.target.checked)} />
                        <span><strong>Include economic analysis</strong><small>Show Economics in the report and apply your economic-margin weight to the ranking score. Pareto criteria remain defined by the engine.</small></span>
                      </label>
                      {draft.advancedEconomics && <>
                        <div className={styles.priorityRow}>
                          <label htmlFor="priority-profitto"><span>{PRIORITY_LABELS.profitto}</span><strong>{draft.priorities.profitto} / 10</strong></label>
                          <input id="priority-profitto" type="range" min="0" max="10" step="1"
                            value={draft.priorities.profitto}
                            style={{ "--priority-fill": `${draft.priorities.profitto * 10}%` } as CSSProperties}
                            onChange={(event) => changePriority("profitto", Number(event.target.value))} />
                        </div>
                        <p className={styles.advancedCaution}>This version does not accept custom crop prices or farming costs from the website. The report uses the engine&apos;s predefined economic assumptions; a personalized financial assessment requires the updated economic input/output contract.</p>
                      </>}
                    </div>
                  </details>
                </section>
                <section className={styles.formCard} aria-label="Future climate simulation settings">
                  <details className={styles.advancedSection}>
                    <summary className={styles.advancedSummary}>
                      <span><span className={styles.cardEyebrow}>06 / CLIMATE PROJECTIONS</span><strong>Future Climate Simulation (CMIP6)</strong></span>
                      <span className={`${styles.advancedIndicator} ${draft.includeFuture ? styles.advancedIndicatorActive : ""}`} role="img" aria-label={draft.includeFuture ? "Future simulation enabled" : "Future simulation disabled"} />
                    </summary>
                    <div className={styles.advancedBody}>
                      <p className={styles.helper}>Simulate climate change impacts on your rotation using IPCC CMIP6 Delta Change consensus projections for the Po Valley.</p>
                      <label className={styles.advancedToggle}>
                        <input type="checkbox" checked={draft.includeFuture === true}
                          onChange={(event) => changeIncludeFuture(event.target.checked)} />
                        <span><strong>Include climate projections (CMIP6)</strong><small>Evaluate future yield resilience, water demand, heat stress and adaptive rotation opportunities over 5 to 20 years.</small></span>
                      </label>
                      {draft.includeFuture && <>
                        <div className={styles.priorityRow}>
                          <label htmlFor="future-horizon"><span>Time horizon</span><strong>{draft.futureHorizon ?? 10} years</strong></label>
                          <select id="future-horizon" className={styles.futureSelect} value={draft.futureHorizon ?? 10}
                            onChange={(event) => changeFutureHorizon(Number(event.target.value) as FutureHorizon)}>
                            {FUTURE_HORIZONS.map((h) => (
                              <option key={h} value={h}>{h} years {h === 10 ? "(Medium term · Default)" : h === 5 ? "(Short term)" : h === 15 ? "(Medium-long term)" : "(Long term)"}</option>
                            ))}
                          </select>
                        </div>
                        <div className={styles.priorityRow}>
                          <label htmlFor="future-ssp"><span>IPCC Scenario</span><strong>{FUTURE_SSP_LABELS[draft.futureSsp ?? "ssp245"]?.short ?? "SSP2-4.5"}</strong></label>
                          <select id="future-ssp" className={styles.futureSelect} value={draft.futureSsp ?? "ssp245"}
                            onChange={(event) => changeFutureSsp(event.target.value as FutureSsp)}>
                            {FUTURE_SSPS.map((code) => (
                              <option key={code} value={code}>{FUTURE_SSP_LABELS[code].title}</option>
                            ))}
                          </select>
                        </div>
                        <p className={styles.advancedCaution}>{FUTURE_SSP_LABELS[draft.futureSsp ?? "ssp245"]?.description}. Projections use the CMIP6 ensemble delta-change method calibrated on historical NASA POWER weather series without runtime network dependencies.</p>
                      </>}
                    </div>
                  </details>
                </section>
                <section className={styles.submitCard} aria-labelledby="ready-heading">
                  <div>
                    <p className={styles.cardEyebrow}>07 / RUN ANALYSIS</p>
                    <h2 id="ready-heading">Your configuration is ready</h2>
                    <p>These settings are saved locally for this field. You can edit them anytime.</p>
                  </div>
                  <div className={styles.summaryChips}>
                    <span>3-year rotation</span><span>{IRRIGATION_LABELS[draft.irrigation]}</span><span>{draft.advancedEconomics ? "Advanced economics" : "Standard analysis"}</span>
                    {draft.includeFuture && <span>{`Future ${draft.futureHorizon ?? 10}y (${(draft.futureSsp ?? "ssp245").toUpperCase()})`}</span>}
                  </div>
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
            <Link href="/mappa" className={styles.backLink}>Return to the map</Link>
          </div>
        )}
      </div>
    </main>
  );
}
