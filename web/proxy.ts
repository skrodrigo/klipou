import { type NextRequest, NextResponse } from "next/server";
import { BACKEND_BASE_URL } from "./infra/http";

const protectedRoutes = [
  "/dashboard",
  "/profile",
  "/upgrade",
  "/video-settings",
  "/processing",
  "/clips",
];

export async function proxy(request: NextRequest) {
  try {
    const cookies = request.headers.get("cookie") || "";
    const { pathname } = request.nextUrl;

    const authResponse = await fetch(`${BACKEND_BASE_URL}/api/auth/me/`, {
      method: "GET",
      headers: {
        cookie: cookies,
      },
      cache: "no-store",
    });

    if (!authResponse.ok) {
      return NextResponse.redirect(new URL("/auth/register", request.url));
    }

    const user = await authResponse.json();
    const onboardingCompleted = user.onboarding_completed === true;

    // Se está em /onboarding e já completou, redireciona para /dashboard
    if (pathname === "/onboarding" && onboardingCompleted) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }

    // Se está em rota protegida e não completou onboarding, redireciona para /onboarding
    if (protectedRoutes.some((route) => pathname.startsWith(route))) {
      if (!onboardingCompleted) {
        return NextResponse.redirect(new URL("/onboarding", request.url));
      }
    }

    return NextResponse.next();
  } catch (error) {
    return NextResponse.redirect(new URL("/auth/register", request.url));
  }
}

export const config = {
  matcher: ["/", "/dashboard(.*)", "/profile(.*)", "/upgrade(.*)", "/video-settings(.*)", "/processing(.*)", "/clips(.*)", "/onboarding(.*)"],
};