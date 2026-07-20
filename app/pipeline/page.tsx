import fs from "node:fs";
import path from "node:path";
import { LiveRagflowStatus } from "@/components/live-ragflow-status";

export const dynamic = "force-static";

export default function PipelinePage() {
  const manifest=JSON.parse(fs.readFileSync(path.join(process.cwd(),"knowledge_base","manifest.json"),"utf8"));
  return <main className="page"><section className="panel"><h1>数据流程看板</h1><p className="lede">实时 RAGFlow 运行状态与当前 GitHub 版本知识库快照。</p>
    <h3>实时运行状态</h3><LiveRagflowStatus/>
    <h3>GitHub 数据快照</h3>
    <div className="metric-grid"><div className="metric"><strong>{manifest.dataset_count}</strong><span>知识库</span></div><div className="metric"><strong>{manifest.document_count}</strong><span>文档</span></div><div className="metric"><strong>{manifest.chunk_count}</strong><span>文本分块</span></div><div className="metric"><strong>{manifest.image_chunk_count}</strong><span>图片分块</span></div></div>
    <h3>知识库版本</h3><div className="dataset-list">{manifest.datasets.map((item:{id:string;name:string;documents:number;chunks:number;image_chunks:number})=><div className="dataset-row" key={item.id}><span><strong>{item.name}</strong><br/><span className="muted">{item.chunks} 个分块 · {item.image_chunks} 个图片块</span></span><span>{item.documents} 份文档</span></div>)}</div>
    <h3>处理流程</h3><ol className="steps"><li>暨南大学公开网站增量采集</li><li>正文、附件和元数据清洗</li><li>MinerU 图文表格结构化解析</li><li>服务卡片与视觉描述生成</li><li>RAGFlow 上传、分块与解析</li><li>召回测试、阈值调整与拒答验证</li></ol>
  </section></main>;
}
