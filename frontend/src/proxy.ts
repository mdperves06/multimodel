import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "acc_session";
const PRIVATE = ["/dashboard", "/accounts", "/jobs", "/gallery", "/usage", "/settings"];
const AUTH_ONLY = ["/login", "/register"];

// Optimistic check only (cookie present). The API enforces real authentication on every call.
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = request.cookies.has(SESSION_COOKIE);
  const isPrivate = PRIVATE.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  if (isPrivate && !hasSession) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  const expired = request.nextUrl.searchParams.has("expired");
  if ((AUTH_ONLY.includes(pathname) || pathname === "/") && hasSession && !expired) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/login", "/register", "/dashboard/:path*", "/accounts/:path*", "/jobs/:path*", "/gallery/:path*", "/usage/:path*", "/settings/:path*"],
};
