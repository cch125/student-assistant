import { NextRequest, NextResponse } from "next/server";
import { adminCredentials, createSession, SESSION_COOKIE } from "@/lib/auth";

export const runtime = "nodejs";

export async function POST(request: NextRequest) {
  const { username, password } = await request.json().catch(() => ({ username: "", password: "" }));
  const expected = adminCredentials();
  if (!expected.password) {
    return NextResponse.json({ ok: false, message: "管理员密码尚未配置。" }, { status: 500 });
  }
  if (String(username || "").trim() !== expected.username || String(password || "") !== expected.password) {
    return NextResponse.json({ ok: false, message: "账号或密码错误。" }, { status: 401 });
  }
  const response = NextResponse.json({ ok: true, user: { username: expected.username, role: "admin" } });
  response.cookies.set(SESSION_COOKIE, createSession(expected.username), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production" && process.env.ALLOW_LOCAL_RAGFLOW !== "1",
    path: "/",
    maxAge: 60 * 60 * 8
  });
  return response;
}
