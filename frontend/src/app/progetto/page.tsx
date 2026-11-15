import type { Metadata } from "next";
import Link from "next/link";
import styles from "../../styles/project.module.css";

export const metadata: Metadata = { title: "Project Overview | FIELDWISE" };

/** Introduction and overview are a single landing page. */
export default function ProjectPage() {
  return (
    <article className={`${styles.contentCard} ${styles.overviewCard}`}>
      <div className={styles.overviewBody}>
        <div className={styles.overviewIntro}>
          <span className={styles.sectionLabel}>CHAPTER 01 / 09 · PROJECT OVERVIEW</span>
          <h1 className={styles.pageTitle}>A clearer view of every field.</h1>
          <p className={styles.lead}>
            FIELDWISE is a decision-support project developed for the NASA Space Apps Challenge 2026.
            By combining Earth observation data with agricultural models, we help farmers compare
            crop rotations, understand trade-offs and make better-informed decisions.
          </p>
        </div>

        <div className={styles.overviewHighlights} aria-label="Introduction at a glance">
          <div className={styles.overviewHighlight}>
            <span>THE CHALLENGE</span>
            <p>Make complex environmental information useful for real agricultural decisions.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>OUR APPROACH</span>
            <p>Compare crop rotations using historical climate data and physical soil balances.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>OUR GOAL</span>
            <p>Show evidence, risks and limitations clearly—not just a recommendation.</p>
          </div>
        </div>
      </div>

      <footer className={styles.overviewFooter}>
        <div className={styles.overviewInfo}>
          <span className={styles.overviewNumber}>09</span>
          <span>Dedicated sections, including Scalability. Explore them using the chapter navigation.</span>
        </div>
        <Link className={styles.primaryLink} href="/progetto/analytical-framework">
          Explore the framework <span aria-hidden="true">→</span>
        </Link>
      </footer>
    </article>
  );
}
