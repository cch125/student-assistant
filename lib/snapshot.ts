import { readFile } from "node:fs/promises"
import path from "node:path"

// 只读访问仓库中的 knowledge_base 快照。绝不修改这些文件。
const ROOT = process.cwd()
const KB_DIR = path.join(ROOT, "knowledge_base")

export type SnapshotDataset = {
  id: string
  name: string
  documents: number
  chunks: number
  path: string
}

export type SnapshotManifest = {
  exported_at?: string
  dataset_count?: number
  document_count?: number
  datasets: SnapshotDataset[]
}

export type SnapshotDocument = {
  id: string
  name: string
  blob_path?: string
  size?: number
  suffix?: string
  content_type?: string
}

export async function readManifest(): Promise<SnapshotManifest> {
  const raw = await readFile(path.join(KB_DIR, "manifest.json"), "utf-8")
  return JSON.parse(raw) as SnapshotManifest
}

/** 读取某个快照数据集下的全部文档条目（来自 documents.jsonl）。 */
export async function readSnapshotDocuments(datasetId: string): Promise<SnapshotDocument[]> {
  // 防止路径穿越：只接受纯十六进制 id。
  if (!/^[a-f0-9]+$/i.test(datasetId)) {
    throw new Error("非法的数据集 ID")
  }
  const file = path.join(KB_DIR, "datasets", datasetId, "documents.jsonl")
  let raw: string
  try {
    raw = await readFile(file, "utf-8")
  } catch {
    throw new Error("找不到该快照数据集")
  }
  const docs: SnapshotDocument[] = []
  for (const line of raw.split("\n")) {
    const trimmed = line.trim()
    if (!trimmed) continue
    try {
      const obj = JSON.parse(trimmed) as SnapshotDocument
      if (obj.blob_path) docs.push(obj)
    } catch {
      // 跳过损坏行
    }
  }
  return docs
}

/** 读取某个 blob 文件的二进制内容。blobPath 必须位于 knowledge_base 目录内。 */
export async function readBlob(blobPath: string): Promise<Buffer> {
  const normalized = path.normalize(blobPath).replace(/^(\.\.(\/|\\|$))+/, "")
  const full = path.join(KB_DIR, normalized)
  if (!full.startsWith(KB_DIR + path.sep)) {
    throw new Error("非法的文件路径")
  }
  return readFile(full)
}

const MIME_BY_SUFFIX: Record<string, string> = {
  md: "text/markdown",
  txt: "text/plain",
  pdf: "application/pdf",
  doc: "application/msword",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  xls: "application/vnd.ms-excel",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

export function mimeFor(suffix?: string): string {
  return MIME_BY_SUFFIX[(suffix ?? "").toLowerCase()] ?? "application/octet-stream"
}
