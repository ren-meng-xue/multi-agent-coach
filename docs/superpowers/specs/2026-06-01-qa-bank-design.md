# 面试题库（QA Bank）功能设计规格

**日期**：2026-06-01  
**状态**：待实现

---

## 背景与目标

用户备战 AI Agent 工程师岗位，希望提前准备好自己的面试题和答案，让 AI Coach 直接用这批题目来训练自己。现有系统仅有 STAR 故事库（项目经验），缺少结构化的 Q&A 训练材料。

---

## 功能范围

**在范围内：**
- 下载 Markdown 模板（3 个区块：技术题、HR题、项目讲解）
- 上传填好的模板，解析后入库
- 设置页展示题库条目数量摘要
- 面试开始时的开关：使用题库 vs 走现有逻辑
- 开关打开时，AI Coach 从题库选题，答后对比参考答案给反馈

**不在范围内：**
- 页面内手动逐条录入
- 对题库条目做增删改（上传即覆盖或追加）
- 题库自动生成（AI 推荐题目）

---

## 数据模型

### 新表：`user_qa_bank`

```sql
CREATE TABLE user_qa_bank (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     VARCHAR(64) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category    VARCHAR(20) NOT NULL,  -- 'technical' | 'hr' | 'project'
    question    TEXT NOT NULL,
    model_answer TEXT NOT NULL,
    tags        JSON,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_user_qa_bank_user_id ON user_qa_bank(user_id);
CREATE CHECK CONSTRAINT ck_user_qa_bank_category
    CHECK (category IN ('technical', 'hr', 'project'));
```

---

## Markdown 模板结构

文件名：`面试题库模板.md`，三个区块用 `##` 标题分隔，题目用 `###` 分隔。

```markdown
## 技术题

### 题目 1
**问题：** 解释 RAG 的原理
**参考答案：** RAG 是检索增强生成，核心思路是...
**标签：** AI, RAG, 检索增强

---

### 题目 2
**问题：** ...
**参考答案：** ...
**标签：** ...

---

## HR题

### 题目 1
**问题：** 介绍一下你自己
**参考答案：** 我有 X 年经验，专注于...
**标签：** 自我介绍

---

## 项目讲解

### 题目 1
**问题：** 介绍你的 Multi-Agent Coach 项目
**参考答案：** 这个项目的核心是多 Agent 协作...
**标签：** AI Agent, 项目经验

---
```

**解析规则：**
- `## 技术题` / `## HR题` / `## 项目讲解` 三个 section 标题决定 `category`，区块名必须完全匹配
- `### 题目 N` 表示一条新题目（N 为任意数字或文字）
- `**问题：**`、`**参考答案：**` 为必填字段，`**标签：**` 可选
- 字段冒号后有一个空格，格式必须严格匹配，否则该条跳过
- 三个区块均为选填，缺少某个区块直接忽略

**上传规则：**
- 可以只上传其中一个或几个区块，文件里有哪个区块就更新哪个，没有的区块保持不变
- 例：只有 `## 技术题` 的文件 → 只覆盖技术题，HR题和项目讲解原样保留
- 每条记录必须有 `question` 和 `model_answer`，缺失则跳过并在响应中报告跳过数量

---

## 后端改动

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/user/qa-bank/template` | 下载 Markdown 模板（返回 .md 文件）|
| `POST` | `/api/v1/user/qa-bank/upload` | 上传 Markdown 文件，解析入库 |
| `GET` | `/api/v1/user/qa-bank/summary` | 返回各类数量 `{technical: 12, hr: 5, project: 3}` |

### 上传响应格式

```json
{
  "code": 200,
  "msg": "上传成功",
  "data": {
    "imported": {"technical": 12, "hr": 5, "project": 3},
    "skipped": 2
  }
}
```

### Coach 集成

面试 Session 的 `InterviewSession` 表新增字段：

```sql
ALTER TABLE interview_sessions
ADD COLUMN use_qa_bank BOOLEAN NOT NULL DEFAULT false;
```

当 `use_qa_bank = true` 时：
1. Session 开始时从 `user_qa_bank` 加载用户的题目列表
2. 注入到 Interview Agent 的系统提示词，格式：
   ```
   【用户已准备的题目库】
   以下题目请优先从中选取，覆盖整场面试：
   [技术题]
   1. Q: ... / A（参考）: ...
   [HR题]
   ...
   ```
3. 每轮用户回答后，Coach 的反馈中增加"与参考答案对比"维度

---

## 前端改动

### 设置页（`settings-view.tsx`）

在 STAR 故事库区块下方新增"面试题库"卡片：

```
┌─────────────────────────────────────┐
│ 面试题库                            │
│ 提前准备题目，AI Coach 直接考你      │
│                                     │
│ 技术题 12条 | HR题 5条 | 项目讲解 3条│
│                                     │
│ [下载模板]  [上传题库]               │
└─────────────────────────────────────┘
```

- 下载模板：调用 `/api/v1/user/qa-bank/template`，触发浏览器下载
- 上传题库：`<input type="file" accept=".md">` → multipart POST
- 上传成功后刷新摘要数量

### 面试开始（Coach 页）

如果 `summary.total > 0`，在面试开始前展示开关：

```
┌─────────────────────────────────────┐
│ 本次使用我的题库  [ ○──── ]  OFF    │
│ 开启后 AI 将从你的 20 道准备题中选题 │
└─────────────────────────────────────┘
```

开关状态随 `use_qa_bank` 参数传入创建 Session 的请求体。

---

## 数据流

```
用户下载模板 → 填写 Markdown → 上传
        ↓
后端解析 3 个区块 → 按 category 覆盖写入 user_qa_bank
        ↓
设置页显示摘要数量
        ↓
开始面试 → 选择是否使用题库 → 创建 Session（use_qa_bank=true/false）
        ↓
Interview Agent 加载题库 → 从中选题 → 用户回答 → 对比参考答案反馈
```

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 上传非 .md 文件 | 返回 400，提示"请上传 .md 格式" |
| 题目缺少必填字段（问题/参考答案）| 跳过该条，在响应 `skipped` 计数中体现 |
| 题库为空但开了开关 | 自动降级为正常模式，Coach 提示用户 |
| Markdown 解析失败（格式严重错误）| 返回 400，附带错误描述 |
