# M4 里程碑计划：生态 & 商业化 SaaS

> 覆盖 Phase：**P8 + P9**
> 简历卖点：**"MCP + Voice + SaaS + 企业版"**
> 状态：v0.1（初版）
> 📍 全景位置：见 [`../product-vision.md` §6.5 M↔Phase↔功能模块总览图](../product-vision.md)

---

## 1. 里程碑目标

把 M3 的"成熟单用户产品"升级为「**多平台接入 + 多模态交互 + 多用户 SaaS + 数据飞轮 + 企业版**」的完整商业化产品。完成后产品具备对外服务 / 收费 / 跨平台调用的能力。

## 2. 范围

| 包含 |
|---|
| ✅ MCP Server 化（暴露工具给 Claude Code / Cursor） |
| ✅ Voice 模式（Realtime API + Whisper/TTS fallback） |
| ✅ 中英双语 |
| ✅ 移动端响应式 |
| ✅ 多用户系统（注册 / 登录 / 订阅） |
| ✅ Stripe 计费 |
| ✅ Sentry + Prometheus 监控告警 |
| ✅ PostHog 行为分析 |
| ✅ 用户贡献题库 |
| ✅ 公开 Benchmark 数据集 |
| ✅ 企业版（HR 反向用做候选人筛选） |

---

## 3. P8 — 生态 & 多模态

### 3.1 MCP Server 化

实现 Anthropic MCP 协议，暴露的工具：

| Tool | 输入 | 输出 | 场景 |
|---|---|---|---|
| `start_interview` | `topic`, `duration` | session_id + 第一题 | Claude Code 里"我想练 LangGraph 系统设计 30 分钟" |
| `answer_question` | session_id, answer | 评分 + 下一题 | 在 Claude Code 里完整做题 |
| `get_user_growth` | period | 进步曲线 JSON | "看我最近 4 周的进步" |
| `add_star_story` | project_name, situation, ... | 故事 ID | "把这个项目加到我的 STAR 库" |
| `query_weakness` | category | 弱点清单 | "我的盲区是什么" |
| `mock_phone_screen` | jd_url | 完整电话面 session | "用这个 JD 给我模拟一次电话面" |

技术实现：
- Python MCP SDK
- 单独 `mcp_server/` 目录
- 走 stdio / SSE 双协议

### 3.2 Voice 模式

主链路：OpenAI Realtime API
- 浏览器 WebRTC 直连 OpenAI
- Agent prompt + 工具调用桥接到后端
- 中间用 Anthropic 不可用 fallback Whisper + TTS（自建链路）

技术挑战：
- Realtime API 不支持 LangGraph state 自动注入 → 自定义中间层
- VAD（语音活动检测）参数调优
- 用户中途打断 Agent 说话的处理

### 3.3 中英双语

- i18n 用 `next-intl`
- Agent prompt 双语模板
- RAG 题库标签双语
- Voice 模式自动语种识别

### 3.4 移动端响应式

- Next.js + Tailwind responsive
- 关键页面：登录 / 面试 / 复盘 / 仪表盘
- PWA 支持（manifest + service worker）
- 不做原生 App（用 PWA 即可）

### 3.5 P8 验收标准

- [ ] MCP Server 在 Claude Code 中可用 `npx @multi-agent-coach/mcp` 一键接入
- [ ] Voice 模式能完整跑通一次面试（用户说话 → Agent 答 → 评分）
- [ ] 双语切换无 bug
- [ ] iPhone Safari 能流畅使用

---

## 4. P9 — 商业化 & 数据飞轮

### 4.1 多用户系统

- 注册 / 登录 / 邮箱验证（用 Clerk / Auth.js / 自建二选一）
- 推荐 Clerk（Vercel Marketplace 一键集成）
- 用户 settings 页：偏好语言 / 目标岗位 / 通知

### 4.2 Stripe 计费

定价方案：
| 套餐 | 价格 | 包含 |
|---|---|---|
| Free | $0 | 每月 3 场面试，基础复盘 |
| Pro | $19/月 | 无限面试 + 高级 Eval + Meta-reflection + Voice |
| Enterprise | 定制 | 多账户 + 自定义题库 + HR 反向筛选 |

技术：
- Stripe Checkout + Webhook
- usage metering：每场面试调 `track_usage`

### 4.3 监控告警

| 工具 | 用途 |
|---|---|
| Sentry | 异常告警（前后端） |
| Prometheus + Grafana | 自定义 metrics（Agent 调用延迟 / 错误率） |
| Langfuse (self-host) | LLM 调用链路追踪 + 成本 |
| Uptime Robot | 服务可用性监控 |

### 4.4 用户行为分析

- PostHog（self-host 或 cloud）
- 关键事件：`interview_started` / `interview_completed` / `weakness_improved` / `paid`
- 漏斗分析：注册 → 首次面试 → 完整复盘 → 第二次面试

### 4.5 用户贡献题库

- 用户面试后可"建议入题库"
- 编辑流程：自动质量评分 + 人工 review（前期）→ 入题库
- 贡献者激励：贡献 N 道题免费 1 个月 Pro

### 4.6 公开 Benchmark 数据集

- 去敏 M3 的 50 题黄金集
- 增加到 200+ 题，覆盖更多方向（RAG / Agent / Eval / 系统设计 / NLP）
- GitHub 公开 + paper / blog
- 简历可写："维护 200+ 题的 AI Agent 工程师面试公开 Benchmark"

### 4.7 企业版（HR 反向用）

把同一套技术反过来：
- HR 上传候选人 JD → 自动生成面试题
- 候选人面试时，系统记录 → Eval 给 HR 看
- HR 仪表盘：候选人列表 + 评分对比 + 录用建议

商业模式：按企业账户 / 按候选人面试场次计费。

### 4.8 P9 验收标准

- [ ] Free / Pro 套餐切换 + Stripe 计费跑通
- [ ] 监控告警生效（人为制造异常能收到 Sentry 通知）
- [ ] PostHog 漏斗能看
- [ ] 用户贡献题库流程跑通 1 个 case
- [ ] 公开 Benchmark 数据集发布 GitHub
- [ ] 企业版 demo 流程可演示

---

## 5. 工期粗估

| Phase | 名义工时 |
|---|---|
| P8 | 60-80h |
| P9 | 80-120h |
| **小计 M4** | **140-200h** |

## 6. 简历兑现点（M4 完成后能写什么）

简历项目栏（200 字）：
> Multi Agent Coach - 完整的 AI SaaS 产品。从 0-1 独立设计 / 开发 / 运营。技术亮点：① 多 Agent + 分级长期记忆 + Meta-cognition；② MCP 协议接入 Claude Code/Cursor；③ Realtime API 语音模式；④ 多用户 SaaS（Clerk + Stripe）+ 移动端 PWA；⑤ Langfuse 自托管全链路追踪 + Sentry / Prometheus / PostHog 完整可观测；⑥ 公开 200+ 题 AI Agent 工程师 Benchmark 数据集。截至 X 年 Y 月：N 注册用户 / M 完成面试 / K 付费转化率。

招聘官能 get 的强信号：
- ✅ 独立做完一个 SaaS 的完整能力（极少见）
- ✅ MCP + Voice 双前沿技术
- ✅ 完整运营 / 监控 / 计费经验
- ✅ 公开学术贡献（Benchmark）

## 7. 关键风险

| 风险 | 应对 |
|---|---|
| MCP 协议演进 / SDK 不稳定 | 用 context7 拉最新文档，锁定 SDK 版本 |
| Voice 成本高 | Free 不开放 Voice；Pro 用量限制 |
| 商业化获客 | 走 SEO + 独立开发者社群 + ProductHunt；不依赖广告 |
| 监管合规 | 隐私政策 + GDPR / CCPA 合规 |
| 企业版销售周期长 | M4 只做产品 demo，不强推销售 |

## 8. 简历可讲的"独立做完 SaaS"故事

招聘 AI Agent 工程师岗时，一个真实跑起来的 SaaS 比 10 个 GitHub demo 都值钱。M4 完成后简历项目栏可以独立写一段"运营数据"，这是 99% 候选人没有的差异化。

---

**📌 M4 不在 7 天 ship 范围内**，是产品长期愿景。建议 M2 完成后投简历拿 offer，offer 拿到后利用 onboarding 期把 M3 完成 + M4 部分跑起来。
