"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Database, FileText, History, LayoutDashboard, LogOut, MessageSquareText, Settings } from "lucide-react";
import { useEffect, useState } from "react";

const links = [
  { href: "/", label: "智能问答", icon: MessageSquareText },
  { href: "/services", label: "服务卡片", icon: BookOpen },
  { href: "/history", label: "历史记录", icon: History },
  { href: "/documents", label: "文档管理", icon: FileText },
  { href: "/pipeline", label: "数据看板", icon: LayoutDashboard },
  { href: "/settings", label: "连接与导入", icon: Settings },
  { href: "/pipeline", label: "知识库", icon: Database }
];

export function SiteNav() {
  const pathname = usePathname();
  const [user, setUser] = useState<{ username: string; role: string } | null>(null);
  useEffect(() => {
    fetch("/api/auth/me").then(response => response.json()).then(data => setUser(data.user || null)).catch(() => setUser(null));
  }, []);
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    location.href = "/login";
  }
  return <aside className="site-sidebar">
    <Link className="brand" href="/"><span className="brand-mark">暨</span><span><strong>学生问答助手</strong><small>Student Q&A Console</small></span></Link>
    <nav className="site-nav" aria-label="主导航">
      <span className="nav-section">导航</span>
      {links.map(({ href, label, icon: Icon }) => <Link key={`${href}-${label}`} href={href} className={pathname === href ? "active" : ""}><Icon size={16} /><span>{label}</span></Link>)}
    </nav>
    <div className="sidebar-user">
      <span className="user-avatar">{user?.username?.[0]?.toUpperCase() || "访"}</span>
      <span><strong>{user?.username || "访客"}</strong><small>{user ? "管理员" : "公开访问"}</small></span>
      {user ? <button type="button" aria-label="退出登录" onClick={logout}><LogOut size={15} /></button> : <Link className="icon-link" href="/login" aria-label="登录"><LogOut size={15} /></Link>}
    </div>
  </aside>;
}
