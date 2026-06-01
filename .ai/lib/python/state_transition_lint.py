#!/usr/bin/env python3
"""PreToolUse hook：拦截 `.ai/tasks/*/status.json` 写入 state=done 时缺失关键 outputs。

最简版策略：
- 仅针对 state=done 的 transition 做防御
- 仅严格强制 review.md（最易被跳过的关键证据）
- 其他 outputs（plan.md/task.md/handoff.md 等）不拦，避免误伤历史 task

输入（stdin）: Claude Code PreToolUse hook payload JSON
输出（stdout）: {"continue": false, "stopReason": "..."} 拒绝；空输出放行
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS_DIR = REPO_ROOT / ".ai" / "workflows"

# 加载 workflow_loader（失败时放行，永不阻塞 Claude）
sys.path.insert(0, str(REPO_ROOT / ".ai" / "lib" / "python"))


def _allow() -> None:
    """放行（不输出 = 允许）。"""
    return


def _reject(reason: str) -> None:
    print(json.dumps({"continue": False, "stopReason": reason}, ensure_ascii=False))


def _extract_new_state(tool_input: dict) -> str | None:
    """从 tool_input 中尽力抽取即将写入的 state 值。"""
    for key in ("content", "new_string"):
        text = tool_input.get(key)
        if not text:
            continue
        m = re.search(r'"state"\s*:\s*"([a-zA-Z_-]+)"', text)
        if m:
            return m.group(1)
    return None


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return _allow()

    tool_input = payload.get("tool_input") or {}
    file_path = str(tool_input.get("file_path") or "")

    # 仅针对 .ai/tasks/<任务名>/status.json
    if not re.search(r"\.ai/tasks/[^/]+/status\.json$", file_path):
        return _allow()

    new_state = _extract_new_state(tool_input)
    if new_state != "done":
        return _allow()

    status_path = Path(file_path)
    task_dir = status_path.parent

    # status.json 必须已存在（新建直接写 done 可疑）
    if not status_path.exists():
        return _reject(
            "[lint-state-transition] 拒绝直接新建 status.json 为 state=done："
            f"{file_path} 不存在。请先按 `.ai/bin/new-task` 正常建任务。"
        )

    try:
        old_status = json.loads(status_path.read_text(encoding="utf-8"))
    except Exception:
        return _allow()  # 解析失败（可能部分写入），不拦

    if old_status.get("state") == "done":
        return _allow()  # 已经是 done，重写不变（如 notes 修订），放行

    workflow_id = old_status.get("workflow")
    if not workflow_id:
        return _allow()  # 缺 workflow 字段，不拦

    # 加载 workflows 并计算 done 前的累积 outputs
    try:
        from workflow_loader import cumulative_outputs, load_workflows
        workflows, _errors = load_workflows(WORKFLOWS_DIR)
    except Exception as exc:
        return _reject(
            "[lint-state-transition] 加载 .ai/workflows 失败，"
            f"无法验证 state=done 安全性：{exc}。"
        )

    wf = workflows.get(workflow_id)
    if not wf:
        return _allow()  # 未知 workflow，不拦

    required = cumulative_outputs(wf).get("done", [])

    # 最简版：只严格强制 review.md（最易被跳过的关键证据）
    if "review.md" in required and not (task_dir / "review.md").exists():
        return _reject(
            "[lint-state-transition] 拒绝写入 state=done：缺失 review.md。"
            f" workflow={workflow_id} 要求 done 之前 review step 必须产出 review.md。"
            f" 任务目录：{task_dir}。"
            " 请先戴 reviewer 面具完成 review 并写出 review.md，再 transition 到 done。"
        )

    return _allow()


if __name__ == "__main__":
    main()
