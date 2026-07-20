"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useSettings } from "@/components/use-settings"
import { authHeaders, hasCredentials } from "@/lib/client-settings"

type SnapshotSummary = {
  exportedAt: string
  documentCount: number
  datasets: { id: string; name: string; documents: number; chunks: number }[]
}

type LiveDataset = {
  id: string
  name: string
  documentCount: number
  chunkCount: number
}

type LiveDoc = {
  id: string
  name: string
  run: string
  chunkCount: number
  progress: number | null
  progressMsg: string
  updateDate: string
}

const RUN_LABEL: Record<string, { label: string; tone: string }> = {
  DONE: { label: "已完成", tone: "text-success" },
  RUNNING: { label: "解析中", tone: "text-warning" },
  FAIL: { label: "失败", tone: "text-danger" },
  UNSTART: { label: "未开始", tone: "text-muted-foreground" },
  CANCEL: { label: "已取消", tone: "text-muted-foreground" },
  "": { label: "未知", tone: "text-muted-foreground" },
}

export function PipelineBoard() {
  const { settings, ready } = useSettings()
  const [snapshot, setSnapshot] = useState<SnapshotSummary | null>(null)
  const [liveDatasets, setLiveDatasets] = useState<LiveDataset[]>([])
  const [selected, setSelected] = useState("")
  const [docs, setDocs] = useState<LiveDoc[]>([])
  const [loadingDocs, setLoadingDocs] = useState(false)
  const [liveError, setLiveError] = useState("")

  const connected = ready && hasCredentials(settings)

  useEffect(() => {
    fetch("/api/snapshot")
      .then((r) => r.json())
      .then(setSnapshot)
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!connected) return
    fetch("/api/ragflow/datasets", { headers: authHeaders(settings) })
      .then((r) => r.json())
      .then((d) => {
        if (d.datasets) {
          setLiveDatasets(d.datasets)
          setLiveError("")
        } else if (d.error) {
          setLiveError(d.error)
        }
      })
      .catch(() => setLiveError("无法读取 RAGFlow 知识库"))
  }, [connected, settings])

  useEffect(() => {
    if (!selected || !connected) return
    setLoadingDocs(true)
    fetch(`/api/ragflow/documents?datasetId=${encodeURIComponent(selected)}`, {
      headers: authHeaders(settings),
    })
      .then((r) => r.json())
      .then((d) => setDocs(d.documents ?? []))
      .catch(() => setDocs([]))
      .finally(() => setLoadingDocs(false))
  }, [selected, connected, settings])

  const snapshotDocs = snapshot?.documentCount ?? 0
  const snapshotChunks =
    snapshot?.datasets.reduce((sum, d) => sum + (d.chunks ?? 0), 0) ?? 0
  const doneCount = docs.filter((d) => d.run === "DONE").length

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-balance text-xl font-semibold tracking-tight sm:text-2xl">
          数据看板
        </h1>
        <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
          从数据清洗到知识库、解析与检索的整体概览。
        </p>
      </header>

      {/* 流水线阶段 */}
      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StageCard
          step="1"
          title="数据清洗"
          desc="爬取与清洗暨大官方材料，去重后生成结构化文档。"
          metric={`${snapshotDocs}`}
          metricLabel="快照文档"
        />
        <StageCard
          step="2"
          title="知识库"
          desc="按分块策略组织为多个 RAGFlow 知识库快照。"
          metric={`${snapshot?.datasets.length ?? 0}`}
          metricLabel="快照知识库"
        />
        <StageCard
          step="3"
          title="解析"
          desc="上传至 RAGFlow 并解析为可检索的分块。"
          metric={`${snapshotChunks}`}
          metricLabel="快照分块"
        />
        <StageCard
          step="4"
          title="检索"
          desc="严格基于知识库检索作答，无依据则拒答。"
          metric={connected ? `${liveDatasets.length}` : "—"}
          metricLabel="在线知识库"
        />
      </section>

      {/* 快照知识库明细 */}
      <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight">仓库知识库快照</h2>
        {snapshot?.exportedAt && (
          <p className="mt-1 text-xs text-muted-foreground">
            导出时间：{snapshot.exportedAt}
          </p>
        )}
        <div className="mt-4 -mx-2 overflow-x-auto">
          <table className="w-full min-w-[28rem] border-collapse text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="px-2 py-2 font-medium">知识库</th>
                <th className="px-2 py-2 text-right font-medium">文档</th>
                <th className="px-2 py-2 text-right font-medium">分块</th>
              </tr>
            </thead>
            <tbody>
              {snapshot?.datasets.map((d) => (
                <tr key={d.id} className="border-b border-border/60">
                  <td className="px-2 py-2.5 font-medium">{d.name}</td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-muted-foreground">
                    {d.documents}
                  </td>
                  <td className="px-2 py-2.5 text-right tabular-nums text-muted-foreground">
                    {d.chunks}
                  </td>
                </tr>
              ))}
              {!snapshot && (
                <tr>
                  <td colSpan={3} className="px-2 py-4 text-center text-muted-foreground">
                    正在加载…
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 在线解析状态 */}
      <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
        <h2 className="text-lg font-semibold tracking-tight">在线解析状态</h2>
        {!connected ? (
          <p className="mt-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">
            未连接 RAGFlow。请前往{" "}
            <Link href="/settings" className="font-medium text-primary underline underline-offset-2">
              连接与导入
            </Link>{" "}
            配置后查看实时文档解析状态。
          </p>
        ) : (
          <div className="mt-4 flex flex-col gap-4">
            {liveError && (
              <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
                {liveError}
              </p>
            )}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium">选择知识库</label>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3.5 py-2.5 text-sm outline-none focus:border-ring focus:ring-2 focus:ring-ring/30 sm:max-w-sm"
              >
                <option value="">请选择…</option>
                {liveDatasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}（{d.documentCount} 文档）
                  </option>
                ))}
              </select>
            </div>

            {selected && (
              <>
                {loadingDocs ? (
                  <p className="text-sm text-muted-foreground">正在读取文档解析状态…</p>
                ) : (
                  <>
                    <p className="text-sm text-muted-foreground">
                      共 {docs.length} 个文档，已完成解析 {doneCount} 个。
                    </p>
                    <div className="-mx-2 overflow-x-auto">
                      <table className="w-full min-w-[32rem] border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-border text-left text-xs text-muted-foreground">
                            <th className="px-2 py-2 font-medium">文档</th>
                            <th className="px-2 py-2 font-medium">状态</th>
                            <th className="px-2 py-2 text-right font-medium">分块</th>
                          </tr>
                        </thead>
                        <tbody>
                          {docs.map((doc) => {
                            const tone = RUN_LABEL[doc.run] ?? RUN_LABEL[""]
                            return (
                              <tr key={doc.id} className="border-b border-border/60">
                                <td className="max-w-[16rem] px-2 py-2.5">
                                  <span className="block truncate font-medium">{doc.name}</span>
                                </td>
                                <td className={`px-2 py-2.5 font-medium ${tone.tone}`}>
                                  {tone.label}
                                </td>
                                <td className="px-2 py-2.5 text-right tabular-nums text-muted-foreground">
                                  {doc.chunkCount}
                                </td>
                              </tr>
                            )
                          })}
                          {docs.length === 0 && (
                            <tr>
                              <td colSpan={3} className="px-2 py-4 text-center text-muted-foreground">
                                该知识库暂无文档
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

function StageCard({
  step,
  title,
  desc,
  metric,
  metricLabel,
}: {
  step: string
  title: string
  desc: string
  metric: string
  metricLabel: string
}) {
  return (
    <div className="flex flex-col rounded-xl border border-border bg-card p-4">
      <div className="flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
          {step}
        </span>
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <p className="mt-2 flex-1 text-xs leading-relaxed text-muted-foreground">{desc}</p>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="text-2xl font-semibold tabular-nums tracking-tight">{metric}</span>
        <span className="text-xs text-muted-foreground">{metricLabel}</span>
      </div>
    </div>
  )
}
