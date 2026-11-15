import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Future Development | FIELDWISE" };

const roadmap = [
  { no: "01", title: "Climate stress tests", detail: "Explore CMIP6 delta-change scenarios for +5, +10, +15 and +20 years under SSP1-2.6, SSP2-4.5 and SSP5-8.5. Recalculate daily ET₀ after applying monthly temperature, rainfall and radiation changes to historical POWER weather." },
  { no: "02", title: "Additional crops", detail: "Introduce sunflower, sorghum, sugar beet, potato and pulses with validated parameters. Rice requires a dedicated flooded-paddy module rather than a simple crop coefficient." },
  { no: "03", title: "Geographical adaptation", detail: "Use location-appropriate soil profiles and investigate weather interpolation, elevation effects and terrain shading. Coarse climate grids will still limit field-scale precision." },
  { no: "04", title: "Efficient computation", detail: "Reuse soil preparation, compatible simulations and precomputed terrain information. Benchmark execution time, memory consumption and concurrent requests before claiming production scalability." },
  { no: "05", title: "Independent field validation", detail: "Compare additional soils, crops and locations with field and station measurements; publish parameter provenance, sensitivity and model limitations." },
];

export default function FutureDevelopmentPage() {
  return (
    <ProjectChapter slug="scalability-and-future-development">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>DEVELOPMENT ROADMAP</span>
          <h2>Beyond historical scenarios and a single pilot region.</h2>
          <p>
            Future work combines climate stress testing with better agricultural coverage. The aim
            is not simply to increase the number of simulations: every new region and crop also
            requires quality-controlled inputs and independent validation.
          </p>
        </section>
        <section className={styles.roadmapSection} aria-label="Technical roadmap">
          <div className={styles.roadmapGrid}>
            {roadmap.map((item) => (
              <article className={styles.roadmapCard} key={item.no}>
                <span className={styles.roadmapNumber}>{item.no}</span>
                <h3>{item.title}</h3><p>{item.detail}</p>
              </article>
            ))}
          </div>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>ILLUSTRATIVE CLIMATE SCENARIO FROM THE REPORT</span>
          <h2>A short-term stress test, not a weather forecast.</h2>
          <div className={styles.projectMetrics}>
            <div><strong>881 → 890</strong><span>Modelled annual ET₀, mm; SSP1-2.6 at +5 years</span></div>
            <div><strong>−0.8 pp</strong><span>Relative yield change in the tested diversified rotation</span></div>
            <div><strong>−27.4 €</strong><span>Change in partial margin, per ha/year</span></div>
          </div>
          <p>
            In the report's Field 1 example, the simulated relative yield moves from 94.4% to 93.7%
            and the margin from about 908 to 881 €/ha/year. The scenario holds soil parameters
            and input prices constant so that the climate perturbation is isolated. It is an
            exploratory comparison, not a validated prediction of a future harvest.
          </p>
        </section>
        <aside className={styles.projectNotice}>
          <strong>Necessary safeguards for expansion</strong>
          <p>
            New regions need suitable soil and agronomic configurations; interpolating weather does
            not create finer observations. New crops require crop-specific parameters and independent
            comparisons, and any practical rollout needs farmers' feedback and operational benchmarks.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
