"""FastAPI 应用主入口：挂载路由、中间件、全局异常处理、生命周期事件。"""
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.agents.interviewer.graph import (
    close_interviewer_checkpointer,
    setup_interviewer_checkpointer,
)
from app.api.v1 import auth as auth_v1
from app.api.v1 import coach as coach_v1
from app.api.v1 import eval as eval_v1
from app.api.v1 import health as health_v1
from app.api.v1 import interview as interview_v1
from app.api.v1 import prepare as prepare_v1
from app.api.v1 import qa_bank as qa_bank_v1
from app.api.v1 import user as user_v1
from app.core.config import configure_langsmith_environment, get_settings
from app.core.exceptions import AppException
from app.core.logging import configure_logging, get_logger
from app.schemas.response import Response
from app.services.interview_chat import close_client as close_interview_chat_client

settings = get_settings()
configure_langsmith_environment(settings)
configure_logging(level=settings.log_level, json_output=(settings.app_env != "dev"))
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期事件。"""
    log.info("startup", app_env=settings.app_env)
    await setup_interviewer_checkpointer(settings.database_url)
    yield
    await close_interviewer_checkpointer()
    await close_interview_chat_client()
    log.info("shutdown")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


class ContentSizeLimitMiddleware:
    """ASGI 中间件：在 multipart parser 解析前拦截超大 payload，防止磁盘/内存 spool 被写满。"""
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):
        self.app = app
        self.max_size = max_size

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            content_length = 0
            for header, value in scope.get("headers", []):
                if header == b"content-length":
                    with suppress(ValueError):
                        content_length = int(value)
                    break
            if content_length > self.max_size:
                from starlette.responses import JSONResponse
                response = JSONResponse(
                    status_code=413,
                    content={"code": 413, "message": "请求体大小不能超过 10MB", "data": None}
                )
                await response(scope, receive, send)
                return

            # 对 chunked 传输等没有 Content-Length 声明或逃避声明的请求，通过代理 receive 对实际接收的 body 进行累计拦截
            total_received = 0

            async def custom_receive():
                nonlocal total_received
                message = await receive()
                if message["type"] == "http.request":
                    body = message.get("body", b"")
                    total_received += len(body)
                    if total_received > self.max_size:
                        from fastapi import HTTPException
                        raise HTTPException(
                            status_code=413,
                            detail="请求体大小不能超过 10MB"
                        )
                return message

            await self.app(scope, custom_receive, send)
            return

        await self.app(scope, receive, send)


# 挂载自定义限速中间件
app.add_middleware(ContentSizeLimitMiddleware, max_size=10 * 1024 * 1024)

# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ── 全局异常处理器 ──────────────────────────────────────────────


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """捕获 404/405 等 FastAPI 内置 HTTPException，统一返回 Response 结构。"""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=exc.status_code,
        content=Response.fail(code=exc.status_code, msg=exc.detail).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request, exc: RequestValidationError):
    """捕获 FastAPI 请求参数校验失败，返回 422。"""
    from fastapi.responses import JSONResponse

    errors = exc.errors()
    log.warning("request_validation_error", path=str(request.url), errors=errors)
    return JSONResponse(
        status_code=422,
        content=Response.fail(code=422, msg="请求参数校验失败").model_dump(),
    )


@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    """捕获所有业务异常，返回统一 Response 结构。"""
    from fastapi.responses import JSONResponse

    log.warning("business_exception", path=str(request.url), status=exc.status_code, msg=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content=Response.fail(code=exc.status_code, msg=exc.message).model_dump(),
    )


@app.exception_handler(ValidationError)
async def validation_exception_handler(request, exc: ValidationError):
    """捕获 Pydantic 校验异常，返回 422。"""
    from fastapi.responses import JSONResponse

    log.warning("validation_error", path=str(request.url), errors=exc.errors())
    return JSONResponse(
        status_code=422,
        content=Response.fail(code=422, msg="请求参数校验失败").model_dump(),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    """兜底捕获所有未处理的异常，返回 500 并记录完整日志。"""
    from fastapi.responses import JSONResponse

    log.exception("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500,
        content=Response.fail(code=500, msg="服务器内部错误").model_dump(),
    )


# 挂载路由
app.include_router(health_v1.router, prefix="/api/v1", tags=["health"])
app.include_router(auth_v1.router, prefix="/api/v1", tags=["auth"])
app.include_router(interview_v1.router, prefix="/api/v1", tags=["interview"])
app.include_router(prepare_v1.router, prefix="/api/v1", tags=["prepare"])
app.include_router(user_v1.router, prefix="/api/v1", tags=["user"])
app.include_router(coach_v1.router, prefix="/api/v1", tags=["coach"])
app.include_router(eval_v1.router, prefix="/api/v1", tags=["eval"])
app.include_router(qa_bank_v1.router, prefix="/api/v1", tags=["qa-bank"])
app.include_router(coach_v1.router, prefix="/api", tags=["coach"])
