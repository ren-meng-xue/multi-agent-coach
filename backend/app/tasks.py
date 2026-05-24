"""Celery 异步任务队列配置，用于后台 LLM 调用、向量索引等耗时操作。"""
from celery import Celery  # type: ignore[import-untyped]

from app.core.config import get_settings

_settings = get_settings()

celery_app = Celery(
    "multi-agent-coach",
    broker=_settings.redis_url,
    backend=_settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
