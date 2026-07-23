"use client";

import Link from "next/link";
import { Camera, CheckCircle2, ExternalLink, MessageSquarePlus, RefreshCw, Search, ShieldX, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { loadConnection } from "@/lib/connection";

type HarnessTrace = { node: string; status: "success" | "retry" | "rejected" | "error"; attempt: number; query: string; score?: number; detail: string; durationMs: number };
type Answer = { ok: boolean; mode?: "demo" | "ragflow" | "agent"; route?: string; answer: string; documentName?: string; similarity?: number; sourceUrl?: string; downloads?: { name: string; url: string }[]; matches?: { documentName: string; similarity: number; snippet: string }[]; harness?: { retries: number; finalQuery: string; reason: string; trace: HarnessTrace[] } };
type ChatMessage = { id: string; role: "user" | "assistant"; content: string; createdAt: string; meta?: Answer };
type ConversationSummary = { id: string; title: string; updatedAt: string; messageCount: number };
type Conversation = { id: string; title: string; messages: ChatMessage[] };

const nodeLabels: Record<string,string> = { intent_agent:"Intent Agent", llm_router:"LLM Router Agent", health_router:"Health Agent", llm_analyzer:"LLM Analyzer Agent", llm_reflection:"LLM Reflection Agent", tool_agent:"Tool Agent", guard_input:"Router Agent", retrieve_knowledge:"Retriever Agent", quality_check:"Reflection Agent", rewrite_query:"Rewrite Agent", generate_answer:"Analyzer / Tool Agent", reject:"Reject Agent" };

function localId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function api(path: string, init?: RequestInit) {
  const response = await fetch(path, init);
  const data = await response.json();
  if (!response.ok || data.ok === false) throw new Error(data.message || "请求失败");
  return data;
}

function AnswerDetails({ answer }: { answer: Answer }) {
  return <>
    {(answer.mode || answer.documentName || typeof answer.similarity === "number") && <div className="source">
      <span>{answer.mode === "demo" ? "演示知识库快照" : answer.mode === "ragflow" ? "RAGFlow 实时知识库" : "Agent 工具链"}{answer.route ? ` · ${answer.route}` : ""}{answer.documentName ? ` · ${answer.documentName}` : ""}{typeof answer.similarity === "number" ? ` · 相似度 ${Number(answer.similarity || 0).toFixed(3)}` : ""}</span>
      {answer.sourceUrl && <a href={answer.sourceUrl} target="_blank" rel="noreferrer">查看官方来源 <ExternalLink size={14}/></a>}
    </div>}
    {answer.downloads?.map(item => <a className="button secondary" key={item.url} href={item.url} target="_blank" rel="noreferrer">下载 {item.name} <ExternalLink size={14}/></a>)}
    {answer.harness && <details className="harness-trace">
      <summary>{answer.ok ? <CheckCircle2 size={16}/> : <ShieldX size={16}/>}执行过程 · {answer.harness.retries ? `重试 ${answer.harness.retries} 次` : "首次通过"}</summary>
      <div className="trace-list">{answer.harness.trace.map((item,index) => <div className={`trace-row ${item.status}`} key={`${item.node}-${index}`}>
        <span className="trace-icon">{item.status === "retry" ? <RefreshCw size={15}/> : item.status === "success" ? <CheckCircle2 size={15}/> : <ShieldX size={15}/>}</span>
        <div><strong>{nodeLabels[item.node] || item.node}</strong><small>第 {item.attempt + 1} 轮{typeof item.score === "number" ? ` · 分数 ${item.score.toFixed(3)}` : ""} · {item.durationMs} ms</small><p>{item.detail}</p>{item.node === "rewrite_query" && <code>{item.query}</code>}</div>
      </div>)}</div>
    </details>}
    {answer.matches?.slice(0,3).map((item,index) => <div className="match" key={`${item.documentName}-${index}`}><strong>{item.documentName} · {item.similarity.toFixed(3)}</strong><div>{item.snippet}</div></div>)}
  </>;
}

export default function AssistantPage() {
  const [question, setQuestion] = useState("");
  const [image, setImage] = useState<{ base64: string; mime: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [managed, setManaged] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const historyForAgent = useMemo(() => messages.slice(-8).map(item => ({ role: item.role, content: item.content })), [messages]);

  async function refreshConversations(selectedId = activeId) {
    const data = await api("/api/conversations");
    setConversations(data.conversations || []);
    if (selectedId) await loadConversation(selectedId);
    else if (data.conversations?.[0]?.id) await loadConversation(data.conversations[0].id);
  }

  async function loadConversation(id: string) {
    const data = await api(`/api/conversations?id=${encodeURIComponent(id)}`);
    if (!data.conversation) return;
    setActiveId(data.conversation.id);
    setMessages(data.conversation.messages || []);
  }

  async function newConversation() {
    const data = await api("/api/conversations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "create", title: "新对话" }) });
    setActiveId(data.conversation.id);
    setMessages([]);
    await refreshConversations(data.conversation.id);
  }

  async function removeConversation(id: string) {
    await api("/api/conversations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "delete", conversationId: id }) });
    if (id === activeId) {
      setActiveId("");
      setMessages([]);
    }
    await refreshConversations("");
  }

  useEffect(() => {
    const value = loadConnection();
    const personal = Boolean(value.baseUrl && value.apiKey && value.datasetId);
    setConfigured(personal);
    fetch("/api/ragflow", { method:"POST", headers:{ "Content-Type":"application/json" }, body:JSON.stringify({ action:"configuration" }) })
      .then(response => response.json())
      .then(data => { setManaged(Boolean(data.managed)); setConfigured(personal || Boolean(data.managed)); })
      .catch(() => {});
    refreshConversations("").catch(() => {});
  }, []);

  async function chooseImage(file?: File) {
    if (!file) return setImage(null);
    if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 4 * 1024 * 1024) {
      const content = "请选择不超过 4 MB 的 JPG、PNG 或 WebP 图片。";
      setMessages(current => current.concat({ id: localId(), role: "assistant", content, createdAt: new Date().toISOString(), meta: { ok:false, answer: content } }));
      return;
    }
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, 1280 / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    const value = canvas.toDataURL("image/jpeg", .78);
    setImage({ mime:"image/jpeg", base64:value.split(",", 2)[1] });
  }

  async function ask() {
    const text = question.trim();
    if (!text && !image) return;
    const connection = loadConnection();
    const userMessage: ChatMessage = { id: localId(), role: "user", content: text || "请识别这张图片", createdAt: new Date().toISOString() };
    setMessages(current => current.concat(userMessage));
    setQuestion("");
    setLoading(true);
    try {
      const response = await fetch("/api/ragflow", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body:JSON.stringify({ action:"ask", connection, question:text, messages: historyForAgent, conversationId: activeId, imageBase64:image?.base64 || "", imageMime:image?.mime || "" })
      });
      const answer = await response.json() as Answer;
      const assistantMessage: ChatMessage = { id: localId(), role:"assistant", content: answer.answer, createdAt: new Date().toISOString(), meta: answer };
      setMessages(current => current.concat(assistantMessage));
      const saved = await api("/api/conversations", {
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ action:"append", conversationId: activeId, messages: [
          { role:"user", content:userMessage.content },
          { role:"assistant", content:assistantMessage.content, meta: answer }
        ] })
      });
      setActiveId(saved.conversation.id);
      setMessages(saved.conversation.messages || []);
      await refreshConversations(saved.conversation.id);
      setImage(null);
    } catch {
      const content = "查询暂时失败，请稍后重试。";
      setMessages(current => current.concat({ id: localId(), role:"assistant", content, createdAt: new Date().toISOString(), meta:{ ok:false, answer:content } }));
    } finally {
      setLoading(false);
    }
  }

  return <main className="page wide-page"><div className="chat-layout">
    <aside className="panel conversation-panel">
      <button className="button full-button" onClick={newConversation}><MessageSquarePlus size={17}/>新建对话</button>
      <div className="conversation-list">{conversations.map(item => <div className={`conversation-item ${item.id === activeId ? "active" : ""}`} key={item.id}>
        <button onClick={() => loadConversation(item.id)}><strong>{item.title}</strong><span>{item.messageCount} 条消息</span></button>
        <button className="icon-danger" aria-label="删除对话" onClick={() => removeConversation(item.id)}><Trash2 size={14}/></button>
      </div>)}</div>
    </aside>
    <section className="panel chat-panel">
      <div className="chat-header"><div><h1>学生事务多智能体助手</h1><p className="lede">多轮对话会进入 Router、Health、Tool、Retriever、Reflection、Rewrite、Analyzer 等 Agent 链路。</p></div></div>
      {managed && <div className="status-box ok">已连接暨南大学学生助手知识库，可直接查询。</div>}
      {!managed && configured && <div className="status-box ok">已读取本机保存的 RAGFlow 配置，将优先使用实时知识库。</div>}
      {!configured && <div className="status-box ok">演示模式已开启。需要完整知识库、照片识别或导入数据时，进入 <Link href="/settings">连接与导入</Link>。</div>}
      <div className="message-list">
        {!messages.length && <div className="empty-state"><strong>开始一段多轮咨询</strong><span>例如先问“感冒了怎么办”，再补充“我在番禺校区，有点发烧”。系统会保留上下文继续分流。</span></div>}
        {messages.map(item => <div className={`message ${item.role}`} key={item.id}>
          <div className="bubble"><p className={item.meta?.ok === false ? "error" : ""}>{item.content}</p>{item.role === "assistant" && item.meta && <AnswerDetails answer={item.meta} />}</div>
        </div>)}
      </div>
      <div className="composer">
        <textarea value={question} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if(e.key === "Enter" && !e.shiftKey){ e.preventDefault(); ask(); } }} placeholder="继续追问，例如：我在番禺校区，有点发烧" aria-label="学生事务问题" />
        <button className="button" disabled={loading} onClick={ask}><Search size={17}/>{loading ? "处理中" : "发送"}</button>
      </div>
      <div className="photo-row"><label className="button secondary" htmlFor="query-photo"><Camera size={17}/>添加照片</label><input id="query-photo" hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={e => chooseImage(e.target.files?.[0])}/><span className="muted">{image ? "照片已准备，将结合上下文进入视觉识别和检索" : "可上传通知、表格或办事页面截图"}</span></div>
    </section>
    <aside className="panel helper-panel"><h2>常用问题</h2><div className="dataset-list">{["校巴时间","本科生请假申请表","学生证补办","暑期课程选课时间","感冒了怎么办"].map(item => <button className="button secondary" key={item} onClick={() => setQuestion(item)}>{item}</button>)}</div><h3>多 Agent 链路</h3><div className="privacy">每轮都会带最近上下文进入智能体编排。补充校区、症状、对象或流程时，系统会把它和上一轮问题合并理解。</div></aside>
  </div></main>;
}
