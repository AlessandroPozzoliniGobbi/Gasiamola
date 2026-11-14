"use client";

import { useEffect, useState, type CSSProperties } from "react";
import Link from "next/link";
import type { FieldItem } from "../types/field";
import { loadSavedFields } from "../lib/fieldStorage";
import { getLabelPosition } from "../lib/fieldGeometry";
import { estimateFieldHectares } from "../lib/fieldArea";
import {
  CROP_KEYS, CROP_LABELS, IRRIGATION_KEYS, IRRIGATION_LABELS, PRIORITY_KEYS,
  PRIORITY_LABELS, defaultAnalysisDraft, loadAnalysisDraft, saveAnalysisDraft,
  rotationBackendLabel,
  type AnalysisDraft, type CropId, type IrrigationScenario, type PriorityId,
} from "../lib/analysisStorage";
import AnalysisFieldMap from "../components/map/AnalysisFieldMap";
import styles from "../styles/analysis.module.css";

type Props = { fieldId: string };
type LoadState =
  | { status: "loading" }
  | { status: "found"; field: FieldItem }
  | { status: "not-found" }
  | { status: "error" };

type DraftSaveStatus = "saved" | "saving" | "error";

export default function Analysis({ fieldId }: Props) {
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
  const changePriority = (key: PriorityId, value: number) => {
    updateDraft((old) => ({ ...old, priorities: { ...old.priorities, [key]: value } }));
  };

  const field = state.status === "found" ? state.field : null;
  const point = field ? getLabelPosition(field) : null;
  const hectares = field ? estimateFieldHectares(field) : null;
  const weightSum = draft ? Object.values(draft.priorities).reduce((a, b) => a + b, 0) : 0;

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
                  <div className={styles.ndviSection}>
                    <div className={styles.ndviHeader}>
                      <h3>NDVI <span className={styles.ndviSubheading}>vegetation index</span></h3>
                      <span className={styles.subtleTag}>Coming soon</span>
                    </div>
                    <div className={styles.ndviGradient} aria-hidden="true" />
                    <div className={styles.ndviTicks}><span>0 · Low</span><span>0.5</span><span>1 · High</span></div>
                    <div className={styles.ndviThreshold}>
                      <label className={styles.ndviLabel} htmlFor="ndvi-threshold">Display threshold</label>
                      <input id="ndvi-threshold" type="range" min="0" max="1" step="0.01" value="0.5" disabled className={styles.ndviSlider} readOnly />
                    </div>
                    <p className={styles.ndviHint}>Preview only — no NDVI data loaded.</p>
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
                    {PRIORITY_KEYS.map((key) => (
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
                <section className={styles.submitCard} aria-labelledby="ready-heading">
                  <div>
                    <p className={styles.cardEyebrow}>05 / RUN ANALYSIS</p>
                    <h2 id="ready-heading">Your configuration is ready</h2>
                    <p>These settings are saved locally for this field. You can edit them anytime.</p>
                  </div>
                  <div className={styles.summaryChips}>
                    <span>3-year rotation</span><span>{IRRIGATION_LABELS[draft.irrigation]}</span><span>5 priorities</span>
                  </div>
                  <div className={styles.submitActions}>
                    <button className={styles.resetButton} type="button" onClick={() => {
                      if (window.confirm("Reset this field's analysis settings to the defaults?")) updateDraft(() => defaultAnalysisDraft());
                    }}>Reset settings</button>
                    <button type="button" className={styles.runButton} disabled title="Backend integration is not yet available">
                      Run analysis <span>Coming soon</span>
                    </button>
                  </div>
                  <p className={styles.helper}>The simulation is not connected yet. No results, reports, or NDVI values have been generated.</p>
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
