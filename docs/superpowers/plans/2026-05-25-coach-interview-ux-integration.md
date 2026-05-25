# Coach–Interview UX 集成实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通 `/coach` 与 `/interview` 的上下文传递，新老用户由真实后端数据驱动，消除面试房间每次重复询问开场白的问题。

**Architecture:** 新增 `GET /api/v1/interview/context` 只读 API 供 Coach 页面判断新老用户；`POST /reset` 扩展可选 body 接收岗位上下文，并预建含上下文的新 session；前端用 sessionStorage 跨页传参，InterviewChat 根据上下文动态生成开场白。

**Tech Stack:** Python / FastAPI / SQLAlchemy 2 async / Pydantic v2；TypeScript / React / Next.js / Clerk / Vitest + Testing Library

---

## 文件结构

| 文件 | 变更类型 | 职责 |
|---|---|---|
| `backend/app/schemas/interview.py` | 修改 | 新增 `UserContextResponse`；新增 `ResetRequest` |
| `backend/app/services/interview_turn.py` | 修改 | 新增 `get_user_interview_context`；扩展 `reset_interview_session` 签名 |
| `backend/app/api/v1/interview.py` | 修改 | 新增 `GET /context` 路由；为 `POST /reset` 绑定可选请求体 |
| `backend/tests/unit/test_interview_routes.py` | 修改 | 新增路由单元测试 |
| `backend/tests/integration/test_interview_turn_service.py` | 修改 | 新增 service 集成测试 |
| `frontend/lib/interview-chat.ts` | 修改 | 新增 `fetchInterviewContext`；扩展 `resetInterviewSession` 参数 |
| `frontend/lib/interview-chat.test.ts` | 修改 | 新增对应测试 |
| `frontend/app/interview/_components/interview-chat.tsx` | 修改 | 读 sessionStorage + 动态开场白 |
| `frontend/app/interview/_components/interview-chat.test.tsx` | 修改 | 新增 context 场景测试 |
| `frontend/app/coach/coach-dashboard.tsx` | 修改 | 真实 API 调用；移除 Demo toggle；写 sessionStorage |
| `frontend/app/coach/coach-dashboard.test.tsx` | 新建 | 骨架屏、老用户 UI、新用户 UI 测试 |

---

## Task 1: Backend Schema 扩展

**Files:**
- Modify: `backend/app/schemas/interview.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/unit/test_interview_schema.py` 末尾追加：

```python
def test_user_context_response_new_user():
    """新用户：is_returning=False，role/company/background 均为 None，session_count=0。"""
    from app.schemas.interview import UserContextResponse
    resp = UserContextResponse(
        is_returning=False, target_role=None,
        target_company=None, user_background=None, session_count=0
    )
    assert resp.is_returning is False
    assert resp.session_count == 0


def test_user_context_response_returning_user():
    """老用户：is_returning=True，role 有值。"""
    from app.schemas.interview import UserContextResponse
    resp = UserContextResponse(
        is_returning=True, target_role="AI Agent 工程师",
        target_company="字节跳动", user_background="LangGraph 系统",
        session_count=7
    )
    assert resp.is_returning is True
    assert resp.target_role == "AI Agent 工程师"


def test_reset_request_allows_empty_body():
    """ResetRequest 的两个字段均为可选，空 body 等价于 {}。"""
    from app.schemas.interview import ResetRequest
    req = ResetRequest()
    assert req.target_role is None
    assert req.user_background is None


def test_reset_request_with_context():
    """ResetRequest 可携带岗位与背景。"""
    from app.schemas.interview import ResetRequest
    req = ResetRequest(target_role="前端工程师", user_background="Vue 项目")
    assert req.target_role == "前端工程师"
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interview_schema.py -v -k "user_context or reset_request"
```

预期：`ERROR` —— `ImportError: cannot import name 'UserContextResponse'`

- [ ] **Step 3: 实现 schema**

在 `backend/app/schemas/interview.py` 末尾追加：

```python
class UserContextResponse(BaseModel):
    """GET /interview/context 的响应：用于 Coach 页面判断新老用户。"""

    is_returning: bool
    target_role: str | None
    target_company: str | None
    user_background: str | None
    session_count: int


class ResetRequest(BaseModel):
    """POST /interview/reset 的可选请求体：携带 Coach 收集的上下文。"""

    target_role: str | None = None
    user_background: str | None = None
```

- [ ] **Step 4: 运行以确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interview_schema.py -v -k "user_context or reset_request"
```

预期：4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/interview.py backend/tests/unit/test_interview_schema.py
git commit -m "feat(interview): 新增 UserContextResponse 和 ResetRequest schema"
```

---

## Task 2: Backend Service — `get_user_interview_context`

**Files:**
- Modify: `backend/app/services/interview_turn.py`
- Modify: `backend/tests/integration/test_interview_turn_service.py`

- [ ] **Step 1: 写失败集成测试**

在 `backend/tests/integration/test_interview_turn_service.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_get_user_interview_context_new_user(db):
    """没有任何历史 session：is_returning=False，字段全为 None，count=0。"""
    from app.services.interview_turn import get_user_interview_context

    user_id = f"user_ctx_new_{uuid4().hex}"
    await ensure_user_exists(db, user_id=user_id)

    result = await get_user_interview_context(db, user_id=user_id)

    assert result["is_returning"] is False
    assert result["target_role"] is None
    assert result["session_count"] == 0


@pytest.mark.asyncio
async def test_get_user_interview_context_returning_user(db):
    """有含 target_role 的历史 session：is_returning=True，返回最近的 role。"""
    from app.services.interview_turn import get_user_interview_context

    user_id = f"user_ctx_ret_{uuid4().hex}"
    await ensure_user_exists(db, user_id=user_id)

    session = InterviewSession(user_id=user_id, status="completed", target_role="AI Agent 工程师")
    db.add(session)
    await db.flush()

    result = await get_user_interview_context(db, user_id=user_id)

    assert result["is_returning"] is True
    assert result["target_role"] == "AI Agent 工程师"
    assert result["session_count"] == 1


@pytest.mark.asyncio
async def test_get_user_interview_context_ignores_sessions_without_role(db):
    """所有 session 的 target_role 均为 None 时，仍视为新用户。"""
    from app.services.interview_turn import get_user_interview_context

    user_id = f"user_ctx_norole_{uuid4().hex}"
    await ensure_user_exists(db, user_id=user_id)

    session = InterviewSession(user_id=user_id, status="abandoned", target_role=None)
    db.add(session)
    await db.flush()

    result = await get_user_interview_context(db, user_id=user_id)

    assert result["is_returning"] is False
    assert result["target_role"] is None
    assert result["session_count"] == 1
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py -v -k "get_user_interview_context"
```

预期：`ImportError: cannot import name 'get_user_interview_context'`

- [ ] **Step 3: 实现 service 函数**

在 `backend/app/services/interview_turn.py` 的 `reset_interview_session` 函数前插入：

```python
async def get_user_interview_context(db: AsyncSession, *, user_id: str) -> dict:
    """返回 Coach 页面所需的用户上下文：最近有效 session 的岗位信息与历史场次数。"""
    count_result = await db.execute(
        select(func.count())
        .select_from(InterviewSession)
        .where(InterviewSession.user_id == user_id)
    )
    session_count = count_result.scalar_one()

    latest_result = await db.execute(
        select(InterviewSession)
        .where(
            InterviewSession.user_id == user_id,
            InterviewSession.target_role.is_not(None),
        )
        .order_by(InterviewSession.started_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()

    if latest is None:
        return {
            "is_returning": False,
            "target_role": None,
            "target_company": None,
            "user_background": None,
            "session_count": session_count,
        }

    return {
        "is_returning": True,
        "target_role": latest.target_role,
        "target_company": latest.target_company,
        "user_background": latest.user_background,
        "session_count": session_count,
    }
```

- [ ] **Step 4: 运行以确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py -v -k "get_user_interview_context"
```

预期：3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview_turn.py backend/tests/integration/test_interview_turn_service.py
git commit -m "feat(interview): 新增 get_user_interview_context service"
```

---

## Task 3: Backend Service — 扩展 `reset_interview_session`

**Files:**
- Modify: `backend/app/services/interview_turn.py`
- Modify: `backend/tests/integration/test_interview_turn_service.py`

- [ ] **Step 1: 写失败集成测试**

在 `backend/tests/integration/test_interview_turn_service.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_reset_interview_session_preseeds_context(db):
    """携带 target_role 时，reset 创建预置岗位的新 session。"""
    from app.services.interview_turn import reset_interview_session

    user_id = f"user_reset_ctx_{uuid4().hex}"
    old_session, _ = await get_or_create_active_session(db, user_id=user_id)
    await db.commit()

    await reset_interview_session(
        db, user_id=user_id, target_role="前端工程师", user_background="Vue 项目"
    )

    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.status == "in_progress")
    )
    new_session = result.scalar_one_or_none()

    assert new_session is not None
    assert new_session.id != old_session.id
    assert new_session.target_role == "前端工程师"
    assert new_session.user_background == "Vue 项目"


@pytest.mark.asyncio
async def test_reset_without_context_does_not_create_new_session(db):
    """不携带 target_role 时，reset 只 abandon 旧 session，不预建新 session。"""
    from app.services.interview_turn import reset_interview_session

    user_id = f"user_reset_noctx_{uuid4().hex}"
    await get_or_create_active_session(db, user_id=user_id)
    await db.commit()

    await reset_interview_session(db, user_id=user_id)

    result = await db.execute(
        select(InterviewSession)
        .where(InterviewSession.user_id == user_id, InterviewSession.status == "in_progress")
    )
    assert result.scalar_one_or_none() is None
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py -v -k "reset_interview_session_preseeds or reset_without_context"
```

预期：`TypeError: reset_interview_session() got an unexpected keyword argument 'target_role'`

- [ ] **Step 3: 扩展 `reset_interview_session`**

将 `backend/app/services/interview_turn.py` 中的 `reset_interview_session` 函数替换为：

```python
async def reset_interview_session(
    db: AsyncSession,
    *,
    user_id: str,
    target_role: str | None = None,
    user_background: str | None = None,
) -> None:
    """放弃当前用户所有进行中的面试 session。

    若携带 target_role，则在 abandon 旧 session 后立即创建预置岗位信息的新 session，
    供 LangGraph opening 节点直接跳过重新收集。
    """
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.user_id == user_id,
            InterviewSession.status == "in_progress",
        )
    )
    sessions = result.scalars().all()
    for session in sessions:
        session.status = "abandoned"
        log.info("interview_session_reset", user_id=user_id, session_id=str(session.id))

    if target_role:
        new_session = InterviewSession(
            user_id=user_id,
            target_role=target_role,
            user_background=user_background,
        )
        db.add(new_session)
        log.info(
            "interview_session_preseeded",
            user_id=user_id,
            target_role=target_role,
        )

    if sessions or target_role:
        await db.commit()
```

- [ ] **Step 4: 运行以确认通过**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_interview_turn_service.py -v -k "reset"
```

预期：所有 reset 相关测试 PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/interview_turn.py backend/tests/integration/test_interview_turn_service.py
git commit -m "feat(interview): reset 支持携带岗位上下文预建新 session"
```

---

## Task 4: Backend Routes — 新增 `GET /context`，扩展 `POST /reset`

**Files:**
- Modify: `backend/app/api/v1/interview.py`
- Modify: `backend/tests/unit/test_interview_routes.py`

- [ ] **Step 1: 写路由单元测试（失败）**

在 `backend/tests/unit/test_interview_routes.py` 末尾追加：

```python
async def _fake_get_context(db, *, user_id):
    return {
        "is_returning": True,
        "target_role": "AI Agent 工程师",
        "target_company": None,
        "user_background": "LangGraph 系统",
        "session_count": 7,
    }


async def _fake_get_context_new(db, *, user_id):
    return {
        "is_returning": False,
        "target_role": None,
        "target_company": None,
        "user_background": None,
        "session_count": 0,
    }


def test_context_returns_returning_user_data():
    """GET /context 老用户：is_returning=True，含 target_role。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.get_user_interview_context", _fake_get_context):
            resp = TestClient(app).get("/api/v1/interview/context")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["is_returning"] is True
    assert body["target_role"] == "AI Agent 工程师"
    assert body["session_count"] == 7


def test_context_returns_new_user_data():
    """GET /context 新用户：is_returning=False，role 为 null。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.get_user_interview_context", _fake_get_context_new):
            resp = TestClient(app).get("/api/v1/interview/context")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["is_returning"] is False


def test_context_requires_auth():
    """GET /context 无效 token 必须 401。"""
    resp = TestClient(app).get(
        "/api/v1/interview/context",
        headers={"Authorization": "Bearer invalid"},
    )
    assert resp.status_code == 401


def test_reset_with_context_passes_role_to_service():
    """POST /reset 携带 target_role 时，service 以正确参数被调用。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_reset = AsyncMock()
    try:
        with patch("app.api.v1.interview.reset_interview_session", mock_reset):
            resp = TestClient(app).post(
                "/api/v1/interview/reset",
                json={"target_role": "前端工程师", "user_background": "Vue 项目"},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    mock_reset.assert_awaited_once()
    _, kwargs = mock_reset.call_args
    assert kwargs["target_role"] == "前端工程师"
    assert kwargs["user_background"] == "Vue 项目"


def test_reset_without_body_still_works():
    """POST /reset 不带 body 时仍然返回 {status: ok}（保持向后兼容）。"""
    app.dependency_overrides[get_current_user_id] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    mock_reset = AsyncMock()
    try:
        with patch("app.api.v1.interview.reset_interview_session", mock_reset):
            resp = TestClient(app).post("/api/v1/interview/reset")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interview_routes.py -v -k "context or reset_with_context or reset_without_body"
```

预期：`404 Not Found` 或 `ImportError`

- [ ] **Step 3: 更新路由文件**

将 `backend/app/api/v1/interview.py` 替换为：

```python
"""面试对话接口：以 SSE 流式返回面试官回复。"""
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.core.auth import get_current_user_id
from app.db.session import get_db
from app.schemas.interview import ChatRequest, ResetRequest, TurnRequest, UserContextResponse
from app.services.interview_chat import stream_interview_reply
from app.services.interview_turn import (
    get_user_interview_context,
    reset_interview_session,
    stream_interview_turn,
)

router = APIRouter(prefix="/interview")


@router.post("/chat")
async def chat(
    req: ChatRequest, user_id: str = Depends(get_current_user_id)
) -> EventSourceResponse:
    """面试官单轮流式问答：逐段以 delta 事件下发，正常结束发 done，失败发 error。

    鉴权/入参校验失败（401/422）由全局异常处理器以统一 Response 返回，不进入此流。
    """

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        try:
            async for text in stream_interview_reply(req.messages, user_id=user_id):
                yield {"event": "delta", "data": json.dumps({"text": text}, ensure_ascii=False)}
            yield {"event": "done", "data": "{}"}
        except Exception:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "AI 暂时无法响应，请稍后重试"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(
        event_gen(),
        headers={
            "Deprecation": "true",
            "Link": '</api/v1/interview/turn>; rel="successor-version"',
            "X-Deprecated-Endpoint": "Use /api/v1/interview/turn",
        },
    )


@router.post("/turn")
async def turn(
    req: TurnRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> EventSourceResponse:
    """统一面试入口：前端只传本轮 message，后端按 Clerk user_id 管内部 run。"""

    async def event_gen() -> AsyncIterator[dict[str, str]]:
        try:
            async for event in stream_interview_turn(req.message, user_id=user_id, db=db):
                yield {
                    "event": event["event"],
                    "data": json.dumps(event["data"], ensure_ascii=False),
                }
        except Exception:
            yield {
                "event": "error",
                "data": json.dumps(
                    {"message": "AI 暂时无法响应，请稍后重试"}, ensure_ascii=False
                ),
            }

    return EventSourceResponse(event_gen())


@router.get("/context", response_model=UserContextResponse)
async def get_context(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserContextResponse:
    """返回 Coach 页面所需的用户上下文：判断新老用户、展示历史岗位信息。"""
    data = await get_user_interview_context(db, user_id=user_id)
    return UserContextResponse(**data)


@router.post("/reset")
async def reset(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    req: ResetRequest | None = None,
) -> dict:
    """放弃当前进行中的面试；可携带 Coach 收集的岗位上下文预建新 session。"""
    await reset_interview_session(
        db,
        user_id=user_id,
        target_role=req.target_role if req else None,
        user_background=req.user_background if req else None,
    )
    return {"status": "ok"}
```

- [ ] **Step 4: 运行全部路由测试**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_interview_routes.py -v
```

预期：全部 PASSED（包含新增测试）

- [ ] **Step 5: Lint + typecheck**

```bash
cd backend && .venv/bin/python -m ruff check . && .venv/bin/python -m mypy app
```

预期：无错误

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/v1/interview.py backend/app/schemas/interview.py backend/tests/unit/test_interview_routes.py
git commit -m "feat(interview): 新增 GET /context 路由，POST /reset 支持携带上下文"
```

---

## Task 5: Frontend lib — `fetchInterviewContext` + 扩展 `resetInterviewSession`

**Files:**
- Modify: `frontend/lib/interview-chat.ts`
- Modify: `frontend/lib/interview-chat.test.ts`

- [ ] **Step 1: 写失败测试**

在 `frontend/lib/interview-chat.test.ts` 末尾追加：

```typescript
describe("fetchInterviewContext", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("调用 GET /context 并返回用户上下文", async () => {
    const payload = {
      is_returning: true,
      target_role: "AI Agent 工程师",
      target_company: null,
      user_background: "LangGraph 系统",
      session_count: 7,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify(payload), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { fetchInterviewContext } = await import("./interview-chat");
    const result = await fetchInterviewContext({ token: "test-token" });

    expect(result.is_returning).toBe(true);
    expect(result.target_role).toBe("AI Agent 工程师");
    expect(result.session_count).toBe(7);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/interview/context",
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: "Bearer test-token" }),
      }),
    );
  });

  it("HTTP 失败时抛出错误", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 401 })));
    const { fetchInterviewContext } = await import("./interview-chat");
    await expect(fetchInterviewContext({ token: "bad" })).rejects.toThrow("获取用户信息失败");
  });
});

describe("resetInterviewSession with context", () => {
  beforeEach(() => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://localhost:8000");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("携带 target_role 时发送 JSON body", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { resetInterviewSession } = await import("./interview-chat");
    await resetInterviewSession({
      token: "test-token",
      target_role: "前端工程师",
      user_background: "Vue 项目",
    });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body.target_role).toBe("前端工程师");
    expect(body.user_background).toBe("Vue 项目");
  });

  it("不携带 target_role 时 body 为空对象", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { resetInterviewSession } = await import("./interview-chat");
    await resetInterviewSession({ token: "test-token" });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse(call[1].body);
    expect(body).toEqual({});
  });
});
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd frontend && pnpm test -- --reporter=verbose lib/interview-chat.test.ts
```

预期：`fetchInterviewContext is not a function`

- [ ] **Step 3: 更新 `frontend/lib/interview-chat.ts`**

```typescript
import { readSseStream, type SseEvent } from "./sse";

export type InterviewChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type InterviewProgressState = {
  stage: "opening" | "interview" | "closing";
  question_count: number;
  total_questions: number;
};

export interface InterviewReport {
  overall_score: number;
  technical_depth: number;
  quantified_results: number;
  failure_tradeoffs: number;
  structure: number;
  highlights: string[];
  improvements: string[];
}

export type UserContextResponse = {
  is_returning: boolean;
  target_role: string | null;
  target_company: string | null;
  user_background: string | null;
  session_count: number;
};

type StreamInterviewChatOptions = {
  token: string;
  message: string;
  signal?: AbortSignal;
  onDelta: (text: string) => void;
  onState?: (state: InterviewProgressState) => void;
  onReport?: (report: InterviewReport) => void;
};

const DEFAULT_ERROR_MESSAGE = "请求失败，请稍后重试";

/** 调用后端统一面试入口，并把 SSE state / delta / report 事件交给 UI 层渲染。 */
export async function streamInterviewChat({
  token,
  message,
  signal,
  onDelta,
  onState,
  onReport,
}: StreamInterviewChatOptions): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) {
    throw new Error("缺少后端接口配置");
  }

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/turn`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }

  await readSseStream({
    stream: response.body,
    onEvent: (event) => handleSseEvent(event, onDelta, onState, onReport),
  });
}

function handleSseEvent(
  { event, data }: SseEvent,
  onDelta: (text: string) => void,
  onState?: (state: InterviewProgressState) => void,
  onReport?: (report: InterviewReport) => void,
) {
  if (event === "done") return;

  if (event === "state") {
    const payload = parseJsonPayload<InterviewProgressState>(data);
    onState?.(payload);
    return;
  }

  if (event === "delta") {
    const payload = parseJsonPayload<{ text?: string }>(data);
    if (payload.text) onDelta(payload.text);
    return;
  }

  if (event === "report") {
    const payload = parseJsonPayload<InterviewReport>(data);
    onReport?.(payload);
    return;
  }

  if (event === "error") {
    const payload = parseJsonPayload<{ message?: string }>(data);
    throw new Error(payload.message || DEFAULT_ERROR_MESSAGE);
  }
}

/** 返回 Coach 页面所需的用户上下文，判断新老用户。 */
export async function fetchInterviewContext({
  token,
}: {
  token: string;
}): Promise<UserContextResponse> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/context`, {
    headers: { Authorization: `Bearer ${token}` },
  });

  if (!response.ok) throw new Error("获取用户信息失败");
  return response.json() as Promise<UserContextResponse>;
}

/** 放弃当前面试 session，可携带 Coach 收集的上下文预建新 session。失败时静默忽略，不影响 UI。 */
export async function resetInterviewSession({
  token,
  target_role,
  user_background,
}: {
  token: string;
  target_role?: string;
  user_background?: string;
}): Promise<void> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) return;

  const body: Record<string, string> = {};
  if (target_role) body.target_role = target_role;
  if (user_background) body.user_background = user_background;

  try {
    await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/interview/reset`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    // 网络错误不阻塞 UI 初始化
  }
}

function parseJsonPayload<T>(data: string): T {
  try {
    return JSON.parse(data) as T;
  } catch {
    throw new Error(DEFAULT_ERROR_MESSAGE);
  }
}
```

- [ ] **Step 4: 运行以确认通过**

```bash
cd frontend && pnpm test -- --reporter=verbose lib/interview-chat.test.ts
```

预期：全部 PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/lib/interview-chat.ts frontend/lib/interview-chat.test.ts
git commit -m "feat(interview): 前端 lib 新增 fetchInterviewContext，resetInterviewSession 支持携带上下文"
```

---

## Task 6: Frontend — InterviewChat 动态开场白

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`
- Modify: `frontend/app/interview/_components/interview-chat.test.tsx`

- [ ] **Step 1: 写失败测试**

在 `frontend/app/interview/_components/interview-chat.test.tsx` 的 `describe("InterviewChat")` 块末尾追加：

```typescript
  it("从 sessionStorage 读取上下文后显示确认消息", () => {
    sessionStorage.setItem(
      "interview_context",
      JSON.stringify({ target_role: "前端工程师", user_background: "Vue 项目" }),
    );

    render(<InterviewChat />);

    expect(screen.getByText(/前端工程师/)).toBeInTheDocument();
    expect(sessionStorage.getItem("interview_context")).toBeNull();
  });

  it("没有 sessionStorage 上下文时显示通用开场白", () => {
    sessionStorage.removeItem("interview_context");

    render(<InterviewChat />);

    expect(screen.getByText(/面试岗位/)).toBeInTheDocument();
  });
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd frontend && pnpm test -- --reporter=verbose app/interview/_components/interview-chat.test.tsx
```

预期：`从 sessionStorage 读取上下文后显示确认消息` FAIL —— 找不到"前端工程师"

- [ ] **Step 3: 更新 `interview-chat.tsx`**

在 `interview-chat.tsx` 中，将文件顶部的 `OPENING_MESSAGE` 常量和 `messages` useState 替换为：

```typescript
// 删除顶部的 OPENING_MESSAGE 常量

// 新增 buildOpeningMessage 函数（放在组件定义之前）：
function buildOpeningMessage(
  context: { target_role?: string; user_background?: string } | null,
): string {
  if (context?.target_role) {
    // ...
  }
  return "你好！在开始之前，请告诉我你想练习的面试岗位、公司，或特定的技术主题。\n\n**你可以这样发起：**\n\n**前端开发**\n\n**后端开发**\n\n**移动端开发**\n\n**Python AI Agent**";
}
```

然后在 `InterviewChat` 函数内，将 `useState<InterviewChatMessage[]>([OPENING_MESSAGE])` 替换为：

```typescript
const [messages, setMessages] = useState<InterviewChatMessage[]>(() => {
  if (typeof window === "undefined") {
    return [{ role: "assistant", content: buildOpeningMessage(null) }];
  }
  const raw = sessionStorage.getItem("interview_context");
  if (raw) sessionStorage.removeItem("interview_context");
  const ctx = raw
    ? (JSON.parse(raw) as { target_role?: string; user_background?: string })
    : null;
  return [{ role: "assistant", content: buildOpeningMessage(ctx) }];
});
```

将 `handleNewRound` 中的 `setMessages([OPENING_MESSAGE])` 替换为：

```typescript
setMessages([{ role: "assistant", content: buildOpeningMessage(null) }]);
```

- [ ] **Step 4: 运行所有面试聊天测试**

```bash
cd frontend && pnpm test -- --reporter=verbose app/interview/_components/interview-chat.test.tsx
```

预期：全部 PASSED（含原有测试与新增测试）

- [ ] **Step 5: Commit**

```bash
git add frontend/app/interview/_components/interview-chat.tsx frontend/app/interview/_components/interview-chat.test.tsx
git commit -m "feat(interview): 面试房间开场白根据 coach 传入的上下文动态生成"
```

---

## Task 7: Frontend — CoachDashboard 真实 API 数据

**Files:**
- Modify: `frontend/app/coach/coach-dashboard.tsx`
- Create: `frontend/app/coach/coach-dashboard.test.tsx`

- [ ] **Step 1: 写失败测试**

新建 `frontend/app/coach/coach-dashboard.test.tsx`：

```typescript
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CoachDashboard } from "./coach-dashboard";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: true,
    getToken: vi.fn().mockResolvedValue("test-token"),
  }),
}));

vi.mock("@/lib/interview-chat", () => ({
  fetchInterviewContext: vi.fn(),
  resetInterviewSession: vi.fn().mockResolvedValue(undefined),
}));

import { fetchInterviewContext } from "@/lib/interview-chat";
const mockFetch = vi.mocked(fetchInterviewContext);

describe("CoachDashboard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("加载期间显示骨架屏", () => {
    mockFetch.mockImplementation(() => new Promise(() => {})); // 永不 resolve
    render(<CoachDashboard />);
    expect(screen.getByTestId("coach-skeleton")).toBeInTheDocument();
  });

  it("老用户：显示「欢迎回来」并展示历史场次数", async () => {
    mockFetch.mockResolvedValue({
      is_returning: true,
      target_role: "AI Agent 工程师",
      target_company: null,
      user_background: "LangGraph 系统",
      session_count: 7,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/欢迎回来/)).toBeInTheDocument();
    });
    expect(screen.getByText(/7 场/)).toBeInTheDocument();
    expect(screen.queryByTestId("coach-skeleton")).not.toBeInTheDocument();
  });

  it("新用户：显示「你好，我还不认识你」和岗位选择按钮", async () => {
    mockFetch.mockResolvedValue({
      is_returning: false,
      target_role: null,
      target_company: null,
      user_background: null,
      session_count: 0,
    });

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "AI Agent 工程师" })).toBeInTheDocument();
  });

  it("API 失败时降级为新用户 UI", async () => {
    mockFetch.mockRejectedValue(new Error("网络错误"));

    render(<CoachDashboard />);

    await waitFor(() => {
      expect(screen.getByText(/还不认识你/)).toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: 运行以确认失败**

```bash
cd frontend && pnpm test -- --reporter=verbose app/coach/coach-dashboard.test.tsx
```

预期：多项 FAIL —— `coach-skeleton` 找不到、`fetchInterviewContext` 未被调用等

- [ ] **Step 3: 更新 `coach-dashboard.tsx`**

在文件顶部的 import 区域，添加：

```typescript
import { useAuth } from "@clerk/nextjs";
import { fetchInterviewContext, resetInterviewSession, type UserContextResponse } from "@/lib/interview-chat";
```

在组件内，将现有的 `userState` 相关状态替换为：

```typescript
const { isLoaded, isSignedIn, getToken } = useAuth();
const [isLoading, setIsLoading] = useState(true);
const [contextData, setContextData] = useState<UserContextResponse | null>(null);
// 兼容现有状态机，is_returning 对应 "returning"，否则 "new"
const userState: "returning" | "new" = contextData?.is_returning ? "returning" : "new";
```

删除 `resetConversation` 中对 `setUserState` 的调用（保留其他重置逻辑），改为：
```typescript
const resetConversation = () => {
  setUserMessage(null);
  setIsThinking(false);
  setInputText("");
  setSpeechStage("initial");
  setSelectedRole("");
  setSelectedTargetLabel("");
};
```

添加 API 加载 effect（紧接 `textareaRef` 定义之后）：

```typescript
useEffect(() => {
  if (!isLoaded || !isSignedIn) return;
  getToken().then(async (token) => {
    if (!token) { setIsLoading(false); return; }
    try {
      const data = await fetchInterviewContext({ token });
      setContextData(data);
    } catch {
      // 降级为新用户 UI
    } finally {
      setIsLoading(false);
    }
  });
}, [isLoaded, isSignedIn, getToken]);
```

将 `handleAction` 改为 async，并在 `"go-room"` 分支写入 sessionStorage + 调用 reset：

```typescript
const handleAction = async (action: string, extra?: string) => {
  // ... 其他 if/else 分支保持不变 ...
  } else if (action === "go-room") {
    const role = selectedRole || contextData?.target_role || "";
    const bg = userMessage || contextData?.user_background || "";
    if (role) {
      sessionStorage.setItem(
        "interview_context",
        JSON.stringify({ target_role: role, user_background: bg }),
      );
      const token = await getToken();
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
  // ... 其余 else if 分支不变
```

在 JSX 的最外层 `<div>` 内，最前面插入骨架屏：

```tsx
{isLoading && (
  <div data-testid="coach-skeleton" className="animate-pulse space-y-4 py-6">
    <div className="h-6 w-48 rounded bg-[#e8e7e2]" />
    <div className="h-4 w-72 rounded bg-[#e8e7e2]" />
    <div className="h-4 w-56 rounded bg-[#e8e7e2]" />
  </div>
)}
```

在骨架屏之后、其余内容之前加条件：`{!isLoading && (/* 原有 JSX */)}` 包裹剩余 Coach 内容。

同时，删除右上角 Demo toggle 区块（第 123–147 行）。

在老用户开场白中，将硬编码的 `7 场` 和历史数据改为使用 `contextData`：

```tsx
{/* 老用户开场语 */}
已陪你 <b className="text-[#525252] font-semibold">{contextData?.session_count ?? 0} 场</b>
```

- [ ] **Step 4: 运行测试**

```bash
cd frontend && pnpm test -- --reporter=verbose app/coach/coach-dashboard.test.tsx
```

预期：全部 PASSED

- [ ] **Step 5: Typecheck + build**

```bash
cd frontend && pnpm typecheck
```

预期：无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/app/coach/coach-dashboard.tsx frontend/app/coach/coach-dashboard.test.tsx
git commit -m "feat(coach): 替换 mock 数据为真实 API，移除 Demo toggle，写入 sessionStorage 上下文"
```

---

## Task 8: 全量验证

- [ ] **Step 1: 后端全量测试**

```bash
cd backend && .venv/bin/python -m pytest tests/ -v
```

预期：全部 PASSED

- [ ] **Step 2: 前端全量测试**

```bash
cd frontend && pnpm test
```

预期：全部 PASSED

- [ ] **Step 3: 前端 build**

```bash
cd frontend && pnpm build
```

预期：构建成功，无 TypeScript 或 ESLint 错误

- [ ] **Step 4: 手动验收（启动服务后执行）**

1. 直接访问 `/interview` → 应显示通用开场白（"面试岗位"字样）
2. 访问 `/coach` → 新用户：显示"还不认识你"，老用户：显示"欢迎回来 · N 场"
3. 老用户点"好，今天就练这个" → "进入考场" → `/interview` 显示确认消息（含 target_role）
4. 新用户选岗位 → "我直接试一场吧" → `/interview` 显示含岗位的确认消息
5. 刷新 `/interview` 后 sessionStorage 已清空，显示通用开场白（不重复显示上次 context）

- [ ] **Step 5: Commit（如有未 commit 改动）**

```bash
git add -p  # 按文件逐一确认
git commit -m "chore: 全量验证通过"
```
