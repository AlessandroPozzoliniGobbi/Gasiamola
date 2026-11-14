"use client";

import { useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent, ReactNode } from "react";
import styles from "../../styles/map.module.css";

type Props = {
  count: number;
  onClose: () => void;
  children: ReactNode;
};
type Position = { x: number; y: number };
type Size = { width: number; height: number };
type DragInfo = Position & {
  pointerX: number;
  pointerY: number;
  pointerId: number;
};

/**
 * Inizialmente e' un pannello nella sidebar (stessa larghezza, sotto la tendina).
 * Trascinando la testata viene staccato e puo' muoversi sulla mappa.
 */
export default function FloatingFieldWindow({ count, onClose, children }: Props) {
  const panelRef = useRef<HTMLElement | null>(null);
  const dragRef = useRef<DragInfo | null>(null);
  const [detached, setDetached] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [position, setPosition] = useState<Position>({ x: 20, y: 20 });
  const [size, setSize] = useState<Size>({ width: 328, height: 280 });

  const isMobile = () => window.matchMedia("(max-width: 768px)").matches;

  const rememberPosition = () => {
    const rect = panelRef.current?.getBoundingClientRect();
    if (rect) {
      setPosition({ x: rect.left, y: rect.top });
      setSize({ width: rect.width, height: rect.height });
    }
  };

  const toggleMaximize = () => {
    if (!detached) rememberPosition();
    setDetached(true);
    setMaximized((value) => !value);
  };

  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (event.button !== 0 || maximized || isMobile()) return;
    if ((event.target as HTMLElement).closest("button")) return;
    const panel = panelRef.current;
    if (!panel) return;

    const rect = panel.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      pointerX: event.clientX,
      pointerY: event.clientY,
      x: rect.left,
      y: rect.top,
    };
    setPosition({ x: rect.left, y: rect.top });
    setSize({ width: rect.width, height: rect.height });
    setDetached(true);
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  };

  const moveDrag = (event: ReactPointerEvent<HTMLElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const panel = panelRef.current;
    if (!panel) return;
    const x = drag.x + event.clientX - drag.pointerX;
    const y = drag.y + event.clientY - drag.pointerY;
    setPosition({
      x: Math.min(Math.max(8, x), Math.max(8, window.innerWidth - panel.offsetWidth - 8)),
      y: Math.min(Math.max(8, y), Math.max(8, window.innerHeight - panel.offsetHeight - 8)),
    });
  };

  const stopDrag = (event: ReactPointerEvent<HTMLElement>) => {
    if (dragRef.current?.pointerId !== event.pointerId) return;
    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  // Se il browser viene ristretto, la finestra staccata resta visibile.
  useEffect(() => {
    if (!detached || maximized) return;
    const clamp = () => {
      const panel = panelRef.current;
      if (!panel) return;
      setPosition((old) => {
        const x = Math.min(Math.max(8, old.x), Math.max(8, window.innerWidth - panel.offsetWidth - 8));
        const y = Math.min(Math.max(8, old.y), Math.max(8, window.innerHeight - panel.offsetHeight - 8));
        return old.x === x && old.y === y ? old : { x, y };
      });
    };
    window.addEventListener("resize", clamp);
    return () => window.removeEventListener("resize", clamp);
  }, [detached, maximized]);

  const className = [
    styles.floatingFields,
    detached ? styles.floatingDetached : styles.floatingDocked,
    maximized ? styles.floatingMaximized : "",
  ].join(" ");

  return (
    <section
      id="fields-floating-panel"
      ref={panelRef}
      className={className}
      style={detached ? {
        left: position.x,
        top: position.y,
        width: size.width,
        height: size.height,
      } : undefined}
      aria-label="Finestra degli appezzamenti"
    >
      <header
        className={styles.floatingHeader}
        onPointerDown={startDrag}
        onPointerMove={moveDrag}
        onPointerUp={stopDrag}
        onPointerCancel={stopDrag}
        onDoubleClick={toggleMaximize}
        title="Trascina per spostare la finestra"
      >
        <div className={styles.floatingHeading}>
          <span className={styles.floatingHeadingIcon} aria-hidden="true">⠿</span>
          <strong>{detached ? "Appezzamenti" : "Elenco appezzamenti"}</strong>
          <span className={styles.floatingCount}>{count}</span>
        </div>
        <div className={styles.floatingButtons}>
          <button
            type="button"
            className={styles.floatingIconButton}
            onClick={toggleMaximize}
            aria-label={maximized ? "Riduci la finestra" : "Ingrandisci la finestra"}
          >
            {maximized ? "❐" : "□"}
          </button>
          <button
            type="button"
            className={styles.floatingIconButton}
            onClick={onClose}
            aria-label="Chiudi elenco appezzamenti"
          >×</button>
        </div>
      </header>
      <div className={styles.floatingBody}>{children}</div>
      {!maximized && detached && <div className={styles.floatingResizeHint} aria-hidden="true">⋰</div>}
    </section>
  );
}
