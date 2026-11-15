/** Project chapters follow the completed FIELDWISE 2026 technical report. */
export type ProjectSection = {
  slug: string;
  title: string;
  navLabel: string;
  number: string;
  description: string;
};

export const projectSections: readonly ProjectSection[] = [
  {
    slug: "analytical-framework", title: "Analytical Framework", navLabel: "Framework", number: "02",
    description: "The farmer's decision: compare crop rotations across production, risk, resources, soil and partial margins.",
  },
  {
    slug: "data-and-processing", title: "Data & Processing", navLabel: "Data", number: "03",
    description: "NASA weather, soil properties and independent observations: where the inputs come from and what they can tell us.",
  },
  {
    slug: "methodology-and-engine", title: "Methodology & Engine", navLabel: "Engine", number: "04",
    description: "A transparent daily crop, water, nitrogen and humus simulation with comparable irrigation scenarios.",
  },
  {
    slug: "results", title: "Results & Validation", navLabel: "Results", number: "05",
    description: "What the Cremona pilot validation supports, where results diverge and how stable the rankings are.",
  },
  {
    slug: "stakeholder-analysis", title: "Economics & Stakeholders", navLabel: "Stakeholders", number: "06",
    description: "How partial-margin comparisons could support farmers, advisers and agricultural organisations.",
  },
  {
    slug: "scalability-and-future-development", title: "Future Development", navLabel: "Future", number: "07",
    description: "Climate stress testing, additional crops, geographic transfer and the evidence needed for expansion.",
  },
  {
    slug: "limitations", title: "Limitations", navLabel: "Limits", number: "08",
    description: "Important physical, agronomic, economic and geographic boundaries of the current prototype.",
  },
  {
    slug: "conclusions", title: "Conclusions", navLabel: "Conclusions", number: "09",
    description: "The contribution, the findings and the next steps towards reliable agricultural decision support.",
  },
  {
    slug: "sources", title: "Data & References", navLabel: "Sources", number: "10",
    description: "A guide to the datasets, measurement products and scientific methods identified in the report.",
  },
] as const;

export const PROJECT_TOTAL_CHAPTERS = projectSections.length + 1;

export function projectSectionBySlug(slug: string): ProjectSection | undefined {
  return projectSections.find((section) => section.slug === slug);
}
