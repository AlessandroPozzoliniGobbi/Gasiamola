import PortfolioFieldViewer from "../../../../../../components/portfolio/PortfolioFieldViewer";
export default async function PortfolioFieldPage({params}:{params:Promise<{id:string;reportId:string}>}){
  const {id,reportId}=await params;
  return <PortfolioFieldViewer portfolioId={id} reportId={reportId}/>;
}
