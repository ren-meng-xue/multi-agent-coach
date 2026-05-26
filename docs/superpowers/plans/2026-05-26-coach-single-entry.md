# Coach 单门口 + 入口收紧 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/coach` 收紧为面试品牌单门口，导航上移除 Interview Tab；用户无活动会话访问 `/interview` 时重定向回 Coach；同时为路线图第五步「教练 Agent + 共享记忆层」预留好接口位。

**Architecture:** Page-level useEffect 守卫（不引入 Next.js middleware），保留现有"sessionStorage → /interview/active → fallback"三级判定，仅把 fallback 从"渲染冗长提示卡"改成"router.replace 回 Coach"。同时抽出 `enterInterviewRoom(ctx)` 公共工具消除重复逻辑，并在后端 `CoachOpeningMessageResponse` 与 `PrepareState` 新增空槽字段为记忆 agent 留位。

**Tech Stack:**
- 前端：Next.js (App Router) + React + Clerk + vitest + @testing-library/react
- 后端：FastAPI + pydantic + SQLAlchemy 2.x async + LangGraph + pytest

**关联 spec:** `docs/superpowers/specs/2026-05-26-coach-single-entry-design.md`

---

## 文件结构

| 文件 | 类型 | 改动概述 |
|---|---|---|
| `backend/app/schemas/interview.py` | 修改 | `CoachOpeningMessageResponse` 增加 `long_memory_hints` / `hobby_hints` 默认空槽 |
| `backend/app/services/coach_opening.py` | 修改 | `_fallback_opening_message` 兼容新字段（默认空 list） |
| `backend/app/agents/prepare/state.py` | 修改 | `PrepareState` 增加 `long_memory` 槽（TypedDict total=False，默认不填） |
| `backend/tests/unit/test_coach_opening_service.py` | 修改 | 新增对 fallback 返回结构包含新字段的断言 |
| `frontend/lib/interview-chat.ts` | 修改 | (1) `CoachOpeningMessageResponse` 增加可选字段；(2) 新增 `enterInterviewRoom(ctx)` 工具 |
| `frontend/lib/interview-chat.test.ts` | 修改 | 新增 `enterInterviewRoom` 单测 |
| `frontend/app/components/nav.tsx` | 修改 | `navItems` 移除 `{label: "面试房间", href: "/interview"}` |
| `frontend/app/components/nav.test.tsx` | 修改 | 调整现有断言：「面试房间」不再出现 |
| `frontend/app/interview/_components/interview-chat.tsx` | 修改 | (1) fallback 分支替换为 `router.replace("/coach?from=interview")`；(2) active 接口异常时不重定向，渲染兜底；(3) 删除 `buildOpeningMessage(null)` 长 fallback 文本 |
| `frontend/app/interview/_components/interview-chat.test.tsx` | 修改 | 新增守卫重定向相关用例 |
| `frontend/app/coach/coach-dashboard.tsx` | 修改 | (1) 检测 `?from=interview` 显示 4s 软提示；(2) `CoachOpeningCopy` 增加 `long_memory_hints` / `hobby_hints` 渲染槽；(3) `handleAction("go-room")` / `handlePracticeMemory` 改用 `enterInterviewRoom` |
| `frontend/app/coach/coach-dashboard.test.tsx` | 修改 | 新增软提示出现 + 4s 后消失 + query 清理三个用例 |

---

## 执行顺序

1. **Task 1-3**：后端 schema/服务/state 加字段（先做，不影响现有调用方）
2. **Task 4-5**：前端 lib 扩展类型 + 抽 `enterInterviewRoom`（基础设施）
3. **Task 6**：导航 Tab 移除（用户已可见的最小入口收紧）
4. **Task 7-8**：Interview 路由守卫 + 兜底（核心收紧逻辑）
5. **Task 9-11**：Coach 软提示 + 记忆槽位 + 重构 enterInterviewRoom 调用

---

### Task 1: 后端 - `CoachOpeningMessageResponse` 增加记忆 hints 槽

**Files:**
- Modify: `backend/app/schemas/interview.py:82-89`
- Test: `backend/tests/unit/test_coach_opening_service.py`

- [ ] **Step 1: 在已有测试文件中追加测试用例**

`backend/tests/unit/test_coach_opening_service.py` 末尾追加：

```python
from app.schemas.interview import CoachOpeningMessageResponse


def test_coach_opening_response_has_memory_hint_slots():
    """schema 必须提供 long_memory_hints / hobby_hints 默认空槽，为第五步记忆 agent 预留位。"""
    response = CoachOpeningMessageResponse(
        greeting="hi",
        weakness_summary=None,
        evidence=None,
        focus_today="练 X",
        cta_type="new",
    )
    assert response.long_memory_hints == []
    assert response.hobby_hints == []
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_coach_opening_service.py::test_coach_opening_response_has_memory_hint_slots -v
```

Expected: FAIL — `long_memory_hints` / `hobby_hints` 不是合法字段。

- [ ] **Step 3: 在 schema 中加新字段**

修改 `backend/app/schemas/interview.py` `CoachOpeningMessageResponse`：

```python
class CoachOpeningMessageResponse(BaseModel):
    """GET /api/coach/opening-message 的展示文案响应。"""

    greeting: str
    weakness_summary: str | None
    evidence: str | None
    focus_today: str
    cta_type: Literal["new", "returning"]
    # 第五步「教练 Agent + 共享记忆层」预留：默认空，本次不实现填充逻辑
    long_memory_hints: list[str] = []
    hobby_hints: list[str] = []
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_coach_opening_service.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: 跑 lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/schemas/interview.py tests/unit/test_coach_opening_service.py
cd backend && .venv/bin/python -m mypy app/schemas/interview.py
```

Expected: 无错误。

- [ ] **Step 6: 询问用户是否 commit**

总结：在 `CoachOpeningMessageResponse` 加 `long_memory_hints` / `hobby_hints` 默认空字段并补单测。等用户回 `ok`/`1`/`好`/`可以`/`继续`/`确认` 后执行：

```bash
git add backend/app/schemas/interview.py backend/tests/unit/test_coach_opening_service.py
git commit -m "feat(schema): reserve memory hint slots on CoachOpeningMessageResponse"
```

---

### Task 2: 后端 - `_fallback_opening_message` 兼容新字段

**Files:**
- Modify: `backend/app/services/coach_opening.py:278-329`
- Test: `backend/tests/unit/test_coach_opening_service.py`

> 背景：Task 1 给 schema 加了字段（带默认值），但 fallback 函数显式构造 response，需补单测确认这两条 fallback 路径返回的 response 也带正确的默认空 list。

- [ ] **Step 1: 在测试文件追加 fallback 用例**

```python
from app.services.coach_opening import _fallback_opening_message
from app.services.coach_opening import CoachHistoryContext


def test_fallback_opening_includes_memory_hint_slots_for_new_user():
    ctx = CoachHistoryContext(
        session_count=0,
        recent_scores=[],
        pass_rate=0.0,
        common_issues={},
        trend="flat",
        is_new=True,
        practiced_roles={},
        recent_sessions=[],
    )
    response = _fallback_opening_message(ctx)
    assert response.long_memory_hints == []
    assert response.hobby_hints == []


def test_fallback_opening_includes_memory_hint_slots_for_returning_user():
    ctx = CoachHistoryContext(
        session_count=3,
        recent_scores=[3.2, 3.0, 2.8],
        pass_rate=0.33,
        common_issues={"量化欠缺": 2},
        trend="declining",
        is_new=False,
        practiced_roles={"AI Agent 工程师": 3},
        recent_sessions=[],
    )
    response = _fallback_opening_message(ctx)
    assert response.long_memory_hints == []
    assert response.hobby_hints == []
```

- [ ] **Step 2: 运行测试，确认通过（Task 1 已让默认值生效）**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_coach_opening_service.py -v
```

Expected: 新增两个用例 PASS（依赖 Task 1 的字段默认值，不需要改 service 实现）。

- [ ] **Step 3: 跑全量后端测试，确认无回归**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Expected: 全部 PASS。

- [ ] **Step 4: 询问用户是否 commit**

总结：补 `_fallback_opening_message` 两条路径的回归测试，确认新字段默认值在 fallback 中也工作。等用户确认后执行：

```bash
git add backend/tests/unit/test_coach_opening_service.py
git commit -m "test(coach_opening): assert fallback includes memory hint slots"
```

---

### Task 3: 后端 - `PrepareState` 增加 `long_memory` 槽

**Files:**
- Modify: `backend/app/agents/prepare/state.py`
- Test: 不需要单测（TypedDict 总是 total=False，纯类型声明）

> 背景：spec 里这是给第五步教练 agent 注入历史记忆的槽位。本次只加声明，不接入消费者。

- [ ] **Step 1: 修改 `PrepareState`**

修改 `backend/app/agents/prepare/state.py`：

```python
class PrepareState(TypedDict, total=False):
    # 输入
    session_id: str
    user_id: str
    user_direction: str | None
    user_background: str | None
    jd_raw: str | None

    # MASTER 决策输出
    direction: str
    chain: list[str]
    need_direction: bool

    # 子 Agent 结果
    weak_areas: list[str]
    star_stories: list[dict[str, Any]]
    jd_context: JDContext | None
    prepared_questions: list[PreparedQuestion]
    # 第五步「教练 Agent + 共享记忆层」预留：长期记忆/爱好记忆注入槽。本次不实现填充。
    long_memory: list[dict[str, Any]]

    # 最终输出
    summary: str
```

- [ ] **Step 2: 跑 lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check app/agents/prepare/state.py
cd backend && .venv/bin/python -m mypy app/agents/prepare
```

Expected: 无错误。

- [ ] **Step 3: 跑现有 prepare 相关测试，确认无回归**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q -k "prepare or master or jd or question_gen or memory_search"
```

Expected: 全部 PASS（新字段在 total=False 下不影响任何现有调用）。

- [ ] **Step 4: 询问用户是否 commit**

总结：`PrepareState` 增加 `long_memory: list[dict[str, Any]]` 可选槽位，未接入消费者。等用户确认后执行：

```bash
git add backend/app/agents/prepare/state.py
git commit -m "feat(prepare): reserve long_memory slot on PrepareState"
```

---

### Task 4: 前端 - `CoachOpeningMessageResponse` 类型扩展

**Files:**
- Modify: `frontend/lib/interview-chat.ts:156-162`

> 背景：与后端 Task 1 对齐，前端类型加可选字段；后续 Coach UI 才能消费。

- [ ] **Step 1: 修改类型声明**

修改 `frontend/lib/interview-chat.ts`：

```ts
export type CoachOpeningMessageResponse = {
  greeting: string;
  weakness_summary: string | null;
  evidence: string | null;
  focus_today: string;
  cta_type: "new" | "returning";
  // 第五步「教练 Agent + 共享记忆层」预留：默认空数组，本次不渲染
  long_memory_hints?: string[];
  hobby_hints?: string[];
};
```

- [ ] **Step 2: 跑前端 typecheck，确认无回归**

```bash
cd frontend && pnpm typecheck
```

Expected: 无新增错误（旧调用方不传字段也兼容，因为是 optional）。

- [ ] **Step 3: 跑前端测试套件，确认无回归**

```bash
cd frontend && pnpm test
```

Expected: 全绿。

- [ ] **Step 4: 询问用户是否 commit**

总结：前端 `CoachOpeningMessageResponse` 类型加两个可选 hints 字段，与后端 schema 对齐。等用户确认后执行：

```bash
git add frontend/lib/interview-chat.ts
git commit -m "feat(types): add memory hint slots to CoachOpeningMessageResponse"
```

---

### Task 5: 前端 - 新增 `enterInterviewRoom(ctx)` 公共工具

**Files:**
- Modify: `frontend/lib/interview-chat.ts`
- Modify: `frontend/lib/interview-chat.test.ts`

> 背景：Coach `handleAction("go-room")` 和 `handlePracticeMemory` 都重复"写 sessionStorage + reset + push"。抽公共函数，未来 Reports / Dashboard 也能复用。

- [ ] **Step 1: 在 `frontend/lib/interview-chat.test.ts` 追加测试**

参考已有用例的 mock 风格。先确认现有文件 import 风格，再追加：

```ts
import { enterInterviewRoom } from "./interview-chat";

describe("enterInterviewRoom", () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("写 sessionStorage 并 push /interview", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    );
    const push = vi.fn();
    const router = { push, replace: vi.fn() } as unknown as Parameters<typeof enterInterviewRoom>[0]["router"];

    process.env.NEXT_PUBLIC_API_URL = "http://api";

    await enterInterviewRoom({
      getToken: async () => "tok",
      router,
      context: { target_role: "AI Agent 工程师", user_background: "bg" },
    });

    const raw = sessionStorage.getItem("interview_context");
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw!)).toMatchObject({ target_role: "AI Agent 工程师", user_background: "bg" });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api/api/v1/interview/reset",
      expect.objectContaining({ method: "POST" }),
    );
    expect(push).toHaveBeenCalledWith("/interview");
  });

  it("reset 接口失败时仍然 push，仅 warn", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const push = vi.fn();
    const router = { push, replace: vi.fn() } as unknown as Parameters<typeof enterInterviewRoom>[0]["router"];

    process.env.NEXT_PUBLIC_API_URL = "http://api";

    await enterInterviewRoom({
      getToken: async () => "tok",
      router,
      context: { target_role: "前端工程师" },
    });

    expect(push).toHaveBeenCalledWith("/interview");
    expect(warn).toHaveBeenCalled();
  });

  it("getToken 返回 null 时跳过 reset 但仍 push", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    const push = vi.fn();
    const router = { push, replace: vi.fn() } as unknown as Parameters<typeof enterInterviewRoom>[0]["router"];

    await enterInterviewRoom({
      getToken: async () => null,
      router,
      context: { target_role: "后端工程师" },
    });

    expect(fetchMock).not.toHaveBeenCalled();
    expect(push).toHaveBeenCalledWith("/interview");
  });
});
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && pnpm test -- interview-chat.test.ts
```

Expected: FAIL — `enterInterviewRoom is not exported`。

- [ ] **Step 3: 在 `frontend/lib/interview-chat.ts` 末尾实现**

```ts
type AppRouter = {
  push: (href: string) => void;
  replace: (href: string) => void;
};

export type EnterInterviewRoomContext = {
  target_role: string;
  user_background?: string;
  jd_text?: string;
  jd_url?: string;
};

/** 统一封装从任意入口进入 /interview 的流程：写 sessionStorage + reset 后台 session + push。
 *  reset 失败仅 warn，不阻塞跳转 —— 路由守卫层会兜底处理无 active session 的情况。 */
export async function enterInterviewRoom({
  getToken,
  router,
  context,
}: {
  getToken: () => Promise<string | null>;
  router: AppRouter;
  context: EnterInterviewRoomContext;
}): Promise<void> {
  sessionStorage.setItem("interview_context", JSON.stringify(context));

  const token = await getToken();
  if (token) {
    try {
      await resetInterviewSession({
        token,
        target_role: context.target_role,
        user_background: context.user_background,
      });
    } catch (err) {
      console.warn("enterInterviewRoom: reset failed, proceeding anyway", err);
    }
  }

  router.push("/interview");
}
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- interview-chat.test.ts
```

Expected: 3 个新用例全部 PASS。

- [ ] **Step 5: 跑前端全量测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全部 PASS。

- [ ] **Step 6: 询问用户是否 commit**

总结：在 `frontend/lib/interview-chat.ts` 新增 `enterInterviewRoom(ctx)` 公共工具 + 3 个单测；尚未替换 Coach 调用方（Task 11 接入）。等用户确认后执行：

```bash
git add frontend/lib/interview-chat.ts frontend/lib/interview-chat.test.ts
git commit -m "feat(lib): add enterInterviewRoom helper for unified interview entry"
```

---

### Task 6: 前端 - 导航移除「面试房间」Tab

**Files:**
- Modify: `frontend/app/components/nav.tsx`
- Modify: `frontend/app/components/nav.test.tsx`

- [ ] **Step 1: 修改测试断言（让旧用例失败暴露需要移除）**

修改 `frontend/app/components/nav.test.tsx` 现有 "渲染所有导航菜单项" 用例：

```ts
it("渲染所有导航菜单项（不含已收紧的面试房间）", () => {
  render(<MainNav isLoggedIn={true} />);
  expect(screen.getByText("Coach")).toBeInTheDocument();
  // 面试房间已收紧为 Coach 的派生入口，不在导航栏单列
  expect(screen.queryByText("面试房间")).not.toBeInTheDocument();
  expect(screen.getByText("个人仪表盘")).toBeInTheDocument();
  expect(screen.getByText("复盘报告")).toBeInTheDocument();
  expect(screen.getByText("设置 & 故事库")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && pnpm test -- components/nav.test.tsx
```

Expected: FAIL — 「面试房间」当前仍在 DOM 中。

- [ ] **Step 3: 修改 `nav.tsx` 移除该项**

修改 `frontend/app/components/nav.tsx`：

```tsx
const navItems = [
  { label: "Coach", href: "/coach" },
  { label: "个人仪表盘", href: "/dashboard" },
  { label: "复盘报告", href: "/reports" },
  { label: "设置 & 故事库", href: "/settings" },
];
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- components/nav.test.tsx
```

Expected: PASS。

- [ ] **Step 5: 跑全量前端测试，确认无其他用例引用旧 Tab**

```bash
cd frontend && pnpm test
```

Expected: 全绿。如有引用 `/interview` 导航行为的其他用例失败，按"用户必须从 Coach 派发"的语义调整。

- [ ] **Step 6: 询问用户是否 commit**

总结：导航栏移除「面试房间」Tab，单测同步。等用户确认后执行：

```bash
git add frontend/app/components/nav.tsx frontend/app/components/nav.test.tsx
git commit -m "feat(nav): remove standalone interview tab — Coach is the single entry"
```

---

### Task 7: 前端 - Interview 路由守卫（路径 3/4 重定向）

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`
- Modify: `frontend/app/interview/_components/interview-chat.test.tsx`

> 背景：当前 useEffect 第三分支是 `setMessages([buildOpeningMessage(null)])`；改为 `router.replace("/coach?from=interview")`。

- [ ] **Step 1: 在测试文件追加守卫用例（先了解现有 mock）**

先看 `frontend/app/interview/_components/interview-chat.test.tsx` 顶部 mock 段，确认 `useRouter` 是否已被 mock。如果未 mock，需补充。在测试文件适当位置追加：

```tsx
describe("路由守卫", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("无 sessionStorage context 且 /interview/active 返回空时，重定向到 /coach?from=interview", async () => {
    // mock fetchActiveInterviewSession 返回无 session_id 的响应
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/interview/active")) {
        return new Response(JSON.stringify({ messages: [] }), { status: 200 });
      }
      return new Response("{}", { status: 200 });
    });
    const replace = vi.fn();
    // 通过 next/navigation mock 注入 router
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

    render(<InterviewChat />);
    await waitFor(() => {
      expect(replace).toHaveBeenCalledWith("/coach?from=interview");
    });
  });

  it("有 sessionStorage context 时不重定向，触发 prepare", async () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({ target_role: "AI Agent 工程师" }),
    );
    const replace = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

    render(<InterviewChat />);
    // 给守卫一点时间执行
    await new Promise((r) => setTimeout(r, 50));
    expect(replace).not.toHaveBeenCalled();
  });

  it("/interview/active 返回 in_progress 会话时不重定向，恢复消息", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/api/v1/interview/active")) {
        return new Response(
          JSON.stringify({
            session_id: "abc",
            stage: "interview",
            question_count: 2,
            messages: [
              { role: "assistant", content: "已开始的面试" },
              { role: "user", content: "我的回答" },
            ],
          }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    });
    const replace = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

    render(<InterviewChat />);
    await waitFor(() => {
      expect(screen.getByText("已开始的面试")).toBeInTheDocument();
    });
    expect(replace).not.toHaveBeenCalled();
  });
});
```

如果 `useRouter` 尚未 mock，需在文件顶部 mock 段加：

```tsx
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: vi.fn(() => "/interview"),
}));

import { useRouter } from "next/navigation";
```

- [ ] **Step 2: 运行测试，确认重定向用例失败**

```bash
cd frontend && pnpm test -- interview-chat.test.tsx
```

Expected: 第一个用例 FAIL — `replace` 未被调用（当前是 `setMessages` 兜底文本）。

- [ ] **Step 3: 修改 `interview-chat.tsx` 守卫逻辑**

定位现有 useEffect 中的 fallback 分支（约 240-247 行）：

```tsx
// 旧版（需替换）
} else {
  // 没有任何活动会话，正常展示默认欢迎卡片
  setMessages([{ role: "assistant", content: buildOpeningMessage(null) }]);
}
```

改为：

```tsx
} else {
  // 路径 3/4：无 sessionStorage 上下文 + 无活动会话 → 守卫重定向回 Coach
  router.replace("/coach?from=interview");
  return; // 即将卸载，不再触发后续 setIsInitialLoading
}
```

同时，组件顶部需添加 `const router = useRouter();`（参考 Coach Dashboard 的写法）—— 检查是否已存在，没有就加 import 和声明。

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- interview-chat.test.tsx
```

Expected: 三个新用例全部 PASS，现有用例若依赖 `buildOpeningMessage(null)` 渲染兜底卡片需配合调整（见 Step 5）。

- [ ] **Step 5: 修复因 fallback 卡片消失而失败的旧用例**

如果有用例渲染 `<InterviewChat />` 且依赖"你好！请告诉我..."文案出现，把这些用例的预期改为：mock 一个有 session_id 的 active 响应，或显式注入 sessionStorage context。具体看 test 输出。

- [ ] **Step 6: 跑全量前端测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。

- [ ] **Step 7: 询问用户是否 commit**

总结：Interview 路由守卫重定向就位（无活动会话回 Coach），单测覆盖三条主路径。等用户确认后执行：

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(interview): redirect to /coach when no active session"
```

---

### Task 8: 前端 - active 接口异常时兜底，不重定向

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`
- Modify: `frontend/app/interview/_components/interview-chat.test.tsx`

> 背景：spec 明确「active 超时/500 不重定向，渲染兜底错误 UI」—— 防止进行中面试被误踢回 Coach。

- [ ] **Step 1: 在测试文件追加异常兜底用例**

```tsx
it("/interview/active 抛错时不重定向，渲染兜底错误 UI", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith("/api/v1/interview/active")) {
      throw new Error("network");
    }
    return new Response("{}", { status: 200 });
  });
  const replace = vi.fn();
  vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

  render(<InterviewChat />);
  await waitFor(() => {
    expect(screen.getByText(/连接异常/)).toBeInTheDocument();
  });
  expect(replace).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && pnpm test -- interview-chat.test.tsx
```

Expected: FAIL — 当前 catch 分支 fallback 走的是已删的兜底卡片。

- [ ] **Step 3: 在 `interview-chat.tsx` 加 loadError 状态 + catch 分支**

在组件状态部分加：

```tsx
const [loadError, setLoadError] = useState(false);
```

在 useEffect 现有的 `try { ... } catch (err) { ... }` catch 分支改为：

```tsx
} catch (err) {
  console.error("Failed to load active interview session:", err);
  setLoadError(true); // 不重定向，让用户决定
}
```

在 JSX 中插入兜底 UI（紧邻 `isInitialLoading` 渲染分支之前/之后，依视觉层级）：

```tsx
{loadError && messages.length === 0 && (
  <div className="flex flex-1 flex-col items-center justify-center gap-3 text-sm">
    <div className="text-black/60 dark:text-white/60">连接异常，请重试或返回 Coach。</div>
    <Button
      variant="outline"
      onClick={() => router.replace("/coach")}
    >
      返回 Coach
    </Button>
  </div>
)}
```

注意：`Button` 已经在文件顶部 import。

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- interview-chat.test.tsx
```

Expected: 新用例 PASS。

- [ ] **Step 5: 跑全量前端测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。

- [ ] **Step 6: 询问用户是否 commit**

总结：active 接口异常时显示兜底 UI（返回 Coach 按钮），守卫不强制 replace。等用户确认后执行：

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(interview): show fallback UI when /active fails instead of redirecting"
```

---

### Task 9: 前端 - Coach 软提示（4s 自动消失 + query 清理）

**Files:**
- Modify: `frontend/app/coach/coach-dashboard.tsx`
- Modify: `frontend/app/coach/coach-dashboard.test.tsx`

- [ ] **Step 1: 在 coach-dashboard 测试文件追加软提示用例**

先确认现有 `coach-dashboard.test.tsx` 的 mock 风格，特别是 `next/navigation` 是否已 mock `useSearchParams` / `useRouter`。在适当位置追加：

```tsx
describe("from=interview 软提示", () => {
  it("URL 带 from=interview 时显示软提示并在 4 秒后消失", async () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams("from=interview"));
    vi.useFakeTimers();
    const replace = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

    render(<CoachDashboard />);

    expect(screen.getByText(/先在这里告诉我练什么/)).toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/coach"); // 立即清 query

    vi.advanceTimersByTime(4000);

    await waitFor(() => {
      expect(screen.queryByText(/先在这里告诉我练什么/)).not.toBeInTheDocument();
    });

    vi.useRealTimers();
  });

  it("URL 不带 from=interview 时不显示软提示", () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams(""));
    const replace = vi.fn();
    vi.mocked(useRouter).mockReturnValue({ push: vi.fn(), replace } as any);

    render(<CoachDashboard />);

    expect(screen.queryByText(/先在这里告诉我练什么/)).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalledWith("/coach");
  });
});
```

如果 `useSearchParams` 在现有 mock 里没设置，需要加：

```tsx
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: vi.fn(), replace: vi.fn() })),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: vi.fn(() => "/coach"),
}));

import { useRouter, useSearchParams } from "next/navigation";
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && pnpm test -- coach-dashboard.test.tsx
```

Expected: FAIL — 软提示元素不存在。

- [ ] **Step 3: 在 `coach-dashboard.tsx` 实现软提示**

顶部 import 部分增加：

```tsx
import { useRouter, useSearchParams } from "next/navigation";
```

`useRouter` 已存在，确认无需重复。在 `CoachDashboard` 组件内（`useRouter` 旁）添加：

```tsx
const searchParams = useSearchParams();
const fromInterview = searchParams.get("from") === "interview";
const [showFromInterviewHint, setShowFromInterviewHint] = useState(fromInterview);

useEffect(() => {
  if (!fromInterview) return;
  // 同步清掊 query，防止刷新/分享链接时重复出现
  router.replace("/coach");
  const t = setTimeout(() => setShowFromInterviewHint(false), 4000);
  return () => clearTimeout(t);
}, [fromInterview, router]);
```

在 JSX 中找到 Coach 身份条（约 683 行）下方，插入软提示：

```tsx
{showFromInterviewHint && (
  <div className="rounded-xl border border-[#e8e7e2] bg-[#faf9f5] px-4 py-2.5 text-xs text-[#525252] animate-in fade-in slide-in-from-top-2 duration-300">
    面试还没开始，先在这里告诉我练什么。
  </div>
)}
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- coach-dashboard.test.tsx
```

Expected: 两个新用例 PASS。

- [ ] **Step 5: 跑全量前端测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。

- [ ] **Step 6: 询问用户是否 commit**

总结：Coach 检测 `?from=interview` 时顶部插一行 4s 自动消失的软提示，并立即 `router.replace("/coach")` 清 query。等用户确认后执行：

```bash
git add frontend/app/coach/coach-dashboard.tsx frontend/app/coach/coach-dashboard.test.tsx
git commit -m "feat(coach): show soft hint and clear query when redirected from /interview"
```

---

### Task 10: 前端 - `CoachOpeningCopy` 增加记忆 hints 渲染槽

**Files:**
- Modify: `frontend/app/coach/coach-dashboard.tsx:113-192`
- Modify: `frontend/app/coach/coach-dashboard.test.tsx`

> 背景：本次只加渲染槽，hints 始终为空（后端默认 []）。Task 完成后即可被第五步直接消费。

- [ ] **Step 1: 在测试文件追加 hints 渲染用例**

```tsx
describe("CoachOpeningCopy 记忆 hints 槽", () => {
  it("long_memory_hints 有内容时渲染", () => {
    // 让 fetchCoachOpeningMessage 返回带 hints 的响应
    vi.mocked(fetchCoachOpeningMessage).mockResolvedValue({
      greeting: "hi",
      weakness_summary: null,
      evidence: null,
      focus_today: "练 X",
      cta_type: "new",
      long_memory_hints: ["上次你说过偏好用 RAG"],
      hobby_hints: ["你喜欢分布式系统"],
    });

    render(<CoachDashboard />);

    return waitFor(() => {
      expect(screen.getByText(/上次你说过偏好用 RAG/)).toBeInTheDocument();
      expect(screen.getByText(/你喜欢分布式系统/)).toBeInTheDocument();
    });
  });

  it("hints 为空/缺失时不渲染槽", () => {
    vi.mocked(fetchCoachOpeningMessage).mockResolvedValue({
      greeting: "hi",
      weakness_summary: null,
      evidence: null,
      focus_today: "练 X",
      cta_type: "new",
    });

    render(<CoachDashboard />);

    return waitFor(() => {
      expect(screen.getByText("hi")).toBeInTheDocument();
    }).then(() => {
      // 没有 hints 元素出现
      expect(screen.queryByTestId("coach-long-memory-hints")).not.toBeInTheDocument();
      expect(screen.queryByTestId("coach-hobby-hints")).not.toBeInTheDocument();
    });
  });
});
```

注意：根据现有 `coach-dashboard.test.tsx` mock 风格调整 `fetchCoachOpeningMessage` 的 mock 注入方式。

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd frontend && pnpm test -- coach-dashboard.test.tsx
```

Expected: FAIL — hints 文案不在 DOM 中。

- [ ] **Step 3: 在 `CoachOpeningCopy` 渲染槽中插入 hints**

修改 `frontend/app/coach/coach-dashboard.tsx` 中 `CoachOpeningCopy` 函数的 `coachMessage` 分支，在 `focus_today` 段之后追加：

```tsx
{coachMessage.long_memory_hints && coachMessage.long_memory_hints.length > 0 && (
  <div data-testid="coach-long-memory-hints" className="mt-3.5 space-y-1">
    {coachMessage.long_memory_hints.map((hint) => (
      <p key={hint} className="text-sm text-[#525252]">
        <CoachHighlightedText text={hint} />
      </p>
    ))}
  </div>
)}
{coachMessage.hobby_hints && coachMessage.hobby_hints.length > 0 && (
  <div data-testid="coach-hobby-hints" className="mt-2 space-y-1">
    {coachMessage.hobby_hints.map((hint) => (
      <p key={hint} className="text-sm text-[#8a8a8a]">
        <CoachHighlightedText text={hint} />
      </p>
    ))}
  </div>
)}
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
cd frontend && pnpm test -- coach-dashboard.test.tsx
```

Expected: 两个新用例 PASS。

- [ ] **Step 5: 跑全量前端测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。

- [ ] **Step 6: 询问用户是否 commit**

总结：`CoachOpeningCopy` 增加 `long_memory_hints` / `hobby_hints` 两个空槽渲染位，hints 非空才渲染；为第五步教练 agent 接入留位。等用户确认后执行：

```bash
git add frontend/app/coach/coach-dashboard.tsx frontend/app/coach/coach-dashboard.test.tsx
git commit -m "feat(coach): reserve memory hint render slots in opening copy"
```

---

### Task 11: 前端 - Coach 改用 `enterInterviewRoom` 消除重复

**Files:**
- Modify: `frontend/app/coach/coach-dashboard.tsx:597-667`

> 背景：现 `handleAction("go-room")` 和 `handlePracticeMemory` 内有重复的 sessionStorage 写 + reset + push 流程，替换为 Task 5 抽出的 `enterInterviewRoom`。

- [ ] **Step 1: 顶部 import 增加**

```tsx
import {
  fetchCoachOpeningMessage,
  fetchInterviewContext,
  fetchInterviewHistory,
  resetInterviewSession,
  enterInterviewRoom,
  type CoachOpeningMessageResponse,
  type UserContextResponse,
  type InterviewHistoryItem,
} from "@/lib/interview-chat";
```

- [ ] **Step 2: 替换 `handleAction("go-room")` 分支**

定位现有 (约 619-642 行)：

```tsx
} else if (action === "go-room") {
  const role = selectedRole || contextData?.target_role || "";
  const bg = userMessage || contextData?.user_background || "";
  if (role) {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({
        target_role: role,
        user_background: bg,
        jd_text: jdText,
        jd_url: jdUrl,
      }),
    );
    const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();
    const token = await fetchToken;
    if (token) {
      await resetInterviewSession({
        token,
        target_role: role,
        user_background: bg || undefined,
      });
    }
  }
  router.push("/interview");
}
```

替换为：

```tsx
} else if (action === "go-room") {
  const role = selectedRole || contextData?.target_role || "";
  const bg = userMessage || contextData?.user_background || "";
  if (role) {
    await enterInterviewRoom({
      getToken: () =>
        isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken(),
      router,
      context: {
        target_role: role,
        user_background: bg || undefined,
        jd_text: jdText || undefined,
        jd_url: jdUrl || undefined,
      },
    });
  } else {
    router.push("/interview"); // 不该到这里，但兜底
  }
}
```

- [ ] **Step 3: 替换 `handlePracticeMemory` 函数体**

定位现有 (约 648-667 行)：

```tsx
const handlePracticeMemory = async (session: MemorySession) => {
  const userBackground = `我想围绕「${session.topic}」再练一场，重点补齐：${session.improvements
    .slice(0, 2)
    .join("；")}`;
  sessionStorage.setItem(
    "interview_context",
    JSON.stringify({ target_role: session.targetRole, user_background: userBackground }),
  );
  const fetchToken = isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken();
  const token = await fetchToken;
  if (token) {
    await resetInterviewSession({
      token,
      target_role: session.targetRole,
      user_background: userBackground,
    });
  }
  setSelectedMemory(null);
  router.push("/interview");
};
```

替换为：

```tsx
const handlePracticeMemory = async (session: MemorySession) => {
  const userBackground = `我想围绕「${session.topic}」再练一场，重点补齐：${session.improvements
    .slice(0, 2)
    .join("；")}`;
  setSelectedMemory(null);
  await enterInterviewRoom({
    getToken: () =>
      isDevAuthBypassEnabled ? Promise.resolve(DEV_AUTH_BYPASS_TOKEN) : getToken(),
    router,
    context: {
      target_role: session.targetRole,
      user_background: userBackground,
    },
  });
};
```

- [ ] **Step 4: 检查 `resetInterviewSession` 是否仍被引用**

```bash
cd frontend && grep -n "resetInterviewSession" app/coach/coach-dashboard.tsx
```

如果没有别处再用，可从 import 中移除以保持干净；如果还在用（如其他分支），保留。

- [ ] **Step 5: 跑全量前端测试 + typecheck**

```bash
cd frontend && pnpm typecheck && pnpm test
```

Expected: 全绿。原有 coach-dashboard 测试若 spy 了 `resetInterviewSession` 也应该仍工作（`enterInterviewRoom` 内部仍调它）。

- [ ] **Step 6: 询问用户是否 commit**

总结：Coach 的「go-room」与「practice memory」分支改用 `enterInterviewRoom` 工具，DRY 消除重复。等用户确认后执行：

```bash
git add frontend/app/coach/coach-dashboard.tsx
git commit -m "refactor(coach): use enterInterviewRoom helper for room entry paths"
```

---

### Task 12: 集成验证 + 手动 QA

**Files:** 不修改代码，仅运行验证。

- [ ] **Step 1: 跑全量后端验证**

```bash
cd backend && .venv/bin/python -m ruff check .
cd backend && .venv/bin/python -m mypy app
cd backend && .venv/bin/python -m pytest tests/
```

Expected: lint/typecheck 无错误，所有测试 PASS。

- [ ] **Step 2: 跑全量前端验证**

```bash
cd frontend && pnpm typecheck
cd frontend && pnpm test
cd frontend && pnpm build
```

Expected: typecheck/test/build 全绿。

- [ ] **Step 3: 手动 QA 五条用户路径**

启动后端 + 前端 dev server，逐条手动验证：

1. **路径 1** — 登录 → 进入 `/coach` → 选岗位 → 点「开始面试」/「我直接试一场吧」 → 预期：跳到 `/interview`，prepare 流正常跑
2. **路径 2** — 面试进行中（已生成第 1 题），刷新 `/interview` 页面 → 预期：消息恢复，进度恢复，**不**被重定向
3. **路径 3** — 完成一场面试后，导航回 Coach，再用浏览器后退按钮回 `/interview` → 预期：被重定向到 `/coach?from=interview`，顶部一行软提示 4s 后消失
4. **路径 4** — 在新 tab 直接敲 `localhost:3000/interview` → 预期：重定向到 Coach
5. **导航条** — 验证「面试房间」Tab 已消失，其他 Tab 正常

- [ ] **Step 4: 整体总结，询问用户是否做 squash commit / push / PR**

> 按 CLAUDE.md：禁止自动 push / merge / rebase。仅在用户明确同意后执行。

总结 12 个任务的累积影响：
- 后端：3 个文件改动（schema、service test、prepare state），无破坏性
- 前端：6 个文件改动（nav、interview-chat、coach-dashboard、lib），用户可见行为收紧
- 测试：新增 ~12 个用例
- 风险：低，所有改动可单 commit 回滚

询问用户接下来要做 push / 开 PR 还是先保留本地。

---

## Self-Review 结果

- **Spec coverage**：
  - § 4.2 改动地图 7 项 ↔ Task 1-11 ✓
  - § 5.1 五条用户路径 ↔ Task 7 + Task 12 手动 QA 全部覆盖 ✓
  - § 5.4 `enterInterviewRoom` 签名 ↔ Task 5 实现 + Task 11 接入 ✓
  - § 6 错误矩阵 5 行 ↔ Task 7-8（active 异常）、Task 11（reset 失败）、Task 9（query 清理）覆盖；其它由 Clerk 中间件/现有 prepare 兜底，不需额外任务 ✓
  - § 7 测试要点 5 类 ↔ Task 1/2/5/6/7/8/9/10 内都已包含 ✓
- **Placeholder scan**：无 TBD/TODO/"similar to Task N"/未定义类型引用 ✓
- **Type consistency**：`enterInterviewRoom` 在 Task 5 定义、Task 11 引用，签名一致 ✓；`CoachOpeningMessageResponse` 在前后端 Task 1/4 都加 `long_memory_hints` / `hobby_hints` 同名字段 ✓；`PrepareState.long_memory` 在 Task 3 定义但本次无消费方（spec 已明示是接口位）✓
