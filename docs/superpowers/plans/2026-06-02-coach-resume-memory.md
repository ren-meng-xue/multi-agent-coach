# Coach Resume Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coach Agent 在生成面试复盘（review）和学习计划（plan）时，补充读取用户简历摘要，让点评和建议更贴合候选人的个人背景、工作经历和技能栈。

**Architecture:** 简历上传时用 LLM 生成结构化摘要并持久化到 `User.resume_summary`（一次生成，多次复用）；Coach 的 `load_memory_node` 读取该摘要注入 state；`_generate_review_text` 和 `_generate_structured_plan` 在 HumanMessage 中追加摘要上下文。

**Tech Stack:** Python / FastAPI / SQLAlchemy async / LangGraph / Alembic

---

## 改动文件

- `backend/app/models/core.py` — User 模型新增字段
- `backend/alembic/versions/<new>.py` — 数据库迁移
- `backend/app/services/resume_extractor.py` — 新增摘要生成函数
- `backend/app/api/v1/user.py` — 上传时调用摘要生成
- `backend/app/agents/coach/state.py` — 新增字段
- `backend/app/agents/coach/nodes.py` — 读摘要、注入上下文

---

## 实现步骤

### Step 1 — models/core.py：User 新增 `resume_summary` 字段

- [ ] 在 `User` 类的 `resume_filename` 字段后追加：
  ```python
  resume_summary: Mapped[str | None] = mapped_column(Text)
  ```

---

### Step 2 — Alembic 迁移

- [ ] 新建迁移文件，在 `users` 表新增 `resume_summary TEXT` 列：
  ```bash
  cd backend && alembic revision --autogenerate -m "add_resume_summary_to_users"
  ```
- [ ] 确认生成的迁移文件正确后执行：
  ```bash
  alembic upgrade head
  ```

---

### Step 3 — resume_extractor.py：新增 `summarize_resume` 函数

- [ ] 在文件末尾新增函数，调用 LLM 生成结构化中文摘要（200 字以内），涵盖：候选人年限、核心技能栈、代表性项目、求职意向：

  ```python
  async def summarize_resume(resume_text: str) -> str:
      """用 LLM 将简历浓缩为结构化摘要，供 Coach Agent 使用。"""
      settings = get_settings()
      model = ChatOpenAI(
          model=settings.openai_model_chat_fast,
          api_key=settings.openai_api_key,
          temperature=0.1,
          timeout=settings.llm_timeout_seconds,
      )
      prompt = f"""请将以下简历浓缩为一段 200 字以内的中文结构化摘要，供面试教练参考。
  摘要需包含：工作年限、核心技能栈、代表性项目经历（1-2 条）、求职意向岗位。
  只输出摘要正文，不要加标题或前缀。

  简历内容：
  {resume_text[:6000]}"""
      result = await model.ainvoke([HumanMessage(content=prompt)])
      return result.content.strip()
  ```

---

### Step 4 — user.py：上传时调用摘要生成

- [ ] 在 `upload_resume` 的 import 中补充 `summarize_resume`：
  ```python
  from app.services.resume_extractor import (
      extract_target_role_from_resume,
      extract_target_role_locally,
      summarize_resume,
  )
  ```
- [ ] 在 `extract_target_role_from_resume` 调用之后，追加摘要生成（失败不阻塞上传）：
  ```python
  try:
      summary = await summarize_resume(text_content)
      if summary:
          user.resume_summary = summary
  except Exception:
      pass
  ```

---

### Step 5 — coach/state.py：新增 `resume_summary` 字段

- [ ] 在 `CoachState` TypedDict 中新增字段：
  ```python
  resume_summary: str | None
  ```

---

### Step 6 — coach/nodes.py：`load_memory_node` 读取摘要

- [ ] 在文件顶部 import 中补充 `User` 模型：
  ```python
  from app.models.core import CandidateMemory, CoachPlan, InterviewSession, User
  ```
- [ ] 在 `load_memory_node` 的 `return` 之前追加查询：
  ```python
  stmt_user = select(User.resume_summary).where(User.id == user_id)
  res_user = await db.execute(stmt_user)
  resume_summary = res_user.scalar_one_or_none()
  ```
- [ ] 在 `return` 字典中加入：
  ```python
  "resume_summary": resume_summary,
  ```

---

### Step 7 — coach/nodes.py：`_generate_review_text` 注入摘要

- [ ] 在构建 `messages` 之前组装上下文变量：
  ```python
  resume_ctx = (
      f"\n\n【候选人简历摘要】\n{state['resume_summary']}"
      if state.get("resume_summary") else ""
  )
  ```
- [ ] 将 HumanMessage 内容改为：
  ```python
  HumanMessage(content=f"{memory_ctx}\n\n{session_ctx}{resume_ctx}")
  ```

---

### Step 8 — coach/nodes.py：`_generate_structured_plan` 注入摘要

- [ ] 同 Step 7，在构建 `messages` 之前组装上下文变量（复用同名变量）：
  ```python
  resume_ctx = (
      f"\n\n【候选人简历摘要】\n{state['resume_summary']}"
      if state.get("resume_summary") else ""
  )
  ```
- [ ] 将 HumanMessage 内容改为：
  ```python
  HumanMessage(content=f"{role_ctx}\n\n{review_ctx}\n\n{memory_ctx}{resume_ctx}")
  ```

---

## 设计决策

- **上传时一次生成，多次复用**：摘要在上传时由 LLM 生成并持久化，Coach 每次调用只做一次 DB 读取，不额外消耗 LLM token。
- **摘要而非原文**：原始简历可能几千字，注入原文会撑大 context 且噪音多；摘要 200 字内，结构化，LLM 利用效率更高。
- **生成失败不阻塞上传**：摘要生成用 try/except 包裹，失败时 `resume_summary` 保持 `None`，Coach 无摘要时行为与现在完全一致。
- **使用 `openai_model_chat_fast`**：摘要是轻量任务，用 fast 模型节省成本，与 `extract_target_role_from_resume` 保持一致。

## 不在范围内

- 已有简历用户的摘要回填（存量数据，可后续单独做一个迁移脚本）
- prepare / interviewer agent 的简历逻辑（已有，不改）
- 前端改动（无需展示摘要字段）
