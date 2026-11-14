"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "../../lib/engineApi";
import { IRRIGATION_KEYS, IRRIGATION_LABELS, type IrrigationScenario } from "../../lib/analysisStorage";
import type { Limitations } from "../../lib/reportTypes";
import styles from "../../styles/project.module.css";

type State = { status: "loading" } | { status: "ready"; data: Limitations } | { status: "error"; message: string };

/** Ranking stability and validation results, read from the engine reports through the API.
 *  No number is written in the frontend. */
export default function EngineLimitations() {
  const [scenario, setScenario] = useState<IrrigationScenario>("tetto_irriguo");
  const [state, setState] = useState<State>({ status: "loading" });
  useEffect(() => {
    let active = true;
    if (!API_BASE) {
      queueMicrotask(() => { if (active) setState({ status: "error", message: "The FIELDWISE API URL is not configured." }); });
      return () => { active = false; };
    }
    fetch(`${API_BASE}/api/v1/limitations?scenario=${encodeURIComponent(scenario)}`, { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error(`The API answered HTTP ${response.status}.`);
        const data = await response.json() as Limitations;
        if (active) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (active) setState({ status: "error", message: error instanceof Error && !(error instanceof TypeError)
          ? error.message : "Cannot reach the FIELDWISE API, which provides these results." });
      });
    return () => { active = false; };
  }, [scenario]);

  return (
    <section className={styles.draftArea} aria-labelledby="engine-limitations-heading">
      <h2 className={styles.draftTitle} id="engine-limitations-heading">Ranking stability and validation</h2>
      <p className={styles.draftText}>
        Results of the engine&apos;s sensitivity analysis and validation for the Cremona pilot point. They are read from the
        engine reports at request time and are also included in every field report.
      </p>
      <label className={styles.draftText}>
        Irrigation scenario{" "}
        <select value={scenario} onChange={(event) => { setState({ status: "loading" }); setScenario(event.target.value as IrrigationScenario); }}>
          {IRRIGATION_KEYS.map((key) => <option key={key} value={key}>{IRRIGATION_LABELS[key]}</option>)}
        </select>
      </label>
      {state.status === "loading" && <p role="status" className={styles.draftText}>Loading the engine results…</p>}
      {state.status === "error" && <p role="alert" className={styles.draftText}>{state.message}</p>}
      {state.status === "ready" && <ul className={styles.topicList}>
        {state.data.statements.map((statement, index) => <li key={index}>{statement}</li>)}
      </ul>}
      <p className={styles.draftText}>
        Further limits: one representative point per field; gridded climate (NASA POWER) and predicted soil (SoilGrids)
        rather than field measurements; historical weather, not a forecast; groundwater and local management are not
        fully represented; compliance with regional rotation rules must be verified for the actual field.
      </p>
    </section>
  );
}
