"use client";

import { useEffect, useRef, useState } from "react";
import { CROP_LABELS, FUTURE_SSP_LABELS, IRRIGATION_LABELS, REGULATORY_REGIMES, type AnalysisDraft } from "../../lib/analysisStorage";
import { runBeamSearch, type BeamObjective, type BeamClimateMode, type BeamResult } from "../../lib/beamApi";
import styles from "../../styles/beam.module.css";

const LABELS: Record<BeamObjective, string> = { resa: "Maximize yield", guadagno: "Maximize margin", costo: "Minimize costs" };
const fmt = (number: number | null | undefined, decimals = 1) =>
  number === null || number === undefined || !Number.isFinite(number)
    ? "N/A" : number.toLocaleString("en-GB", { maximumFractionDigits: decimals });

type Props = { fieldName: string; point: [number, number]; draft: AnalysisDraft; disabled?: boolean };

export default function BeamOptimizerPanel({ fieldName, point, draft, disabled }: Props) {
  const [objectives, setObjectives] = useState<[BeamObjective, BeamObjective, BeamObjective]>(["resa", "guadagno", "costo"]);
  const [climateMode, setClimateMode] = useState<BeamClimateMode>(draft.includeFuture ? "cmip6" : "storico");
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<{ result: BeamResult; sourceMode: string } | null>(null);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);

  // Changing the field analysis settings invalidates a displayed result; it
  // should never look like a newly computed recommendation for new inputs.
  const settingKey = JSON.stringify([point, draft.irrigation, draft.regulatoryRegime,
    draft.otherCropCostsEurHa, draft.advancedEconomics, draft.futureSsp, draft.futureHorizon,
    climateMode, objectives]);
  const [computedKey, setComputedKey] = useState<string | null>(null);
  const visible = computedKey === settingKey ? data : null;

  async function run() {
    if (loading || disabled) return;
    const controller = new AbortController();
    abort.current = controller;
    const key = settingKey;
    setData(null); setError(null); setStage("Sending your request to the backend..."); setLoading(true);
    try {
      const answer = await runBeamSearch(point, draft, objectives, climateMode, setStage, controller.signal);
      if (!controller.signal.aborted) { setComputedKey(key); setData(answer); }
    } catch (cause) {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Unable to run the optimizer.");
    } finally {
      if (!controller.signal.aborted) setLoading(false);
      abort.current = null;
    }
  }

  function downloadJson() {
    if (!visible) return;
    const file = new Blob([JSON.stringify({ field: fieldName, ...visible }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(file);
    const link = document.createElement("a");
    link.href = url; link.download = "fieldwise-nine-year-optimization.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <section className={styles.card} aria-label="Nine-year crop rotation optimization">
      <div className={styles.header}>
        <div>
          <span className={styles.eyebrow}>EXPERIMENTAL / ADVANCED OPTIMIZATION</span>
          <div className={styles.titleRow}><h2>9-year crop rotation optimizer</h2><span className={styles.tag}>Experimental</span></div>
          <p>Three consecutive three-crop cycles, with soil water, nitrogen and humus inherited between cycles. Calendar duration may differ from exactly nine years.</p>
        </div>
      </div>
      <div className={styles.selectors}>
        {objectives.map((value, i) => (
          <label key={i} className={styles.field}>
            <span>Cycle {i + 1} · objective</span>
            <select value={value} disabled={loading} onChange={(e) => {
              const next = [...objectives] as [BeamObjective, BeamObjective, BeamObjective];
              next[i] = e.target.value as BeamObjective; setObjectives(next);
            }}>
              {(Object.keys(LABELS) as BeamObjective[]).map((objective) =>
                <option value={objective} key={objective}>{LABELS[objective]}</option>)}
            </select>
          </label>
        ))}
        <label className={styles.field}>
          <span>Climate forcing</span>
          <select value={climateMode} disabled={loading} onChange={(e) => setClimateMode(e.target.value as BeamClimateMode)}>
            <option value="storico">Historical NASA POWER</option>
            <option value="cmip6">Future CMIP6 delta change</option>
          </select>
        </label>
      </div>
      <p className={styles.settings}>
        <strong>From your analysis:</strong> {IRRIGATION_LABELS[draft.irrigation]} · {REGULATORY_REGIMES[draft.regulatoryRegime ?? "lombardia_impegno_quinquennale"]}
        {climateMode === "cmip6" && ` · ${FUTURE_SSP_LABELS[draft.futureSsp ?? "ssp245"].short}, ${draft.futureHorizon ?? 10}-year horizon`}
        {draft.advancedEconomics ? " · Custom crop costs (if set)" : " · Standard engine crop costs"}
      </p>
      <p className={styles.fieldNote}>This optimizer only uses the field analyzed in this report. If local preparation is missing or outdated, update the field analysis before retrying.</p>
      <div className={styles.actions}>
        <button type="button" className={styles.run} onClick={() => void run()} disabled={disabled || loading}>
          {loading ? "Optimizing…" : "Optimize 9 years →"}
        </button>
        {loading && <button type="button" className={styles.secondary} onClick={() => { abort.current?.abort(); setLoading(false); setStage(""); }}>Stop waiting</button>}
      </div>
      {loading && <p className={styles.progress} role="status">{stage} The calculation continues on the backend while you wait.</p>}
      {error && <p className={styles.error} role="alert">{error}</p>}
      {visible && <div className={styles.results}>
        <div className={styles.resultTop}>
          <div><h3>Recommended sequence</h3><p>{"Simulated at the selected field point"} · {fmt(visible.result.performance.tempo_beam_s, 2)} s engine computation</p></div>
          <button type="button" className={styles.secondary} onClick={downloadJson}>Export JSON ↓</button>
        </div>
        <div className={styles.cycleGrid}>
          {visible.result.trienni.map((cycle, i) => (
            <article key={cycle.numero} className={styles.cycle}>
              <span className={styles.eyebrow}>CYCLE {cycle.numero} / 3 · {LABELS[cycle.obiettivo]}</span>
              <h4>{cycle.rotazione_label.split(" > ").map((step) => {
                const key = step.replace("+cover", "") as keyof typeof CROP_LABELS;
                return `${CROP_LABELS[key] ?? step}${step.includes("+cover") ? " + rye cover" : ""}`;
              }).join(" → ")}</h4>
              <span className={cycle.stato_conformita === "conforme" ? styles.compliant : styles.warning}>
                {cycle.stato_conformita === "conforme" ? "Compliant" : `Status: ${cycle.stato_conformita ?? "unknown"}`}
              </span>
              <div className={styles.metrics}>
                <div><span>Mean yield</span><strong>{fmt(cycle.resa_t_ha, 2)} t/ha</strong></div>
                <div><span>Relative yield</span><strong>{fmt(cycle.resa_rel_pct)}%</strong></div>
                <div><span>Annual costs</span><strong>€{fmt(cycle.costo_totale_eur_ha, 0)}/ha</strong></div>
                <div><span>Annual margin</span><strong>€{fmt(cycle.guadagno_eur_ha, 0)}/ha</strong></div>
              </div>
              <details className={styles.details}><summary>Crop-level details and benchmarks</summary>
                <ul>{cycle.colture.map((crop, idx) => <li key={idx}>{CROP_LABELS[crop.coltura] ?? crop.coltura}: {fmt(crop.resa_t_ha)} t/ha · irrigation {fmt(crop.irrigazione_mm, 0)} mm · N {fmt(crop.concime_kg_n_ha, 0)} kg/ha</li>)}</ul>
                <p>Best standalone yield: {fmt(cycle.best_sim_resa_t_ha, 2)} t/ha · best cost: €{fmt(cycle.best_sim_costo_eur_ha)} · best margin: €{fmt(cycle.best_sim_guadagno_eur_ha)} (benchmarks at reference soil state)</p>
              </details>
              {cycle.fallback_siccita && <p className={styles.warning}>Drought fallback used: 70% minimum relative yield not attainable.</p>}
              {i < 2 && visible.result.eredita_suolo[i] && <div className={styles.heritage}>
                <strong>Soil carried to cycle {i + 2}</strong>
                <span>Water {fmt(visible.result.eredita_suolo[i].acqua_totale_mm)} mm · N {fmt(visible.result.eredita_suolo[i].n_min_kg_n_ha)} kg/ha · Humus {fmt(visible.result.eredita_suolo[i].humus_t_ha)} t/ha</span>
              </div>}
            </article>
          ))}
        </div>
        {!!visible.result.note?.length && <details className={styles.details}><summary>Simulation notes ({visible.result.note.length})</summary><ul>{visible.result.note.map((n, i) => <li key={i}>{n}</li>)}</ul></details>}
        <p className={styles.disclaimer}>Experimental decision support, not a validated nine-year forecast or official legal compliance certification. Soil and management assumptions remain model-based. The hypothetical brute-force runtime is not a measured benchmark.</p>
      </div>}
    </section>
  );
}
