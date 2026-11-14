import Analysis from "../../../views/Analysis";

type Props = { params: Promise<{ id: string }> };

export default async function AnalizzaCampoPage({ params }: Props) {
  const { id } = await params;
  return <Analysis key={id} fieldId={id} />;
}
