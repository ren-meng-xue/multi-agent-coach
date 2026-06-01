# API Conventions

## 路由结构

| 前缀 | 模块 | 说明 |
|---|---|---|
| `/api/v1/auth/*` | `api/v1/auth.py` | 登录、token 校验、用户初始化 |
| `/api/v1/user/*` | `api/v1/user.py` | 当前用户、设置 |
| `/api/v1/prepare/*` | `api/v1/prepare.py` | 简历 / JD 上传与解析 |
| `/api/v1/interview/*` | `api/v1/interview.py` | 面试 session、消息、SSE 流 |
| `/api/v1/coach/*` | `api/v1/coach.py` | Coach 复盘、改进建议 |
| `/api/v1/eval/*` | `api/v1/eval.py` | 评测查询 |
| `/api/v1/health` | `api/v1/health.py` | 健康检查 |

## 响应包装

所有非 SSE 端点统一返回 `app.schemas.response.Response[T]`：

```python
class Response(BaseModel, Generic[T]):
    code: int     # 0 = 成功，其他 = 业务错误码
    message: str
    data: T | None
```

错误通过 `core.exceptions.AppException` 抛出，FastAPI 全局 handler 翻译成 `Response`。

## SSE

- 流式接口（如 `interview/chat`）走 `sse-starlette`
- 事件类型见 `frontend/lib/interview-chat.ts`，前后端必须同步定义
- 客户端用 `frontend/lib/sse.ts`，支持自动重连和事件 dispatch

## 鉴权

- 所有 `/api/v1/*` 除 `health` 默认要 Clerk session token（`Authorization: Bearer <token>`）
- 后端从 token 解析 `clerk_user_id`，对应 `users.id`
- 不要自建 JWT；不要 mock 用户

## 版本演进

- 不破坏现有 v1 字段——加字段而非删字段
- 破坏性变更走 `/api/v2`，与 v1 并存一段时间
