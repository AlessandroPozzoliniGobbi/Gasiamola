import ReportDashboard from "../../../components/reports/ReportDashboard";
import { createDemoReport } from "../../../lib/reportDemo";
export default function DemoReportPreview() { return <ReportDashboard report={createDemoReport()} demo />; }
