import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isProtectedPageRoute = createRouteMatcher([
  "/coach(.*)",
  "/interview(.*)",
  "/dashboard(.*)",
  "/reports(.*)",
  "/settings(.*)",
]);

const isProtectedApiRoute = createRouteMatcher([
  "/api(.*)",
  "/trpc(.*)",
]);

const isDevAuthBypassEnabled =
  process.env.NODE_ENV !== "production" && process.env.DEV_AUTH_BYPASS === "1";

export default clerkMiddleware(async (auth, req) => {
  if (isDevAuthBypassEnabled) {
    return;
  }

  if (isProtectedApiRoute(req)) {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ code: 401, msg: "unauthorized", data: null }, { status: 401 });
    }
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
    "/((?!_next|login|sign-up|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // 始终对 API 路由鉴权
    "/(api|trpc)(.*)",
  ],
};
