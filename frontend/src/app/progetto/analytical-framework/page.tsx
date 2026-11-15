import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Analytical Framework | FIELDWISE" };

const criteria = [
  { heading: "Production", metric: "Relative crop yield", detail: "Compare performance across different crop sequences." },
  { heading: "Resilience", metric: "Worst historical outcome", detail: "Understand how a rotation behaves in difficult past seasons." },
  { heading: "Resources", metric: "Water & nitrogen demand", detail: "Examine the irrigation and fertilizer requirements of each option." },
  { heading: "Soil", metric: "Humus & nitrogen leaching", detail: "Consider long-term soil indicators alongside production." },
  { heading: "Economics", metric: "Modelled partial margin", detail: "Include crop revenue and selected production costs, not total farm profit." },
] as const;

export default function FrameworkPage() {
  return (
    <ProjectChapter slug="analytical-framework">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>THE FARMER&apos;S DECISION</span>
          <h2>One choice affects the next.</h2>
          <p>
            FIELDWISE addresses a practical question: <strong>keep the current rotation or adopt a different one?</strong>
            Crops use resources, leave residues and change soil conditions for the seasons that follow.
            Yield alone cannot describe the consequences of that choice.
          </p>
          <p>
            Farmers make these decisions before they know the weather or the outcome of the next harvest.
            Scientific information can reduce uncertainty, but accessing and interpreting it takes time.
            The framework brings a selection of those factors into a common comparison, while recognising
            the importance of experience, costs and local constraints.
          </p>
        </section>

        <section className={styles.projectFeatureBand} aria-label="Prototype scope">
          <div><strong>03</strong><span>Main crops</span><small>Maize · soybean · soft wheat</small></div>
          <div><strong>01</strong><span>Optional cover crop</span><small>Rye between main crops</small></div>
          <div><strong>45</strong><span>Distinct rotation classes</span><small>Per irrigation scenario in the reference comparison</small></div>
        </section>

        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>HOW OPTIONS ARE COMPARED</span>
          <h2>Several priorities. One transparent comparison.</h2>
          <p>
            The current rotation serves as a <strong>simulated baseline</strong>. Alternatives are tested using
            common historical weather and management assumptions, allowing like-for-like comparisons.
            The user can adjust the importance of each criterion; different priorities can legitimately
            lead to different recommendations.
          </p>
          <div className={styles.projectCriteriaGrid}>
            {criteria.map((item, index) => (
              <div className={styles.projectCriterion} key={item.heading}>
                <span className={styles.projectCriterionNumber}>0{index + 1}</span>
                <h3>{item.heading}</h3>
                <strong>{item.metric}</strong>
                <p>{item.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <aside className={styles.projectNotice}>
          <strong>What a ranking does — and does not — mean</strong>
          <p>
            A high score is not a guaranteed harvest or a forecast of farm profit. The comparison
            reveals modelled trade-offs under the chosen conditions. Regional compliance filters,
            practical feasibility and the farmer&apos;s own knowledge remain essential.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
