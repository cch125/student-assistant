import { NextResponse } from "next/server"
import { readCredentials, ragflowRequest, listDocuments, type RagflowDocument } from "@/lib/ragflow"
import { readSnapshotDocuments, readBlob, mimeFor } from "@/lib/snapshot"
import { handleError, jsonError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

// 每批导入的文档数量上限，保证单次 Serverless 调用时间可控。
const MAX_BATCH = 8

export async function POST(req: Request) {
  try {
    const creds = await readCredentials(req)
    const body = (await req.json().catch(() => ({}))) as {
      snapshotDatasetId?: string
      targetDatasetId?: string
      offset?: number
      limit?: number
    }

    const snapshotDatasetId = body.snapshotDatasetId
    const targetDatasetId = body.targetDatasetId
    if (!snapshotDatasetId) return jsonError("缺少快照数据集 ID")
    if (!targetDatasetId) return jsonError("请选择要导入到的目标知识库")

    const offset = Math.max(0, Number(body.offset ?? 0) | 0)
    const limit = Math.min(MAX_BATCH, Math.max(1, Number(body.limit ?? MAX_BATCH) | 0))

    const allDocs = await readSnapshotDocuments(snapshotDatasetId)
    const total = allDocs.length
    const batch = allDocs.slice(offset, offset + limit)

    // 读取目标知识库现有文档名，用于「同名跳过」。
    const existing = await listDocuments(creds, targetDatasetId)
    const existingNames = new Set(existing.docs.map((d) => d.name))

    const imported: string[] = []
    const skipped: string[] = []
    const failed: { name: string; reason: string }[] = []

    const seenInBatch = new Set<string>()
    const toUpload: { name: string; suffix?: string; blobPath: string }[] = []

    for (const doc of batch) {
      if (!doc.blob_path) {
        skipped.push(doc.name)
        continue
      }
      if (existingNames.has(doc.name) || seenInBatch.has(doc.name)) {
        skipped.push(doc.name)
        continue
      }
      seenInBatch.add(doc.name)
      toUpload.push({ name: doc.name, suffix: doc.suffix, blobPath: doc.blob_path })
    }

    // 逐个上传，任一失败不影响其它文件。
    const uploadedIds: string[] = []
    for (const item of toUpload) {
      try {
        const buffer = await readBlob(item.blobPath)
        const form = new FormData()
        const blob = new Blob([new Uint8Array(buffer)], { type: mimeFor(item.suffix) })
        form.append("file", blob, item.name)
        const uploaded = await ragflowRequest<RagflowDocument[]>(creds, {
          method: "POST",
          path: `/datasets/${encodeURIComponent(targetDatasetId)}/documents`,
          body: form,
        })
        const docs = Array.isArray(uploaded) ? uploaded : []
        for (const d of docs) if (d.id) uploadedIds.push(d.id)
        imported.push(item.name)
      } catch (err) {
        failed.push({
          name: item.name,
          reason: err instanceof Error ? err.message : "上传失败",
        })
      }
    }

    // 触发解析。
    if (uploadedIds.length > 0) {
      try {
        await ragflowRequest(creds, {
          method: "POST",
          path: `/datasets/${encodeURIComponent(targetDatasetId)}/documents/parse`,
          json: { document_ids: uploadedIds },
        })
      } catch (err) {
        // 解析失败不阻断导入进度，记录到 failed。
        failed.push({
          name: "(触发解析)",
          reason: err instanceof Error ? err.message : "解析触发失败",
        })
      }
    }

    const nextOffset = offset + batch.length
    const done = nextOffset >= total

    return NextResponse.json({
      total,
      processed: nextOffset,
      nextOffset,
      done,
      imported,
      skipped,
      failed,
    })
  } catch (err) {
    return handleError(err)
  }
}
