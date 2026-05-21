# 前端 HTTP 请求封装设计

> 状态：已确认
> 日期：2026-05-19
> 关联：M1 里程碑

---

## 1. 目标

为 Next.js 前端封装 HTTP 请求层，统一处理 baseURL、Clerk JWT 注入、超时、错误处理、SSE 流式连接。

## 2. 方案

纯 `fetch` 轻量封装，零额外依赖。分为两个模块：

| 模块 | 文件 | 用途 |
|---|---|---|
| REST 客户端 | `lib/api-client.ts` | GET/POST 请求，token 注入，超时，错误处理 |
| SSE 客户端 | `lib/sse.ts` | EventSource 封装，token 注入，自动重连 |

## 3. api-client.ts

### 3.1 核心函数

```ts
async function apiClient<T>(path: string, config?: RequestConfig): Promise<T>
```

`path` 为相对于 `/api/backend` 的路径，如 `/v1/health`。

### 3.2 RequestConfig

```ts
interface RequestConfig {
  method?: "GET" | "POST";
  body?: unknown;       // 自动 JSON.stringify
  timeout?: number;     // 默认 30000ms
  headers?: Record<string, string>;
}
```

### 3.3 请求流程

1. 调 `getToken()`（Clerk）获取 JWT
2. token 为 null → 跳转 `/sign-in`，抛 `ApiError(401, "请重新登录")`
3. 构造 `fetch(url, { method, headers, body, signal })`
4. signal 来自 `AbortController`，默认 30s 超时
5. 响应 401 → 跳转 `/sign-in`，抛 `ApiError(401, "认证已过期")`
6. 响应非 2xx → 解析后端错误体，抛 `ApiError(status, data)`
7. 响应 2xx → `res.json()` 返回

### 3.4 ApiError

```ts
class ApiError extends Error {
  status: number;
  data: unknown;
}
```

## 4. sse.ts

### 4.1 架构

`EventSource` 不支持自定义 HTTP header，无法直接带 Clerk token。采用 **Next.js API Route 代理** 方案：

```
浏览器 EventSource
  → /api/sse-proxy?target=/v1/interview/{id}/stream
    → Next.js Route Handler（服务端注入 Authorization header）
      → backend /api/v1/interview/{id}/stream
```

### 4.2 代理路由

新建 `app/api/sse-proxy/route.ts`，在 Route Handler 中：
1. 读取 `getToken()` 获取 JWT
2. 转发到后端 SSE 端点，带上 `Authorization: Bearer xxx`
3. 将后端的 `ReadableStream` pipe 到 response

### 4.3 connectSSE 函数

```ts
function connectSSE(path: string, options: SSEOptions): () => void
```

- `path`：后端 SSE 端点路径，如 `/v1/interview/session-123/stream`
- 返回 unsubscribe 函数，调用后断开连接

### 4.4 SSEOptions

```ts
interface SSEOptions {
  onToken?: (token: string) => void;  // event: token
  onDone?: () => void;                 // event: done
  onError?: (err: Error) => void;      // 连接失败/中断
  maxRetries?: number;                 // 默认 3
}
```

### 4.5 重连策略

- 连接中断后自动重连，最多 `maxRetries` 次
- 指数退避：1s → 2s → 4s
- 重试耗尽后调用 `onError`
- 手动调用 unsubscribe 断开不触发重连

## 5. 鉴权处理

### 5.1 Token 刷新

Clerk `getToken()` 内部自动处理 refresh token rotation，我们不需要手动攥写 refresh 逻辑。

### 5.2 失效处理

两个场景统一处理：

1. `getToken()` 返回 null（session 完全过期）
2. 后端返回 401（边缘情况，如服务端 token 校验失败）

统一操作：`window.location.href = "/sign-in"` + 抛出 `ApiError`

## 6. 文件清单

```
frontend/
├── app/api/sse-proxy/route.ts   # 新建：SSE 代理路由
├── lib/
│   ├── utils.ts                 # 已有
│   ├── api-client.ts            # 新建
│   └── sse.ts                   # 新建
```

## 7. 测试策略

- `api-client.ts`：单元测试，mock `fetch`，覆盖正常/超时/401/非2xx
- `sse.ts`：单元测试，mock `EventSource`
- 集成测试：启动后端，真实调用 health 端点验证通联
