import { NextResponse } from "next/server"
import { readManifest } from "@/lib/snapshot"
import { handleError } from "@/lib/api"

export const runtime = "nodejs"

export async function GET() {
  try {
    const manifest = await readManifest()
    return NextResponse.json({
      exportedAt: manifest.exported_at ?? "",
      documentCount: manifest.document_count ?? 0,
      datasets: (manifest.datasets ?? []).map((d) => ({
        id: d.id,
        name: d.name,
        documents: d.documents ?? 0,
        chunks: d.chunks ?? 0,
      })),
    })
  } catch (err) {
    return handleError(err)
  }
}
