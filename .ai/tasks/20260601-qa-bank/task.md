# Task: qa-bank

## Description
实现用户自定义 QA 题库（面试题库）功能。让用户上传 Markdown 格式题库，面试时 AI Coach 优先从题库选题并对比参考答案给反馈。

架构：新建 `user_qa_bank` 表，Markdown 解析服务按 category 覆盖写入；`InterviewSession` 加 `use_qa_bank` 字段；Agent `_state_messages()` 注入题库上下文。

## Acceptance Criteria
- [ ] `user_qa_bank` 表已创建，`interview_sessions.use_qa_bank` 字段已添加
- [ ] Markdown 解析器通过全部 8 个单元测试
- [ ] 3 个 API 路由可用：模板下载、题库上传、摘要查询
- [ ] Interview Agent 在 session 启用题库时注入题库上下文到提示词
- [ ] 前端 API 客户端已创建
- [ ] 设置页展示 QABankCard（题库统计 + 下载/上传按钮）
- [ ] Coach 调度台显示题库开关（有题库时才展示）
