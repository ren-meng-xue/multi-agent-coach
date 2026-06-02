# Task: Backend Chain Prepare-to-Interview

## 描述
新增 `POST /api/v1/prepare/launch` 端点，将 prepare 多 Agent 流水线与面试开场轮（__START__）串联成单条 SSE 流。前端接收 `phase_change` 事件后自动进入面试，无需用户点击任何按钮。

## 背景
用户反馈从 prepare 完成到面试开始需要手动点击按钮，体验割裂。前一个 PR 做了前端 auto-start 的临时方案；本 task 是后端驱动的最终方案，由 Agent Pipeline 统一编排整个流程。

## 验收标准
- [ ] `/prepare/launch` 端点正常工作，SSE 流依次输出 prepare 事件 → launch 节点 → turn_* 事件
- [ ] need_direction=True 时，流在 prepare 阶段结束后停止，不自动进入面试
- [ ] prepared_questions 从 prepare done 事件提取并正确传递给 stream_interview_turn
- [ ] 前端接收 phase_change 后 assistantIndexRef 设置正确（无 stale closure）
- [ ] 单元测试 3 个全部通过
- [ ] 浏览器端到端冒烟：发起面试后直接流式输出第一道题
