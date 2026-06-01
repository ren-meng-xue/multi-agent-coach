import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const loginPagePath = resolve("app/login/[[...login]]/page.tsx");
const signUpPagePath = resolve("app/sign-up/[[...sign-up]]/page.tsx");
const layoutPath = resolve("app/layout.tsx");
const middlewarePath = resolve("middleware.ts");
const shellPath = resolve("app/components/app-shell.tsx");
const authPagePath = resolve("app/components/auth-page.tsx");
const authCardRouterPath = resolve("app/components/auth-card-router.tsx");
const page = [
  existsSync(loginPagePath) ? readFileSync(loginPagePath, "utf8") : "",
  existsSync(signUpPagePath) ? readFileSync(signUpPagePath, "utf8") : "",
  existsSync(layoutPath) ? readFileSync(layoutPath, "utf8") : "",
  existsSync(middlewarePath) ? readFileSync(middlewarePath, "utf8") : "",
  existsSync(shellPath) ? readFileSync(shellPath, "utf8") : "",
  existsSync(authPagePath) ? readFileSync(authPagePath, "utf8") : "",
  existsSync(authCardRouterPath) ? readFileSync(authCardRouterPath, "utf8") : "",
].join("\n");

const requiredRoutes = [
  "app/login/[[...login]]/page.tsx",
  "app/coach/page.tsx",
  "app/interview/page.tsx",
  "app/dashboard/page.tsx",
  "app/settings/page.tsx",
  "app/not-found.tsx",
  "app/components/auth-page.tsx",
  "app/components/auth-card-router.tsx",
  "app/sign-up/[[...sign-up]]/page.tsx",
];

const requiredSnippets = [
  "AI-Powered Interview Coach",
  "你的",
  "AI 面试陪练",
  "数字分身",
  "8 角色多 Agent 协作",
  "跨会话分级长期记忆",
  "Reflexion 自反思引擎",
  "to continue to Multi Agent Coach",
  "/vite.svg",
  "auth-split",
  "clerk-card",
  "ClerkProvider",
  "telemetry={false}",
  "suppressHydrationWarning",
  "ClerkLoading",
  "ClerkLoaded",
  "AuthCardSkeleton",
  "AuthCardRouter",
  "onClickCapture",
  "data-auth-card-router",
  "SignIn",
  "SignUp",
  'routing="path"',
  'path="/login"',
  'path="/sign-up"',
  "UserButton",
  "auth(",
  "auth.protect",
  "unauthenticatedUrl",
  "redirect_url",
  "/sign-up",
];

const missing = requiredSnippets.filter((snippet) => !page.includes(snippet));
const missingRoutes = requiredRoutes.filter((route) => !existsSync(resolve(route)));

if (missing.length > 0 || missingRoutes.length > 0) {
  if (missing.length > 0) {
    console.error(`登录页实现缺少关键片段: ${missing.join(", ")}`);
  }
  if (missingRoutes.length > 0) {
    console.error(`缺少路由页面: ${missingRoutes.join(", ")}`);
  }
  process.exit(1);
}

console.log("登录页与 5 个路由检查通过");
