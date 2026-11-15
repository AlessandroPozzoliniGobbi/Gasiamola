import type { Metadata } from "next";
import Link from "next/link";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Conclusions | FIELDWISE" };

const nextSteps = [
  { number: "01", title: "Validate beyond Cremona", text: "Compare additional regions, crops and soil processes with independent measurements and on-farm records." },
  { number: "02", title: "Work with farmers", text: "Test whether the alternatives, uncertainty indicators and economic assumptions support practical decisions." },
  { number: "03", title: "Refine the engine", text: "Improve crop stress, nitrogen, humus and hydrological processes before making stronger agronomic claims." },
  { number: "04", title: "Scale responsibly", text: "Reuse prepared field data and simulations while benchmarking the service and its cost of operation." },
];

export default function ConclusionsPage() {
  return (
    <ProjectChapter slug="conclusions">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>THE CENTRAL TAKEAWAY</span>
          <h2>Better comparisons lead to better questions.</h2>
          <p>
            FIELDWISE demonstrates how NASA Earth observations and a daily, process-based model
            can make crop-rotation decisions more transparent. It combines production, resource
            requirements, soil indicators and partial economic outcomes without pretending that
            one model can fully describe every field.
          </p>
          <p>
            At the Cremona pilot, surface moisture, maize stress and maize yield variability show
            encouraging agreement with selected independent datasets. Other crops and processes
            remain uncertain, and the ranking of competing rotations changes when assumptions do.
          </p>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>WHAT WE NEED NEXT</span>
          <h2>Build confidence before reach.</h2>
          <div className={styles.projectSteps}>
            {nextSteps.map((step) => (
              <div className={styles.projectStep} key={step.number}>
                <span>{step.number}</span><div><h3>{step.title}</h3><p>{step.text}</p></div>
              </div>
            ))}
          </div>
        </section>
        <aside className={styles.projectNotice}>
          <strong>Science-informed, farmer-led</strong>
          <p>
            FIELDWISE is a decision-support framework, not an automatic recommendation system.
            The final choice belongs to farmers and professionals who know the field, its
            regulatory constraints and its economic context.
          </p>
        </aside>
        <div className={styles.projectCtaRow}>
          <a className={styles.primaryLink} href="/project/fieldwise-technical-report.pdf" download="FIELDWISE_Technical_Report_2026.pdf">Download the complete report (PDF)</a>
          <Link href="/progetto/sources" className={styles.projectTextLink}>Explore the data and references →</Link>
        </div>
      </div>
    </ProjectChapter>
  );
}
