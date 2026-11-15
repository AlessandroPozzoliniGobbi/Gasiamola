import type { ReactNode } from "react";
import Link from "next/link";
import { projectSectionBySlug, projectSections, PROJECT_TOTAL_CHAPTERS } from "../../lib/projectSections";
import styles from "../../styles/project.module.css";

type Props = { slug: string; children?: ReactNode };

/** Shared project chapter frame, fed by the report-based content pages. */
export default function ProjectChapter({ slug, children }: Props) {
  const section = projectSectionBySlug(slug);
  if (!section) return null;

  const currentIndex = projectSections.findIndex((candidate) => candidate.slug === slug);
  const previous = projectSections[currentIndex - 1];
  const next = projectSections[currentIndex + 1];

  return (
    <article className={styles.contentCard}>
      <div className={styles.contentHeading}>
        <span className={styles.sectionLabel}>CHAPTER {section.number} / {String(PROJECT_TOTAL_CHAPTERS).padStart(2, "0")}</span>
        <h1 className={styles.pageTitle}>{section.title}</h1>
        <p className={styles.lead}>{section.description}</p>
      </div>

      {children}

      <footer className={styles.chapterFooter}>
        {previous ? (
          <Link href={`/progetto/${previous.slug}`} className={styles.chapterMove}>
            <span className={styles.moveKicker}>← PREVIOUS</span>
            <strong>{previous.title}</strong>
          </Link>
        ) : (
          <Link href="/progetto" className={styles.chapterMove}>
            <span className={styles.moveKicker}>← BACK TO</span>
            <strong>Project overview</strong>
          </Link>
        )}
        {next ? (
          <Link href={`/progetto/${next.slug}`} className={`${styles.chapterMove} ${styles.chapterMoveNext}`}>
            <span className={styles.moveKicker}>NEXT →</span>
            <strong>{next.title}</strong>
          </Link>
        ) : (
          <Link href="/progetto" className={`${styles.chapterMove} ${styles.chapterMoveNext}`}>
            <span className={styles.moveKicker}>BACK TO →</span>
            <strong>Project overview</strong>
          </Link>
        )}
      </footer>
    </article>
  );
}
