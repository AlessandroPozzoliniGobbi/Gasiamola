import ReportViewer from "../../../components/reports/ReportViewer";
export default async function SavedReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportViewer reportId={id} />;
}
