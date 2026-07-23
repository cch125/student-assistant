import Link from "next/link";
import { promises as fs } from "node:fs";
import path from "node:path";
import { FileText } from "lucide-react";

type Snapshot = { id: string; name: string; documents: number; chunks: number };

async function countSnapshotDocs(): Promise<Snapshot[]> {
  try {
    const manifest = JSON.parse(await fs.readFile(path.join(process.cwd(), "knowledge_base", "manifest.json"), "utf8"));
    return (manifest.datasets || []).map((item: Record<string, unknown>): Snapshot => ({
      id: String(item.id || ""),
      name: String(item.name || "知识库快照"),
      documents: Number(item.documents || 0),
      chunks: Number(item.chunks || 0)
    }));
  } catch {
    return [] as Snapshot[];
  }
}

export default async function DocumentsPage() {
  const snapshots = await countSnapshotDocs();
  return <main className="page"><section className="panel">
    <h1>文档管理</h1>
    <p className="lede">这里展示项目内置知识库快照。需要实时上传、解析和导入 RAGFlow 时，请进入连接与导入。</p>
    <div className="document-list">
      {snapshots.map(item => <div className="document-row" key={item.id}><span><FileText size={16} /> {item.name}</span><span>{item.documents} 文档 · {item.chunks} 分块</span></div>)}
      {!snapshots.length && <div className="empty-state"><FileText size={34} /><strong>暂无快照</strong><span>请先导出或导入知识库快照。</span></div>}
    </div>
    <div className="actions"><Link className="button" href="/settings">连接与导入</Link><Link className="button secondary" href="/pipeline">查看数据看板</Link></div>
  </section></main>;
}
