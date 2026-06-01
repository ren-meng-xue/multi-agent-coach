#!/usr/bin/env python3
"""Small MCP server that exposes OpenAI vision as a Claude Code tool."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


PROTOCOL_VERSION = "2024-11-05"
LOCAL_ENV_FILE = ".env.claude-mcp-openai.local"


def _debug(message: str) -> None:
    if os.environ.get("OPENAI_VISION_MCP_DEBUG") != "1":
        return
    log_path = Path(os.environ.get("OPENAI_VISION_MCP_LOG", "/tmp/openai_vision_mcp.log"))
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(message + "\n")


def _read_message() -> dict | None:
    line = sys.stdin.buffer.readline()
    if line == b"":
        _debug("stdin_eof")
        return None
    message = json.loads(line.decode("utf-8"))
    _debug(f"recv:{message.get('method')} id={message.get('id')}")
    return message


def _write_message(message: dict) -> None:
    payload = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(payload + b"\n")
    sys.stdout.buffer.flush()
    _debug(f"send:{'error' if 'error' in message else 'result'} id={message.get('id')}")


def _result(request_id, result: dict) -> None:
    _write_message({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(request_id, code: int, message: str) -> None:
    _write_message({"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


def _image_path_to_data_url(image_path: str) -> str:
    path = Path(image_path).expanduser()
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_file():
        raise ValueError(f"Image file not found: {path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    if not mime_type or not mime_type.startswith("image/"):
        mime_type = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _is_placeholder(value: str | None) -> bool:
    return not value or value.startswith("${")


def _load_local_env_if_needed() -> None:
    if not _is_placeholder(os.environ.get("OPENAI_API_KEY")):
        return

    env_path = Path.cwd() / LOCAL_ENV_FILE
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in {"OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL", "OPENAI_MAX_TOKENS"}:
            os.environ[key] = value


def _extract_openai_text(data: dict) -> str:
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            if parts:
                return "\n".join(parts)
    return json.dumps(data, ensure_ascii=False)


def _call_openai_vision(arguments: dict) -> str:
    _load_local_env_if_needed()
    api_key = os.environ.get("OPENAI_API_KEY")
    if _is_placeholder(api_key):
        raise ValueError("OPENAI_API_KEY is not set for the vision MCP server.")

    image_url = arguments.get("image_url")
    image_path = arguments.get("image_path")
    if not image_url and image_path:
        image_url = _image_path_to_data_url(image_path)
    if not image_url:
        raise ValueError("Provide either image_path or image_url.")

    prompt = arguments.get("prompt") or "请详细分析这张图片。"
    detail = arguments.get("detail") or "auto"
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    max_tokens = int(os.environ.get("OPENAI_MAX_TOKENS", "1200"))
    timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "120"))
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    body = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url, "detail": detail}},
                ],
            }
        ],
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc

    return _extract_openai_text(data)


def _tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "analyze_image",
                "description": "Analyze an image with OpenAI vision. Provide a local image_path or an image_url.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Local image path. Relative paths resolve from the Claude Code working directory.",
                        },
                        "image_url": {
                            "type": "string",
                            "description": "HTTP(S) URL or data URL for the image.",
                        },
                        "prompt": {
                            "type": "string",
                            "description": "Question or instruction for image analysis.",
                        },
                        "detail": {
                            "type": "string",
                            "enum": ["auto", "low", "high"],
                            "description": "Vision detail level.",
                        },
                    },
                    "anyOf": [{"required": ["image_path"]}, {"required": ["image_url"]}],
                },
            }
        ]
    }


def _handle_request(message: dict) -> None:
    request_id = message.get("id")
    method = message.get("method")

    if method == "initialize":
        _result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "openai-vision", "version": "0.1.0"},
            },
        )
    elif method == "tools/list":
        _result(request_id, _tools_list())
    elif method == "tools/call":
        params = message.get("params") or {}
        if params.get("name") != "analyze_image":
            _error(request_id, -32601, f"Unknown tool: {params.get('name')}")
            return
        try:
            text = _call_openai_vision(params.get("arguments") or {})
            _result(request_id, {"content": [{"type": "text", "text": text}]})
        except Exception as exc:  # noqa: BLE001 - MCP should return tool errors as text.
            _result(request_id, {"content": [{"type": "text", "text": f"Vision MCP error: {exc}"}], "isError": True})
    elif request_id is not None:
        _error(request_id, -32601, f"Unsupported method: {method}")


def main() -> None:
    _debug(f"startup cwd={Path.cwd()} argv={sys.argv!r}")
    while True:
        message = _read_message()
        if message is None:
            break
        _handle_request(message)


if __name__ == "__main__":
    main()
