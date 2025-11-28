import { type NextRequest, NextResponse } from "next/server";
import { BACKEND_BASE_URL } from "./infra/http";

export async function proxy(request: NextRequest) {
  try {
    const cookies = request.headers.get("cookie") || "";

    const response = await fetch(`${BACKEND_BASE_URL}/api/auth/me/`, {
      method: "GET",
      headers: {
        cookie: cookies,
      },
    });

    if (!response.ok) {
      return NextResponse.redirect(new URL("/auth/register", request.url));
    }

    return NextResponse.next();
  } catch (error) {
    return NextResponse.redirect(new URL("/auth/register", request.url));
  }
}

export const config = {
  matcher: ["/", "/dashboard(.*)"],
};