"use client";

import { Clock3, MessageSquareText } from "lucide-react";
import { useEffect, useState } from "react";

type ConversationSummary = { id: string; title: string; updatedAt: string; messageCount: number };

export default function HistoryPage() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  useEffect(() => {
    fetch("/api/conversations").then(response => response.json()).then(data => setItems(data.conversations || [])).catch(() => setItems([]));
  }, []);
  return <main className="page"><section className="panel">
    <h1>历史记录</h1>
    <p className="lede">这里展示服务器保存的多轮对话。每条对话都保留用户问题、助手回答和 Agent 执行过程。</p>
    {!items.length ? <div className="empty-state"><Clock3 size={34} /><strong>暂无历史对话</strong><span>在智能问答页开始咨询后，会话会自动保存到这里。</span></div> : <div className="dataset-list">
      {items.map(item => <div className="dataset-row" key={item.id}><span><strong><MessageSquareText size={15}/> {item.title}</strong><br/><span className="muted">{new Date(item.updatedAt).toLocaleString()}</span></span><span>{item.messageCount} 条消息</span></div>)}
    </div>}
  </section></main>;
}
