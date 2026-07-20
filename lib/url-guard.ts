import { lookup } from "node:dns/promises"
import net from "node:net"

// 将 RAGFlow 地址限制为「公网 HTTPS」，防止 SSRF：
// - 仅允许 https
// - 禁止 localhost / 环回 / 内网 / 链路本地 / 保留地址
// - 通过 DNS 解析后再次校验所有解析结果，抵御 DNS rebinding

export class UrlGuardError extends Error {}

function ipIsPrivate(ip: string): boolean {
  const type = net.isIP(ip)
  if (type === 4) {
    const parts = ip.split(".").map((n) => Number.parseInt(n, 10))
    const [a, b] = parts
    if (a === 10) return true
    if (a === 127) return true
    if (a === 0) return true
    if (a === 169 && b === 254) return true // 链路本地
    if (a === 172 && b >= 16 && b <= 31) return true
    if (a === 192 && b === 168) return true
    if (a === 100 && b >= 64 && b <= 127) return true // CGNAT
    if (a >= 224) return true // 组播/保留
    return false
  }
  if (type === 6) {
    const lower = ip.toLowerCase()
    if (lower === "::1" || lower === "::") return true
    if (lower.startsWith("fe80")) return true // 链路本地
    if (lower.startsWith("fc") || lower.startsWith("fd")) return true // 唯一本地地址
    // IPv4 映射地址 ::ffff:a.b.c.d
    const mapped = lower.match(/::ffff:(\d+\.\d+\.\d+\.\d+)/)
    if (mapped) return ipIsPrivate(mapped[1])
    return false
  }
  return true
}

const BLOCKED_HOSTNAMES = new Set([
  "localhost",
  "localhost.localdomain",
  "ip6-localhost",
  "metadata",
  "metadata.google.internal",
])

/**
 * 校验并规范化用户提供的 RAGFlow 基础地址。
 * 返回规范化后的 origin（不含末尾斜杠）。
 */
export async function assertSafeRagflowUrl(rawUrl: string): Promise<string> {
  if (!rawUrl || typeof rawUrl !== "string") {
    throw new UrlGuardError("缺少 RAGFlow 地址")
  }

  let url: URL
  try {
    url = new URL(rawUrl.trim())
  } catch {
    throw new UrlGuardError("RAGFlow 地址格式无效，请填写完整的 https:// 地址")
  }

  if (url.protocol !== "https:") {
    throw new UrlGuardError("仅允许使用 HTTPS 地址访问 RAGFlow")
  }

  const hostname = url.hostname.toLowerCase().replace(/^\[|\]$/g, "")

  if (BLOCKED_HOSTNAMES.has(hostname) || hostname.endsWith(".localhost")) {
    throw new UrlGuardError("禁止访问本机或内网地址")
  }

  // 若主机名本身是 IP，直接校验
  if (net.isIP(hostname)) {
    if (ipIsPrivate(hostname)) {
      throw new UrlGuardError("禁止访问本机、内网或保留 IP 地址")
    }
  } else {
    // 通过 DNS 解析，校验所有解析结果
    let records: { address: string }[]
    try {
      records = await lookup(hostname, { all: true })
    } catch {
      throw new UrlGuardError("无法解析该域名，请检查地址是否正确")
    }
    if (records.length === 0) {
      throw new UrlGuardError("无法解析该域名")
    }
    for (const record of records) {
      if (ipIsPrivate(record.address)) {
        throw new UrlGuardError("该域名解析到内网或保留地址，已被拒绝")
      }
    }
  }

  return url.origin
}
