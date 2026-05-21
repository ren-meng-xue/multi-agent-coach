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

export default clerkMiddleware(async (auth, req) => {
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
    // 跳过 Next.js 内部资源和静态文件，其他请求都过 Clerk
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    // 始终对 API 路由鉴权
    "/(api|trpc)(.*)",
  ],
};
