# Backend-Chain Prepare-to-Interview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `/prepare/launch` 后端端点，将 prepare 多 Agent 流水线与面试开场轮（`__START__`）串联成单条 SSE 流，前端接收后自动进入面试，无需用户点击任何按钮。

**Architecture:** 后端新建 `POST /api/v1/prepare/launch` 端点（保持旧 `/prepare/start` 不变），内部先 `yield` prepare 阶段所有 SSE 事件，在 `done` 事件后接续发出合成 `node_start{launch}` → `phase_change` → `node_done{launch}` → 前缀 `turn_` 的面试 turn 事件流。前端 `handlePrepareEvent` 扩展处理新事件，`phase_change` 到达时在 `setMessages` 的 functional update 内原子设置 `assistantIndexRef`，彻底规避 stale closure 问题。

**Tech Stack:** Python / FastAPI / SQLAlchemy async / LangGraph；TypeScript / React / Next.js；SSE（text/event-stream）

---

## 事件协议（统一 SSE 流时序）

```
← init              {session_id}
← node_start        {node: "master", label: "MASTER"}
← node_token        {node: "master", text: "..."}
← node_done         {node: "master", elapsed_ms, chain, need_direction}
← node_start        {node: "memory_search"} [按需]
← node_done         {node: "memory_search"}
← node_start        {node: "question_gen"}
← node_token        {node: "question_gen", text: "..."} x N
← node_done         {node: "question_gen"}
← done              {jd_context, prepared_questions, summary, direction}
← node_start        {node: "launch", label: "进入面试"}
← node_done         {node: "launch"}
← phase_change      {turn_id: "<uuid>"}
← turn_node_start   {node: "master", label: "调度"}
← turn_node_token   {node: "master", text: "..."}
← turn_node_done    {node: "master", elapsed_ms}
← turn_node_start   {node: "ask_question", label: "出题官"}
← turn_node_done    {node: "ask_question", elapsed_ms}
← turn_delta        {text: "..."}  x N
← turn_state        {stage, question_count, total_questions}
← turn_report       {...}   [仅 closing 阶段]
← turn_done         {}
```

`need_direction=true` 时（用户未提供岗位方向），流在 `node_done{master}` 后结束，不继续自动进入面试——与旧行为一致。

---

## File Map

| 角色 | 路径 | 变更 |
|---|---|---|
| 后端新端点 | `backend/app/api/v1/prepare.py` | 新增 `/prepare/launch` route + `stream_prepare_and_launch` generator |
| 后端测试 | `backend/tests/unit/test_prepare_launch.py` | 新建，覆盖 happy path + need_direction 早退 |
| 前端类型 | `frontend/lib/prepare-types.ts` | `PrepareSSEEvent.event` 添加新事件名 |
| 前端 API | `frontend/lib/interview-chat.ts` | 新增 `startPrepareAndLaunchStreamFetch` |
| 前端组件 | `frontend/app/interview/_components/interview-chat.tsx` | 扩展 `handlePrepareEvent`；移除上一次加的 auto-start `useEffect` |

---

## Task 1：后端 `stream_prepare_and_launch` generator

**Files:**
- Modify: `backend/app/api/v1/prepare.py`
- Create: `backend/tests/unit/test_prepare_launch.py`

### Step 1-1：写失败测试

```python
# backend/tests/unit/test_prepare_launch.py
"""Unit tests for stream_prepare_and_launch generator."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# 被测 generator（待实现）
from app.api.v1.prepare import stream_prepare_and_launch
from app.agents.prepare.state import PrepareState


def _make_state(need_direction: bool = False) -> PrepareState:
    return {
        "session_id": "test-session",
        "user_id": "user-1",
        "user_direction": None if need_direction else "前端工程师",
        "user_background": None,
        "jd_raw": None,
        "weak_areas": [],
        "star_stories": [],
    }


MOCK_PREPARE_EVENTS_NORMAL = [
    {"event": "node_start", "data": {"node": "master", "label": "MASTER"}},
    {"event": "node_done",  "data": {"node": "master", "elapsed_ms": 100, "chain": ["question_gen"], "need_direction": False}},
    {"event": "node_start", "data": {"node": "question_gen", "label": "出题"}},
    {"event": "node_done",  "data": {"node": "question_gen", "elapsed_ms": 200}},
    {
        "event": "done",
        "data": {
            "jd_context": None,
            "prepared_questions": [{"id": 1, "question": "Q1", "category": "technical", "focus_area": "f", "priority": 1}],
            "summary": "1道题",
            "direction": "前端工程师",
        },
    },
]

MOCK_PREPARE_EVENTS_NEED_DIRECTION = [
    {"event": "node_start", "data": {"node": "master", "label": "MASTER"}},
    {"event": "node_done",  "data": {"node": "master", "elapsed_ms": 100, "chain": [], "need_direction": True}},
]

MOCK_TURN_EVENTS = [
    {"event": "node_start", "data": {"node": "master", "label": "调度", "phase": "start"}},
    {"event": "node_done",  "data": {"node": "master", "elapsed_ms": 50,  "phase": "done"}},
    {"event": "delta",      "data": {"text": "好的，第一题："}},
    {"event": "state",      "data": {"stage": "interview", "question_count": 1, "total_questions": 5}},
    {"event": "done",       "data": {}},  # service 本身会发的 done，generator 应吞掉、自行合成 turn_done
]


async def _collect(gen) -> list[dict]:
    result = []
    async for ev in gen:
        result.append(ev)
    return result


@pytest.mark.asyncio
async def test_happy_path_event_sequence():
    """正常流：prepare done 后接 launch 节点 + phase_change + 前缀 turn_* 事件。"""
    mock_db = AsyncMock()

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NORMAL:
            yield ev

    # 注意：stream_interview_turn 的 message 是 positional 参数（见 service 签名），
    # mock 必须接受 positional + kwargs，否则 side_effect 透传 positional 会触发 TypeError。
    async def mock_turn_stream(message, **kwargs):
        assert message == "__START__"
        for ev in MOCK_TURN_EVENTS:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn", side_effect=mock_turn_stream),
    ):
        events = await _collect(
            stream_prepare_and_launch(_make_state(), db=mock_db)
        )

    event_names = [e["event"] for e in events]

    # prepare 事件原样透传
    assert "node_start" in event_names
    # service 自带的 done 事件仅有 prepare 阶段一次（mock_turn 的 done 应被吞掉）
    assert event_names.count("done") == 1

    # launch 节点
    launch_start_idx = next(i for i, e in enumerate(events) if e["event"] == "node_start" and e["data"]["node"] == "launch")
    launch_done_idx  = next(i for i, e in enumerate(events) if e["event"] == "node_done"  and e["data"]["node"] == "launch")
    phase_change_idx = next(i for i, e in enumerate(events) if e["event"] == "phase_change")

    done_idx = next(i for i, e in enumerate(events) if e["event"] == "done")

    # 顺序：prepare.done < launch_start < launch_done < phase_change < turn 事件
    assert done_idx < launch_start_idx < launch_done_idx < phase_change_idx

    # phase_change 携带 turn_id
    assert "turn_id" in events[phase_change_idx]["data"]

    # turn 事件被加 turn_ 前缀
    turn_events = [e for e in events if e["event"].startswith("turn_")]
    assert any(e["event"] == "turn_delta" for e in turn_events)
    assert any(e["event"] == "turn_state" for e in turn_events)
    assert events[-1]["event"] == "turn_done"


@pytest.mark.asyncio
async def test_need_direction_stops_before_launch():
    """need_direction=True：prepare 事件后不产生 launch 节点，不调 turn。"""
    mock_db = AsyncMock()

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NEED_DIRECTION:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn") as mock_turn,
    ):
        events = await _collect(
            stream_prepare_and_launch(_make_state(need_direction=True), db=mock_db)
        )

    mock_turn.assert_not_called()
    assert all(e["event"] != "phase_change" for e in events)
    assert all(e["event"] != "turn_done" for e in events)


@pytest.mark.asyncio
async def test_prepared_questions_passed_to_turn():
    """prepared_questions 从 done 事件提取后正确透传给 stream_interview_turn。"""
    mock_db = AsyncMock()
    captured: dict = {}

    async def mock_prepare_stream(state):
        for ev in MOCK_PREPARE_EVENTS_NORMAL:
            yield ev

    async def mock_turn_stream(message, **kwargs):
        captured["message"] = message
        captured.update(kwargs)
        for ev in MOCK_TURN_EVENTS:
            yield ev

    with (
        patch("app.api.v1.prepare.stream_prepare_events", side_effect=mock_prepare_stream),
        patch("app.api.v1.prepare.stream_interview_turn", side_effect=mock_turn_stream),
    ):
        await _collect(stream_prepare_and_launch(_make_state(), db=mock_db))

    assert captured.get("message") == "__START__"
    pqs = captured.get("prepared_questions", [])
    assert len(pqs) == 1
    assert pqs[0]["question"] == "Q1"
```

- [ ] **Step 1-2：运行测试验证失败**

```bash
cd backend
pytest tests/unit/test_prepare_launch.py -v 2>&1 | head -30
```

预期：`ImportError: cannot import name 'stream_prepare_and_launch'`

- [ ] **Step 1-3：实现 `stream_prepare_and_launch` generator**

在 `backend/app/api/v1/prepare.py` 顶部 import 区域追加（位置：现有 `import json` 之后；旧文件中 `prepare_start` 函数内的 `import uuid` 也一并提到顶部，避免重复）：

```python
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.interview_turn import stream_interview_turn
```

> 同时把现有 `prepare_start` 和 `prepare_launch` 内部函数体里的 `import uuid` 删除（已提到顶部）。

然后在文件末尾（`prepare_resume` 路由之后）添加 generator 函数和新路由：

```python
# 哪些 service-side 事件需要透传给前端（加 turn_ 前缀）。
# done 单独吞掉、由本 generator 自行合成最终 turn_done。
_TURN_FORWARD_EVENTS = frozenset({
    "node_start", "node_token", "node_done", "delta", "state", "report",
})


async def stream_prepare_and_launch(
    state: PrepareState,
    *,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Prepare + interview 开场一体化 SSE generator。

    事件时序：
      prepare 阶段事件（node_start/token/done/...→ done）
      → node_start{launch} → node_done{launch} → phase_change{turn_id}
      → turn_* 面试事件 → turn_done
    need_direction=True 时在 prepare 阶段结束后直接返回，不接续面试。
    """
    prepared_questions: list[dict] = []
    jd_context: dict | None = None
    need_direction = False

    # Phase 1: 透传 prepare 流
    async for ev in stream_prepare_events(state):
        yield ev
        evt = ev.get("event", "")
        if evt == "done":
            data = ev.get("data", {})
            prepared_questions = data.get("prepared_questions", []) or []
            jd_context = data.get("jd_context")
        if evt == "node_done" and ev.get("data", {}).get("need_direction"):
            need_direction = True

    if need_direction:
        return  # 用户未提供方向，停在准备阶段等追问

    # Phase 2: 合成 "launch" 节点 + phase_change
    # 把 launch 节点的 start/done 当作 prepare 阶段最后一个子节点，
    # 然后再发 phase_change 作为"切到 turn 模式"的明确分界，前端处理时序更干净。
    turn_id = str(uuid.uuid4())
    yield {"event": "node_start", "data": {"node": "launch", "label": "进入面试"}}
    yield {"event": "node_done", "data": {"node": "launch"}}
    yield {"event": "phase_change", "data": {"turn_id": turn_id}}

    # Phase 3: 面试 turn，事件加 turn_ 前缀；吞掉 service 的 done，自行合成 turn_done。
    async for turn_ev in stream_interview_turn(
        "__START__",
        user_id=state["user_id"],
        db=db,
        prepared_questions=prepared_questions or None,
        jd_context=jd_context,
    ):
        turn_event = turn_ev.get("event", "")
        if turn_event == "done":
            break
        if turn_event in _TURN_FORWARD_EVENTS:
            yield {"event": f"turn_{turn_event}", "data": turn_ev.get("data", {})}
    yield {"event": "turn_done", "data": {}}


@router.post("/prepare/launch")
async def prepare_launch(
    user_direction: str = Form(""),
    user_background: str = Form(""),
    jd_text: str = Form(""),
    jd_url: str = Form(""),
    jd_file: UploadFile | None = File(None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """准备 + 面试开场一体化端点：prepare pipeline 完成后自动接续 __START__ 轮。"""
    content_bytes = b""
    if jd_file and jd_file.filename:
        filename_lower = jd_file.filename.lower()
        if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".docx") or filename_lower.endswith(".doc")):
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")
        ALLOWED_TYPES = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }
        if jd_file.content_type not in ALLOWED_TYPES:
            raise HTTPException(status_code=400, detail="只支持 PDF 或 DOCX 文件")
        MAX_SIZE = 10 * 1024 * 1024
        content_bytes = await jd_file.read(MAX_SIZE + 1)
        if len(content_bytes) > MAX_SIZE:
            raise HTTPException(status_code=413, detail="文件大小不能超过 10MB")

    jd_raw: str | None = None
    try:
        if jd_text.strip():
            jd_raw = jd_text.strip()
        elif jd_file is not None and jd_file.filename:
            source = JDSource(type="file", filename=jd_file.filename, content_bytes=content_bytes)
            jd_raw = await extract_jd_text_async(source)
        elif jd_url.strip():
            source = JDSource(type="url", url=jd_url.strip())
            jd_raw = await extract_jd_text_async(source)
    except NeedManualInput as exc:
        err_msg = str(exc)
        async def _err():
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': err_msg, 'code': 'need_manual_input'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except Exception as exc:
        log.error("jd_extract_failed", error=str(exc))
        err_msg = "JD 提取失败，请手动粘贴 JD 文本后重试。"
        async def _generic_err():
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': err_msg, 'code': 'jd_extract_failed'}}, ensure_ascii=False)}\n\n"
        return StreamingResponse(_generic_err(), media_type="text/event-stream")

    import uuid
    session_id = str(uuid.uuid4())

    state: PrepareState = {
        "session_id": session_id,
        "user_id": user_id,
        "user_direction": user_direction or None,
        "user_background": user_background or None,
        "jd_raw": jd_raw,
        "weak_areas": [],
        "star_stories": [],
    }

    return StreamingResponse(
        _sse_format(stream_prepare_and_launch(state, db=db)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 1-4：运行测试验证通过**

```bash
cd backend
pytest tests/unit/test_prepare_launch.py -v
```

预期：3 tests PASSED

- [ ] **Step 1-5：提交**

```bash
git add backend/app/api/v1/prepare.py backend/tests/unit/test_prepare_launch.py
git commit -m "feat(backend): add /prepare/launch unified SSE endpoint chaining prepare → interview"
```

---

## Task 2：前端类型 & API 函数

**Files:**
- Modify: `frontend/lib/prepare-types.ts`
- Modify: `frontend/lib/interview-chat.ts`

- [ ] **Step 2-1：扩展 `PrepareSSEEvent.event` 类型**

打开 `frontend/lib/prepare-types.ts`，将：

```typescript
export interface PrepareSSEEvent {
  event: "node_start" | "node_token" | "node_done" | "done" | "error";
```

改为：

```typescript
export interface PrepareSSEEvent {
  event:
    | "node_start" | "node_token" | "node_done" | "done" | "error"
    | "phase_change"
    | "turn_node_start" | "turn_node_token" | "turn_node_done"
    | "turn_delta" | "turn_state" | "turn_report" | "turn_done";
```

同时在 `data` 字段补充新字段（包含 `turn_report` 的 `InterviewReport` 形状）：

```typescript
  data: {
    node?: string;
    label?: string;
    text?: string;
    elapsed_ms?: number;
    chain?: string[];
    need_direction?: boolean;
    prepared_questions?: PreparedQuestion[];
    jd_context?: JDContext;
    summary?: string;
    direction?: string;
    message?: string;
    code?: string;
    // phase_change
    turn_id?: string;
    // turn_state
    stage?: "opening" | "interview" | "closing";
    question_count?: number;
    total_questions?: number;
    // turn_report（仅 closing 阶段，service.stream_interview_turn 在 done 前会发一次）
    overall_score?: number;
    technical_depth?: number;
    quantified_results?: number;
    failure_tradeoffs?: number;
    structure?: number;
    highlights?: string[];
    improvements?: string[];
  };
```

- [ ] **Step 2-2：在 `interview-chat.ts` 添加 `startPrepareAndLaunchStreamFetch`**

打开 `frontend/lib/interview-chat.ts`，找到 `startPrepareStreamFetch` 函数。在该函数定义之后，新增：

```typescript
/** 启动 prepare + 面试开场一体化流（/prepare/launch）。 */
export async function* startPrepareAndLaunchStreamFetch({
  token,
  userDirection,
  userBackground,
  jdText,
  jdUrl,
  signal,
}: {
  token: string;
  userDirection?: string;
  userBackground?: string;
  jdText?: string;
  jdUrl?: string;
  signal?: AbortSignal;
}): AsyncGenerator<PrepareSSEEvent> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL;
  if (!baseUrl) throw new Error("缺少后端接口配置");

  const form = new FormData();
  if (userDirection) form.set("user_direction", userDirection);
  if (userBackground) form.set("user_background", userBackground);
  if (jdText) form.set("jd_text", jdText);
  if (jdUrl) form.set("jd_url", jdUrl);

  const resp = await fetch(`${baseUrl.replace(/\/$/, "")}/api/v1/prepare/launch`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
    signal,
  });

  if (!resp.ok || !resp.body) throw new Error("prepare/launch stream failed");

  for await (const ev of readSseStream(resp.body)) {
    const parsed = JSON.parse(ev.data) as PrepareSSEEvent;
    yield parsed;
  }
}
```

> `readSseStream` 和 `PrepareSSEEvent` 已在文件中导入/定义，无需额外引入。

- [ ] **Step 2-3：TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "app/layout.tsx"
```

预期：无新增错误（`layout.tsx` 里的 Clerk 版本警告是既有问题，忽略）

- [ ] **Step 2-4：提交**

```bash
git add frontend/lib/prepare-types.ts frontend/lib/interview-chat.ts
git commit -m "feat(frontend): add PrepareSSEEvent turn_* types and startPrepareAndLaunchStreamFetch"
```

---

## Task 3：前端 `handlePrepareEvent` 扩展 + 移除旧 auto-start effect

**Files:**
- Modify: `frontend/app/interview/_components/interview-chat.tsx`

此任务核心是让 `handlePrepareEvent` 能处理 `phase_change` / `turn_*` 事件，并在 `phase_change` 时原子设置 `assistantIndexRef`（避免 stale closure）。同时移除上一次在前端加的 auto-start `useEffect`，改为由后端驱动。

- [ ] **Step 3-1：在 `interview-chat.tsx` 顶部 import 添加 `startPrepareAndLaunchStreamFetch`**

找到现有 import：

```typescript
  startPrepareStreamFetch,
  resumePrepareStreamFetch,
```

在其后添加：

```typescript
  startPrepareAndLaunchStreamFetch,
```

- [ ] **Step 3-2：添加 `currentTurnIdRef`**

在 `abortRef` 附近（约 168 行），已有：

```typescript
  const abortRef = useRef<AbortController | null>(null);
  const prepAbortRef = useRef<AbortController | null>(null);
  const assistantIndexRef = useRef<number | null>(null);
```

在这组 ref 后面追加：

```typescript
  const currentTurnIdRef = useRef<string | null>(null);
```

- [ ] **Step 3-3：给 auto-start `useEffect` 加 guard，保留作为 resume 路径兜底**

> ⚠️ 关键决策：当走 `/prepare/launch`（autoLaunch=true）时，后端会主动发 `phase_change` 触发开场；
> 但走 `/prepare/resume`（用户回答 need_direction 追问）时，后端仍只发 prepare 事件，前端必须自己接力。
> 因此 auto-start `useEffect` **不能删**，只需加一行 guard：若已被 `phase_change` 接管（`currentTurnIdRef` 非空），跳过自启动。
> `handleStartFirstQuestionRef` 也保留，仍作为该 effect 的回调入口。
>
> 不加 guard 的话，resume 路径删 effect 后用户会卡住——"开始本轮面试"按钮已删，无入口可点。

找到现有代码：

```typescript
  // 准备完成后自动加"进入面试"节点并触发开场
  useEffect(() => {
    if (prepStatus !== "done") return;
```

在 `if (prepStatus !== "done") return;` 之后立刻插入一行 guard：

```typescript
  useEffect(() => {
    if (prepStatus !== "done") return;
    // 已经由后端 phase_change 接管开场（/prepare/launch 路径），跳过前端 auto-start。
    if (currentTurnIdRef.current) return;
```

`handleStartFirstQuestionRef` 与 `handleStartFirstQuestion` 函数本身 **保持不变**——仍是 resume 路径的开场入口。

- [ ] **Step 3-4a：把现有 `error` 分支改为 phase-aware**

找到 `handlePrepareEvent` 顶部已有：

```typescript
    if (event === "error") {
      fallbackFromPrepareFailure(initialContextRef.current);
      return;
    }
```

替换为：

```typescript
    if (event === "error") {
      // 错误若发生在 turn 阶段（currentTurnIdRef 非空），不能走 prepare-only 的 fallback——
      // 那会清掉 prepare trace 但留下半截 user/assistant/turn 消息形成僵尸 UI。
      if (currentTurnIdRef.current) {
        const turnId = currentTurnIdRef.current;
        const assistantIdx = assistantIndexRef.current;
        const errMsg = data.message ?? "AI 暂时无法响应，请稍后重试";
        discardBufferedDelta();
        setMessages((prev) =>
          prev.map((m, i) =>
            i === assistantIdx && isTextMessage(m) ? { ...m, content: errMsg } : m,
          ),
        );
        finishTurnTrace(turnId);
        setIsStreaming(false);
        assistantIndexRef.current = null;
        currentTurnIdRef.current = null;
        return;
      }
      fallbackFromPrepareFailure(initialContextRef.current);
      return;
    }
```

> `isTextMessage` 已在文件顶部 import；`discardBufferedDelta` / `finishTurnTrace` 也是组件内已有的工具函数。

- [ ] **Step 3-4b：在 `handlePrepareEvent` 末尾追加新事件分支**

在末尾（`if (event === "done")` 块之后，函数 `}` 之前）追加：

```typescript
    // ── Phase-change：后端信号接续面试开场 ──────────────────────────
    if (event === "phase_change") {
      const turnId = data.turn_id ?? crypto.randomUUID();
      currentTurnIdRef.current = turnId;
      const turnIndex = 1;

      setPrepStatus(null);
      setIsStreaming(true);

      // updater 外捕获 assistantIndex 后再写入 ref，规避 StrictMode 下 functional
      // updater 被双调用时对 ref 的 race；之后到达的 turn_delta 通过 scheduleDeltaFlush
      // 在下一帧 flush，此时 ref 已写好，时序安全。
      let newAssistantIndex = -1;
      setMessages((prev) => {
        newAssistantIndex = prev.length + 1;
        return [
          ...prev,
          { role: "user" as const, content: "开始本轮面试" },
          { role: "assistant" as const, content: "" },
          {
            role: "trace" as const,
            kind: "turn" as const,
            id: turnId,
            payload: {
              status: "running" as const,
              nodes: [],
              turnIndex,
              isOpening: true,
            },
          },
        ];
      });
      assistantIndexRef.current = newAssistantIndex;
    }

    // ── turn_node_* → 更新 turn trace ────────────────────────────────
    if (event === "turn_node_start" || event === "turn_node_token" || event === "turn_node_done") {
      const turnId = currentTurnIdRef.current;
      if (!turnId) return;

      const phase =
        event === "turn_node_start" ? "start"
        : event === "turn_node_token" ? "token"
        : "done";

      updateTurnTrace(turnId, {
        phase,
        node: data.node ?? "",
        label: data.label,
        text: data.text,
        elapsedMs: data.elapsed_ms,
      });
    }

    // ── turn_delta → 缓冲区追加文字 ──────────────────────────────────
    if (event === "turn_delta") {
      deltaBufferRef.current += data.text ?? "";
      scheduleDeltaFlush();
    }

    // ── turn_state → 更新进度 ─────────────────────────────────────────
    if (event === "turn_state") {
      setProgress({
        stage: (data.stage as "opening" | "interview" | "closing") ?? "interview",
        question_count: data.question_count ?? 0,
        total_questions: data.total_questions ?? 5,
      });
    }

    // ── turn_report → 设置评估报告（service 在 closing 阶段会发一次） ──
    // 开场轮一般不会到 closing，此分支是对协议完整性的保险，未来 fast-forward
    // 或合成完整面试的 launch 路径才会真正用到。
    if (event === "turn_report") {
      setReport({
        overall_score: data.overall_score ?? 0,
        technical_depth: data.technical_depth ?? 0,
        quantified_results: data.quantified_results ?? 0,
        failure_tradeoffs: data.failure_tradeoffs ?? 0,
        structure: data.structure ?? 0,
        highlights: data.highlights ?? [],
        improvements: data.improvements ?? [],
      });
    }

    // ── turn_done → 收尾 ─────────────────────────────────────────────
    if (event === "turn_done") {
      const turnId = currentTurnIdRef.current;
      flushBufferedDelta();
      if (turnId) finishTurnTrace(turnId);
      setIsStreaming(false);
      assistantIndexRef.current = null;
      currentTurnIdRef.current = null;
    }
```

- [ ] **Step 3-5：修改 `runPrepare` 调用改为按配置选择 endpoint**

> 只有从 Coach 页面传来 `target_role`/`jd_*` 的情况（即主动发起新面试）才走 launch 端点；用户在聊天框手动输入方向时，仍走原 `startPrepareStreamFetch`（因为 `/prepare/launch` 不支持二次 resume 流，resume 由独立 `/prepare/resume` 处理）。

找到 `runPrepare` 函数：

```typescript
  async function runPrepare(ctx: { target_role?: string; user_background?: string; jd_text?: string; jd_url?: string }) {
    prepAbortRef.current?.abort();
    const abortController = new AbortController();
    prepAbortRef.current = abortController;

    try {
      const token = isDevAuthBypassEnabled ? DEV_AUTH_BYPASS_TOKEN : (await getToken() ?? "");
      for await (const ev of startPrepareStreamFetch({
        token,
        userDirection: ctx.target_role,
        userBackground: ctx.user_background,
        jdText: ctx.jd_text,
        jdUrl: ctx.jd_url,
        signal: abortController.signal,
      })) {
        if (abortController.signal.aborted) break;
        handlePrepareEvent(ev);
      }
    } catch (err) {
      if (abortController.signal.aborted) return;
      console.error("Preparation stream failed:", err);
      fallbackFromPrepareFailure(ctx);
    }
  }
```

改为：

```typescript
  async function runPrepare(
    ctx: { target_role?: string; user_background?: string; jd_text?: string; jd_url?: string },
    { autoLaunch = false }: { autoLaunch?: boolean } = {},
  ) {
    prepAbortRef.current?.abort();
    const abortController = new AbortController();
    prepAbortRef.current = abortController;

    try {
      const token = isDevAuthBypassEnabled ? DEV_AUTH_BYPASS_TOKEN : (await getToken() ?? "");
      const streamFn = autoLaunch ? startPrepareAndLaunchStreamFetch : startPrepareStreamFetch;
      for await (const ev of streamFn({
        token,
        userDirection: ctx.target_role,
        userBackground: ctx.user_background,
        jdText: ctx.jd_text,
        jdUrl: ctx.jd_url,
        signal: abortController.signal,
      })) {
        if (abortController.signal.aborted) break;
        handlePrepareEvent(ev);
      }
    } catch (err) {
      if (abortController.signal.aborted) return;
      console.error("Preparation stream failed:", err);
      fallbackFromPrepareFailure(ctx);
    }
  }
```

- [ ] **Step 3-6：将初始 `runPrepare` 调用改为 `autoLaunch: true`**

在 `useEffect`（约 207 行）中，找到：

```typescript
          runPrepare(initialContextRef.current);
```

改为：

```typescript
          runPrepare(initialContextRef.current, { autoLaunch: true });
```

注意：`handleSend` 里用户手动输入方向触发的 `runPrepare` 调用**不**改（不加 `autoLaunch`），保持原行为（用户明确输入方向后需要手动触发面试，或由 `waiting_direction` 流程处理）。

- [ ] **Step 3-7：TypeScript 检查**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -v "app/layout.tsx"
```

预期：无新增错误

- [ ] **Step 3-8：提交**

```bash
git add frontend/app/interview/_components/interview-chat.tsx
git commit -m "feat(frontend): handle phase_change/turn_* events for backend-driven interview launch"
```

---

## Task 4：端到端冒烟测试

这一步在浏览器中验证完整流程。

- [ ] **Step 4-1：启动开发服务器**

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && pnpm dev
```

- [ ] **Step 4-2：打开 http://localhost:3000/coach，走正常面试发起流**

预期观察：
1. 在 Coach 页填写岗位/方向，点击"开始面试"
2. 跳转到 `/interview` 页，看到 prepare trace 节点依次出现（master → question_gen）
3. prepare done 后，trace 中自动追加"进入面试"节点（running → done）
4. 不需要点任何按钮，面试官问题直接流式出现
5. 进度条出现（stage: interview）

- [ ] **Step 4-3：验证 need_direction 场景仍能进入面试（关键回归点）**

在 Coach 页不填岗位方向，直接打开面试页并在聊天框输入方向。

预期：
1. prepare trace 出现 → `node_done{master, need_direction: true}` → 出现追问气泡
2. 用户输入方向 → `resumePrepareStreamFetch` 继续 prepare 流
3. resume 流结束后 `prepStatus === "done"`，**Step 3-3 保留的 auto-start `useEffect` 仍会触发**（因为它的 guard `currentTurnIdRef.current` 为 null，没被 phase_change 接管）→ 在 prepare trace 中追加 "进入面试" 节点 → 600ms 后调用 `handleStartFirstQuestion()` 走旧的 `/api/v1/interview/turn` `__START__` 路径
4. 出现第一道题，不卡住

> 这一步是 review S2 的关键修复：「开始本轮面试」按钮已在上一个 PR 删除，
> 如果完全删掉 auto-start effect，resume 路径会卡死。Step 3-3 的 guard 设计是为了让两条路径同时存活：
>   - `/prepare/launch` 路径：由 `phase_change` 接管，effect 被 guard 跳过
>   - `/prepare/resume` 路径：effect 仍然兜底

- [ ] **Step 4-4：回归检查**

打开 `http://localhost:3000/interview`（不带 sessionStorage context）：
- 预期被重定向回 `/coach`（守卫逻辑不变）

刷新面试进行中的页面：
- 预期从 `/interview/active` 恢复历史消息（不触发 launch）

---

## Task 5：更新 task.md / plan.md / review.md / handoff.md

- [ ] **Step 5-1：核对 / 补全 task.md（不要覆盖）**

`task.md` 已经存在（planner 已填）。**不要用 `>` 覆盖**，先查看现状：

```bash
cat .ai/tasks/20260601-backend-chain-prepare-to-interview/task.md
```

如果缺少"验收标准"或字段已过期，用 Edit/Write 工具替换具体段落，参考目标内容：

```markdown
# Task: Backend Chain Prepare-to-Interview

## 描述
新增 `POST /api/v1/prepare/launch` 端点，将 prepare 多 Agent 流水线与面试开场轮（__START__）串联成单条 SSE 流。前端接收 `phase_change` 事件后自动进入面试，无需用户点击任何按钮。

## 背景
用户反馈从 prepare 完成到面试开始需要手动点击按钮，体验割裂。前一个 PR 做了前端 auto-start 的临时方案；本 task 是后端驱动的最终方案，由 Agent Pipeline 统一编排整个流程。

## 验收标准
- [ ] `/prepare/launch` 端点正常工作，SSE 流依次输出 prepare 事件 → launch 节点 → phase_change → turn_* 事件
- [ ] need_direction=True 时，流在 prepare 阶段结束后停止，不接续 launch 与 turn 事件
- [ ] prepared_questions 从 prepare done 事件提取并正确传递给 stream_interview_turn
- [ ] 前端接收 phase_change 后 assistantIndex 正确指向新 assistant bubble（无 stale closure）
- [ ] resume 路径仍能进入面试（auto-start effect 带 guard 兜底）
- [ ] 单元测试 3 个全部通过
- [ ] 浏览器端到端冒烟：launch 路径直接流式输出第一道题；resume 路径在 600ms 后流式输出
```

- [ ] **Step 5-2：写 review.md（新建文件，可以用 `>`）**

```bash
cat > .ai/tasks/20260601-backend-chain-prepare-to-interview/review.md << 'EOF'
# Review

## 审查要点

### 协议设计
- `turn_*` 前缀命名规避了与 prepare 阶段 `node_start`/`node_done` 同名冲突 ✓
- `phase_change` 携带 `turn_id` 使前端可信地接力 turnId（无需 randomUUID 兜底） ✓
- `phase_change` 放在 launch 节点 start/done 之后，避免前端 prep handler 处理"已切走"状态时的脏 update ✓
- service 端 `done` 事件被 generator 吞掉，仅由其自行合成最终 `turn_done`，避免双 done ✓
- `turn_report` 已纳入转发集合（开场轮目前不到 closing，但留出协议完整性） ✓

### 后端
- `stream_prepare_and_launch` 是纯 generator，无副作用，易测试 ✓
- DB session 由 FastAPI DI 注入，不手动管理事务 ✓
- 旧 `/prepare/start` 未改动，向后兼容 ✓
- 测试 mock 正确处理 `stream_interview_turn` 的 positional `message` 参数 ✓

### 前端
- `phase_change` handler 在 updater 外捕获 assistantIndex、updater 后写 ref，规避 StrictMode 双调用风险 ✓
- `runPrepare` 新增 `autoLaunch` 参数，默认 false，仅初始化时传 true ✓
- auto-start `useEffect` 保留 + guard，让 launch 路径和 resume 路径同时存活 ✓
- `handlePrepareEvent.error` 分支按 `currentTurnIdRef` 区分 phase，避免半截僵尸 UI ✓

## 已知 scope 外
- `/prepare/resume-and-launch` 一体化端点：当前 resume 路径仍由前端 effect 兜底，
  视觉上有 600ms 的 "进入面试" 节点延迟，与 launch 路径节奏略不同。若未来需要统一节奏，
  补一个对称端点即可。
EOF
```

- [ ] **Step 5-3：写 handoff.md 并更新 status.json**

```bash
cat >> .ai/tasks/20260601-backend-chain-prepare-to-interview/handoff.md << 'EOF'

## 2026-06-01 — planner → implementation

### Completed
- 完成架构调研：确认 prepare + interview turn 两个 SSE 流可串联
- 识别事件命名冲突（两者都用 node_start/done），选择 `turn_` 前缀方案
- 写完完整实现计划，保存至 docs/superpowers/plans/

### Next Step
backend 面具实现 Task 1；frontend 面具实现 Task 2-3；人工冒烟 Task 4。

### Risks
- need_direction 场景（waiting_direction 后 resume）暂不自动进入面试，已记录在 review.md
EOF
```

```bash
# 更新 status.json state → planning（plan.md 写完，等用户拍板）
```

---

## 自检

**Spec coverage:**
- ✅ 后端单条 SSE 流（Task 1）
- ✅ launch 路径无按钮自动进入（Task 3-4b / 3-5 / 3-6）
- ✅ resume 路径仍能进入面试（Task 3-3 保留 effect + guard）
- ✅ need_direction 早退（Task 1 测试覆盖）
- ✅ prepared_questions 传递（Task 1 测试覆盖）
- ✅ stale closure 问题（Task 3-4b 在 updater 外捕获 assistantIndex、updater 后写 ref）
- ✅ phase 切换后的 error 兜底（Task 3-4a）
- ✅ service 端 done 事件被吞、turn_report 已转发（Task 1-3 _TURN_FORWARD_EVENTS）
- ✅ 端到端冒烟（Task 4 含 launch / resume 两条路径）

**Placeholder scan:** 无 TBD / TODO / "similar to" 语句。

**Type consistency:**
- `startPrepareAndLaunchStreamFetch` 在 Task 2 定义，Task 3 使用 ✓
- `turn_id` 字段在 `PrepareSSEEvent.data` 中声明（Task 2），`handlePrepareEvent` 中读取（Task 3）✓
- `currentTurnIdRef` 在 Task 3-2 声明，Task 3-3 guard / 3-4 使用 ✓
- `autoLaunch` 参数在 Task 3-5 定义，Task 3-6 调用 ✓
- `turn_report` 在 `PrepareSSEEvent.event` 联合类型中声明（Task 2-1），handler 在 Task 3-4b 使用 ✓

**Test mock 签名一致性：**
- `stream_interview_turn(message: str, *, user_id, db, ...)` —— `message` 为 positional ✓
- Task 1-1 的 `mock_turn_stream(message, **kwargs)` 与之匹配 ✓

**Review 修订记录（vs 初版）：**
- 调整 phase_change 时序为 launch 节点之后（修复前端处理状态错乱）
- `_TURN_FORWARD_EVENTS` 转发 report、吞 done（避免 service done 与合成 turn_done 重复）
- 保留 auto-start `useEffect` + `currentTurnIdRef` guard（修复 resume 路径卡死）
- `handlePrepareEvent.error` 分支 phase-aware（修复错误兜底脏状态）
- assistantIndex 在 updater 外捕获后写 ref（规避 StrictMode 双调用）
- `task.md` 改为非破坏性编辑（避免覆盖既有内容）
- `import uuid` 移到模块顶部、去掉 `_uuid` 别名与无意义的 launch elapsed_ms
