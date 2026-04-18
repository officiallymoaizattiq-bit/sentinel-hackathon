import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const token = req.cookies.get("sentinel_session")?.value;
  const pathname = req.nextUrl.pathname;
  const protectedAdmin = pathname.startsWith("/admin");
  const protectedPatient = pathname.startsWith("/patient");
  if (!token && (protectedAdmin || protectedPatient)) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/admin/:path*", "/patient/:path*"],
};
