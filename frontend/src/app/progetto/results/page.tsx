import type { Metadata } from "next";
import Image from "next/image";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Results & Validation | FIELDWISE" };

const findings = [
  {
    value: "r ≈ 0.70", label: "Surface soil moisture", detail: "92 monthly SMAP/model pairs, 2015–2022. The 95% confidence interval remained above 0.58.",
  },
  {
    value: "r = 0.60", label: "Maize water stress", detail: "MODIS summer NDVI versus modelled maize stress, 22 paired years (95% CI: 0.25–0.82).",
  },
  {
    value: "r = 0.70", label: "Maize yield variability", detail: "Detrended provincial ISTAT versus simulated maize yield under capped irrigation, 2006–2022 (95% CI: 0.33–0.88).",
  },
];
const caveats = [
  { title: "Soybean & wheat", detail: "Soybean yield evidence was inconclusive; wheat yield correlation was negative (r = −0.50), pointing to missing drivers such as disease and waterlogging." },
  { title: "Evapotranspiration", detail: "ECOSTRESS matched the seasonal pattern (r = 0.77 in the growing season) but the model overestimated growing-season ET by 1.61 mm/day under capped irrigation." },
  { title: "Soil processes", detail: "Observations do not independently validate the complete root-zone water balance, humus, nitrogen cycling, leaching or crop-sequence effects." },
];
const charts = [
  { src: "/project/figures/smap-soil-moisture.webp", width: 1430, height: 585, title: "Observed vs simulated surface moisture", caption: "Report Figure 5.1 · Monthly SMAP and model moisture anomalies, 2015–2022." },
  { src: "/project/figures/modis-maize-stress.webp", width: 1430, height: 598, title: "Vegetation and maize water stress", caption: "Report Figure 5.2 · MODIS NDVI versus simulated maize water factors, 2001–2022." },
  { src: "/project/figures/istat-crop-yields.webp", width: 1600, height: 542, title: "Crop yield comparisons", caption: "Report Figure 5.3 · Detrended ISTAT yields versus model results, 2006–2022." },
  { src: "/project/figures/ranking-stability.webp", width: 1040, height: 520, title: "How much does the ranking change?", caption: "Report Figure 5.4 · Rank correlation in 256 Monte Carlo samples." },
];

export default function ResultsPage() {
  return (
    <ProjectChapter slug="results">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>CREMONA PILOT / INDEPENDENT COMPARISONS</span>
          <h2>Promising agreement in selected processes, not a blanket validation.</h2>
          <p>
            The pilot was evaluated against satellite observations and provincial statistics without
            calibrating its model parameters to these comparisons. Correlations describe agreement
            in variability, not guaranteed accuracy for an individual farmer or crop rotation.
          </p>
        </section>
        <div className={styles.projectSourceGrid}>
          {findings.map((finding) => (
            <article className={styles.projectSourceCard} key={finding.label}>
              <span>OBSERVED ASSOCIATION</span>
              <div className={styles.projectBigNumber}>{finding.value}</div>
              <h3>{finding.label}</h3><p>{finding.detail}</p>
            </article>
          ))}
        </div>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>STABILITY UNDER UNCERTAINTY</span>
          <h2>One optimum is not the whole story.</h2>
          <div className={styles.projectMetrics}>
            <div><strong>11.7%</strong><span>Monte Carlo runs retaining the same top rotation</span></div>
            <div><strong>256</strong><span>Monte Carlo samples across uncertain parameters</span></div>
            <div><strong>0.581</strong><span>Median Kendall rank correlation</span></div>
          </div>
          <p>
            In 179 one-at-a-time parameter tests (±30%), nine parameters changed the top-ranked
            rotation under capped irrigation. Continuous maize remained in the bottom quarter in
            51.2% of capped-irrigation samples and 86.7% of rainfed samples. The broad diagnosis
            is more stable than the exact order of competing alternatives.
          </p>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>WHERE VALIDATION IS INCOMPLETE</span>
          <h2>Important discrepancies.</h2>
          <div className={styles.projectCompactGrid}>
            {caveats.map((item) => (
              <article className={styles.projectCompactItem} key={item.title}><h3>{item.title}</h3><p>{item.detail}</p></article>
            ))}
          </div>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>FIGURES FROM THE ORIGINAL REPORT</span>
          <h2>The evidence, in context.</h2>
          <div className={styles.projectFigureGrid}>
            {charts.map((chart) => (
              <figure className={styles.projectFigure} key={chart.src}>
                <div className={styles.projectFigureImage}>
                  <Image src={chart.src} width={chart.width} height={chart.height} alt={chart.title} />
                </div>
                <figcaption><strong>{chart.title}</strong><span>{chart.caption}</span></figcaption>
              </figure>
            ))}
          </div>
        </section>
        <aside className={styles.projectNotice}>
          <strong>How to read these numbers</strong>
          <p>
            Correlation is not a measure of causal accuracy. SMAP senses approximately 0–5 cm of
            surface soil, the MODIS extraction covers mixed vegetation, and ISTAT yields aggregate
            many fields. These checks do not validate personalised recommendations outside Cremona.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
