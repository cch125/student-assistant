import { NextRequest, NextResponse } from "next/server";

const SESSION_COOKIE = "student_assistant_session";
const protectedPrefixes = ["/settings", "/documents", "/history"];

export function proxy(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (!protectedPrefixes.some(prefix => pathname === prefix || pathname.startsWith(`${prefix}/`))) {
    return NextResponse.next();
  }
  if (request.cookies.get(SESSION_COOKIE)?.value) return NextResponse.next();
  const loginUrl = new URL("/login", request.url);
  loginUrl.searchParams.set("next", pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/settings/:path*", "/documents/:path*", "/history/:path*"]
};
