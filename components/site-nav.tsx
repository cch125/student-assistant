"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Database, LayoutDashboard, MessageSquareText, Settings } from "lucide-react";

const links = [
  { href: "/", label: "学生助手", icon: MessageSquareText },
  { href: "/pipeline", label: "数据看板", icon: LayoutDashboard },
  { href: "/settings", label: "连接与导入", icon: Settings }
];

export function SiteNav() {
  const pathname = usePathname();
  return <header className="site-header"><div className="site-bar">
    <Link className="brand" href="/"><span className="brand-mark">暨</span><span><strong>暨南大学学生助手</strong><small>学生事务知识服务</small></span></Link>
    <nav className="site-nav" aria-label="主导航">
      {links.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={pathname === href ? "active" : ""}><Icon size={16} /><span>{label}</span></Link>)}
    </nav>
  </div></header>;
}
