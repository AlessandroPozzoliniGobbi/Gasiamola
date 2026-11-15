import type { ReactNode } from "react";
import Link from "next/link";
import { projectSectionBySlug, projectSections } from "../../lib/projectSections";
import styles from "../../styles/project.module.css";

type Props = { slug: string; children?: ReactNode };

/** Shared frame. Each chapter has its own page.tsx, ready to receive custom content. */
export default function ProjectChapter({ slug, children }: Props) {
  const section = projectSectionBySlug(slug);
  if (!section) return null;

  const currentIndex = projectSections.findIndex((candidate) => candidate.slug === slug);
  const previous = projectSections[currentIndex - 1];
  const next = projectSections[currentIndex + 1];

  return (
    <article className={styles.contentCard}>
      <div className={styles.contentHeading}>
        <span className={styles.sectionLabel}>CHAPTER {section.number} / {String(projectSections.length + 1).padStart(2, "0")}</span>
        <h1 className={styles.pageTitle}>{section.title}</h1>
        <p className={styles.lead}>{section.description}</p>
      </div>

      {children ?? (
        <section className={styles.draftArea} aria-labelledby="chapter-outline-heading">
          <div className={styles.draftTopline}>
            <span className={styles.draftDot} aria-hidden="true" />
            <span>SECTION IN PREPARATION</span>
          </div>
          <h2 className={styles.draftTitle} id="chapter-outline-heading">Planned content</h2>
          <p className={styles.draftText}>
            This chapter is ready for the project team&apos;s research, explanations, illustrations, and references.
          </p>
          <ul className={styles.topicList}>
            {section.topics.map((topic) => <li key={topic}>{topic}</li>)}
          </ul>
        </section>
      )}

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
