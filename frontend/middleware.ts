import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedPageRoute = createRouteMatcher([
  "/coach(.*)",
  "/interview(.*)",
  "/dashboard(.*)",
  "/settings(.*)",
]);

const isDevAuthBypassEnabled =
  process.env.NODE_ENV !== "production" && process.env.DEV_AUTH_BYPASS === "1";

export default clerkMiddleware(async (auth, req) => {
  if (isDevAuthBypassEnabled) {
    return;
  }

  if (isProtectedPageRoute(req)) {
    const signInUrl = new URL("/login", req.url);
    signInUrl.searchParams.set("redirect_url", req.url);
    await auth.protect({ unauthenticatedUrl: signInUrl.toString() });
  }
});

export const config = {
  matcher: [
    // 跳过 Next.js 内部资源、静态文件、以及登录/注册公开页面（避免 Clerk dev 握手拖慢首屏）
    "/((?!_next|healthz|login|sign-up|[^?]*\\.(?:prototype?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // 始终对 API 路由鉴权
    "/(api|trpc)(.*)",
  ],
};
