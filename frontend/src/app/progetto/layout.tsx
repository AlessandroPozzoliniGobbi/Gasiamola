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
        </header>

        <ProjectSectionNav />
        {children}
      </div>
    </main>
  );
}
