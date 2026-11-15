"use client";

import type { ReactNode } from "react";
import styles from "../../styles/map.module.css";

type Props = {
  count: number;
  onClose: () => void;
  children: ReactNode;
};

/** A fixed, collapsible field list inside the map sidebar.
 * Field polygons remain editable on the map; only the panel's dragging
 * and window resizing have been removed.
 */
export default function FloatingFieldWindow({ count, onClose, children }: Props) {
  return (
    <section id="fields-floating-panel" className={`${styles.floatingFields} ${styles.floatingDocked}`}
      aria-label="Field list">
      <header className={styles.floatingHeader}>
        <div className={styles.floatingHeading}>
          <strong>Saved fields</strong>
          <span className={styles.floatingCount}>{count}</span>
        </div>
        <button type="button" className={styles.floatingIconButton} onClick={onClose}
          aria-label="Close field list">×</button>
      </header>
      <div className={styles.floatingBody}>{children}</div>
    </section>
  );
}
