import Analysis from "../../../views/Analysis";

type Props = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ from?: string; selected?: string }>;
};

export default async function AnalizzaCampoPage({ params, searchParams }: Props) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  // Only show the contextual back link when this page was opened from the
  // multi-field selection. Keep its chosen field IDs in the return URL.
  const returnToMultipleHref = query.from === "multiple"
    ? `/analizza/tutti?selected=${encodeURIComponent(query.selected ?? "")}#select-fields-heading`
    : undefined;
  return <Analysis key={id} fieldId={id} returnToMultipleHref={returnToMultipleHref} />;
}
