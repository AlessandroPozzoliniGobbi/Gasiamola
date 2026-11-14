"use client";

import { useEffect, useRef } from "react";

// Ogni figura inizia in (0, -120) e termina in (0, 120).
// I raccordi uniscono questi punti: il risultato e un filo continuo.
const FIGURES = [
  // Satellite.
  `M 0 -120 C 0 -90 -40 -87 -92 -52
   L -92 -26 L -108 -26 L -108 12 L -76 12 L -76 -26 L -108 -26
   L -118 -26 L -118 -36 L -170 -36 L -170 12 L -118 12 L -118 -26
   L -144 -26 L -144 -36 L -144 12 L -170 12 L -170 -12 L -118 -12
   L -108 -12 L -108 -26 L -76 -26 L -66 -26 L -66 -36
   L -14 -36 L -14 12 L -66 12 L -66 -26
   L -40 -26 L -40 -36 L -40 12 L -14 12 L -14 -12 L -66 -12
   L -76 -12 L -76 12 L -92 12 L -92 29
   Q -115 29 -121 43 Q -92 68 -63 43 Q -69 29 -92 29
   L -92 48 C -82 78 -8 64 0 120`,

  // Spiga.
  `M 0 -120 C 0 -87 -40 -95 -74 -88
   Q -104 -96 -104 -120 Q -76 -114 -74 -88 L -74 -65
   Q -113 -67 -121 -94 Q -85 -94 -74 -65
   Q -39 -71 -28 -100 Q -66 -98 -74 -65 L -74 -39
   Q -112 -40 -126 -70 Q -87 -66 -74 -39
   Q -40 -44 -22 -73 Q -63 -70 -74 -39 L -74 -12
   Q -118 -15 -130 -43 Q -91 -38 -74 -12
   Q -35 -16 -19 -46 Q -62 -40 -74 -12 L -74 17
   Q -113 16 -129 -12 Q -89 -5 -74 17
   Q -34 13 -20 -15 Q -61 -11 -74 17
   C -74 55 -77 72 -66 82 C -45 103 -2 73 0 120`,

  // Goccia con onda.
  `M 0 -120 C 0 -80 -69 -104 -88 -78
   C -107 -48 -149 -3 -149 31 C -149 66 -124 91 -88 91
   C -52 91 -27 66 -27 31 C -27 -3 -69 -48 -88 -78
   C -107 -48 -149 -3 -149 31
   Q -121 13 -91 32 T -27 31 C -3 48 0 87 0 120`,

  // Germoglio.
  `M 0 -120 C 0 -90 -30 -107 -39 -95
   Q -101 -95 -94 -23 Q -39 -26 -39 -95 Q -76 -64 -94 -23
   L -94 6 Q -153 4 -168 -53 Q -111 -54 -94 6
   Q -128 -13 -168 -53 Q -111 -54 -94 6 L -94 78
   Q -125 68 -145 84 Q -94 65 -43 84 C -14 94 0 90 0 120`,
];

type Stroke = {
  element: SVGPathElement;
  start: number;
  end: number;
};

export default function HomeLineArt() {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    const home = svg?.parentElement;

    if (!svg || !home) return;

    const sections = Array.from(
      home.querySelectorAll<HTMLElement>("[data-line-section]"),
    );

    if (!sections.length) return;

    const motion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    );

    let strokes: Stroke[] = [];
    let frame = 0;
    let needsLayout = true;

    function addStroke(
      d: string,
      start: number,
      end: number,
      transform = "",
      scale = 1,
    ) {
      const element = document.createElementNS(
        "http://www.w3.org/2000/svg",
        "path",
      );

      element.setAttribute("d", d);
      element.setAttribute("pathLength", "1");

      if (transform) {
        element.setAttribute("transform", transform);
      }

      // Mantiene sottile il tratto anche quando le figure cambiano scala.
      element.style.strokeWidth = String(1.7 / scale);
      element.style.strokeDasharray = "1 1";
      element.style.strokeDashoffset = "1";
      element.style.opacity = "0";

      svg!.appendChild(element);
      strokes.push({ element, start, end });
    }

    function layout() {
      const bounds = home!.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;

      const mobile = width <= 700;
      const edge = mobile ? 18 : Math.min(56, width * 0.04);
      const scale = mobile ? 0.46 : Math.min(1.1, width / 1200);
      const half = 120 * scale;

      svg!.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg!.replaceChildren();

      strokes = [];

      let previousX = width - edge;
      let previousY = 0;

      sections.forEach((section, index) => {
        const rect = section.getBoundingClientRect();
        const top = rect.top - bounds.top;

        const right = index % 2 === 0;
        const x = right ? width - edge : edge;

        // Su mobile la figura sta sopra il testo, vicino al bordo.
        const y = top + (mobile ? 94 : rect.height * 0.42);

        const entry = y - half;
        const exit = y + half;

        const connector =
          index === 0
            ? `M ${x} 0
               C ${x} ${entry * 0.3}
                 ${x} ${entry * 0.7}
                 ${x} ${entry}`
            : `M ${previousX} ${previousY}
               C ${previousX} ${top - 55}
                 ${previousX} ${top - 25}
                 ${width / 2} ${top}
               C ${x} ${top + 25}
                 ${x} ${top + 30}
                 ${x} ${entry}`;

        addStroke(connector, previousY, entry);

        addStroke(
          FIGURES[index % FIGURES.length],
          entry,
          exit,
          `translate(${x} ${y}) scale(${
            right ? scale : -scale
          } ${scale})`,
          scale,
        );

        previousX = x;
        previousY = exit;
      });

      addStroke(
        `M ${previousX} ${previousY}
         C ${previousX} ${previousY + 100}
           ${previousX} ${height - 100}
           ${previousX} ${height - 24}`,
        previousY,
        height - 24,
      );
    }

    function paint() {
      const bounds = home!.getBoundingClientRect();
      const viewport = window.innerHeight;

      const bottomVisible = bounds.bottom <= viewport + 1;
      const front = viewport * 0.88 - bounds.top;

      for (const { element, start, end } of strokes) {
        const progress =
          motion.matches || bottomVisible
            ? 1
            : Math.max(
                0,
                Math.min(
                  1,
                  (front - start) / Math.max(1, end - start),
                ),
              );

        element.style.strokeDashoffset = String(1 - progress);
        element.style.opacity = progress > 0 ? "1" : "0";
      }
    }

    function tick() {
      frame = 0;

      if (needsLayout) {
        layout();
        needsLayout = false;
      }

      paint();
    }

    function schedule() {
      if (!frame) {
        frame = window.requestAnimationFrame(tick);
      }
    }

    function resize() {
      needsLayout = true;
      schedule();
    }

    // Ricalcola il percorso anche quando cambia l'altezza dei testi.
    const observer = new ResizeObserver(resize);

    observer.observe(home);

    sections.forEach((section) => {
      observer.observe(section);
    });

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", resize);
    window.addEventListener("pageshow", schedule);
    motion.addEventListener("change", schedule);

    schedule();

    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();

      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pageshow", schedule);
      motion.removeEventListener("change", schedule);

      svg.replaceChildren();
    };
  }, []);

  return (
    <svg
      ref={svgRef}
      className="home-line-art"
      aria-hidden="true"
      focusable="false"
      preserveAspectRatio="none"
    />
  );
}