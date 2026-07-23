"use client";

import { LockKeyhole } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function LoginForm() {
  const params = useSearchParams();
  const [username, setUsername] = useState("cch125");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function login() {
    setBusy(true);
    setMessage("");
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json().catch(() => ({}));
    setBusy(false);
    if (!response.ok || data.ok === false) {
      setMessage(data.message || "登录失败。");
      return;
    }
    location.href = params.get("next") || "/settings";
  }

  return <main className="page login-page">
    <section className="panel login-card">
      <div className="login-icon"><LockKeyhole size={22} /></div>
      <h1>管理员登录</h1>
      <p className="lede">登录后可进入连接导入、文档管理和历史记录页面。</p>
      <label className="field full">
        <span>账号</span>
        <input value={username} onChange={event => setUsername(event.target.value)} autoComplete="username" />
      </label>
      <label className="field full">
        <span>密码</span>
        <input type="password" value={password} onChange={event => setPassword(event.target.value)} autoComplete="current-password" onKeyDown={event => { if (event.key === "Enter") login(); }} />
      </label>
      <button className="button" disabled={busy} onClick={login}>{busy ? "登录中" : "登录"}</button>
      {message && <div className="status-box error">{message}</div>}
    </section>
  </main>;
}

export default function LoginPage() {
  return <Suspense fallback={<main className="page login-page"><section className="panel login-card"><p className="muted">正在加载登录页...</p></section></main>}>
    <LoginForm />
  </Suspense>;
}
