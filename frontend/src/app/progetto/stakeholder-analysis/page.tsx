import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";
import styles from "../../../styles/project.module.css";

export const metadata: Metadata = { title: "Economics & Stakeholders | FIELDWISE" };

const actors = [
  { title: "Farmers & managers", text: "Set objectives and decide whether a rotation is feasible under actual field, labour and equipment constraints." },
  { title: "Agronomists & advisers", text: "Interpret soil, crop and regulatory assumptions before a simulated alternative becomes a management decision." },
  { title: "Cooperatives & buyers", text: "Determine market access, delivery conditions and whether production can be sold on viable terms." },
  { title: "Suppliers & service providers", text: "Provide the seeds, equipment, inputs and services needed to implement a change." },
  { title: "Public institutions", text: "Shape compliance requirements and support measures, including CAP and regional programmes." },
  { title: "Lenders, insurers & landowners", text: "Become important where a transition entails investment, financing, risk cover or contractual changes." },
];

export default function StakeholdersPage() {
  return (
    <ProjectChapter slug="stakeholder-analysis">
      <div className={styles.projectEditorial}>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>FROM SIMULATION TO FARM VALUE</span>
          <h2>Less resource use is valuable only if the whole decision makes sense.</h2>
          <p>
            FIELDWISE converts simulated yields and selected variable input requirements into an
            <strong> annualised partial margin (€/ha/year)</strong>. It helps compare scenarios on a
            common basis, but it is not a full business profit forecast. Lower water or nitrogen
            requirements do not automatically mean higher net income.
          </p>
          <div className={styles.projectEquation}>
            <span>MODELLED PARTIAL MARGIN / €/HA/YEAR</span>
            <strong>Crop revenue − nitrogen cost − irrigation cost − other crop costs</strong>
            <small>Excludes rents, CAP payments, capital investments and general farm overheads.</small>
          </div>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>PEOPLE IN THE DECISION</span>
          <h2>Who turns a scenario into a change?</h2>
          <div className={styles.projectCompactGrid}>
            {actors.map((actor) => (
              <article className={styles.projectCompactItem} key={actor.title}><h3>{actor.title}</h3><p>{actor.text}</p></article>
            ))}
          </div>
        </section>
        <section className={styles.projectTextSection}>
          <span className={styles.projectKicker}>POSSIBLE SERVICE MODEL / NOT YET PROVEN</span>
          <h2>Start with advisers and practical trials.</h2>
          <div className={styles.projectSteps}>
            <div className={styles.projectStep}><span>01</span><div><h3>Test with farms</h3><p>Ask farmers and advisers whether outputs are understandable, actionable and worth the effort.</p></div></div>
            <div className={styles.projectStep}><span>02</span><div><h3>Support organisations</h3><p>Consultancies and cooperatives could use repeatable scenario comparisons across their clients.</p></div></div>
            <div className={styles.projectStep}><span>03</span><div><h3>Explore pricing</h3><p>Consider basic access for farmers and paid organisational services, training or integration.</p></div></div>
            <div className={styles.projectStep}><span>04</span><div><h3>Validate viability</h3><p>Compare willingness to pay with ongoing software, hosting, data, agronomy and support costs.</p></div></div>
          </div>
        </section>
        <aside className={styles.projectNotice}>
          <strong>Potential value, not demonstrated savings</strong>
          <p>
            No farm-level cost saving, profitability gain or sustainable revenue model has yet been
            demonstrated. Adoption depends on equipment, markets, regulation, agronomic advice
            and whether the tool changes real decisions.
          </p>
        </aside>
      </div>
    </ProjectChapter>
  );
}
