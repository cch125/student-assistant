import { NextResponse } from "next/server"
import { readCredentials, retrieve, type RagflowChunk } from "@/lib/ragflow"
import { handleError, jsonError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

const MAX_QUESTION = 500
const REFUSAL =
  "抱歉，我在已连接的知识库中没有检索到可靠依据，无法回答该问题。请换一种问法，或在“连接与导入”中补充相关知识库内容。"

function cleanContent(chunk: RagflowChunk): string {
  const raw = chunk.content || chunk.content_with_weight || ""
  return raw.replace(/\r/g, "").trim()
}

function extractSourceUrl(text: string): string | null {
  const match = text.match(/(?:来源链接|来源|链接)\s*[:：]\s*(https?:\/\/\S+)/)
  if (match) return match[1].replace(/[.,，。)）]+$/, "")
  const bare = text.match(/https?:\/\/[^\s)）]+/)
  return bare ? bare[0].replace(/[.,，。)）]+$/, "") : null
}

export async function POST(req: Request) {
  try {
    const creds = await readCredentials(req)
    const body = (await req.json().catch(() => ({}))) as {
      question?: string
      datasetIds?: string[]
      similarityThreshold?: number
    }

    const question = (body.question ?? "").trim()
    if (!question) return jsonError("请输入问题")
    if (question.length > MAX_QUESTION) {
      return jsonError(`问题过长，请控制在 ${MAX_QUESTION} 字以内`)
    }

    const datasetIds = (body.datasetIds ?? []).filter(Boolean)
    if (datasetIds.length === 0) {
      return jsonError("尚未选择知识库，请先在“连接与导入”中配置问答知识库", 400)
    }

    const threshold =
      typeof body.similarityThreshold === "number" ? body.similarityThreshold : 0.2

    const chunks = await retrieve(creds, {
      question,
      datasetIds,
      similarityThreshold: threshold,
      pageSize: 6,
    })

    // 严格接地：无检索结果即明确拒答，绝不编造。
    const grounded = chunks
      .map((c) => ({
        content: cleanContent(c),
        similarity: c.similarity ?? 0,
        documentName: c.document_keyword || c.document_name || "知识库文档",
      }))
      .filter((c) => c.content.length > 0)

    if (grounded.length === 0) {
      return NextResponse.json({ answered: false, message: REFUSAL, sources: [] })
    }

    const sources = grounded.slice(0, 4).map((c, index) => ({
      index: index + 1,
      documentName: c.documentName,
      similarity: Math.round(c.similarity * 1000) / 1000,
      content: c.content.slice(0, 1200),
      sourceUrl: extractSourceUrl(c.content),
    }))

    return NextResponse.json({
      answered: true,
      message:
        "以下内容严格来自你连接的 RAGFlow 知识库检索结果，未做任何编造。请以官方来源为准：",
      sources,
    })
  } catch (err) {
    return handleError(err)
  }
}
