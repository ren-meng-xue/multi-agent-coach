import os
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，从 .env 文件和系统环境变量加载。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # 应用基础
    app_env: Literal["dev", "prod"] = "dev"
    app_name: str = "multi-agent-coach"
    log_level: str = "INFO"

    # 数据库与缓存
    database_url: str
    redis_url: str

    # OpenAI
    openai_api_key: SecretStr
    openai_model_chat: str = "gpt-4o"
    openai_model_chat_fast: str = "gpt-4o-mini"
    openai_model_coach: str = "gpt-4o-mini"
    openai_model_embedding: str = "text-embedding-3-small"
    openai_model_judge: str = "gpt-4o"  # Judge 专用模型，与被评测模型分离
    # LLM 调用超时（秒），避免单次请求长时间挂起拖垮连接
    llm_timeout_seconds: int = 30

    # Eval
    eval_max_concurrency: int = 5       # 评测并发数
    eval_max_retries: int = 3           # 单 case 最大重试次数
    run_llm_eval_secret: SecretStr | None = None  # 触发 eval 的 secret

    # LangSmith / LangChain tracing：LangGraph 会直接读取这些环境变量上报轨迹
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_project: str = "multi-agent-coach"
    # LangSmith 新命名；启动时会与 LANGCHAIN_* 兼容同步到 os.environ
    langsmith_tracing: bool | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_endpoint: str | None = None
    langsmith_project: str | None = None

    # Firecrawl 爬取
    firecrawl_api_key: SecretStr

    # Clerk 鉴权：JWT PEM 公钥，从 Clerk Dashboard → JWT Templates → Copy public key
    clerk_jwt_key: str
    # issuer 必须参与 JWT 校验，避免跨 Clerk 实例 token 混用
    clerk_issuer: str = ""
    # 二选一：优先校验 aud；Clerk session token 常见场景可用 azp 校验前端来源
    clerk_jwt_audience: str = ""
    clerk_authorized_party: str = ""

    # 跨域白名单
    cors_origins: list[str] = ["http://localhost:3000"]

    # job-intel MCP server（Prepare 阶段 research_agent 使用）
    mcp_job_intel_url: str = "http://localhost:9001/mcp"
    mcp_job_intel_timeout_seconds: int = 90

    # 本地开发/QA 专用：显式开启后允许固定测试 token 跳过 Clerk。
    dev_auth_bypass: bool = False
    dev_auth_user_id: str = "dev-user"


@lru_cache
def get_settings() -> Settings:
    """返回缓存的单例 Settings 实例，用于依赖注入（避免每请求重复解析配置）。"""
    return Settings()  # type: ignore[call-arg]


def configure_langsmith_environment(settings: Settings) -> None:
    """将 pydantic-settings 读取到的 LangSmith 配置同步给 LangChain/LangGraph。

    LangChain/LangSmith 自动 tracing 直接读取进程环境变量；仅通过 Settings 读取 .env
    不会自动写回 os.environ，因此这里同时设置新旧两套变量名。
    """
    tracing_enabled = (
        settings.langsmith_tracing
        if settings.langsmith_tracing is not None
        else settings.langchain_tracing_v2
    )
    if tracing_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"

    api_key = settings.langsmith_api_key or settings.langchain_api_key
    if api_key is not None:
        value = api_key.get_secret_value()
        os.environ["LANGSMITH_API_KEY"] = value
        os.environ["LANGCHAIN_API_KEY"] = value

    endpoint = settings.langsmith_endpoint or settings.langchain_endpoint
    if endpoint:
        os.environ["LANGSMITH_ENDPOINT"] = endpoint
        os.environ["LANGCHAIN_ENDPOINT"] = endpoint

    project = settings.langsmith_project or settings.langchain_project
    if project:
        os.environ["LANGSMITH_PROJECT"] = project
        os.environ["LANGCHAIN_PROJECT"] = project
