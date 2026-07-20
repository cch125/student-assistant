import type { Metadata, Viewport } from "next"
import { Geist, Geist_Mono } from "next/font/google"
import { SiteHeader } from "@/components/site-header"
import "./globals.css"

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-sans-var",
})

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-mono-var",
})

export const metadata: Metadata = {
  title: "暨南大学学生助手",
  description:
    "基于 RAGFlow 知识库的暨南大学学生助手，支持文字与照片提问、数据清洗与检索看板、连接与知识库导入配置。",
  keywords: ["暨南大学", "学生助手", "RAGFlow", "知识库", "检索问答"],
}

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf8f6" },
    { media: "(prefers-color-scheme: dark)", color: "#26201f" },
  ],
  width: "device-width",
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN" className={`bg-background ${geistSans.variable} ${geistMono.variable}`}>
      <body className="min-h-dvh font-sans antialiased">
        <SiteHeader />
        <main className="mx-auto w-full max-w-5xl px-4 pb-16 pt-6 sm:px-6">{children}</main>
      </body>
    </html>
  )
}
