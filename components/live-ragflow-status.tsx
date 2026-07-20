"use client";

import { useEffect, useState } from "react";

type Dataset = {
  id: string;
  name: string;
  documentCount: number;
  chunkCount: number;
};

export function LiveRagflowStatus() {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [state, setState] = useState<"loading" | "ready" | "offline" | "personal">("loading");

  useEffect(() => {
    fetch("/api/ragflow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "overview" })
    })
      .then(async response => {
        const data = await response.json();
        if (!response.ok || data.ok === false) throw new Error(data.message || "offline");
        setDatasets(data.datasets || []);
        setState(data.managed ? "ready" : "personal");
      })
      .catch(() => setState("offline"));
  }, []);

  if (state === "loading") return <div className="status-box">正在读取实时 RAGFlow 状态...</div>;
  if (state === "personal") return <div className="status-box">当前使用个人连接，实时数据请在“连接与导入”中查看。</div>;
  if (state === "offline") return <div className="status-box error">实时 RAGFlow 暂时离线；下方 GitHub 快照仍可正常查看。</div>;

  const documents = datasets.reduce((sum, item) => sum + item.documentCount, 0);
  const chunks = datasets.reduce((sum, item) => sum + item.chunkCount, 0);
  return <>
    <div className="status-box ok">实时 RAGFlow 已连接</div>
    <div className="metric-grid">
      <div className="metric"><strong>{datasets.length}</strong><span>实时知识库</span></div>
      <div className="metric"><strong>{documents}</strong><span>实时文档</span></div>
      <div className="metric"><strong>{chunks}</strong><span>实时分块</span></div>
    </div>
  </>;
}
