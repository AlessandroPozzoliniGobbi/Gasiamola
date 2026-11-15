import type { Metadata } from "next";
import Link from "next/link";
import styles from "../../styles/project.module.css";

export const metadata: Metadata = {
  title: "Project Overview | FIELDWISE",
  description: "FIELDWISE is a crop-rotation decision-support project created for the NASA Space Apps Challenge 2026.",
};

export default function ProjectPage() {
  return (
    <article className={`${styles.contentCard} ${styles.overviewCard}`}>
      <div className={styles.overviewBody}>
        <div className={styles.overviewIntro}>
          <span className={styles.sectionLabel}>CHAPTER 01 / 09 · PROJECT OVERVIEW</span>
          <h1 className={styles.pageTitle}>Know your land. Grow your future.</h1>
          <p className={styles.lead}>
            Agriculture depends on decisions made under uncertainty. Water scarcity, soil degradation
            and changing weather patterns make it increasingly difficult to choose what to grow
            and how to manage limited resources.
          </p>
          <p className={styles.overviewSecondary}>
            Created for the <strong>NASA Space Apps Challenge 2026</strong>, FIELDWISE responds to
            <em> Field Shift: Adapting Farms with NASA Data</em>. It brings together Earth observation,
            soil information and crop-rotation simulations to help farmers compare alternatives
            rather than rely on a single prediction.
          </p>
        </div>

        <div className={styles.overviewHighlights} aria-label="The project at a glance">
          <div className={styles.overviewHighlight}>
            <span>THE CHALLENGE</span>
            <p>Make scientific environmental data useful for real farming decisions.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>THE PROTOTYPE</span>
            <p>Explore maize, soybean and soft-wheat rotations around a pilot area in Cremona.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>THE PRINCIPLE</span>
            <p>Show resource use, soil effects, economic trade-offs and uncertainty together.</p>
          </div>
        </div>
      </div>

      <section className={styles.overviewMission} aria-label="Our mission">
        <span className={styles.projectKicker}>WHY IT MATTERS</span>
        <p>
          History shows how vulnerable agriculture can become when choices are constrained and
          risks are poorly understood. FIELDWISE does not replace the farmer or the agronomist:
          it makes selected evidence easier to compare, while leaving practical decisions to
          people who know the land.
        </p>
      </section>

      <footer className={styles.overviewFooter}>
        <div className={styles.overviewInfo}>
          <span className={styles.overviewNumber}>09</span>
          <span>Project chapters: methodology, data, results, stakeholders, limitations and more.</span>
        </div>
        <Link className={styles.primaryLink} href="/progetto/analytical-framework">
          Explore the framework <span aria-hidden="true">→</span>
        </Link>
      </footer>
    </article>
  );
}
