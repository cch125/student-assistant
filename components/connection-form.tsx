"use client"

import { useEffect, useState } from "react"
import {
  authHeaders,
  clearCredentials,
  loadSettings,
  saveSettings,
  type Settings,
} from "@/lib/client-settings"

type DatasetOption = { id: string; name: string; documentCount?: number }

type VerifyState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ok"; count: number }
  | { status: "error"; message: string }

export function ConnectionForm({
  onDatasetsLoaded,
}: {
  onDatasetsLoaded?: (datasets: DatasetOption[], settings: Settings) => void
}) {
  const [form, setForm] = useState<Settings>({
    baseUrl: "",
    apiKey: "",
    qaDatasetId: "",
    noticeDatasetId: "",
    remember: false,
  })
  const [datasets, setDatasets] = useState<DatasetOption[]>([])
  const [verify, setVerify] = useState<VerifyState>({ status: "idle" })
  const [showKey, setShowKey] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    setForm(loadSettings())
  }, [])

  function update<K extends keyof Settings>(key: K, value: Settings[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setSaved(false)
  }

  async function verifyConnection() {
    setVerify({ status: "loading" })
    setDatasets([])
    try {
      const res = await fetch("/api/ragflow/verify", {
        headers: authHeaders(form),
      })
      const data = await res.json()
      if (!res.ok) {
        setVerify({ status: "error", message: data.error ?? "验证失败" })
        return
      }
      const list: DatasetOption[] = data.datasets ?? []
      setDatasets(list)
      setVerify({ status: "ok", count: data.datasetCount ?? list.length })
      onDatasetsLoaded?.(list, form)
    } catch {
      setVerify({ status: "error", message: "网络错误，无法连接" })
    }
  }

  function persist() {
    saveSettings(form)
    setSaved(true)
    window.dispatchEvent(new Event("jnu:settings-updated"))
  }

  function forget() {
    clearCredentials()
    setForm((prev) => ({ ...prev, apiKey: "", remember: false }))
    setVerify({ status: "idle" })
    setDatasets([])
    window.dispatchEvent(new Event("jnu:settings-updated"))
  }

  return (
    <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
      <h2 className="text-lg font-semibold tracking-tight">连接配置</h2>
      <p className="mt-1 text-sm leading-relaxed text-muted-foreground">
        每位组员填写各自的 RAGFlow 连接信息。API Key 默认仅保存在本浏览器的 sessionStorage 中，
        不会写入源码、GitHub、日志或数据库，也不会保存在服务器。
      </p>

      <div className="mt-5 flex flex-col gap-4">
        <Field label="RAGFlow HTTPS 地址" hint="必须为 https:// 公网地址，禁止内网或本机地址">
          <input
            type="url"
            inputMode="url"
            value={form.baseUrl}
            onChange={(e) => update("baseUrl", e.target.value)}
            placeholder="https://ragflow.example.com"
            className={inputClass}
          />
        </Field>

        <Field label="RAGFlow API Key" hint="用于访问你自己的 RAGFlow，仅在调用时通过请求头转发">
          <div className="flex gap-2">
            <input
              type={showKey ? "text" : "password"}
              value={form.apiKey}
              onChange={(e) => update("apiKey", e.target.value)}
              placeholder="ragflow-xxxxxxxxxxxxxxxx"
              autoComplete="off"
              className={inputClass}
            />
            <button
              type="button"
              onClick={() => setShowKey((v) => !v)}
              className="shrink-0 rounded-lg border border-border px-3 text-sm font-medium hover:bg-muted"
            >
              {showKey ? "隐藏" : "显示"}
            </button>
          </div>
        </Field>

        <label className="flex items-start gap-2.5 text-sm">
          <input
            type="checkbox"
            checked={form.remember}
            onChange={(e) => update("remember", e.target.checked)}
            className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--primary)]"
          />
          <span className="leading-relaxed text-muted-foreground">
            在此浏览器记住 API Key（写入 localStorage，下次打开仍可用）。
            共享或公用电脑请勿勾选。
          </span>
        </label>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={verifyConnection}
            disabled={!form.baseUrl || !form.apiKey || verify.status === "loading"}
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {verify.status === "loading" ? "验证中…" : "验证连接"}
          </button>
          <button
            type="button"
            onClick={forget}
            className="inline-flex items-center rounded-lg border border-border px-4 py-2 text-sm font-medium hover:bg-muted"
          >
            忘记 API Key
          </button>
        </div>

        {verify.status === "ok" && (
          <p className="rounded-lg border border-success/40 bg-success/10 px-3 py-2 text-sm">
            连接成功，共发现 {verify.count} 个知识库。请在下方选择用途并保存。
          </p>
        )}
        {verify.status === "error" && (
          <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm">
            {verify.message}
          </p>
        )}

        {datasets.length > 0 && (
          <>
            <Field label="问答知识库" hint="首页提问时检索的主知识库">
              <select
                value={form.qaDatasetId}
                onChange={(e) => update("qaDatasetId", e.target.value)}
                className={inputClass}
              >
                <option value="">请选择…</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="通知补充知识库" hint="可选，用于补充官方通知类内容">
              <select
                value={form.noticeDatasetId}
                onChange={(e) => update("noticeDatasetId", e.target.value)}
                className={inputClass}
              >
                <option value="">不使用</option>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
          </>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={persist}
            className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            保存设置
          </button>
          {saved && <span className="text-sm text-success">已保存到本浏览器</span>}
        </div>
      </div>
    </section>
  )
}

const inputClass =
  "w-full rounded-lg border border-input bg-background px-3.5 py-2.5 text-sm outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30"

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium">{label}</label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}
