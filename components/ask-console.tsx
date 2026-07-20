"use client"

import Link from "next/link"
import { useRef, useState } from "react"
import { useSettings } from "@/components/use-settings"
import { authHeaders, hasCredentials } from "@/lib/client-settings"

type Source = {
  index: number
  documentName: string
  similarity: number
  content: string
  sourceUrl: string | null
}

type Answer = {
  id: string
  question: string
  imageUrl?: string
  loading: boolean
  answered?: boolean
  message?: string
  sources?: Source[]
  error?: string
}

export function AskConsole() {
  const { settings, ready } = useSettings()
  const [question, setQuestion] = useState("")
  const [image, setImage] = useState<{ file: File; url: string } | null>(null)
  const [answers, setAnswers] = useState<Answer[]>([])
  const fileRef = useRef<HTMLInputElement>(null)

  const configured = ready && hasCredentials(settings) && Boolean(settings.qaDatasetId)
  const busy = answers.some((a) => a.loading)

  function pickImage(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith("image/")) return
    setImage({ file, url: URL.createObjectURL(file) })
  }

  function clearImage() {
    if (image) URL.revokeObjectURL(image.url)
    setImage(null)
    if (fileRef.current) fileRef.current.value = ""
  }

  async function submit() {
    const q = question.trim()
    if (!q || busy || !configured) return

    const id = crypto.randomUUID()
    const imageUrl = image?.url
    setAnswers((prev) => [
      { id, question: q, imageUrl, loading: true },
      ...prev,
    ])
    setQuestion("")
    // 保留图片预览到消息中，输入区清空。
    setImage(null)
    if (fileRef.current) fileRef.current.value = ""

    const datasetIds = [settings.qaDatasetId, settings.noticeDatasetId].filter(Boolean)

    try {
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...authHeaders(settings),
        },
        body: JSON.stringify({ question: q, datasetIds }),
      })
      const data = await res.json()
      if (!res.ok) {
        setAnswers((prev) =>
          prev.map((a) => (a.id === id ? { ...a, loading: false, error: data.error } : a)),
        )
        return
      }
      setAnswers((prev) =>
        prev.map((a) =>
          a.id === id
            ? {
                ...a,
                loading: false,
                answered: data.answered,
                message: data.message,
                sources: data.sources ?? [],
              }
            : a,
        ),
      )
    } catch {
      setAnswers((prev) =>
        prev.map((a) =>
          a.id === id ? { ...a, loading: false, error: "网络错误，请稍后重试" } : a,
        ),
      )
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      if (e.nativeEvent.isComposing || e.keyCode === 229) return
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-xl border border-border bg-card p-5 sm:p-6">
        <h1 className="text-balance text-xl font-semibold tracking-tight sm:text-2xl">
          暨南大学学生助手
        </h1>
        <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
          输入文字或附上照片提问。回答严格基于你连接的 RAGFlow 知识库检索结果，若没有可靠依据会明确拒答，绝不编造。
        </p>

        {ready && !configured && (
          <div className="mt-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm">
            <span className="text-foreground">尚未完成配置。</span>{" "}
            请前往{" "}
            <Link href="/settings" className="font-medium text-primary underline underline-offset-2">
              连接与导入
            </Link>{" "}
            填写 RAGFlow 地址、API Key 并选择问答知识库。
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3">
          {image && (
            <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/50 p-2">
              {/* 本地预览图，仅在当前会话内存中 */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={image.url || "/placeholder.svg"}
                alt="待提问的照片预览"
                className="h-16 w-16 rounded-md object-cover"
              />
              <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
                {image.file.name}
              </span>
              <button
                type="button"
                onClick={clearImage}
                className="rounded-md px-2 py-1 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                移除
              </button>
            </div>
          )}

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            rows={3}
            disabled={!configured}
            placeholder={
              configured
                ? "例如：本科生转专业的申请时间和材料有哪些？"
                : "请先在“连接与导入”完成配置后再提问"
            }
            className="w-full resize-y rounded-lg border border-input bg-background px-3.5 py-2.5 text-sm leading-relaxed outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/30 disabled:cursor-not-allowed disabled:opacity-60"
          />

          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              onChange={pickImage}
              className="hidden"
              id="photo-input"
            />
            <label
              htmlFor="photo-input"
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted ${
                !configured ? "pointer-events-none opacity-60" : ""
              }`}
            >
              <PhotoIcon />
              添加照片
            </label>

            <span className="hidden text-xs text-muted-foreground sm:inline">
              照片用于辅助说明，请配合文字描述你的问题
            </span>

            <button
              type="button"
              onClick={submit}
              disabled={!configured || busy || !question.trim()}
              className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? "检索中…" : "提问"}
            </button>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-4" aria-live="polite">
        {answers.length === 0 && (
          <p className="text-center text-sm text-muted-foreground">
            提问后，检索到的知识库依据会显示在这里。
          </p>
        )}
        {answers.map((a) => (
          <AnswerCard key={a.id} answer={a} />
        ))}
      </section>
    </div>
  )
}

function AnswerCard({ answer }: { answer: Answer }) {
  return (
    <article className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0 rounded-md bg-muted px-2 py-1 text-xs font-medium text-muted-foreground">
          问
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-pretty text-sm font-medium leading-relaxed">{answer.question}</p>
          {answer.imageUrl && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={answer.imageUrl || "/placeholder.svg"}
              alt="提问附带的照片"
              className="mt-2 max-h-48 rounded-lg border border-border object-contain"
            />
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-border pt-4">
        {answer.loading && (
          <p className="text-sm text-muted-foreground">正在检索知识库…</p>
        )}

        {answer.error && (
          <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-foreground">
            {answer.error}
          </p>
        )}

        {!answer.loading && !answer.error && answer.answered === false && (
          <p className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm leading-relaxed text-foreground">
            {answer.message}
          </p>
        )}

        {!answer.loading && answer.answered && (
          <div className="flex flex-col gap-3">
            <p className="text-sm leading-relaxed text-muted-foreground">{answer.message}</p>
            {answer.sources?.map((s) => (
              <div key={s.index} className="rounded-lg border border-border bg-muted/40 p-3.5">
                <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary">
                    依据 {s.index}
                  </span>
                  <span className="min-w-0 truncate font-medium text-foreground">
                    {s.documentName}
                  </span>
                  <span className="ml-auto shrink-0">相似度 {s.similarity}</span>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-pretty text-sm leading-relaxed">
                  {s.content}
                </p>
                {s.sourceUrl && (
                  <a
                    href={s.sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-block break-all text-xs font-medium text-primary underline underline-offset-2"
                  >
                    {s.sourceUrl}
                  </a>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}

function PhotoIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <circle cx="9" cy="9" r="2" />
      <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
    </svg>
  )
}
