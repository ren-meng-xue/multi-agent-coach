# 备考准备阶段（Prepare Flow）

依赖：[overview.md](overview.md)

接口：`POST /prepare/start` → Prepare Graph → 题库生成完成

---

## 1. 功能定位

用户在 `/coach` 页面选择目标岗位或上传 JD，系统自动生成结构化面试题库，作为后续面试阶段的出题依据。

---

## 2. 整体流程

```
用户在 /coach 页面
  ├─ 输入目标岗位（如"AI Agent 工程师"）
  └─ 或上传 JD 文档
        │
        ▼ POST /prepare/start
        │
        ▼
┌─────────────────────────────────────┐
│          Prepare Graph               │
│                                     │
│  parse_jd                           │
│    └─ 提取岗位要求、技能栈、职级     │
│         │                           │
│         ▼                           │
│  generate_questions                 │
│    └─ 按维度批量生成面试题           │
│         │                           │
│         ▼                           │
│  store_qa_bank                      │
│    └─ 写入 user_qa_bank 表          │
└─────────────────────────────────────┘
        │
        ▼
  面试开始时：
  开关 ON  → Chief 从 user_qa_bank 选题出题
  开关 OFF → Chief 走默认实时出题逻辑
```

---

## 3. QA Bank（用户自定义题库）

除了系统自动生成，用户也可手动上传题库模板，覆盖或追加题目。

### 3.1 上传流程

```
用户下载 Markdown 模板
  └─ 包含三个区块：技术题 / HR题 / 项目讲解
        │
        ▼
用户填写题目 + 参考答案 + 标签
        │
        ▼
上传至系统
        │
        ▼
后端解析 Markdown → 写入 user_qa_bank
```

### 3.2 Markdown 模板结构

```markdown
## 技术题

### 题目 1

**问题：** 解释 RAG 的原理
**参考答案：** RAG 是检索增强生成...
**标签：** AI, RAG

---

## HR题

### 题目 1

**问题：** 介绍一下你自己
**参考答案：** 我有 X 年经验...
**标签：** 自我介绍

---

## 项目讲解

### 题目 1

**问题：** 介绍你做过的最复杂的系统
**参考答案：** 我主导设计了...
**标签：** 系统设计
```

---

## 4. 数据模型

### `user_qa_bank` 表

```sql
CREATE TABLE user_qa_bank (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category     VARCHAR(20) NOT NULL,   -- 'technical' | 'hr' | 'project'
    question     TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    tags         JSON,
    created_at   TIMESTAMPTZ DEFAULT now(),
    updated_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## 5. 面试开关逻辑

```
interview_sessions.use_qa_bank = true/false
        │
        ▼ interview/turn 请求到达
        │
  use_qa_bank = true?
    ├─ 是 → load_context 阶段注入 qa_bank 题目
    │         Chief 优先从 qa_bank 选题
    │         答完题后与 model_answer 对比给反馈
    └─ 否 → Chief 走实时出题逻辑（Designer Agent）
```

---

## 6. 关键文件索引

| 文件                                 | 说明                        |
| ------------------------------------ | --------------------------- |
| `backend/app/agents/prepare/`        | Prepare Graph 定义          |
| `backend/app/api/routes/prepare.py`  | `/prepare/start` 接口       |
| `backend/app/models/user_qa_bank.py` | QA Bank ORM 模型            |
| `frontend/app/coach/`                | /coach 页面，选岗 + 上传 JD |
