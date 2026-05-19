import { clerkMiddleware } from "@clerk/nextjs/server";

export default clerkMiddleware();

export const config = {
  matcher: [
    // 跳过 Next.js 内部资源和静态文件，其他请求都过 Clerk
    "/((?!_next/static|_next/image|favicon.ico).*)",
    // 始终对 API 路由鉴权
    "/(api|trpc)(.*)",
  ],
};
