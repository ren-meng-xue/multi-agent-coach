# Frontend Conventions

## 运行

```bash
cd frontend
pnpm install
pnpm dev        # localhost:3000
pnpm test       # vitest run
pnpm typecheck  # tsc --noEmit
```

## 技术栈

- Next.js 16（App Router）
- React 19（含 RSC / Server Actions）
- TypeScript 严格模式
- Clerk（`@clerk/nextjs`）做 auth
- shadcn/ui（`@base-ui/react` + `tailwind 4`）
- recharts 做图表
- vitest + @testing-library 做测试（jsdom 环境）

## 目录约定

| 目录 | 用途 |
|---|---|
| `app/<segment>/` | 业务页面；每段一个子目录 |
| `app/<segment>/_components/` | 该段私有组件（下划线前缀，Next.js 不路由） |
| `app/components/` | 跨段共享组件（导航等） |
| `components/ui/` | shadcn/ui 生成的组件，不要手改 |
| `lib/` | 客户端工具：sse、interview-chat、coach API、user 等 |

## 数据流

- 默认 RSC + Server Action
- SSE / WebSocket 类的实时数据用 `lib/sse.ts`（含自动重连）
- 不直接 fetch 后端 URL——封装到 `lib/<domain>.ts`，统一 baseURL 与鉴权头

## 鉴权

- `middleware.ts` 配置受保护路由
- 服务端组件用 `@clerk/nextjs/server` 的 `auth()`
- 客户端组件用 `useAuth()` / `useUser()`
- Server Action 里直接读 `auth()` 拿 userId，不要从前端传

## 样式

- Tailwind 4，**不要**写 css module
- 主题色 / 间距走 tailwind config，不要硬编码十六进制
- shadcn 组件 props 改样式优先用 `className` 合并（`clsx` + `tailwind-merge`）

## 测试

- 单测文件与源同目录：`foo.ts` + `foo.test.ts`
- React 组件用 `@testing-library/react` + `userEvent`
- `scripts/assert-login-page.mjs` 是关键文件存在性 check，加新关键路由时要扩展
