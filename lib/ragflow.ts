import { assertSafeRagflowUrl, UrlGuardError } from "./url-guard"

export type RagflowCredentials = {
  baseUrl: string
  apiKey: string
}

export class RagflowError extends Error {
  status: number
  constructor(message: string, status = 502) {
    super(message)
    this.status = status
  }
}

const HEADER_URL = "x-ragflow-url"
const HEADER_KEY = "x-ragflow-key"

/**
 * 从请求头读取本次调用所需的 RAGFlow 凭据。
 * 凭据仅存在于本次请求的内存中，绝不落盘、绝不记录日志。
 */
export async function readCredentials(req: Request): Promise<RagflowCredentials> {
  const rawUrl = req.headers.get(HEADER_URL) ?? ""
  const apiKey = (req.headers.get(HEADER_KEY) ?? "").trim()

  if (!apiKey) {
    throw new RagflowError("缺少 RAGFlow API Key，请先在“连接与导入”中配置", 400)
  }

  let baseUrl: string
  try {
    baseUrl = await assertSafeRagflowUrl(rawUrl)
  } catch (err) {
    if (err instanceof UrlGuardError) {
      throw new RagflowError(err.message, 400)
    }
    throw err
  }

  return { baseUrl, apiKey }
}

type RequestOptions = {
  method?: string
  path: string
  query?: Record<string, string | number | boolean | undefined>
  json?: unknown
  body?: BodyInit
  headers?: Record<string, string>
  signal?: AbortSignal
}

/**
 * 统一发起 RAGFlow REST 调用。RAGFlow 响应形如 { code, data, message }。
 */
export async function ragflowRequest<T = unknown>(
  creds: RagflowCredentials,
  options: RequestOptions,
): Promise<T> {
  const url = new URL(`/api/v1${options.path}`, creds.baseUrl)
  if (options.query) {
    for (const [key, value] of Object.entries(options.query)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${creds.apiKey}`,
    ...options.headers,
  }

  let body = options.body
  if (options.json !== undefined) {
    headers["Content-Type"] = "application/json"
    body = JSON.stringify(options.json)
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30000)

  let response: Response
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal ?? controller.signal,
      redirect: "error", // 禁止跟随重定向，避免绕过 SSRF 校验
      cache: "no-store",
    })
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new RagflowError("连接 RAGFlow 超时，请检查地址与网络", 504)
    }
    throw new RagflowError("无法连接到 RAGFlow 服务，请检查地址是否正确", 502)
  } finally {
    clearTimeout(timeout)
  }

  const text = await response.text()
  let payload: { code?: number; data?: T; message?: string } = {}
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch {
      throw new RagflowError("RAGFlow 返回了无法解析的响应", 502)
    }
  }

  if (!response.ok) {
    throw new RagflowError(
      payload.message || `RAGFlow 请求失败（HTTP ${response.status}）`,
      response.status === 401 || response.status === 403 ? 401 : 502,
    )
  }

  // RAGFlow 业务错误码：非 0 视为失败
  if (typeof payload.code === "number" && payload.code !== 0) {
    throw new RagflowError(payload.message || `RAGFlow 返回错误码 ${payload.code}`, 502)
  }

  return payload.data as T
}

export type RagflowDataset = {
  id: string
  name: string
  description?: string
  document_count?: number
  chunk_count?: number
  embedding_model?: string
  chunk_method?: string
  create_date?: string
  update_date?: string
}

export type RagflowDocument = {
  id: string
  name: string
  run?: string
  status?: string
  chunk_count?: number
  token_count?: number
  size?: number
  type?: string
  create_date?: string
  update_date?: string
  progress?: number
  progress_msg?: string
}

export type RagflowChunk = {
  content?: string
  content_with_weight?: string
  document_keyword?: string
  document_name?: string
  document_id?: string
  similarity?: number
  vector_similarity?: number
  term_similarity?: number
  highlight?: string
}

export async function listDatasets(creds: RagflowCredentials): Promise<RagflowDataset[]> {
  const data = await ragflowRequest<RagflowDataset[]>(creds, {
    path: "/datasets",
    query: { page: 1, page_size: 200 },
  })
  return Array.isArray(data) ? data : []
}

export async function listDocuments(
  creds: RagflowCredentials,
  datasetId: string,
): Promise<{ docs: RagflowDocument[]; total: number }> {
  const data = await ragflowRequest<{ docs?: RagflowDocument[]; total?: number }>(creds, {
    path: `/datasets/${encodeURIComponent(datasetId)}/documents`,
    query: { page: 1, page_size: 200, orderby: "create_time", desc: true },
  })
  return { docs: data?.docs ?? [], total: data?.total ?? 0 }
}

export async function retrieve(
  creds: RagflowCredentials,
  params: {
    question: string
    datasetIds: string[]
    topK?: number
    similarityThreshold?: number
    vectorWeight?: number
    pageSize?: number
  },
): Promise<RagflowChunk[]> {
  const data = await ragflowRequest<{ chunks?: RagflowChunk[] }>(creds, {
    method: "POST",
    path: "/retrieval",
    json: {
      question: params.question,
      dataset_ids: params.datasetIds,
      page: 1,
      page_size: params.pageSize ?? 6,
      top_k: params.topK ?? 1024,
      similarity_threshold: params.similarityThreshold ?? 0.2,
      vector_similarity_weight: params.vectorWeight ?? 0.3,
      keyword: false,
      highlight: true,
    },
  })
  return data?.chunks ?? []
}
