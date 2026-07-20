"use client";

import Link from "next/link";
import { Camera, ExternalLink, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { loadConnection } from "@/lib/connection";

type Answer = { ok: boolean; answer: string; documentName?: string; similarity?: number; sourceUrl?: string; downloads?: { name: string; url: string }[]; matches?: { documentName: string; similarity: number; snippet: string }[] };

export default function AssistantPage() {
  const [question, setQuestion] = useState(""); const [image, setImage] = useState<{ base64: string; mime: string } | null>(null); const [answer, setAnswer] = useState<Answer | null>(null); const [loading, setLoading] = useState(false); const [configured, setConfigured] = useState(false); const [managed,setManaged]=useState(false);
  useEffect(() => { const value = loadConnection(); const personal=Boolean(value.baseUrl && value.apiKey && value.datasetId); setConfigured(personal); fetch("/api/ragflow",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"configuration"})}).then(response=>response.json()).then(data=>{setManaged(Boolean(data.managed));setConfigured(personal||Boolean(data.managed));}).catch(()=>{}); }, []);
  async function chooseImage(file?: File) { if (!file) return setImage(null); if (!/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 4 * 1024 * 1024) return setAnswer({ ok:false, answer:"请选择不超过 4 MB 的 JPG、PNG 或 WebP 图片。" }); const bitmap=await createImageBitmap(file); const scale=Math.min(1,1280/Math.max(bitmap.width,bitmap.height)); const canvas=document.createElement("canvas"); canvas.width=Math.round(bitmap.width*scale); canvas.height=Math.round(bitmap.height*scale); canvas.getContext("2d")?.drawImage(bitmap,0,0,canvas.width,canvas.height); const value=canvas.toDataURL("image/jpeg",.78); setImage({mime:"image/jpeg",base64:value.split(",",2)[1]}); }
  async function ask() { if (!question.trim() && !image) return; const connection=loadConnection(); if (!managed&&(!connection.baseUrl || !connection.apiKey || !connection.datasetId)) return setAnswer({ok:false,answer:"请先完成 RAGFlow 连接与知识库配置。"}); setLoading(true); setAnswer(null); try { const response=await fetch("/api/ragflow",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({action:"ask",connection,question,imageBase64:image?.base64||"",imageMime:image?.mime||""})}); setAnswer(await response.json()); } catch { setAnswer({ok:false,answer:"查询暂时失败，请稍后重试。"}); } finally { setLoading(false); } }
  return <main className="page"><div className="page-grid">
    <section className="panel"><h1>学生事务查询</h1><p className="lede">检索学校官方资料、通知、办事流程、表格与附件。没有可靠材料时，助手会明确拒答。</p>
      <div className="query-row"><textarea value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();ask();}}} placeholder="例如：本科生请假申请表在哪里下载？" aria-label="学生事务问题" /><button className="button" disabled={loading} onClick={ask}><Search size={17}/>{loading?"检索中":"查询"}</button></div>
      <div className="photo-row"><label className="button secondary" htmlFor="query-photo"><Camera size={17}/>添加照片</label><input id="query-photo" hidden type="file" accept="image/jpeg,image/png,image/webp" onChange={e=>chooseImage(e.target.files?.[0])}/><span className="muted">{image?"照片已准备，将先识别再检索":"可上传通知、表格或办事页面截图"}</span></div>
      {managed&&<div className="status-box ok">已连接暨南大学学生助手知识库，可直接查询。</div>}
      {!configured && <div className="status-box error">尚未配置知识库。<Link href="/settings">前往连接与导入</Link></div>}
      <div className="answer"><h2>回答</h2>{!answer?<p className="muted">查询结果会显示在这里。</p>:<><p className={`answer-text ${answer.ok?"":"error"}`}>{answer.answer}</p>{answer.ok&&<div className="source"><span>{answer.documentName} · 相似度 {Number(answer.similarity||0).toFixed(3)}</span>{answer.sourceUrl&&<a href={answer.sourceUrl} target="_blank" rel="noreferrer">查看官方来源 <ExternalLink size={14}/></a>}</div>}{answer.downloads?.map(item=><a className="button secondary" key={item.url} href={item.url} target="_blank" rel="noreferrer">下载 {item.name} <ExternalLink size={14}/></a>)}{answer.matches?.slice(0,3).map((item,index)=><div className="match" key={`${item.documentName}-${index}`}><strong>{item.documentName} · {item.similarity.toFixed(3)}</strong><div>{item.snippet}</div></div>)}</>}</div>
    </section>
    <aside className="panel"><h2>常用问题</h2><div className="dataset-list">{["校巴时间","本科生请假申请表","学生证补办","暑期课程选课时间","校园网申请"].map(item=><button className="button secondary" key={item} onClick={()=>setQuestion(item)}>{item}</button>)}</div><h3>可信回答</h3><div className="privacy">回答来自你所选择的 RAGFlow 知识库。涉及账号密码、个人隐私、医疗诊断和未发布信息时不会推测。</div></aside>
  </div></main>;
}
