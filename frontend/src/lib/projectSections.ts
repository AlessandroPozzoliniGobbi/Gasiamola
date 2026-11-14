/** Single source of truth for the Project chapter navigation and draft outlines. */
export type ProjectSection = {
  slug: string;
  title: string;
  number: string;
  description: string;
  topics: readonly string[];
};

export const projectSections: readonly ProjectSection[] = [
  {
    slug: "analytical-framework",
    title: "Analytical Framework",
    number: "01",
    description: "How we turn an agricultural question into a structured comparison of possible decisions.",
    topics: ["Research questions", "Decision criteria and indicators", "Comparing crop rotations"],
  },
  {
    slug: "data-and-processing",
    title: "Data & Processing",
    number: "02",
    description: "Our data sources, preparation workflow, quality checks, and approach to reproducibility.",
    topics: ["Data sources", "Cleaning and preparation", "Quality control and traceability"],
  },
  {
    slug: "methodology-and-engine",
    title: "Methodology & Engine",
    number: "03",
    description: "The scientific methodology behind the model and the way the simulation engine is organized.",
    topics: ["Water, nitrogen, and soil organic matter", "Simulation scenarios", "Engine architecture and assumptions"],
  },
  {
    slug: "results",
    title: "Results",
    number: "04",
    description: "A home for simulation outputs, visual comparisons, and evidence supporting the recommendations.",
    topics: ["Key findings", "Comparative charts and tables", "Interpreting the recommendations"],
  },
  {
    slug: "stakeholder-analysis",
    title: "Stakeholder Analysis",
    number: "05",
    description: "Who could use FIELDWISE, what they need from it, and where the tool could create value.",
    topics: ["Stakeholder groups", "Needs and expectations", "Potential use cases and impact"],
  },
  {
    slug: "limitations",
    title: "Limitations",
    number: "06",
    description: "Where our model is uncertain, what it does not represent, and how we plan to improve it.",
    topics: ["Spatial and data limitations", "Model uncertainty", "Future improvements"],
  },
  {
    slug: "sources",
    title: "Sources",
    number: "07",
    description: "Scientific publications, official datasets, and technical references used in the project.",
    topics: ["NASA and Earth observation datasets", "Scientific literature", "Official standards and documentation"],
  },
] as const;

export function projectSectionBySlug(slug: string): ProjectSection | undefined {
  return projectSections.find((section) => section.slug === slug);
}
