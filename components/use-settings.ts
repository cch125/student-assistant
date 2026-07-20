"use client"

import { useCallback, useEffect, useState } from "react"
import { emptySettings, loadSettings, type Settings } from "@/lib/client-settings"

/**
 * 读取浏览器中保存的 RAGFlow 设置。
 * 首帧返回空值以避免 SSR/CSR 不一致，挂载后再同步真实值。
 */
export function useSettings() {
  const [settings, setSettings] = useState<Settings>(emptySettings)
  const [ready, setReady] = useState(false)

  const refresh = useCallback(() => {
    setSettings(loadSettings())
  }, [])

  useEffect(() => {
    setSettings(loadSettings())
    setReady(true)

    const onStorage = () => setSettings(loadSettings())
    window.addEventListener("storage", onStorage)
    window.addEventListener("jnu:settings-updated", onStorage)
    return () => {
      window.removeEventListener("storage", onStorage)
      window.removeEventListener("jnu:settings-updated", onStorage)
    }
  }, [])

  return { settings, ready, refresh }
}
