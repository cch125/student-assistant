import { NextResponse } from "next/server"
import { readCredentials, ragflowRequest } from "@/lib/ragflow"
import { handleError, jsonError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function POST(req: Request) {
  try {
    const creds = await readCredentials(req)
    const body = (await req.json().catch(() => ({}))) as {
      datasetId?: string
      documentIds?: string[]
    }
    const datasetId = body.datasetId
    const documentIds = Array.isArray(body.documentIds) ? body.documentIds : []
    if (!datasetId) return jsonError("缺少 datasetId")
    if (documentIds.length === 0) return jsonError("请选择至少一个文档")

    await ragflowRequest(creds, {
      method: "POST",
      path: `/datasets/${encodeURIComponent(datasetId)}/documents/parse`,
      json: { document_ids: documentIds },
    })

    return NextResponse.json({ ok: true, parsed: documentIds.length })
  } catch (err) {
    return handleError(err)
  }
}
