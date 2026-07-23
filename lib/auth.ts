import { createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "student_assistant_session";

type SessionPayload = {
  username: string;
  role: "admin";
  exp: number;
};

function authSecret(): string {
  const value = process.env.AUTH_SECRET || "";
  if (value.length >= 24) return value;
  return "local-student-assistant-development-secret";
}

function sign(value: string): string {
  return createHmac("sha256", authSecret()).update(value).digest("base64url");
}

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function adminCredentials() {
  return {
    username: process.env.ADMIN_USERNAME || "cch125",
    password: process.env.ADMIN_PASSWORD || ""
  };
}

export function createSession(username: string): string {
  const payload: SessionPayload = {
    username,
    role: "admin",
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 8
  };
  const body = Buffer.from(JSON.stringify(payload), "utf8").toString("base64url");
  const nonce = randomBytes(8).toString("base64url");
  const unsigned = `${body}.${nonce}`;
  return `${unsigned}.${sign(unsigned)}`;
}

export function readSession(token?: string): SessionPayload | null {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [body, nonce, signature] = parts;
  const unsigned = `${body}.${nonce}`;
  if (!safeEqual(signature, sign(unsigned))) return null;
  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as SessionPayload;
    if (payload.role !== "admin" || payload.exp < Math.floor(Date.now() / 1000)) return null;
    return payload;
  } catch {
    return null;
  }
}
