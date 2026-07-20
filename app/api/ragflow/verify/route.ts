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
      ok: true,
      datasetCount: datasets.length,
      datasets: datasets.map((d) => ({
        id: d.id,
        name: d.name,
        documentCount: d.document_count ?? 0,
      })),
    })
  } catch (err) {
    return handleError(err)
  }
}
