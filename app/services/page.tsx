import { promises as fs } from "node:fs";
import path from "node:path";
import { ExternalLink } from "lucide-react";

function field(content: string, name: string): string {
  return content.match(new RegExp(`(?:^|\\n)${name}：\\s*([\\s\\S]*?)(?=\\n[^\\n：]{1,24}：|$)`))?.[1]?.replace(/\s+/g, " ").trim() || "";
}

async function loadCards() {
  const directory = path.join(process.cwd(), "data", "cleaned", "service_cards");
  const names = await fs.readdir(directory);
  const cards = [];
  for (const name of names.filter(item => item.endsWith(".md")).sort()) {
    const content = await fs.readFile(path.join(directory, name), "utf8");
    cards.push({
      name: name.replace(/\.md$/i, ""),
      category: field(content, "类别") || "学生事务",
      department: field(content, "负责部门") || "学校相关部门",
      audience: field(content, "适用对象") || "暨南大学学生",
      answer: field(content, "直接回答"),
      sourceUrl: field(content, "来源链接") || content.match(/https?:\/\/[^\s)）]+/)?.[0] || ""
    });
  }
  return cards;
}

export default async function ServicesPage() {
  const cards = await loadCards();
  return <main className="page"><section className="panel">
    <h1>服务卡片</h1>
    <p className="lede">核心学生事务已经整理为结构化卡片，适合演示模式、直达链接和高置信回答。</p>
    <div className="service-grid">
      {cards.map(card => <article className="service-card" key={card.name}>
        <div><strong>{card.name}</strong><span>{card.category}</span></div>
        <p>{card.answer || `${card.department} · ${card.audience}`}</p>
        <footer><span>{card.department}</span>{card.sourceUrl && <a href={card.sourceUrl} target="_blank" rel="noreferrer">来源 <ExternalLink size={13} /></a>}</footer>
      </article>)}
    </div>
  </section></main>;
}
