# AI 面试官 Agent 系统测试报告：维度二质量验证

- 日期：2026-06-05
- 范围：问题相关性、追问质量、语气与中立性、面试节奏、岗位核心能力覆盖率
- 关联清单：[`2026-06-05-ai-interviewer-test-checklist.md`](./2026-06-05-ai-interviewer-test-checklist.md)
- 报告状态：已执行自动化证据映射，待补 LLM judge / 人工 transcript 抽查
- 评分口径：高优先级 5 分，中优先级 3 分，低优先级 1 分；通过得满分，部分通过按 50% 计，失败/阻塞/未执行为 0 分
- Judge 口径：LLM-as-judge 单项 1-5 分，默认 >= 4 分通过；涉及比例的测试按 transcript 中主问题数统计

---

## 1. 量化结论

| 指标 | 当前值 | 目标值 | 结论 |
| ---- | ------ | ------ | ---- |
| 总测试项 | 19 | 19 | 已映射 11 项 |
| 高优先级项 | 10 | 10 | 0 通过 / 8 部分通过 / 2 待执行 |
| 中优先级项 | 8 | 8 | 4 通过 / 3 部分通过 / 1 待执行 |
| 低优先级项 | 1 | 1 | 1 待执行 |
| 总分 | 36.5 / 75 | >= 68 / 75 | 不通过 |
| 总通过率 | 50% | >= 90% | 不通过 |
| 高优先级通过率 | 0% | 100% | 不通过 |
| LLM judge 样本数 | 0 | >= 5 场或 >= 25 条问题/回复 | 待补 |
| 人工抽查样本数 | 0 | >= 2 场完整 transcript | 待补 |
| 阻塞问题数 | 0 | 0 | 通过 |

### 准入标准

| 等级 | 标准 | 发布建议 |
| ---- | ---- | -------- |
| 通过 | 总分 >= 68 且高优先级 100% 通过，且无阻塞问题 | 可进入下一阶段 |
| 有条件通过 | 总分 60-67，或仅中/低优先级存在失败项 | 修复失败项后复测 |
| 不通过 | 任一高优先级失败，或总分 < 60，或存在阻塞问题 | 不建议上线 |

---

## 2. Q1 问题相关性

| # | 测试项 | 优先级 | 权重 | 量化指标 | 通过阈值 | 实测值 | 状态 | 得分 | 证据/备注 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| Q1-1 | 问题与 JD 岗位职责强相关 | 高 | 5 | 5 道主问题相关性平均分 | LLM judge 平均分 >= 4/5 | JD/job_intel 能进入出题和评估 prompt；未跑 5 道题 LLM judge | 部分通过 | 2.5 | backend tests/unit/test_prepare_nodes.py、test_designer_consumes_job_intel.py、test_evaluator_consumes_job_intel.py |
| Q1-2 | 问题结合候选人简历背景定制化 | 高 | 5 | 指向性引用问题占比 | >= 60% 主问题包含候选人具体背景引用 | 简历摘要、候选人背景、岗位强项/Gap 已注入出题上下文；未统计 transcript 引用占比 | 部分通过 | 2.5 | backend tests/unit/test_prepare_nodes.py::test_question_gen_injects_user_background_into_prompt；test_designer_consumes_job_intel.py |
| Q1-3 | 不提问候选人简历已明确给出答案的内容 | 中 | 3 | 无效重复确认问题数 | 0 个 | 出题/追问/题库生成 prompt 已禁止重复确认简历、JD 或候选人已明确给出的事实；未做 transcript 判定 | 部分通过 | 1.5 | backend tests/unit/test_interviewer_quality_guards.py::test_question_prompts_avoid_reconfirming_known_resume_or_jd_facts |

### Q1 小结

| 指标 | 当前值 | 目标值 |
| ---- | ------ | ------ |
| 测试项 | 3 | 3 |
| 可得分 | 13 | 13 |
| 当前得分 | 6.5 | >= 13 |
| 高优先级通过率 | 0% | 100% |

---

## 3. Q2 追问质量

| # | 测试项 | 优先级 | 权重 | 量化指标 | 通过阈值 | 实测值 | 状态 | 得分 | 证据/备注 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| Q2-1 | 能识别浅层/模糊回答并触发追问 | 高 | 5 | 浅层回答触发追问率；追问有效性评分 | 触发率 100%；有效性 >= 4/5 | 低分/缺失维度会选追问；浅层识别本身仍缺真实 judge 样本 | 部分通过 | 2.5 | backend tests/unit/test_chief_reasoning.py::test_parallel_results_ready_low_score_picks_followup；test_pick_question_low_score_returns_followup |
| Q2-2 | 追问分层：技术细节层 | 高 | 5 | 技术细节追问命中率 | >= 1 次有效技术实现/方案追问 | 待执行 | 未执行 | 0 | 缺少技术实现/方案类追问 transcript 与 judge 输出 |
| Q2-3 | 追问分层：行为逻辑层 | 高 | 5 | 行为逻辑追问命中率 | >= 1 次有效决策原因/阻力处理追问 | 待执行 | 未执行 | 0 | 缺少决策原因/阻力处理类追问 transcript 与 judge 输出 |
| Q2-4 | 追问分层：量化结果层 | 中 | 3 | 量化结果追问命中率 | >= 1 次有效结果/影响量化追问 | 缺失维度为量化时选择追问，Designer fallback 会要求最终效果数据 | 通过 | 3 | backend tests/unit/test_chief_reasoning.py::test_followup_focus_uses_missing_dimensions；test_designer_agent.py::test_designer_agent_rewrites_generic_question |
| Q2-5 | 追问不超过 3 层 | 中 | 3 | 单题最大追问轮次；自动推进情况 | 单题追问轮次 <= 3；超过后进入下一题 | 当前 max_followups=2；达到上限后强制选择新题 | 通过 | 3 | backend tests/unit/test_chief_reasoning.py::test_pick_question_max_followups_forces_new_question；test_interviewer_master_node.py |

### Q2 小结

| 指标 | 当前值 | 目标值 |
| ---- | ------ | ------ |
| 测试项 | 5 | 5 |
| 可得分 | 21 | 21 |
| 当前得分 | 8.5 | >= 21 |
| 高优先级通过率 | 0% | 100% |

---

## 4. Q3 语气与中立性

| # | 测试项 | 优先级 | 权重 | 量化指标 | 通过阈值 | 实测值 | 状态 | 得分 | 证据/备注 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| Q3-1 | 语气专业、中立，不过于热情或冷漠 | 高 | 5 | 中立性平均分；夸张表扬次数；冷漠敷衍次数 | 中立性 >= 4/5；夸张表扬 0；冷漠敷衍 0 | Chief/Designer/Followup prompt 明确禁止赞美；未跑中立性 judge | 部分通过 | 2.5 | backend/app/agents/interviewer/chief_prompts.py；backend/app/agents/designer/prompts.py；backend/app/agents/interviewer/prompts.py |
| Q3-2 | 不在问题中暗示正确答案 | 高 | 5 | 引导性措辞次数 | 0 次 | 问题/追问/Designer prompt 已禁止暗示标准答案和引导式问题；未做 transcript 规则扫描 | 部分通过 | 2.5 | backend tests/unit/test_interviewer_quality_guards.py::test_question_prompts_ban_leading_or_answer_revealing_questions |
| Q3-3 | 不对候选人回答做即时评价 | 高 | 5 | 实质性褒贬评价次数 | 0 次 | 面试中追问/出题 prompt 禁止赞美或批评；未做 transcript 标注 | 部分通过 | 2.5 | backend/app/agents/interviewer/chief_prompts.py；backend/app/agents/interviewer/prompts.py::FOLLOWUP_SYSTEM_PROMPT |
| Q3-4 | 面试结束语礼貌、不透露评估结果 | 中 | 3 | 感谢语命中；后续流程命中；评估泄露次数 | 感谢语 = 是；后续流程 = 是；评估泄露 0 次 | closing prompt 只感谢、告知面试结束和后续报告，明确禁止透露表现判断、评分、优缺点或改进建议 | 通过 | 3 | backend tests/unit/test_interviewer_quality_guards.py::test_closing_prompt_does_not_leak_evaluation_result |

### Q3 小结

| 指标 | 当前值 | 目标值 |
| ---- | ------ | ------ |
| 测试项 | 4 | 4 |
| 可得分 | 18 | 18 |
| 当前得分 | 10.5 | >= 18 |
| 高优先级通过率 | 0% | 100% |

---

## 5. Q4 面试节奏

| # | 测试项 | 优先级 | 权重 | 量化指标 | 通过阈值 | 实测值 | 状态 | 得分 | 证据/备注 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| Q4-1 | 主问题之间不跳跃 | 中 | 3 | 话题切换过渡语命中率；突兀跳题次数 | 过渡语命中率 >= 80%；突兀跳题 0 次 | 待执行 | 未执行 | 0 | 缺少完整问题序列和话题切换 judge 输出 |
| Q4-2 | 不重复提问已考察过的内容 | 高 | 5 | 高相似问题对数量 | 余弦相似度 > 0.85 的问题对 = 0 | Designer 会改写与 previous_questions 高度重复的问题；缺少全场 embedding 重复检测结果 | 部分通过 | 2.5 | backend tests/unit/test_designer_agent.py::test_designer_rewrites_question_repeated_with_previous_questions |
| Q4-3 | 总问题数在合理范围 | 中 | 3 | 主问题数；总对话轮次 | 主问题 5-8；加追问后总轮次 <= 25 | 默认 total_questions=5，closing 阶段 question_count=5；max_followups=2 | 通过 | 3 | backend tests/integration/test_interview_turn_service.py；backend tests/unit/test_chief_reasoning.py |
| Q4-4 | 不在候选人回答中途打断 | 低 | 1 | 流式抢答次数；候选人消息完成后回复比例 | 抢答 0 次；完成后回复比例 100% | 待执行 | 未执行 | 0 | 缺少真实浏览器/SSE 时间线标注 |

### Q4 小结

| 指标 | 当前值 | 目标值 |
| ---- | ------ | ------ |
| 测试项 | 4 | 4 |
| 可得分 | 12 | 12 |
| 当前得分 | 5.5 | >= 11 |
| 高优先级通过率 | 0% | 100% |

---

## 6. Q5 岗位核心能力覆盖率

| # | 测试项 | 优先级 | 权重 | 量化指标 | 通过阈值 | 实测值 | 状态 | 得分 | 证据/备注 |
| --- | --- | --- | ---: | --- | --- | --- | --- | ---: | --- |
| Q5-1 | JD 中所有一级能力维度均有覆盖 | 高 | 5 | 一级能力维度覆盖率 | 100%；每个一级维度至少 1 道主问题 | JD key_skills/hard_requirements 可进入题目生成上下文；未做能力维度映射统计 | 部分通过 | 2.5 | backend tests/unit/test_prepare_nodes.py::test_jd_analysis_returns_jd_context；test_designer_consumes_job_intel.py |
| Q5-2 | 无单一维度占比 > 50% 的失衡 | 中 | 3 | 单一维度最高占比 | 任意单一维度问题数 <= 总问题数的 40% | 题库生成 prompt 要求单一 focus_area 不超过 40%；缺少真实题库维度统计输出 | 部分通过 | 1.5 | backend tests/unit/test_interviewer_quality_guards.py::test_prepare_question_generation_requires_dimension_balance |
| Q5-3 | 候选人的亮点/弱项在题库中得到针对性检验 | 中 | 3 | 亮点深度题覆盖；弱项探测题覆盖 | 亮点领域 >= 1 道深度题；弱项区域 >= 1 道探测题 | 历史弱项优先级、岗位强项/Gap 注入已覆盖；未跑亮点/弱项题目映射 judge | 部分通过 | 1.5 | backend tests/unit/test_prepare_nodes.py::test_question_gen_weak_areas_first；test_designer_consumes_job_intel.py |

### Q5 小结

| 指标 | 当前值 | 目标值 |
| ---- | ------ | ------ |
| 测试项 | 3 | 3 |
| 可得分 | 11 | 11 |
| 当前得分 | 5.5 | >= 11 |
| 高优先级通过率 | 0% | 100% |

---

## 7. Judge 执行记录

| 执行批次 | 样本来源 | 样本量 | Judge 模型 | Prompt 版本 | 平均相关性 | 平均中立性 | 平均追问有效性 | 原始输出 |
| -------- | -------- | ------ | ---------- | ----------- | ---------- | ---------- | ---------------- | -------- |
| 2026-06-05-auto-evidence | 自动化测试证据映射，非 LLM judge | 0 个 judge 样本 | 未执行 | checklist 内模板 | 待填 | 待填 | 待填 | 待补真实 transcript/JD/简历摘要 |

---

## 8. 问题登记表

| 问题 ID | 关联用例 | 严重级别 | 现象 | 影响范围 | 复现步骤 | 当前状态 | 修复负责人 |
| ------- | -------- | -------- | ---- | -------- | -------- | -------- | ---------- |
| D2-Q3-4-CLOSING-PROMPT | Q3-4 | 中 | 结束语 prompt 曾要求“最终点评”，可能向候选人泄露表现判断 | closing_node / chief_respond 收尾话术 | 检查 backend/app/agents/interviewer/prompts.py::CLOSING_SYSTEM_PROMPT | 已修复 | Codex |

---

## 9. 执行记录

| 执行批次 | 环境 | 执行人 | 开始时间 | 结束时间 | 通过项 | 失败项 | 阻塞项 | 附件 |
| -------- | ---- | ------ | -------- | -------- | ------ | ------ | ------ | ---- |
| 2026-06-05-auto-evidence | 本地 | Codex | 2026-06-05 | 2026-06-05 | 102 | 0 | 0 | `uv run pytest tests/unit/test_interviewer_quality_guards.py tests/unit/test_prepare_nodes.py tests/unit/test_designer_agent.py tests/unit/test_designer_consumes_job_intel.py tests/unit/test_evaluator_consumes_job_intel.py tests/unit/test_chief_reasoning.py tests/unit/test_chief_safety.py tests/unit/test_interviewer_master_node.py tests/unit/test_interview_three_gaps.py tests/integration/test_interview_turn_service.py` |

---

## 10. 最终结论

当前报告已完成自动化证据映射，但尚未完成 LLM-as-judge 与人工 transcript 抽查。正式结论需要在补齐真实样本后更新：

| 结论项 | 当前结论 |
| ------ | -------- |
| 是否满足质量准入 | 不满足：36.5 / 75，低于 68 / 75 |
| 是否存在高优先级失败 | 未发现高优先级失败，但高优先级通过率为 0%，多数仍为部分通过或未执行 |
| 是否需要扩大样本复测 | 需要：LLM judge 样本 0，人工 transcript 抽查 0 |
| 建议 | Q3-4 已修复；继续补齐 Q2-2、Q2-3、Q4-1、Q4-4 的 transcript / SSE 时间线，以及 Q1、Q3、Q5 的 LLM judge；当前不建议进入下一阶段 |
