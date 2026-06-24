#!/usr/bin/env python3
"""PreToolUse hook：video-to-chinese 文档写入校验。

在 Write 工具写入 video-to-chinese/docs/*.md 之前：
1. 文件名格式强制：YYYY-MM-DD-<slug>.md
2. 必填章节校验：一句话总结 / 核心观点 / 来源与限制

通过 → 不输出（放行）
拦截 → {"continue": false, "stopReason": "..."}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REQUIRED_SECTIONS = ["## 一句话总结", "## 核心观点", "## 来源与限制"]
FILENAME_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}-.+\.md$")
DOCS_MARKER = f"video-to-chinese{re.escape('/')}docs{re.escape('/')}"


def _allow() -> None:
    return


def _reject(reason: str) -> None:
    print(json.dumps({"continue": False, "stopReason": reason}, ensure_ascii=False))


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return _allow()

    if payload.get("tool_name") != "Write":
        return _allow()

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")

    # 只处理 video-to-chinese/docs/ 下的 .md 文件
    norm = file_path.replace("\\", "/")
    if "video-to-chinese/docs/" not in norm or not norm.endswith(".md"):
        return _allow()

    filename = Path(file_path).name

    # 1. 文件名格式校验
    if not FILENAME_PATTERN.match(filename):
        return _reject(
            f"[video-to-chinese] 文件名格式不符：{filename!r}\n"
            "要求格式：YYYY-MM-DD-<slug>.md，例如 2026-06-01-my-video.md"
        )

    # 2. 必填章节校验（字幕文件免检）
    if "-transcript" in filename:
        return _allow()

    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    if missing:
        return _reject(
            f"[video-to-chinese] 缺少必填章节：{', '.join(missing)}\n"
            "请补全后再保存。"
        )

    return _allow()


if __name__ == "__main__":
    main()
