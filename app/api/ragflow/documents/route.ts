import { NextResponse } from "next/server"
import { readCredentials, listDocuments } from "@/lib/ragflow"
import { handleError, jsonError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(req: Request) {
  try {
    const creds = await readCredentials(req)
    const { searchParams } = new URL(req.url)
    const datasetId = searchParams.get("datasetId")
    if (!datasetId) return jsonError("缺少 datasetId 参数")

    const { docs, total } = await listDocuments(creds, datasetId)
    return NextResponse.json({
      total,
      documents: docs.map((d) => ({
        id: d.id,
        name: d.name,
        run: d.run ?? "",
        chunkCount: d.chunk_count ?? 0,
        tokenCount: d.token_count ?? 0,
        size: d.size ?? 0,
        type: d.type ?? "",
        progress: typeof d.progress === "number" ? d.progress : null,
        progressMsg: d.progress_msg ?? "",
        updateDate: d.update_date ?? "",
      })),
    })
  } catch (err) {
    return handleError(err)
  }
}
