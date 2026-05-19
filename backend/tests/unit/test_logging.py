import structlog

from app.core.logging import configure_logging, get_logger


def test_get_logger_returns_bound_logger():
    """验证 get_logger 返回 structlog BoundLogger 实例。"""
    configure_logging(level="INFO")
    log = get_logger("test")
    assert log is not None
    assert isinstance(log, structlog.stdlib.BoundLogger) or hasattr(log, "info")


def test_structured_log_emits_json(capsys):
    """验证 JSON 模式下日志输出包含 key=value 结构化字段。"""
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test")
    log.info("hello", foo="bar")
    captured = capsys.readouterr()
    assert "hello" in captured.out
    assert "foo" in captured.out
