import { redirect } from "next/navigation";

/** Legacy V7 chapter: Introduction is now merged into Project Overview. */
export default function IntroductionRedirect() {
  redirect("/progetto");
}
