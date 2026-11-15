import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Data & Processing | FIELDWISE" };

const drivingSources = [
  { name: "NASA POWER", role: "Daily weather forcing", detail: "Temperature, rainfall, solar radiation, relative humidity and wind; atmospheric grid approximately 0.5° × 0.625° (solar 1° × 1°)." },
  { name: "SoilGrids 2.0", role: "Soil profile", detail: "Predicted soil properties at 250 m and at several depths; hydraulic characteristics are derived from these properties, not directly measured." },
  { name: "ERSAF regional sources", role: "Topsoil organic matter", detail: "Regional reference value of 2.33% for 0–30 cm in the Cremona baseline; an approximately 3.56% SoilGrids alternative is used for sensitivity testing." },
];
const validationSources = [
  { name: "ARPA Lombardia", role: "Precipitation and temperature quality checks" },
  { name: "GPM IMERG Final V07", role: "Independent-style precipitation sensitivity comparison (gauge-adjusted)" },
  { name: "SMAP SPL3SMP_E V006", role: "Monthly surface-soil-moisture comparison (9 km product)" },
  { name: "MODIS MOD13Q1", role: "16-day NDVI composites (250 m), compared with maize water stress" },
  { name: "ISTAT", role: "Annual provincial crop yields, used to assess simulated variability" },
  { name: "ECOSTRESS", role: "Exploratory evapotranspiration comparison, reported in validation results" },
];

export default function DataPage() {
  return (
    <ProjectChapter slug="data-and-processing">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>INPUTS / OBSERVATIONS / CHECKS</span>
          <h2>Different sources play different roles.</h2>
          <p>
            The physical simulation uses NASA POWER weather and a configured soil profile.
            Station measurements, satellite products and regional statistics are primarily used
            to check inputs or assess selected processes. Their different spatial resolutions must
            not be mistaken for field-level measurements.
          </p>
        </section>
        <div className={styles.projectSourceGrid}>
          {drivingSources.map((source) => (
            <article className={styles.projectSourceCard} key={source.name}>
              <span>MODEL INPUT</span>
              <h3>{source.name}</h3>
              <strong>{source.role}</strong>
              <p>{source.detail}</p>
            </article>
          ))}
        </div>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>EXTERNAL COMPARISONS</span>
          <h2>Checks, not extra precision.</h2>
          <div className={styles.projectCompactGrid}>
            {validationSources.map((source) => (
              <div className={styles.projectCompactItem} key={source.name}>
                <h3>{source.name}</h3><p>{source.role}</p>
              </div>
            ))}
          </div>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>DATA QUALITY & TIME WINDOW</span>
          <h2>Why the reference ensemble stops in 2022.</h2>
          <div className={styles.projectMetrics}>
            <div><strong>2000–2025</strong><span>Meteorological archive assembled</span></div>
            <div><strong>2000–2022</strong><span>Quality-checked reference weather</span></div>
            <div><strong>2000–2016</strong><span>17 successful starting years after warm-up</span></div>
          </div>
          <p>
            POWER rainfall diverged more strongly from ground records in 2023–2025, so those years
            were excluded from the baseline ensemble. IMERG precipitation was retained for
            sensitivity tests; its rain-gauge adjustment means the products are not fully independent.
            A complete initial rotation is simulated before evaluating subsequent outcomes.
          </p>
        </section>
        <aside className={styles.projectNotice}>
          <strong>What is measured versus estimated?</strong>
          <p>
            Soil water retention, evapotranspiration, growing degree-days and crop yields are model
            quantities. SMAP observes only near-surface moisture; provincial ISTAT statistics do not
            measure a particular field. A 250 m soil map does not make coarse-grid weather field-specific.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
