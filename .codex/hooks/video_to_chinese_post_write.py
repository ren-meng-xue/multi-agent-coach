#!/usr/bin/env python3
"""PostToolUse hook：video-to-chinese 文档存档确认。

Write 成功写入 video-to-chinese/docs/*.md 后，打印存档提示，
让 Claude 在回复里告知用户文件已落地。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return

    if payload.get("tool_name") != "Write":
        return

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    norm = file_path.replace("\\", "/")
    if "video-to-chinese/docs/" not in norm or not norm.endswith(".md"):
        return

    filename = Path(file_path).name
    print(
        f"[video-to-chinese] ✓ 已存档：{filename}\n"
        f"路径：{file_path}"
    )


if __name__ == "__main__":
    main()
