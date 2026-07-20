import { NextResponse } from "next/server"
import { RagflowError } from "./ragflow"

export function jsonError(message: string, status = 400) {
  return NextResponse.json({ error: message }, { status })
}

/** 将各类错误统一转换为安全的 JSON 响应，避免泄露内部细节。 */
export function handleError(err: unknown) {
  if (err instanceof RagflowError) {
    return jsonError(err.message, err.status)
  }
  if (err instanceof Error) {
    return jsonError(err.message || "请求处理失败", 500)
  }
  return jsonError("未知错误", 500)
}
