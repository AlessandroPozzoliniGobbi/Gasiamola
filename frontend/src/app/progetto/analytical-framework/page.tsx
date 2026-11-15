import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Analytical Framework | FIELDWISE" };

const criteria = [
  { heading: "Yield", metric: "Median historical relative yield", detail: "Higher yield relative to configured crop potential is preferred." },
  { heading: "Risk", metric: "Worst historical relative yield", detail: "A downside indicator based on the observed minimum, not a loss probability." },
  { heading: "Water", metric: "Net irrigation / year", detail: "Lower water demand is preferred, subject to production trade-offs." },
  { heading: "Fertilizer", metric: "Fertilizer nitrogen / year", detail: "Reduce modelled nitrogen application requirements where feasible." },
  { heading: "Soil", metric: "Humus change & nitrogen leaching", detail: "More humus and less leaching are both considered." },
  { heading: "Profit", metric: "Annualised partial margin", detail: "Compare selected variable costs and revenue; not total farm profit." },
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
          <h2>Six priorities. One transparent comparison.</h2>
          <p>
            The current rotation serves as a <strong>simulated baseline</strong>. Alternatives are tested using
            common historical weather and management assumptions, allowing like-for-like comparisons.
            The user can adjust the importance of each of six priorities; different weights can
            legitimately lead to different recommendations. The underlying seven indicators
            are normalised within the comparison set, not on an absolute scale.
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
