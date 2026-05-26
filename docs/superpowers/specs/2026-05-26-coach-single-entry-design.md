# Coach 单门口 + 入口收紧 设计文档

- 日期：2026-05-26
- 分支：feat/phase3-jd-agent
- 关联路线图：第五步「教练 Agent + 共享记忆层」前置铺垫

---

## 1. 背景与动机

当前前端有两个并列入口：
- `/coach`：Coach 仪表盘，承担"开场叙事 + 历史记忆露出 + JD 输入"的品牌入口
- `/interview`：面试房间，可直接进入并展示一个询问岗位的 fallback 卡片

两个入口形成 **品牌与体验割裂**：
- 直入 `/interview` 绕过 Coach 的开场叙事和近期记忆展示
- 直入 `/interview` 时只有一个孤立的"请输入岗位"卡片，与 Coach 的"你的 AI 教练在和你说话"叙事完全不同
- 未来路线图第五步将接入「教练 Agent + 共享记忆层（长短期记忆 / 爱好记忆）」，需要一个稳定的接入位

## 2. 产品决策

**Coach 是品牌单门口，Interview 是其派生的考场。**

收紧强度：**强收紧** —— 导航栏拿掉「面试房间」Tab；用户无意中访问 `/interview` 且无活动会话时，重定向回 `/coach` 并附软提示。

## 3. 范围

**包含**：

1. 入口收紧：导航、路由守卫、Coach 软提示
2. Interview 错误路径 fallback 治理（删除冗余 fallback 卡片）
3. 为第五步预留：Coach 开场结构 + Prepare State 的记忆接入槽位

**不包含**：

- 长期记忆 / 爱好记忆 agent 本体实现（属第五步）
- `/coach` 主体叙事和新老用户分支改造
- LLM-as-Judge 评估模块（属第六步）

## 4. 架构

### 4.1 路由守卫位置

**Page-level useEffect 守卫**（不引入 Next.js middleware）。

理由：
- `sessionStorage.interview_context` 仅客户端可读
- `/interview/active` 需要 Clerk token，在 edge middleware 注入 token 复杂度高
- 现有 `InterviewChat` 已有顺序检查 `interview_context` → `active session`，最小化改动是把 fallback 分支换成 `router.replace`

### 4.2 改动地图

| 层 | 文件 | 改动 |
|---|---|---|
| 前端导航 | `frontend/app/components/nav.tsx` | `navItems` 移除 `{label: "面试房间", href: "/interview"}` |
| 前端守卫 | `frontend/app/interview/_components/interview-chat.tsx` | 现有 useEffect 的 fallback 分支替换为 `router.replace("/coach?from=interview")`；删除 `buildOpeningMessage(null)` 长 fallback 文本 |
| 前端 Coach | `frontend/app/coach/coach-dashboard.tsx` | `useSearchParams` 检测 `from=interview`，顶部插入软提示行 + 4s 自动消失，挂载时同步 `router.replace("/coach")` 清 query |
| 前端 OpeningCopy | `frontend/app/coach/coach-dashboard.tsx::CoachOpeningCopy` | 新增 `long_memory_hints` / `hobby_hints` 渲染槽，空数组时不渲染 |
| 前端公共工具 | `frontend/lib/interview-chat.ts` | 抽出 `enterInterviewRoom(ctx)` 工具函数，统一封装"写 sessionStorage + reset + push /interview" |
| 后端 Opening | `backend/app/services/coach_opening.py` | 返回结构增加 `long_memory_hints: list[str] = []`、`hobby_hints: list[str] = []` 默认空槽 |
| 后端 PrepareState | `backend/app/agents/prepare/state.py` | `PrepareState` 增加 `long_memory: list[dict]` 槽（`total=False` 不影响现有调用方） |

## 5. 数据流

### 5.1 进入 /interview 的所有路径

| # | 入口路径 | 用户场景 | 守卫判定 |
|---|---|---|---|
| 1 | Coach「开始面试」按钮 | 用户从 Coach 派发 | `sessionStorage.interview_context` 有 → 允许，跑 prepare |
| 2 | 浏览器刷新 /interview | 面试进行中刷新 | `interview_context` 已被消费清掉，`/interview/active` 返回 `in_progress` → 允许，恢复消息 |
| 3 | Tab 切换回来 / 后退按钮 | 已结束的面试 | `interview_context` 无，`/active` 返回 `null` → 重定向 `/coach?from=interview` |
| 4 | 直接敲 URL / 书签 | 用户书签里点进 | 同 3，重定向 |
| 5 | 报告页"再练一场" | 未来扩展 | 走 `enterInterviewRoom(ctx)` 工具 → 等价路径 1 |

**关键不变性**：路径 1 和 2 是「允许停留」，路径 3-5 是「重定向回 Coach」。

### 5.2 守卫状态机（伪代码）

```ts
useEffect 内：
  if !isLoaded || (!signedIn && !devBypass) → 返回
  if hasResetRef.current → 返回
  hasResetRef.current = true

  const token = await getInterviewToken(...)

  if (initialContextRef.current?.target_role || jd_text || jd_url) {
    // 路径 1：Coach 派发
    跑 reset + runPrepare
    return
  }

  // 路径 2/3/4：尝试恢复活动会话
  try {
    const activeSession = await fetchActiveInterviewSession({ token })
    if (activeSession.session_id) {
      // 路径 2：有进行中会话，恢复
      setMessages(restored), setProgress, setReport
      return
    }
    // 路径 3/4：无活动会话，重定向
    router.replace("/coach?from=interview")
  } catch (err) {
    // active 接口超时/500：不重定向，显示兜底错误 UI
    setLoadError(true)
  }
```

### 5.3 Coach 端 query 检测

```tsx
const searchParams = useSearchParams();
const fromInterview = searchParams.get("from") === "interview";

useEffect(() => {
  if (!fromInterview) return;
  // 4s 自动消失
  const t = setTimeout(() => setShowHint(false), 4000);
  // 同时清掊 query 防止刷新时重复显示
  router.replace("/coach");
  return () => clearTimeout(t);
}, [fromInterview]);
```

### 5.4 enterInterviewRoom 工具函数签名

```ts
// frontend/lib/interview-chat.ts
export async function enterInterviewRoom(args: {
  getToken: () => Promise<string | null>;
  router: AppRouterInstance;
  context: {
    target_role: string;
    user_background?: string;
    jd_text?: string;
    jd_url?: string;
  };
}): Promise<void>;
```

实现：写 `sessionStorage.interview_context` → 调 `resetInterviewSession`（失败仅 warn，不阻塞）→ `router.push("/interview")`。

## 6. 错误处理

| 场景 | 处理 |
|---|---|
| `/interview/active` 超时或 500 | 不重定向，展示兜底「连接异常，请重试或返回 Coach」+ 返回 Coach 按钮 |
| Clerk 未加载完 | 守卫不触发，等 `isLoaded` 后判定（现有逻辑） |
| 用户登出 | Clerk 中间件接管跳 `/login`，不进入守卫 |
| prepare 失败 | 现有 `fallbackFromPrepareFailure` 已处理，不改 |
| Coach 软提示在 4s 内用户跳走 | `useEffect` cleanup 清掉 setTimeout |
| `enterInterviewRoom` reset 失败 | 仅 warn，仍 push 到 `/interview`，守卫层兜底 |

## 7. 测试要点（TDD）

**前端单测**：

1. `nav.test.tsx`：断言 `navItems` 不再包含「面试房间」
2. `interview-chat.test.tsx`：
   - 无 sessionStorage context + active 返回 null → `router.replace("/coach?from=interview")` 被调用
   - 有 sessionStorage context → 不重定向，正常 runPrepare
   - active 返回 in_progress 会话 → 不重定向，恢复消息
   - active 接口 reject → 不重定向，渲染兜底错误 UI
3. `coach-dashboard.test.tsx`：
   - `useSearchParams` mock 返回 `from=interview` → 软提示出现
   - 4 秒后（fake timers） → 软提示消失
   - 渲染时 `router.replace("/coach")` 清 query
4. `lib/interview-chat.test.ts`（新增） `enterInterviewRoom`：
   - 调用后写 sessionStorage、调 reset、push("/interview")
   - reset 失败时仍 push

**后端单测**：

5. `tests/unit/test_coach_opening_service.py`：返回结构包含 `long_memory_hints: []`、`hobby_hints: []`

**不在测试范围**：

- 「重定向后走 Coach 流程再回 /interview」的 e2e（属 /qa）
- 后端记忆 hints 实际填充逻辑（属第五步）

## 8. 风险与回滚

**主要风险**：

1. 路径 2（进行中刷新）守卫误踢 → 缓解：active 超时不重定向 + 专门回归测试
2. Clerk SSR 边缘场景 `useSearchParams` 异常 → 缓解：保持 client 组件
3. 后端新字段前端未兼容 → 缓解：前端类型字段加 `?`，`?? []` 解构

**回滚策略**：

- 所有改动都是单文件级可逆，git revert 单 commit 即可
- 后端字段只新增不修改，旧前端忽略
- 前端导航变更可单独 revert

## 9. 与路线图的衔接

- **第三步**（JD + 出题 Agent，Orchestrator）：已完成，不动
- **第四步**（评估 Agent + 并行评分）：已完成，不动
- **本次**：入口收紧 + 记忆接入位预留（不动 agent 本体）
- **第五步**（教练 Agent + 共享记忆层）：直接消费本次预留的 `long_memory_hints` / `hobby_hints` / `long_memory` 槽位
- **第六步**（LLM-as-Judge）：与入口无关，独立推进
