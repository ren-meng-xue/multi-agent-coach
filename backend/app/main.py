"""FastAPI 应用主入口：挂载路由、中间件、生命周期事件。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import health as health_v1
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(level=settings.log_level, json_output=(settings.app_env != "dev"))
log = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的生命周期事件。"""
    log.info("startup", app_env=settings.app_env)
    yield
    log.info("shutdown")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# 跨域中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常捕获，返回 500 并记录结构化日志。"""
    from fastapi.responses import JSONResponse

    log.exception("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(status_code=500, content={"detail": "internal_server_error"})


# 挂载路由
app.include_router(health_v1.router, prefix="/api/v1", tags=["health"])
