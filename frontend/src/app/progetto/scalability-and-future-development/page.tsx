import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Scalability & Future Development | FIELDWISE" };

const growthAreas = [
  {
    number: "01",
    title: "Beyond the pilot area",
    description: "Expand geographic coverage when reliable local weather, soil and crop information is available. Adapt agronomic rules to each new region rather than applying the pilot assumptions everywhere.",
  },
  {
    number: "02",
    title: "More crops and farming systems",
    description: "Extend rotation options, irrigation constraints and crop-specific parameters step by step, supported by quality-controlled data and local agronomic expertise.",
  },
  {
    number: "03",
    title: "Faster analyses at scale",
    description: "Explore precomputed climate and soil data, reusable simulation results and queued processing for many fields, with monitoring of computation costs and data freshness.",
  },
  {
    number: "04",
    title: "Validation before wider adoption",
    description: "Compare outputs with field observations, document uncertainty and invite farmers and specialists to test whether recommendations are practical and understandable.",
  },
] as const;

export default function ScalabilityPage() {
  return (
    <ProjectChapter slug="scalability-and-future-development">
      <section className={styles.roadmapSection} aria-labelledby="roadmap-heading">
        <div className={styles.roadmapIntroduction}>
          <span className={styles.roadmapEyebrow}>PROPOSED ROADMAP / NOT YET IMPLEMENTED</span>
          <h2 id="roadmap-heading">From a regional prototype to a scalable platform</h2>
          <p>
            FIELDWISE currently demonstrates an approach to comparing crop rotations through
            environmental data and a simulation engine. Growing the project requires more than
            faster software: each new location and crop needs appropriate data, calibration and validation.
          </p>
        </div>
        <div className={styles.roadmapGrid}>
          {growthAreas.map((area) => (
            <article className={styles.roadmapCard} key={area.number}>
              <span className={styles.roadmapNumber}>{area.number}</span>
              <h3>{area.title}</h3>
              <p>{area.description}</p>
            </article>
          ))}
        </div>
        <aside className={styles.roadmapCaution}>
          <strong>What must come first?</strong>
          <p>
            Geographic availability, model validation, regional farming rules and transparent
            uncertainty reporting remain prerequisites for trustworthy recommendations. These
            are development directions, not claims of existing production-scale coverage.
          </p>
        </aside>
      </section>
    </ProjectChapter>
  );
}
