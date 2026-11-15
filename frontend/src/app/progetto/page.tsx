import type { Metadata } from "next";
import Link from "next/link";
import { PROJECT_TOTAL_CHAPTERS } from "../../lib/projectSections";
import styles from "../../styles/project.module.css";

export const metadata: Metadata = {
  title: "Project Overview | FIELDWISE",
  description: "Explore FIELDWISE: crop-rotation simulation, independent validation and agricultural decision support developed for NASA Space Apps Challenge 2026.",
};

export default function ProjectPage() {
  return (
    <article className={`${styles.contentCard} ${styles.overviewCard}`}>
      <div className={styles.overviewBody}>
        <div className={styles.overviewIntro}>
          <span className={styles.sectionLabel}>CHAPTER 01 / {String(PROJECT_TOTAL_CHAPTERS).padStart(2, "0")} · PROJECT OVERVIEW</span>
          <h1 className={styles.pageTitle}>Know your land. Grow your future.</h1>
          <p className={styles.lead}>
            What should a farmer grow next, when water is limited, weather is uncertain and
            today's choices affect the next harvest? FIELDWISE makes crop-rotation alternatives
            easier to compare.
          </p>
          <p className={styles.overviewSecondary}>
            Created at the <strong>NASA Space Apps Challenge 2026</strong>, at Politecnico di Milano,
            for <em> Field Shift: Adapting Farms with NASA Data</em>. The prototype combines daily
            NASA POWER weather, soil data and a deterministic agronomic model to examine
            production, resource use, soil indicators and an economic margin.
          </p>
        </div>
        <div className={styles.overviewHighlights} aria-label="Project highlights">
          <div className={styles.overviewHighlight}>
            <span>THE PILOT</span>
            <p><strong>Cremona, Italy.</strong> Maize, soybean and soft wheat, with optional rye cover crops.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>THE COMPARISON</span>
            <p><strong>216</strong> initial crop/cover combinations, reduced to <strong>45</strong> distinct classes per irrigation scenario.</p>
          </div>
          <div className={styles.overviewHighlight}>
            <span>THE EVIDENCE</span>
            <p>Selected responses agree with independent satellite and yield observations; rankings remain uncertain.</p>
          </div>
        </div>
      </div>
      <section className={styles.overviewMission} aria-label="Our mission">
        <span className={styles.projectKicker}>DECISION SUPPORT, NOT AUTOMATIC PRESCRIPTION</span>
        <p>
          FIELDWISE compares modelled alternatives under clearly stated assumptions. It does not
          forecast individual harvests or replace farmers and agronomists. The report documents
          the pilot results, unresolved limitations and development roadmap.
        </p>
      </section>
      <div className={styles.projectMetrics} aria-label="Pilot study at a glance">
        <div><strong>2000–2022</strong><span>Reference weather period</span></div>
        <div><strong>17</strong><span>Successful historical starting years</span></div>
        <div><strong>3</strong><span>Irrigation management scenarios</span></div>
      </div>
      <footer className={styles.overviewFooter}>
        <div className={styles.overviewInfo}>
          <span className={styles.overviewNumber}>{String(PROJECT_TOTAL_CHAPTERS).padStart(2, "0")}</span>
          <span>Short chapters distilled from the full 25-page technical report, available to download above.</span>
        </div>
        <Link className={styles.primaryLink} href="/progetto/analytical-framework">
          Explore the framework <span aria-hidden="true">→</span>
        </Link>
      </footer>
    </article>
  );
}
