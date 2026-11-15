/** Single source of truth for the Project chapter navigation and draft outlines. */
export type ProjectSection = {
  slug: string;
  title: string;
  navLabel: string;
  number: string;
  description: string;
  topics: readonly string[];
};

export const projectSections: readonly ProjectSection[] = [
  {
    slug: "analytical-framework",
    title: "Analytical Framework",
    navLabel: "Framework",
    number: "02",
    description: "How crop-rotation choices are compared across yields, risks, resources, soil and economics.",
    topics: ["Research questions", "Decision criteria and indicators", "Comparing crop rotations"],
  },
  {
    slug: "data-and-processing",
    title: "Data & Processing",
    navLabel: "Data",
    number: "03",
    description: "The environmental data behind the model, how sources are checked and what they can measure.",
    topics: ["Data sources", "Cleaning and preparation", "Quality control and traceability"],
  },
  {
    slug: "methodology-and-engine",
    title: "Methodology & Engine",
    navLabel: "Engine",
    number: "04",
    description: "How daily crop, water, nitrogen and soil simulations lead to comparative recommendations.",
    topics: ["Water, nitrogen, and soil organic matter", "Simulation scenarios", "Engine architecture and assumptions"],
  },
  {
    slug: "results",
    title: "Results",
    navLabel: "Results",
    number: "05",
    description: "A home for simulation outputs, visual comparisons, and evidence supporting the recommendations.",
    topics: ["Key findings", "Comparative charts and tables", "Interpreting the recommendations"],
  },
  {
    slug: "stakeholder-analysis",
    title: "Stakeholder Analysis",
    navLabel: "Stakeholders",
    number: "06",
    description: "Who could use FIELDWISE, what they need from it, and where the tool could create value.",
    topics: ["Stakeholder groups", "Needs and expectations", "Potential use cases and impact"],
  },
  {
    slug: "scalability-and-future-development",
    title: "Scalability & Future Development",
    navLabel: "Scalability",
    number: "07",
    description: "How FIELDWISE could grow from a regional pilot to a more widely usable decision-support tool.",
    topics: ["Geographic expansion", "Data and computation at scale", "Validation and adoption"],
  },
  {
    slug: "limitations",
    title: "Limitations",
    navLabel: "Limits",
    number: "08",
    description: "Where our model is uncertain, what it does not represent, and how we plan to improve it.",
    topics: ["Spatial and data limitations", "Model uncertainty", "Future improvements"],
  },
  {
    slug: "sources",
    title: "Sources",
    navLabel: "Sources",
    number: "09",
    description: "Scientific publications, official datasets, and technical references used in the project.",
    topics: ["NASA and Earth observation datasets", "Scientific literature", "Official standards and documentation"],
  },
] as const;

export function projectSectionBySlug(slug: string): ProjectSection | undefined {
  return projectSections.find((section) => section.slug === slug);
}
