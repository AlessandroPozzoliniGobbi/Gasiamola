"use client";

import { useEffect, useRef } from "react";

type Station = {
  x: number;
  cardTop: number;
  cardBottom: number;
  enter: number;
  leave: number;
  sway: number;
  direction: number;
};

/**
 * Un solo tracciato SVG dall'inizio alla fine della Home.
 * Il disegno si rivela con lo scroll utilizzando la lunghezza REALE del path:
 * in questo modo curve e raccordi non scompaiono a seconda del browser.
 */
export default function HomeLineArt() {
  const svgRef = useRef<SVGSVGElement>(null);
  const threadRef = useRef<SVGPathElement>(null);
  const outlineRef = useRef<SVGPathElement>(null);
  const tipRef = useRef<SVGGElement>(null);

  useEffect(() => {
    const svg = svgRef.current;
    const thread = threadRef.current;
    const outline = outlineRef.current;
    const tip = tipRef.current;
    const home = svg?.parentElement;
    if (!svg || !thread || !outline || !tip || !home) return;

    const sections = Array.from(home.querySelectorAll<HTMLElement>("[data-line-section]"));
    if (!sections.length) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let recalculate = true;
    let active = true;
    let totalLength = 0;
    let sampleYs: number[] = [];

    const clamp = (value: number, min: number, max: number) =>
      Math.max(min, Math.min(max, value));

    function layout() {
      if (!home || !svg || !thread || !outline) return;
      const bounds = home.getBoundingClientRect();
      const width = bounds.width;
      const height = bounds.height;
      if (width <= 0 || height <= 0) return;

      const cardRects = sections.map((section) => {
        const content = section.querySelector<HTMLElement>(".landing-content") ?? section;
        const rect = content.getBoundingClientRect();
        return {
          top: rect.top - bounds.top,
          bottom: rect.bottom - bounds.top,
          left: rect.left - bounds.left,
          right: bounds.right - rect.right,
        };
      });

      // Sui dispositivi stretti si rimane nello stesso margine, senza
      // attraversare le card. Su desktop i cambi di lato avvengono nei vuoti.
      const stations: Station[] = cardRects.map((card, index) => {
        const onRight = width >= 860 ? index % 2 === 0 : true;
        const gutter = Math.max(0, onRight ? card.right : card.left);
        const inset = clamp(gutter * 0.24, 11, 46);
        const direction = onRight ? -1 : 1;
        const x = onRight ? width - inset : inset;
        const sway = clamp(gutter - inset - 32, 0, 44);
        return {
          x,
          cardTop: card.top,
          cardBottom: card.bottom,
          enter: Math.max(15, card.top - 15),
          leave: Math.min(height - 15, card.bottom + 15),
          sway,
          direction,
        };
      });

      const first = stations[0];
      if (!first) return;
      let d = `M ${first.x.toFixed(1)} 0`;
      let previous = first;

      for (let index = 0; index < stations.length; index++) {
        const current = stations[index];
        if (index > 0) {
          const availableTop = previous.leave + 10;
          const availableBottom = current.enter - 10;
          const delta = availableBottom - availableTop;

          if (delta > 45 && Math.abs(current.x - previous.x) > 12) {
            // Curva a S con tangenti verticali. Il percorso attraversa la
            // pagina solo dopo la fine della card precedente e prima della
            // successiva: non passa mai sopra il testo.
            d += ` L ${previous.x.toFixed(1)} ${availableTop.toFixed(1)}`;
            d += ` C ${previous.x.toFixed(1)} ${(availableTop + delta * 0.42).toFixed(1)}`;
            d += ` ${current.x.toFixed(1)} ${(availableBottom - delta * 0.42).toFixed(1)}`;
            d += ` ${current.x.toFixed(1)} ${availableBottom.toFixed(1)}`;
          } else {
            // In spazi troppo brevi, una traslazione laterale minima.
            d += ` L ${previous.x.toFixed(1)} ${availableTop.toFixed(1)}`;
            d += ` L ${current.x.toFixed(1)} ${Math.max(availableTop, availableBottom).toFixed(1)}`;
          }
        }

        const top = Math.max(index === 0 ? 2 : previous.leave + 2, current.enter);
        const bottom = Math.max(top + 1, current.leave);
        const quarter = (bottom - top) * 0.25;
        const innerX = current.x + current.direction * current.sway;

        // Una lieve curva a foglia anima i margini senza invadere i riquadri.
        d += ` L ${current.x.toFixed(1)} ${top.toFixed(1)}`;
        d += ` C ${current.x.toFixed(1)} ${(top + quarter).toFixed(1)}`;
        d += ` ${innerX.toFixed(1)} ${(top + quarter).toFixed(1)}`;
        d += ` ${innerX.toFixed(1)} ${(top + quarter * 2).toFixed(1)}`;
        d += ` C ${innerX.toFixed(1)} ${(top + quarter * 3).toFixed(1)}`;
        d += ` ${current.x.toFixed(1)} ${(top + quarter * 3).toFixed(1)}`;
        d += ` ${current.x.toFixed(1)} ${bottom.toFixed(1)}`;
        previous = current;
      }

      d += ` L ${previous.x.toFixed(1)} ${height.toFixed(1)}`;
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      thread.setAttribute("d", d);
      outline.setAttribute("d", d);

      totalLength = thread.getTotalLength();
      if (!Number.isFinite(totalLength) || totalLength <= 0) return;
      const dash = `${totalLength} ${totalLength}`;
      thread.style.strokeDasharray = dash;
      outline.style.strokeDasharray = dash;

      // Campioniamo la corrispondenza y/lunghezza una sola volta al layout.
      // Durante lo scroll la ricerca binaria e' rapida, anche su mobile.
      const sampleCount = Math.ceil(totalLength / 7);
      sampleYs = new Array(sampleCount + 1);
      let lastY = 0;
      for (let i = 0; i <= sampleCount; i++) {
        const point = thread.getPointAtLength((i / sampleCount) * totalLength);
        lastY = Math.max(lastY, point.y);
        sampleYs[i] = lastY;
      }
    }

    function paint() {
      if (!home || !thread || !outline || !tip || !totalLength || sampleYs.length < 2) return;
      const bounds = home.getBoundingClientRect();
      const frontY = window.innerHeight * 0.76 - bounds.top;
      const full = reducedMotion.matches;
      const endIndex = sampleYs.length - 1;
      let distance = totalLength;

      if (!full) {
        let lo = 0;
        let hi = endIndex;
        while (lo < hi) {
          const mid = Math.ceil((lo + hi) / 2);
          if (sampleYs[mid] <= frontY) lo = mid;
          else hi = mid - 1;
        }
        const currentY = sampleYs[lo];
        const nextY = sampleYs[Math.min(lo + 1, endIndex)];
        const fraction = nextY > currentY ? clamp((frontY - currentY) / (nextY - currentY), 0, 1) : 0;
        distance = clamp(((lo + fraction) / endIndex) * totalLength, 0, totalLength);
        if (frontY <= 0) distance = 0;
      }

      const offset = String(totalLength - distance);
      thread.style.strokeDashoffset = offset;
      outline.style.strokeDashoffset = offset;

      const showTip = !full && distance > 6 && distance < totalLength - 6;
      tip.style.opacity = showTip ? "1" : "0";
      if (showTip) {
        const point = thread.getPointAtLength(distance);
        tip.setAttribute("transform", `translate(${point.x} ${point.y})`);
      }
    }

    function tick() {
      frame = 0;
      if (recalculate) {
        layout();
        recalculate = false;
      }
      paint();
    }

    function schedule() {
      if (!frame) frame = window.requestAnimationFrame(tick);
    }

    function refresh() {
      recalculate = true;
      schedule();
    }

    const observer = new ResizeObserver(refresh);
    observer.observe(home);
    sections.forEach((section) => {
      observer.observe(section);
      const card = section.querySelector(".landing-content");
      if (card) observer.observe(card);
    });

    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", refresh);
    window.addEventListener("pageshow", refresh);
    reducedMotion.addEventListener("change", schedule);
    document.fonts?.ready.then(() => { if (active) refresh(); });
    schedule();

    return () => {
      active = false;
      window.cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", refresh);
      window.removeEventListener("pageshow", refresh);
      reducedMotion.removeEventListener("change", schedule);
    };
  }, []);

  return (
    <svg ref={svgRef} className="home-line-art" aria-hidden="true" focusable="false" preserveAspectRatio="none">
      <path ref={outlineRef} className="home-line-art__outline" />
      <path ref={threadRef} className="home-line-art__stroke" />
      <g ref={tipRef} className="home-line-art__tip" opacity="0">
        <circle className="home-line-art__tip-glow" r="8" />
        <circle className="home-line-art__tip-core" r="3.6" />
      </g>
    </svg>
  );
}
