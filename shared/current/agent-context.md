# Agent Context

Generated at: Fri May 29 11:39:20 CST 2026

## Current Agent

planner

## Next Action

# Next Action

Agent: planner

Task: Task-001: Dispatcher 调度测试

Reason: 任务正在执行中

Action: 查看 planner 当前进度

## Current Task

- Task: Task-001: Dispatcher 调度测试
- State: review
- Owner: backend

## Role Instructions

# 角色：Planner（规划者 / Tech Lead）

你是本项目的技术规划与调度 Agent。

开始任何规划任务前，必须先阅读：

1. `CLAUDE.md`
2. `agents/planner.md`
3. `shared/current/tasks.md`
4. `shared/current/status.md`
5. `shared/decisions/`

之后所有计划必须遵守 `CLAUDE.md` 中定义的项目级规则、工程规范、外部工作流规则、Skill Routing 规则与 Multi-Agent Workflow 规则，并把可执行任务写入 `shared/current/tasks.md`。

你的职责：

* 拆解任务
* 创建 spec
* 制定实现计划
* 维护架构一致性
* 给 backend / frontend / reviewer 分配任务
* 更新 `shared/current/tasks.md`
* 更新 `shared/current/status.md`
* 必要时更新 `shared/decisions/`

你的工作重点：

* 先思考再行动
* 保持任务边界清晰
* 避免直接大量实现代码
* 保持系统整体一致性
* 控制复杂度
* 不把历史任务塞进 `shared/current/`
* 任务完成后负责归档到 `shared/archive/`

输出格式：

1. Goal（目标）
2. Architecture（架构）
3. Backend Tasks（后端任务）
4. Frontend Tasks（前端任务）
5. Reviewer Checklist（Review 检查项）
6. Status Update（状态更新）
## Tasks

# Current Tasks

### Task-001: Dispatcher 调度测试
状态: review
负责人: backend
## Status

# Tasks

## Active Tasks

### Task-TEST: Dispatcher 调度测试

状态: in-progress
优先级: P1
负责人: backend
创建时间: 2026-05-29
关联 spec: 无

#### 背景

验证 dispatcher 能否根据 tasks.md 判断下一步 Agent。

#### 目标

- 验证 pending + backend 会显示 Agent: backend

#### Backend Tasks

- [ ] 测试 dispatcher 输出 backend

#### Frontend Tasks

- 无

#### Reviewer Checklist

- [ ] dispatcher 输出正确

#### 阻塞项

- 无

#### 完成标准

- [ ] status-watch 顶部显示 Agent: backend
## Review
# Review

## Current Review

状态: pending | approved | changes-requested
任务: Task-001
Reviewer: reviewer
最后更新: YYYY-MM-DD HH:mm

## Summary

<review 总结>

## Findings

- [ ] <问题 1>
- [ ] <问题 2>

## Test Result

- command: <测试命令>
- result: passing | failing | not-run

## Decision

approved | changes-requested
## Decisions
# Decisions

## 使用规则

- 只记录已经确认或正在讨论的重要决策。
- 不记录普通 TODO。
- 每条决策必须有状态。
- Agent 修改架构前必须先阅读本文件。

---

## Decision-001: <决策标题>

状态: proposed | accepted | rejected | superseded  
日期: YYYY-MM-DD  
负责人: planner  
关联任务: Task-001

### 背景

<为什么需要这个决策>

### 决策

<最终选择是什么>

### 原因

- <原因 1>
- <原因 2>

### 影响范围

Backend:
- <影响>

Frontend:
- <影响>

Reviewer:
- <需要重点检查什么>

### 备选方案

- <方案 A>
- <方案 B>

### 后续动作

- [ ] <动作 1>
- [ ] <动作 2>