"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { projectSections } from "../../lib/projectSections";
import styles from "../../styles/project.module.css";

/** Real subpages, not scroll anchors. Overview is the first destination. */
export default function ProjectSectionNav() {
  const pathname = usePathname();
  const linksRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const links = linksRef.current;
    const active = links?.querySelector<HTMLElement>('[aria-current="page"]');
    if (!links || !active) return;
    // Keep the current chapter visible on small screens without scrolling the page.
    const centeredLeft = active.offsetLeft - links.offsetLeft - (links.clientWidth - active.clientWidth) / 2;
    links.scrollTo({ left: Math.max(0, centeredLeft), behavior: "instant" });
  }, [pathname]);
  const overviewActive = pathname === "/progetto" || pathname === "/progetto/";

  return (
    <nav className={styles.chapterNav} aria-label="Project sections">
      <div ref={linksRef} className={styles.chapterLinks}>
        <Link
          href="/progetto"
          className={`${styles.chapterLink} ${overviewActive ? styles.chapterActive : ""}`}
          aria-current={overviewActive ? "page" : undefined}
        >
          Overview
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
              {section.navLabel}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
