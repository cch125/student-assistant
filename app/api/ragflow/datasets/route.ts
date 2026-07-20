import { NextResponse } from "next/server"
import { readCredentials, listDatasets } from "@/lib/ragflow"
import { handleError } from "@/lib/api"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(req: Request) {
  try {
    const creds = await readCredentials(req)
    const datasets = await listDatasets(creds)
    return NextResponse.json({
      datasets: datasets.map((d) => ({
        id: d.id,
        name: d.name,
        description: d.description ?? "",
        documentCount: d.document_count ?? 0,
        chunkCount: d.chunk_count ?? 0,
        embeddingModel: d.embedding_model ?? "",
        chunkMethod: d.chunk_method ?? "",
        updateDate: d.update_date ?? "",
      })),
    })
  } catch (err) {
    return handleError(err)
  }
}
