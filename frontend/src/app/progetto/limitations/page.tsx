import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Limitations | FIELDWISE" };

const limitations = [
  { category: "WATER & WEATHER", title: "Simplified soil hydrology", detail: "The daily two-layer bucket model cannot describe hourly storms, standing water, surface crusting, shallow groundwater or upward capillary flow." },
  { category: "SOIL PROCESSES", title: "Incomplete carbon & nitrogen dynamics", detail: "Humus excludes below-ground root carbon; decomposition uses simplified rates, while nitrogen leaching is calculated over an averaged water volume. Key processes lack direct local validation." },
  { category: "CROP PHYSIOLOGY", title: "Partial stress representation", detail: "NDVI is used for retrospective comparison, not real-time crop-health diagnosis. Flowering heat damage uses air, not leaf, temperature; disease and waterlogging are not explicitly modelled." },
  { category: "GEOGRAPHY", title: "Transferability is not established", detail: "The core pilot is Cremona. Weather is spatially coarse and the model assumes flat terrain and simplified atmospheric conditions. Hilly fields need additional treatment." },
  { category: "CROP COVERAGE", title: "A restricted crop catalogue", detail: "Only maize, soybean and soft wheat are represented as main crops, with optional rye cover. Perennial forages, rice and other important crops need new modelling work." },
  { category: "ECONOMICS", title: "Partial costs, fixed prices", detail: "Wholesale prices and broad crop costs do not capture contracts, equipment depreciation, land rent, CAP support, insurance, market swings or individual farm accounts." },
];

export default function LimitationsPage() {
  return (
    <ProjectChapter slug="limitations">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>WHAT THE PROTOTYPE DOES NOT KNOW</span>
          <h2>Every recommendation is conditional on its assumptions.</h2>
          <p>
            FIELDWISE is designed for transparent scenario comparisons, not certified field-level
            prescriptions. The technical report identifies these boundaries so that farmers and
            advisers know where observations or expert judgement must take priority.
          </p>
        </section>
        <div className={styles.projectCompactGrid}>
          {limitations.map((item) => (
            <article className={styles.projectCompactItem} key={item.title}>
              <span className={styles.projectKicker}>{item.category}</span>
              <h3>{item.title}</h3><p>{item.detail}</p>
            </article>
          ))}
        </div>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>LIMITS OF THE OBSERVATIONAL EVIDENCE</span>
          <h2>Agreement in one indicator is not validation of the whole system.</h2>
          <p>
            SMAP only samples near-surface moisture; MODIS NDVI represents a mixed-vegetation
            extraction area; ISTAT provides provincial, not individual-field, yield data. Soybean
            and wheat results do not establish reliable yield simulation. Nitrogen losses,
            humus trends and rotation recommendations lack field-scale independent tests.
          </p>
          <p>
            Rankings also change under uncertain parameters: the baseline top rotation remained
            first in just 11.7% of the report's 256 Monte Carlo samples. Results should therefore
            be interpreted as candidate options for further assessment rather than optimal
            solutions guaranteed to work in practice.
          </p>
        </section>
        <aside className={styles.projectNotice}>
          <strong>Before acting on an output</strong>
          <p>
            Check local soil conditions, farm records, current regulations, input availability,
            market contracts and financing requirements with a qualified agronomist or adviser.
            The model's economic margin is not the farm's total profit.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
