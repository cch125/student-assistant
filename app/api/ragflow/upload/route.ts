import { NextResponse } from "next/server"
import { readCredentials, ragflowRequest, type RagflowDocument } from "@/lib/ragflow"
import { handleError, jsonError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

// 单次上传大小上限（Serverless 友好）。
const MAX_TOTAL_BYTES = 20 * 1024 * 1024

export async function POST(req: Request) {
  try {
    const creds = await readCredentials(req)

    const form = await req.formData()
    const datasetId = String(form.get("datasetId") ?? "")
    const autoParse = String(form.get("autoParse") ?? "true") === "true"
    if (!datasetId) return jsonError("缺少 datasetId")

    const files = form.getAll("files").filter((f): f is File => f instanceof File)
    if (files.length === 0) return jsonError("请选择要上传的文件")

    let total = 0
    for (const f of files) total += f.size
    if (total > MAX_TOTAL_BYTES) {
      return jsonError("单次上传总大小超过 20MB，请分批上传", 413)
    }

    // 转发 multipart 到 RAGFlow。
    const forward = new FormData()
    for (const file of files) {
      forward.append("file", file, file.name)
    }

    const uploaded = await ragflowRequest<RagflowDocument[]>(creds, {
      method: "POST",
      path: `/datasets/${encodeURIComponent(datasetId)}/documents`,
      body: forward,
    })

    const docs = Array.isArray(uploaded) ? uploaded : []
    const documentIds = docs.map((d) => d.id).filter(Boolean)

    let parsed = false
    if (autoParse && documentIds.length > 0) {
      await ragflowRequest(creds, {
        method: "POST",
        path: `/datasets/${encodeURIComponent(datasetId)}/documents/parse`,
        json: { document_ids: documentIds },
      })
      parsed = true
    }

    return NextResponse.json({
      ok: true,
      uploaded: docs.map((d) => ({ id: d.id, name: d.name })),
      parsed,
    })
  } catch (err) {
    return handleError(err)
  }
}
