"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { projectSections } from "../../lib/projectSections";
import styles from "../../styles/project.module.css";

/** Real subpages, not scroll anchors. Overview is the first destination. */
export default function ProjectSectionNav() {
  const pathname = usePathname();
  const overviewActive = pathname === "/progetto" || pathname === "/progetto/";

  return (
    <nav className={styles.chapterNav} aria-label="Project sections">
      <div className={styles.chapterLinks}>
        <Link
          href="/progetto"
          className={`${styles.chapterLink} ${overviewActive ? styles.chapterActive : ""}`}
          aria-current={overviewActive ? "page" : undefined}
        >
          Project Overview
        </Link>
        {projectSections.map((section) => {
          const href = `/progetto/${section.slug}`;
          const active = pathname === href;
          return (
            <Link
              key={section.slug}
              href={href}
              className={`${styles.chapterLink} ${active ? styles.chapterActive : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {section.title}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
