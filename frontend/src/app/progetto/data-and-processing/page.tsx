import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Methodology & Engine | FIELDWISE" };

const stages = [
  { no: "01", title: "Generate rotations", detail: "Build crop sequences and optional rye cover crops, then group equivalent cyclical alternatives." },
  { no: "02", title: "Simulate each day", detail: "Track crop development, rainfall, evapotranspiration, irrigation, nitrogen and soil organic matter." },
  { no: "03", title: "Repeat across history", detail: "Apply each alternative under comparable historical weather to expose variability and unfavorable seasons." },
  { no: "04", title: "Compare outcomes", detail: "Calculate yields, resources, soil indicators and partial economic margins; apply priorities and feasible filters." },
] as const;

export default function EnginePage() {
  return (
    <ProjectChapter slug="methodology-and-engine">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>METHODOLOGY & SYSTEM DESIGN</span>
          <h2>A daily model, not a black-box prediction.</h2>
          <p>
            The FIELDWISE engine is a deterministic simulation of crop rotations under historical
            weather and specified management rules. It estimates water and nitrogen requirements,
            crop yields, selected soil outcomes and an annualised economic margin. Its outputs are
            conditional on input data and modelling assumptions.
          </p>
        </section>

        <section className={styles.projectSteps} aria-label="How the simulation works">
          {stages.map((step) => (
            <div className={styles.projectStep} key={step.no}>
              <span>{step.no}</span>
              <div><h3>{step.title}</h3><p>{step.detail}</p></div>
            </div>
          ))}
        </section>

        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>PHYSICAL MODEL</span>
          <h2>What the engine tracks.</h2>
          <div className={styles.projectMethodGrid}>
            <article>
              <h3>Crop growth</h3>
              <p>Accumulated growing degree-days determine development stages. Simulated yield responds to water stress, heat and previous main crops.</p>
            </article>
            <article>
              <h3>Water balance</h3>
              <p>FAO Penman–Monteith evapotranspiration and a dual crop-coefficient approach describe demand across two soil layers.</p>
            </article>
            <article>
              <h3>Nitrogen & humus</h3>
              <p>Mineral nitrogen, crop uptake, soybean fixation, residues, leaching and a simplified topsoil humus stock carry over between crops.</p>
            </article>
          </div>
          <div className={styles.projectEquation}>
            <span>DAILY SOIL WATER BALANCE</span>
            <strong>ΔS = P + I − RO − ETₐ − DP</strong>
            <small>Storage change = rainfall + irrigation − runoff − actual evapotranspiration − drainage</small>
          </div>
        </section>

        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>MANAGEMENT OPTIONS</span>
          <h2>Three irrigation scenarios.</h2>
          <div className={styles.projectScenarioGrid}>
            <div><strong>Rainfed</strong><p>No irrigation supplied.</p></div>
            <div><strong>Capped</strong><p>Refill when needed, with per-crop irrigation limits.</p></div>
            <div><strong>Unrestricted</strong><p>Refill rule applied without a crop-volume cap.</p></div>
          </div>
        </section>

        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>ECONOMIC & DECISION MODEL</span>
          <h2>From simulations to interpretable choices.</h2>
          <p>
            The economic indicator is an <strong>annualised partial margin</strong>: crop revenue minus
            the estimated costs of fertilizer, irrigation and other crop operations. Prices and
            additional crop costs can be changed without rerunning the physical simulations,
            when compatible cached outputs are available.
          </p>
          <div className={styles.projectEquation}>
            <span>PARTIAL ECONOMIC MARGIN · €/HA/YEAR</span>
            <strong>Revenue − fertilizer − irrigation − crop costs</strong>
            <small>Excludes rent, CAP payments, broader farm overheads and investment decisions.</small>
          </div>
          <p>
            Indicators are normalized within the comparison set and combined using farmer-selected
            priority weights. A Pareto comparison identifies alternatives that are not dominated
            across the selected criteria; encoded regional rules can filter out non-compliant options.
          </p>
        </section>

        <aside className={styles.projectNotice}>
          <strong>Model boundaries</strong>
          <p>
            Results are scenario estimates, not direct measurements or guaranteed yields. The
            model simplifies crop physiology, nitrogen limitations, soil–water feedbacks and
            management practices. It does not validate fertilizer schedules or replace local
            agronomic advice.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
