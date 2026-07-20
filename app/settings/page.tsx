"use client"

import { useState } from "react"
import { ConnectionForm } from "@/components/connection-form"
import { ImportPanel } from "@/components/import-panel"

type DatasetOption = { id: string; name: string; documentCount?: number }

export default function SettingsPage() {
  const [datasets, setDatasets] = useState<DatasetOption[]>([])

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-balance text-xl font-semibold tracking-tight sm:text-2xl">
          连接与导入
        </h1>
        <p className="mt-2 text-pretty text-sm leading-relaxed text-muted-foreground">
          配置各自的 RAGFlow 连接、选择问答与通知知识库，并把仓库中的知识库快照导入 RAGFlow。
        </p>
      </header>

      <ConnectionForm onDatasetsLoaded={(list) => setDatasets(list)} />
      <ImportPanel targets={datasets} />
    </div>
  )
}
