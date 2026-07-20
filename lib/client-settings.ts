"use client"

// 凭据存储策略：
// - API Key 默认只写入 sessionStorage（关闭标签页即失效）。
// - 仅当用户主动勾选“在此浏览器记住”时，才镜像到 localStorage。
// - API Key 绝不会发送到本项目自身的数据库或日志，仅在调用时通过请求头转发给用户自己的 RAGFlow。
// - 非敏感项（地址、所选知识库）保存在 localStorage 方便下次使用。

const KEY_API = "jnu.ragflow.apiKey"
const KEY_URL = "jnu.ragflow.baseUrl"
const KEY_QA = "jnu.ragflow.qaDatasetId"
const KEY_NOTICE = "jnu.ragflow.noticeDatasetId"
const KEY_REMEMBER = "jnu.ragflow.remember"

export type Settings = {
  baseUrl: string
  apiKey: string
  qaDatasetId: string
  noticeDatasetId: string
  remember: boolean
}

export const emptySettings: Settings = {
  baseUrl: "",
  apiKey: "",
  qaDatasetId: "",
  noticeDatasetId: "",
  remember: false,
}

function safeGet(storage: Storage | undefined, key: string): string {
  try {
    return storage?.getItem(key) ?? ""
  } catch {
    return ""
  }
}

export function loadSettings(): Settings {
  if (typeof window === "undefined") return emptySettings

  const remember = safeGet(window.localStorage, KEY_REMEMBER) === "1"
  // API Key：优先 sessionStorage；记住时回退到 localStorage。
  const apiKey =
    safeGet(window.sessionStorage, KEY_API) ||
    (remember ? safeGet(window.localStorage, KEY_API) : "")

  return {
    apiKey,
    remember,
    baseUrl: safeGet(window.localStorage, KEY_URL) || safeGet(window.sessionStorage, KEY_URL),
    qaDatasetId:
      safeGet(window.localStorage, KEY_QA) || safeGet(window.sessionStorage, KEY_QA),
    noticeDatasetId:
      safeGet(window.localStorage, KEY_NOTICE) || safeGet(window.sessionStorage, KEY_NOTICE),
  }
}

export function saveSettings(settings: Settings): void {
  if (typeof window === "undefined") return

  // 非敏感配置持久化。
  window.localStorage.setItem(KEY_URL, settings.baseUrl)
  window.localStorage.setItem(KEY_QA, settings.qaDatasetId)
  window.localStorage.setItem(KEY_NOTICE, settings.noticeDatasetId)

  // API Key 始终写入 sessionStorage。
  window.sessionStorage.setItem(KEY_API, settings.apiKey)

  if (settings.remember) {
    window.localStorage.setItem(KEY_REMEMBER, "1")
    window.localStorage.setItem(KEY_API, settings.apiKey)
  } else {
    window.localStorage.setItem(KEY_REMEMBER, "0")
    window.localStorage.removeItem(KEY_API)
  }
}

export function clearCredentials(): void {
  if (typeof window === "undefined") return
  window.sessionStorage.removeItem(KEY_API)
  window.localStorage.removeItem(KEY_API)
  window.localStorage.setItem(KEY_REMEMBER, "0")
}

/** 构造调用本项目 Server API 所需的请求头（携带用户自己的 RAGFlow 凭据）。 */
export function authHeaders(settings: Pick<Settings, "baseUrl" | "apiKey">): HeadersInit {
  return {
    "x-ragflow-url": settings.baseUrl,
    "x-ragflow-key": settings.apiKey,
  }
}

export function hasCredentials(settings: Settings): boolean {
  return Boolean(settings.baseUrl && settings.apiKey)
}
