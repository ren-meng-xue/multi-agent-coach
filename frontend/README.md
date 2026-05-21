# Multi Agent Coach 前端

这是 Multi Agent Coach 的前端应用，基于 Next.js App Router 构建，负责登录注册、主导航、面试陪练、教练台、报告和设置等页面。

## 技术栈

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS 4
- shadcn/ui
- lucide-react
- Clerk 认证
- Vitest + Testing Library

## 本地启动

首次启动前先安装依赖：

```bash
pnpm install
```

复制环境变量示例并填入真实配置：

```bash
cp .env.example .env.local
```

启动开发服务：

```bash
pnpm dev
```

默认访问地址：

```text
http://localhost:3000
```

后端本地默认地址为：

```text
http://localhost:8000
```

当前 `next.config.ts` 会把 `/api/backend/:path*` 代理到 `http://localhost:8000/api/:path*`，用于开发阶段规避跨域问题。

## 常用命令

```bash
pnpm dev
pnpm test
pnpm test:watch
pnpm typecheck
pnpm build
pnpm start
```

说明：

- `pnpm dev`：启动本地开发服务。
- `pnpm test`：运行 Vitest 测试。
- `pnpm test:watch`：以 watch 模式运行测试。
- `pnpm typecheck`：运行 TypeScript 类型检查。
- `pnpm build`：执行生产构建。
- `pnpm start`：启动生产构建后的服务。

## 目录说明

```text
frontend/
├── app/                 # Next.js App Router 页面与布局
├── app/components/      # 当前前端业务组件
├── components/ui/       # shadcn/ui 组件
├── lib/                 # 通用工具函数
├── public/              # 静态资源
├── scripts/             # 项目脚本
├── middleware.ts        # Clerk 认证中间件
├── vitest.config.ts     # 前端测试配置
└── components.json      # shadcn/ui 配置
```

## 与根目录规范的关系

本文件只维护前端专项说明；全仓库工程规则以根目录 `CLAUDE.md` 为准。前端开发时重点注意：

- 组件优先使用 shadcn/ui，图标优先使用 lucide-react。
- 不新增 UI 依赖，除非已经明确评估并获得同意。
- 保持组件职责单一，避免巨型组件和深层 prop drilling。
- 复杂业务逻辑不要堆在组件内，优先放到 hooks、services 或 server actions。
- 用户可见流程必须考虑 loading、error、empty state。
- 公共函数需要说明用途；复杂逻辑注释解释原因、风险和边界条件。
- 新功能至少覆盖 success case 和 failure case；bug 修复需要补 regression test。

## 依赖与 lockfile

项目当前使用 pnpm 工作流，并维护 `pnpm-lock.yaml`。新增、升级或删除依赖时，需要使用 pnpm 更新 lockfile：

```bash
pnpm install
```

不要用 npm 生成新的依赖锁文件，避免 `package.json` 与 `pnpm-lock.yaml` 不一致，导致 `pnpm install --frozen-lockfile` 在 CI 或部署环境失败。

## 环境变量

参考 `.env.example`：

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=
CLERK_SECRET_KEY=
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/login
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FORCE_REDIRECT_URL=/dashboard
NEXT_PUBLIC_CLERK_SIGN_UP_FORCE_REDIRECT_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_OUT_URL=/login
NEXT_PUBLIC_API_URL=http://localhost:8000
```

注意不要提交真实密钥。

## 提交前检查

前端修改提交前至少运行：

```bash
pnpm test
pnpm typecheck
pnpm build
```

如果改动只影响文档，可以不跑前端构建，但需要确认 Markdown 内容准确、命令与项目实际脚本一致。
