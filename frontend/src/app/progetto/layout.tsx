import type { ReactNode } from "react";
import ProjectSectionNav from "../../components/project/ProjectSectionNav";
import styles from "../../styles/project.module.css";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  return (
    <main className={styles.projectShell}>
      <div className={styles.projectContainer}>
        <header className={styles.projectHeader}>
          <div className={styles.headerTitleGroup}>
            <span className={styles.eyebrow}>
              <span className={styles.eyebrowDot} aria-hidden="true" />
              FIELDWISE / NASA SPACE APPS CHALLENGE 2026
            </span>
            <p className={styles.headerTitle}>Explore the project.</p>
            <p className={styles.headerDescription}>
              From Earth observation data to more informed agricultural decisions.
            </p>
          </div>
          <div className={styles.reportDownloadGroup}>
            <a
              className={styles.reportDownloadButton}
              href="/project/fieldwise-technical-report.pdf"
              download="FIELDWISE_Technical_Report_2026.pdf"
              type="application/pdf"
              aria-label="Download the FIELDWISE technical report PDF"
            >
              <span aria-hidden="true">↓</span> Download full report <span className={styles.reportDownloadFormat}>PDF</span>
            </a>
            <span className={styles.reportDownloadNote}>Technical report · Final · 25 pages</span>
          </div>
        </header>

        <ProjectSectionNav />
        {children}
      </div>
    </main>
  );
}
