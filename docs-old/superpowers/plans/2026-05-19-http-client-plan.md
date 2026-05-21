# 前端 HTTP 请求封装 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 封装前端 HTTP 请求层，统一处理 baseURL、Clerk JWT 注入、超时、错误处理、SSE 流式连接。

**Architecture:** 纯 fetch 轻量封装，分两个模块——`api-client.ts` 处理 REST 请求，`sse.ts` 处理 SSE 流式连接。SSE 鉴权通过 Next.js Route Handler 代理解决（EventSource 不支持自定义 header）。

**Tech Stack:** Next.js 16 (App Router), TypeScript 5, fetch, EventSource, vitest + @testing-library/react

---

## 文件清单

| 操作 | 路径 | 职责 |
|---|---|---|
| 新建 | `frontend/lib/api-client.ts` | fetch 封装：GET/POST、token、超时、错误 |
| 新建 | `frontend/lib/sse.ts` | SSE EventSource 封装：token 代理、重连 |
| 新建 | `frontend/app/api/sse-proxy/route.ts` | Next.js Route Handler，服务端注入 JWT 后转发后端 SSE |
| 新建 | `frontend/lib/__tests__/api-client.test.ts` | api-client 单元测试 |
| 新建 | `frontend/lib/__tests__/sse.test.ts` | sse 单元测试 |
| 安装 | `frontend/package.json` | vitest、@testing-library/react、jsdom |

---

### Task 1: 安装 vitest 测试框架

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`

- [ ] **Step 1: 安装依赖**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm add -D vitest @vitejs/plugin-react jsdom @testing-library/react
```

- [ ] **Step 2: 创建 vitest.config.ts**

新建 `frontend/vitest.config.ts`：

```ts
import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
```

- [ ] **Step 3: 修改 package.json 添加 test 脚本**

在 `scripts` 中加入：

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 4: 运行空测试验证配置**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test
```

Expected: 输出 "No test files found" 或类似，但非报错退出。

---

### Task 2: ApiError + apiClient 基础 GET 请求

**Files:**
- Create: `frontend/lib/api-client.ts`
- Create: `frontend/lib/__tests__/api-client.test.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/lib/__tests__/api-client.test.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, ApiError } from "@/lib/api-client";

// Mock Clerk getToken
const mockGetToken = vi.fn();
vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({ getToken: mockGetToken }),
}));

describe("apiClient", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockGetToken.mockResolvedValue("test-jwt-token");
  });

  it("should make a GET request and return JSON", async () => {
    const mockData = { status: "ok" };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockData),
    });

    const result = await apiClient("/v1/health");

    expect(result).toEqual(mockData);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/backend/v1/health",
      expect.objectContaining({ method: "GET" })
    );
  });

  it("should throw ApiError on non-2xx response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.resolve({ detail: "server error" }),
    });

    await expect(apiClient("/v1/broken")).rejects.toThrow(ApiError);
    await expect(apiClient("/v1/broken")).rejects.toMatchObject({
      status: 500,
      message: "server error",
    });
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test -- api-client.test.ts
```

Expected: FAIL — module not found

- [ ] **Step 3: 实现 api-client.ts**

新建 `frontend/lib/api-client.ts`：

```ts
import { useAuth } from "@clerk/nextjs";

const BASE_URL = "/api/backend";
const DEFAULT_TIMEOUT = 30_000;

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, data: unknown) {
    const message =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : `HTTP ${status}`;
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

interface RequestConfig {
  method?: "GET" | "POST";
  body?: unknown;
  timeout?: number;
  headers?: Record<string, string>;
}

export async function apiClient<T = unknown>(
  path: string,
  config: RequestConfig = {}
): Promise<T> {
  const { method = "GET", body, timeout = DEFAULT_TIMEOUT, headers = {} } = config;

  // 获取 Clerk JWT（在非 React 组件环境中需要传 token 参数或从 store 取）
  const token = await getClerkToken();

  if (!token) {
    redirectToSignIn();
    throw new ApiError(401, "请重新登录");
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);

  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });

    if (res.status === 401) {
      redirectToSignIn();
      throw new ApiError(401, "认证已过期");
    }

    if (!res.ok) {
      const errorData = await res.json().catch(() => null);
      throw new ApiError(res.status, errorData);
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") {
      throw new ApiError(408, "请求超时");
    }
    throw new ApiError(0, (err as Error).message);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 获取 Clerk JWT token。
 * 在 React 组件中通过 useAuth() hook 获取；
 * 在非组件上下文中，需要外部通过 setTokenGetter() 注入获取函数。
 */
let tokenGetter: (() => Promise<string | null>) | null = null;

export function setTokenGetter(fn: () => Promise<string | null>) {
  tokenGetter = fn;
}

async function getClerkToken(): Promise<string | null> {
  if (tokenGetter) return tokenGetter();
  // fallback：尝试用 Clerk 的 useAuth（仅限 React 组件内）
  try {
    const { getToken } = useAuth();
    return await getToken();
  } catch {
    return null;
  }
}

function redirectToSignIn(): void {
  if (typeof window !== "undefined") {
    window.location.href = "/sign-in";
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test -- api-client.test.ts
```

Expected: PASS

---

### Task 3: apiClient POST 请求 + 超时处理

**Files:**
- Modify: `frontend/lib/__tests__/api-client.test.ts`

- [ ] **Step 1: 添加 POST + 超时 + 网络错误测试**

在 `frontend/lib/__tests__/api-client.test.ts` 已有 describe 块内追加：

```ts
it("should make a POST request with JSON body", async () => {
  const mockData = { id: "session-1" };
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    json: () => Promise.resolve(mockData),
  });

  const result = await apiClient("/v1/interview/start", {
    method: "POST",
    body: { topic: "LangGraph" },
  });

  expect(result).toEqual(mockData);
  expect(globalThis.fetch).toHaveBeenCalledWith(
    "/api/backend/v1/interview/start",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({ topic: "LangGraph" }),
    })
  );
});

it("should throw ApiError with status 408 on timeout", async () => {
  globalThis.fetch = vi.fn().mockImplementation((_url, { signal }) => {
    return new Promise((_resolve, reject) => {
      signal!.addEventListener("abort", () => {
        const err = new Error("Aborted");
        err.name = "AbortError";
        reject(err);
      });
    });
  });

  await expect(
    apiClient("/v1/slow", { timeout: 100 })
  ).rejects.toMatchObject({ status: 408, message: "请求超时" });
}, 5000);

it("should throw ApiError with status 0 on network error", async () => {
  globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network failure"));

  await expect(apiClient("/v1/health")).rejects.toMatchObject({
    status: 0,
    message: "Network failure",
  });
});
```

- [ ] **Step 2: 运行测试确认全部通过**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test -- api-client.test.ts
```

Expected: PASS (6 tests)

---

### Task 4: SSE 代理路由

**Files:**
- Create: `frontend/app/api/sse-proxy/route.ts`

- [ ] **Step 1: 创建 SSE 代理路由**

新建 `frontend/app/api/sse-proxy/route.ts`：

```ts
import { NextRequest } from "next/server";
import { auth } from "@clerk/nextjs/server";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const { getToken } = await auth();
  const token = await getToken();

  if (!token) {
    return new Response("Unauthorized", { status: 401 });
  }

  const target = request.nextUrl.searchParams.get("target");
  if (!target) {
    return new Response("Missing target parameter", { status: 400 });
  }

  const backendUrl = `${BACKEND_BASE}/api${target}`;

  // 将上游的查询参数（除 target 外）转发给后端
  const upstreamParams = new URLSearchParams(request.nextUrl.searchParams);
  upstreamParams.delete("target");
  const paramStr = upstreamParams.toString();
  const finalUrl = paramStr ? `${backendUrl}?${paramStr}` : backendUrl;

  const upstream = await fetch(finalUrl, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "text/event-stream",
    },
  });

  if (!upstream.ok || !upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
    });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
```

- [ ] **Step 2: 确认 TypeScript 编译通过**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && npx tsc --noEmit app/api/sse-proxy/route.ts
```

Expected: PASS (无报错)

---

### Task 5: SSE 客户端 connectSSE

**Files:**
- Create: `frontend/lib/sse.ts`
- Create: `frontend/lib/__tests__/sse.test.ts`

- [ ] **Step 1: 写失败测试**

新建 `frontend/lib/__tests__/sse.test.ts`：

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { connectSSE } from "@/lib/sse";

describe("connectSSE", () => {
  let mockEventSource: ReturnType<typeof vi.fn>;
  const originalEventSource = globalThis.EventSource;

  beforeEach(() => {
    mockEventSource = vi.fn();
    globalThis.EventSource = mockEventSource as unknown as typeof EventSource;
  });

  afterEach(() => {
    globalThis.EventSource = originalEventSource;
  });

  it("should create EventSource with sse-proxy URL", () => {
    const mockInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
    };
    mockEventSource.mockReturnValue(mockInstance);

    connectSSE("/v1/interview/session-1/stream", {});

    expect(mockEventSource).toHaveBeenCalledWith(
      "/api/sse-proxy?target=%2Fv1%2Finterview%2Fsession-1%2Fstream"
    );
  });

  it("should register event listeners", () => {
    const mockInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
    };
    mockEventSource.mockReturnValue(mockInstance);

    const onToken = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    connectSSE("/v1/interview/session-1/stream", {
      onToken,
      onDone,
      onError,
    });

    expect(mockInstance.addEventListener).toHaveBeenCalledWith(
      "token",
      expect.any(Function)
    );
    expect(mockInstance.addEventListener).toHaveBeenCalledWith(
      "done",
      expect.any(Function)
    );
    expect(mockInstance.addEventListener).toHaveBeenCalledWith(
      "error",
      expect.any(Function)
    );
  });

  it("should return unsubscribe function that closes connection", () => {
    const mockInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
    };
    mockEventSource.mockReturnValue(mockInstance);

    const unsubscribe = connectSSE("/v1/stream", {});

    expect(mockInstance.close).not.toHaveBeenCalled();
    unsubscribe();
    expect(mockInstance.close).toHaveBeenCalled();
  });

  it("should retry on error up to maxRetries", () => {
    vi.useFakeTimers();

    const mockInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      readyState: 2, // CLOSED
    };
    mockEventSource.mockReturnValue(mockInstance);

    let errorCallback: Function = () => {};

    mockInstance.addEventListener.mockImplementation(
      (event: string, cb: Function) => {
        if (event === "error") errorCallback = cb;
      }
    );

    const onError = vi.fn();
    const onToken = vi.fn();
    const onDone = vi.fn();

    connectSSE("/v1/stream", { onError, onToken, onDone, maxRetries: 3 });

    // 第一次 error
    errorCallback(new Event("error"));
    expect(mockInstance.close).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1000);
    expect(mockEventSource).toHaveBeenCalledTimes(2); // 首次 + 重试1

    // 第二次 error
    errorCallback(new Event("error"));
    vi.advanceTimersByTime(2000);
    expect(mockEventSource).toHaveBeenCalledTimes(3);

    // 第三次 error
    errorCallback(new Event("error"));
    vi.advanceTimersByTime(4000);
    expect(mockEventSource).toHaveBeenCalledTimes(4);

    // 第四次 error（超过 maxRetries=3）
    errorCallback(new Event("error"));
    expect(onError).toHaveBeenCalledWith(expect.any(Error));

    vi.useRealTimers();
  });

  it("should not retry after manual unsubscribe", () => {
    vi.useFakeTimers();

    const mockInstance = {
      addEventListener: vi.fn(),
      close: vi.fn(),
      readyState: 2,
    };
    mockEventSource.mockReturnValue(mockInstance);

    let errorCallback: Function = () => {};
    mockInstance.addEventListener.mockImplementation(
      (event: string, cb: Function) => {
        if (event === "error") errorCallback = cb;
      }
    );

    const unsubscribe = connectSSE("/v1/stream", { maxRetries: 3 });

    unsubscribe();
    errorCallback(new Event("error"));

    vi.advanceTimersByTime(1000);
    expect(mockEventSource).toHaveBeenCalledTimes(1); // 没有重连

    vi.useRealTimers();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test -- sse.test.ts
```

Expected: FAIL

- [ ] **Step 3: 实现 sse.ts**

新建 `frontend/lib/sse.ts`：

```ts
interface SSEOptions {
  onToken?: (token: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
  maxRetries?: number;
}

/**
 * 连接后端 SSE 端点，通过 Next.js API Route 代理注入 Clerk JWT。
 * 返回 unsubscribe 函数，调用后断开连接并停止自动重连。
 */
export function connectSSE(path: string, options: SSEOptions = {}): () => void {
  const { onToken, onDone, onError, maxRetries = 3 } = options;

  const encodedPath = encodeURIComponent(path);
  const url = `/api/sse-proxy?target=${encodedPath}`;

  let retries = 0;
  let cancelled = false;
  let es: EventSource | null = null;

  const cleanup = () => {
    cancelled = true;
    if (es) {
      es.close();
      es = null;
    }
  };

  const connect = () => {
    es = new EventSource(url);

    es.addEventListener("token", (event: MessageEvent) => {
      onToken?.(event.data);
    });

    es.addEventListener("done", () => {
      onDone?.();
      cleanup();
    });

    es.addEventListener("error", (event: Event) => {
      if (cancelled) return;

      cleanup();

      if (retries < maxRetries) {
        retries++;
        const delay = Math.min(1000 * Math.pow(2, retries - 1), 8000);
        setTimeout(connect, delay);
      } else {
        onError?.(new Error("SSE 连接失败，已超出最大重试次数"));
      }
    });
  };

  connect();
  return cleanup;
}
```

- [ ] **Step 4: 运行测试确认通过**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test -- sse.test.ts
```

Expected: PASS

---

### Task 6: 整体验证

- [ ] **Step 1: 运行全部测试**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm test
```

Expected: PASS（api-client 和 sse 全部测试通过）

- [ ] **Step 2: 运行 TypeScript 编译检查**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && npx tsc --noEmit
```

Expected: PASS（无类型错误）

- [ ] **Step 3: 启动前端确认无运行时错误**

```bash
cd /Users/xuebao/learn/AI项目/multi-agent-coach/frontend && pnpm dev &
sleep 5
curl -s http://localhost:3000 | head -20
```

Expected: 页面正常返回 HTML
