import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Data & References | FIELDWISE" };

const categories = [
  {
    title: "Primary inputs", items: [
      { name: "NASA POWER", detail: "Daily temperature, rainfall, radiation, humidity and wind for the crop simulation." },
      { name: "SoilGrids 2.0 (ISRIC)", detail: "Depth-resolved spatial soil-property predictions used to estimate hydraulic parameters." },
      { name: "ERSAF regional material", detail: "Organic-matter reference for the upper 0–30 cm in the Cremona pilot." },
    ],
  },
  {
    title: "Checks & independent comparisons", items: [
      { name: "ARPA Lombardia", detail: "Ground-station precipitation and temperature comparisons." },
      { name: "GPM IMERG Final Daily V07", detail: "Alternative daily precipitation estimates for sensitivity analysis." },
      { name: "SMAP SPL3SMP_E V006", detail: "Monthly comparison of near-surface soil moisture." },
      { name: "MODIS MOD13Q1", detail: "NDVI comparison with simulated maize water stress." },
      { name: "ISTAT", detail: "Annual provincial statistics for crop-yield variability." },
      { name: "ECOSTRESS", detail: "Exploratory seasonal evapotranspiration comparison." },
    ],
  },
  {
    title: "Methods named in the report", items: [
      { name: "FAO-56 / Allen et al. (1998)", detail: "Reference evapotranspiration and dual crop-coefficient framework." },
      { name: "FAO-33 / Doorenbos & Kassam (1979)", detail: "Yield response to water deficits." },
      { name: "Saxton–Rawls", detail: "Pedotransfer relationships for water-retention and conductivity estimates." },
      { name: "Simon (1955)", detail: "Bounded rationality, used in the agricultural decision framework." },
      { name: "Masseroni et al. (2024); Cui et al. (2018)", detail: "Agricultural efficiency examples discussed in the problem definition." },
    ],
  },
];

export default function SourcesPage() {
  return (
    <ProjectChapter slug="sources">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>REPORT PROVENANCE</span>
          <h2>What informs the model, and what evaluates it.</h2>
          <p>
            The technical report separates environmental inputs from observations used to evaluate
            the simulation. The list below follows its dataset names and methodological references;
            it is a summary rather than a newly verified bibliography.
          </p>
        </section>
        {categories.map((category) => (
          <section className={styles.projectTextSection} key={category.title}>
            <h2>{category.title}</h2>
            <div className={styles.projectCompactGrid}>
              {category.items.map((item) => (
                <article className={styles.projectCompactItem} key={item.name}>
                  <h3>{item.name}</h3><p>{item.detail}</p>
                </article>
              ))}
            </div>
          </section>
        ))}
        <aside className={styles.projectNotice}>
          <strong>Research status</strong>
          <p>
            The report identifies Sentinel-2, Landsat, GAEZ and related remote-sensing products as
            exploratory, not baseline inputs. Some claims and coefficients are literature-based and
            require local validation before broader deployment. See the full PDF for the original
            context, figures and qualifications.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
