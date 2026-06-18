import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

function getSecret() {
  const raw = process.env.AUTH_SECRET;
  if (!raw) throw new Error("AUTH_SECRET env var is required");
  return new TextEncoder().encode(raw);
}

const PUBLIC_PREFIXES = ["/login", "/webhook"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("session")?.value;

  // Redirect logged-in users away from login page
  if (pathname === "/login") {
    if (token) {
      try {
        await jwtVerify(token, getSecret());
        return NextResponse.redirect(new URL("/", request.url));
      } catch {
        // invalid token — let them see the login page
      }
    }
    return NextResponse.next();
  }

  // Webhooks are public (called by external services)
  if (pathname.startsWith("/webhook")) {
    return NextResponse.next();
  }

  // Everything else requires auth
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    await jwtVerify(token, getSecret());
    return NextResponse.next();
  } catch {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("session");
    return response;
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
