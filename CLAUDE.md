# Multi Agent Coach · Claude Code 主控规范

本仓库工程规范条款，Claude Code 必须优先遵守。

---

# Git 规则

1. 永远不要使用：
   - `git add -A`
   - `git add .`

2. 只能按文件名精确添加，例如：

   ```bash
   git add path/to/file.py
   ```

3. 不要自动执行：
   - `git push`
   - `git merge`
   - `git rebase`

4. 每完成一个可独立验证单元后：
   - 先总结修改内容
   - 再询问用户是否 commit

5. Commit message 必须使用 conventional commits：

   - feat
   - fix
   - test
   - refactor
   - docs
   - chore
   - build

---

# 开发流程

1. 所有新代码优先采用 TDD：
   - 先写失败测试
   - 再实现功能

2. 修复 bug 时必须补 regression test

3. 修改代码后必须运行相关验证：
   - lint
   - typecheck
   - tests
   - build（如果适用）

4. 验证失败时：
   - 只修复失败原因
   - 不做无关重构

5. 不允许大规模重构，除非用户明确要求

6. 较大修改前必须：
   - 先分析当前实现
   - 给出修改计划
   - 说明可能影响
   - 再开始修改代码

7. 默认优先：
   - correctness
   - stability
   - maintainability

8. 不要为了“未来扩展”提前设计复杂框架

---

# 代码设计原则

1. 优先简单实现

2. 避免过度抽象

3. 避免无意义的：
   - factory
   - manager
   - registry
   - generic framework

4. 优先：
   - 可读性
   - 可维护性
   - 清晰的数据流

5. 不要引入与当前需求无关的架构层

---

# 后端规范

1. 配置必须走 `pydantic-settings`

2. 禁止硬编码：
   - API Key
   - Secret
   - Token
   - 数据库 URL

3. 数据库迁移必须走 Alembic

4. 禁止直接手改数据库表结构

5. 异步数据库代码必须使用：
   - SQLAlchemy 2.x async
   - asyncpg

6. 日志必须使用 `structlog`

7. 禁止使用 `print`

8. LLM 调用必须：
   - 有 retry 装饰器
   - 有 timeout
   - 有失败日志

9. 外部 API 调用必须：
   - 有错误处理
   - 有超时控制
   - 有重试机制

10. 禁止 silently swallow exceptions

11. 禁止：

    ```python
    except Exception:
        pass
    ```

12. fallback 必须记录 warning/error 日志

13. 用户可见失败必须返回明确错误

---

# 前端规范

1. 前端组件优先使用 shadcn/ui

2. 不要新增 UI 依赖，除非用户明确同意

3. 保持组件职责单一

4. 避免在组件中写复杂业务逻辑

5. 数据获取逻辑尽量放在：
   - hooks
   - services
   - server actions

6. 避免：
   - 深层 prop drilling
   - 巨型组件
   - 隐式状态

7. 注意：
   - loading state
   - error state
   - empty state

---

# 注释规范

1. 公共函数必须有说明

2. 复杂业务逻辑必须写注释

3. 非显然决策必须解释原因

4. 注释重点解释：
   - 为什么这样做
   - 风险是什么
   - 边界条件是什么

5. 不要写重复代码含义的废话注释

错误示例：

```python
# 获取用户
def get_user():
```

正确示例：

```python
# 这里必须强制刷新缓存，
# 因为权限变更后旧缓存可能导致越权访问
```

---

# Review 重点

review 时必须重点检查：

1. type safety

2. async / race condition

3. auth bypass

4. hardcoded secrets

5. database migration risk

6. missing retry / missing timeout

7. missing failure logs

8. missing regression tests

9. edge cases

10. production incident risk

11. memory leak

12. duplicate requests

13. cache consistency

14. error handling completeness

15. rollback safety

---

# 测试规范

1. 新功能至少包含：
   - success case
   - failure case

2. bug 修复必须包含 regression test

3. 涉及 timeout / retry / cancellation 的 async 流程，必须覆盖对应路径
   （不含这些机制的简单 async 代码，覆盖正常路径与失败路径即可）

4. 不要只测试 happy path

5. 测试应尽量避免：
   - sleep
   - 不稳定时间依赖
   - 外部真实服务依赖

---

# 验证命令

## 后端

后端 lint：

```bash
cd backend && .venv/bin/python -m ruff check .
```

后端 typecheck：

```bash
cd backend && .venv/bin/python -m mypy app
```

后端测试：

```bash
cd backend && .venv/bin/python -m pytest tests/
```

---

## 前端

前端 typecheck：

```bash
cd frontend && npm run typecheck
```

前端构建（含 tsc + eslint）：

```bash
cd frontend && npm run build
```

---

# 默认工作流

较大改动按以下完整流程执行；小改动至少走「开发流程」与「验证命令」即可，无需逐步走完：

1. 分析需求

2. 阅读相关代码

3. 提出实现计划

4. 编写失败测试（TDD）

5. 实现功能

6. 运行验证命令

7. 修复验证失败

8. 执行 review

9. 补 regression tests

10. 总结风险与变更

11. 等待用户确认后再 commit
