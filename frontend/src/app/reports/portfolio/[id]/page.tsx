import PortfolioViewer from "../../../../components/portfolio/PortfolioViewer";
export default async function PortfolioReportPage({params}:{params:Promise<{id:string}>}) {
  const {id}=await params;
  return <PortfolioViewer portfolioId={id}/>;
}
