import type { Metadata } from "next";
import ProjectChapter from "../../../components/project/ProjectChapter";

export const metadata: Metadata = { title: "Analytical Framework | FIELDWISE" };

export default function Page() {
  // Add this chapter's content as children of ProjectChapter when it is ready.
  return <ProjectChapter slug="analytical-framework" />;
}
