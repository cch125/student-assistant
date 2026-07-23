import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { readSession, SESSION_COOKIE } from "@/lib/auth";

export async function GET() {
  const cookieStore = await cookies();
  const session = readSession(cookieStore.get(SESSION_COOKIE)?.value);
  return NextResponse.json({
    ok: true,
    authenticated: Boolean(session),
    user: session ? { username: session.username, role: session.role } : null
  });
}
