"use client"

import { useEffect, useRef, useState } from "react"
import { authHeaders, loadSettings } from "@/lib/client-settings"

type SnapshotDataset = { id: string; name: string; documents: number; chunks: number }
type DatasetOption = { id: string; name: string }

type Progress = {
  total: number
  processed: number
  imported: number
  skipped: number
  failed: number
  log: string[]
}

export function ImportPanel({ targets }: { targets: DatasetOption[] }) {
  const [snapshots, setSnapshots] = useState<SnapshotDataset[]>([])
  const [snapshotId, setSnapshotId] = useState("")
  const [targetId, setTargetId] = useState("")
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState<Progress | null>(null)
  const [error, setError] = useState("")
  const cancelRef = useRef(false)

  useEffect(() => {
    fetch("/api/snapshot")
      .then((r) => r.json())
      .then((d) => setSnapshots(d.datasets ?? []))
      .catch(() => setError("无法读取仓库知识库快照"))
  }, [])

  async function runImport() {
    setError("")
    const settings = loadSettings()
    if (!settings.baseUrl || !settings.apiKey) {
      setError("请先在上方完成连接配置并验证。")
      return
    }
    if (!snapshotId) {
      setError("请选择要导入的快照知识库。")
      return
    }
    if (!targetId) {
      setError("请选择要导入到的目标 RAGFlow 知识库。")
      return
    }

    cancelRef.current = false
    setRunning(true)
    const agg: Progress = {
      total: 0,
      processed: 0,
      imported: 0,
      skipped: 0,
      failed: 0,
      log: [],
    }
    setProgress({ ...agg })

    let offset = 0
    try {
      while (!cancelRef.current) {
        const res = await fetch("/api/snapshot/import", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...authHeaders(settings) },
          body: JSON.stringify({
            snapshotDatasetId: snapshotId,
            targetDatasetId: targetId,
            offset,
            limit: 8,
          }),
        })
        const data = await res.json()
        if (!res.ok) {
          setError(data.error ?? "导入失败")
          break
        }

        agg.total = data.total
        agg.processed = data.processed
        agg.imported += (data.imported ?? []).length
        agg.skipped += (data.skipped ?? []).length
        agg.failed += (data.failed ?? []).length
        for (const name of data.imported ?? []) agg.log.unshift(`导入：${name}`)
        for (const name of data.skipped ?? []) agg.log.unshift(`跳过（同名）：${name}`)
        for (const f of data.failed ?? []) agg.log.unshift(`失败：${f.name} — ${f.reason}`)
        agg.log = agg.log.slice(0, 100)
        setProgress({ ...agg })

        offset = data.nextOffset
        if (data.done) break
      }
    } catch {
      setError("网络错误，导入中断")
    } finally {
      setRunning(false)
    }
  }

  const percent =
    progress && progress.total > 0
      ? Math.round((progress.processed / progress.total) * 100)
      : 0

  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <h2 className="text-lg font-semibold tracking-tight">导入仓库知识库快照</h2>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        将仓库 knowledge_base 中的知识库快照分批导入到你选择的 RAGFlow 知识库，并自动触发解析。
        目标知识库中的同名文件会自动跳过。
      </p>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">快照知识库（来源）</label>
          <select
            value={snapshotId}
            onChange={(e) => setSnapshotId(e.target.value)}
            disabled={running}
            className={inputClass}
          >
            <option value="">请选择…</option>
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}（{s.documents} 文档）
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label className="text-sm font-medium">目标知识库（RAGFlow）</label>
          <select
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
            disabled={running || targets.length === 0}
            className={inputClass}
          >
            <option value="">
              {targets.length === 0 ? "请先在上方验证连接" : "请选择…"}
            </option>
            {targets.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={runImport}
          disabled={running}
          className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {running ? "导入中…" : "开始导入"}
        </button>
        {running && (
          <button
            type="button"
            onClick={() => {
              cancelRef.current = true
            }}
            className="inline-flex items-center rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            停止
          </button>
        )}
      </div>

      {error && (
        <p className="mt-4 rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
          {error}
        </p>
      )}

      {progress && (
        <div className="mt-5 flex flex-col gap-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full bg-primary transition-all"
              style={{ width: `${percent}%` }}
            />
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span>
              进度 {progress.processed}/{progress.total}（{percent}%）
            </span>
            <span className="text-success">已导入 {progress.imported}</span>
            <span>已跳过 {progress.skipped}</span>
            {progress.failed > 0 && (
              <span className="text-danger">失败 {progress.failed}</span>
            )}
          </div>

          {progress.log.length > 0 && (
            <div className="max-h-52 overflow-y-auto rounded-lg border border-border bg-muted/40 p-3">
              <ul className="flex flex-col gap-1 font-mono text-xs leading-relaxed text-muted-foreground">
                {progress.log.map((line, i) => (
                  <li key={i} className="break-all">
                    {line}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  )
}

const inputClass =
  "w-full rounded-lg border border-input bg-background px-3.5 py-2.5 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:opacity-60"
