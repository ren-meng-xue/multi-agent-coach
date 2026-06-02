#!/usr/bin/env python3
"""
Agent OS Protocol Linter

校验 .ai/workflows/*.yaml 与 .ai/tasks/<task>/status.json 的一致性。

退出码：
  0  全部通过
  1  发现 error
  2  仅 warning（没有 error）

使用：
  python3 .ai/lib/python/protocol_linter.py                # 默认扫整个项目
  python3 .ai/lib/python/protocol_linter.py --root <dir>   # 指定项目根
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workflow_loader import (  # noqa: E402
    VALID_DEPTHS,
    collect_step_owners,
    cumulative_outputs,
    load_capabilities as _load_capabilities,
    load_workflows as _load_workflows,
    step_is_active,
)


REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[3]

# 与 .ai/prompts/status-template.md 字段保持一致（type 字段已废弃）
STATUS_REQUIRED_FIELDS = (
    "task_id",
    "title",
    "workflow",
    "state",
    "current_owner",
    "created_at",
    "updated_at",
)
STATUS_PLACEHOLDER_VALUES = {
    "task_id": {"", "YYYYMMDD-semantic-name"},
    "created_at": {""},
    "updated_at": {""},
}
TASK_ID_PATTERN = re.compile(r"^\d{8}-[a-z0-9][a-z0-9-]*[a-z0-9]$")


@dataclass
class Finding:
    level: str  # "ERROR" | "WARN"
    where: str
    message: str

    def fmt(self) -> str:
        return f"[{self.level}] {self.where}: {self.message}"


def load_workflows(workflows_dir: Path) -> tuple[dict[str, dict], list[Finding]]:
    findings: list[Finding] = []
    workflows, loader_errors = _load_workflows(workflows_dir)
    for err in loader_errors:
        findings.append(Finding("ERROR", str(workflows_dir), err))

    for wid, data in workflows.items():
        where = str(workflows_dir / f"{wid}.yaml")
        for field in ("id", "name", "description", "entry", "terminal", "steps"):
            if field not in data:
                findings.append(Finding("ERROR", where, f"缺少必填字段 `{field}`"))

        if "version" not in data:
            findings.append(Finding("WARN", where, "建议加 `version` 字段"))

        steps = data.get("steps") or {}
        if not isinstance(steps, dict):
            findings.append(Finding("ERROR", where, "`steps` 必须是 mapping"))
            steps = {}

        entry = data.get("entry")
        terminal = data.get("terminal")
        if entry and entry not in steps:
            findings.append(Finding("ERROR", where, f"entry `{entry}` 不在 steps 内"))
        if terminal and terminal not in steps:
            findings.append(Finding("ERROR", where, f"terminal `{terminal}` 不在 steps 内"))

        for step_name, step in steps.items():
            if not isinstance(step, dict):
                findings.append(Finding("ERROR", where, f"step `{step_name}` 必须是 mapping"))
                continue
            nxt = step.get("next")
            if nxt and nxt not in steps:
                findings.append(Finding("ERROR", where, f"step `{step_name}.next` -> `{nxt}` 不在 steps 内"))
            trans = step.get("transitions") or {}
            if isinstance(trans, dict):
                for k, v in trans.items():
                    if v not in steps:
                        findings.append(Finding("ERROR", where, f"step `{step_name}.transitions[{k}]` -> `{v}` 不在 steps 内"))
            resume_to = step.get("resume_to")
            if resume_to and resume_to not in steps:
                findings.append(Finding("ERROR", where, f"step `{step_name}.resume_to` -> `{resume_to}` 不在 steps 内"))
            on_blocked = step.get("on_blocked")
            if on_blocked and on_blocked not in steps:
                findings.append(Finding("ERROR", where, f"step `{step_name}.on_blocked` -> `{on_blocked}` 不在 steps 内"))

            min_depth = step.get("min_depth")
            if min_depth and min_depth not in VALID_DEPTHS:
                findings.append(
                    Finding("ERROR", where, f"step `{step_name}.min_depth`=`{min_depth}` 不在有效值 {VALID_DEPTHS} 中")
                )

            checkpoint = step.get("checkpoint")
            if checkpoint is not None and not isinstance(checkpoint, bool):
                findings.append(
                    Finding("ERROR", where, f"step `{step_name}.checkpoint` 必须是 boolean")
                )

    return workflows, findings


def load_capabilities(agents_dir: Path) -> tuple[set[str], list[Finding]]:
    agents, errors = _load_capabilities(agents_dir)
    findings = [Finding("WARN", str(agents_dir), e) for e in errors]
    return agents, findings


def _find_output_producers(wf: dict, output: str) -> set[str]:
    """找出 workflow 中产出指定 output 的所有 step 名称。"""
    steps = wf.get("steps") or {}
    producers: set[str] = set()
    for name, step in steps.items():
        if output in (step.get("outputs") or []):
            producers.add(name)
    return producers


def lint_tasks(tasks_dir: Path, workflows: dict[str, dict], valid_agents: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    if not tasks_dir.is_dir():
        return findings

    for task_dir in sorted(tasks_dir.iterdir()):
        if not task_dir.is_dir():
            continue
        if task_dir.name == "archive":
            continue
        status_path = task_dir / "status.json"
        where = str(status_path)

        if not status_path.is_file():
            findings.append(Finding("ERROR", str(task_dir), "缺 status.json"))
            continue

        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("ERROR", where, f"JSON 损坏: {exc}"))
            continue

        for field in STATUS_REQUIRED_FIELDS:
            if field not in status:
                findings.append(Finding("ERROR", where, f"缺字段 `{field}`"))
                continue
            placeholders = STATUS_PLACEHOLDER_VALUES.get(field)
            if placeholders and status.get(field) in placeholders:
                findings.append(Finding("ERROR", where, f"字段 `{field}` 仍是占位符 `{status[field]}`"))

        if "type" in status:
            findings.append(
                Finding("WARN", where, "字段 `type` 已废弃（与 workflow 冗余），请删除")
            )

        depth = status.get("depth")
        if depth is None:
            findings.append(Finding("WARN", where, "建议添加 `depth` 字段（quick/standard/thorough/full）"))
        elif depth not in VALID_DEPTHS:
            findings.append(
                Finding("ERROR", where, f"depth `{depth}` 不在有效值 {VALID_DEPTHS} 中")
            )

        if status.get("task_id") and not TASK_ID_PATTERN.match(status["task_id"]):
            findings.append(
                Finding(
                    "ERROR",
                    where,
                    f"task_id `{status['task_id']}` 不符合 `YYYYMMDD-semantic-name` 命名（小写、连字符）",
                )
            )

        wf_id = status.get("workflow")
        state = status.get("state")
        cur = status.get("current_owner")
        nxt = status.get("next_owner")

        wf = workflows.get(wf_id) if wf_id else None
        if wf_id and not wf:
            findings.append(Finding("ERROR", where, f"workflow `{wf_id}` 在 .ai/workflows/ 不存在"))

        if wf:
            steps = wf.get("steps") or {}
            if state and state != "blocked" and state not in steps:
                findings.append(Finding("ERROR", where, f"state `{state}` 不在 workflow `{wf_id}` 的 steps 内"))

            step_def = steps.get(state) if state in steps else None
            if step_def:
                # 校验"进入该 state 时必有的 outputs"——前 step 已完成的产出
                # 若 task 指定了 depth，仅检查在该深度下活跃的 step 的 outputs
                cum = cumulative_outputs(wf).get(state, [])
                task_depth = status.get("depth")
                for output in cum:
                    # 找到产出该 output 的 step(s)，若 task 有 depth 则跳过不活跃的
                    if task_depth:
                        producing_steps = _find_output_producers(wf, output)
                        if producing_steps and all(
                            not step_is_active((wf.get("steps") or {}).get(s, {}), task_depth)
                            for s in producing_steps
                        ):
                            continue
                    if not (task_dir / output).is_file():
                        findings.append(
                            Finding("ERROR", where, f"state=`{state}` 缺前置 output `{output}`")
                        )
                # terminal state 自身的 outputs 也必须存在（归档凭证）
                if state == wf.get("terminal"):
                    for output in step_def.get("outputs") or []:
                        if not (task_dir / output).is_file():
                            findings.append(
                                Finding("ERROR", where, f"terminal state=`{state}` 缺归档 output `{output}`")
                            )

            # current_owner 必须能扮演当前 step 的 owner
            if step_def:
                step_owners = set()
                if step_def.get("owner") and step_def["owner"] not in ("current_agent",):
                    step_owners.add(step_def["owner"])
                for o in step_def.get("owners") or []:
                    step_owners.add(o)
                if step_owners and cur and cur not in step_owners:
                    findings.append(Finding("WARN", where, f"current_owner=`{cur}` 不在 step `{state}` 的合法 owner 集 {sorted(step_owners)}"))

        if valid_agents:
            if cur and cur not in valid_agents:
                findings.append(Finding("ERROR", where, f"current_owner `{cur}` 不在已注册 agent 集"))
            if nxt and nxt not in valid_agents:
                findings.append(Finding("ERROR", where, f"next_owner `{nxt}` 不在已注册 agent 集"))

        # 非终端态、非入口态应有 handoff.md
        if wf and state:
            entry_state = wf.get("entry")
            if state != wf.get("terminal") and state != "planning" and state != entry_state:
                handoff = task_dir / "handoff.md"
                if not handoff.is_file():
                    findings.append(Finding("ERROR", str(task_dir), f"state=`{state}` 缺 handoff.md"))

    return findings


def lint_memory(memory_dir: Path, agents_dir: Path) -> list[Finding]:
    """校验 .ai/memory/ 体系一致性。"""
    findings: list[Finding] = []
    if not memory_dir.is_dir():
        return findings

    mem_index = memory_dir / "MEMORY.md"
    actual_memories = {
        p.name for p in memory_dir.iterdir()
        if p.is_file() and p.suffix == ".md" and p.name != "MEMORY.md"
    }

    # MEMORY.md 索引是否存在
    if not mem_index.is_file():
        findings.append(Finding("ERROR", str(memory_dir), "缺 MEMORY.md 索引文件"))
        return findings

    # 解析 MEMORY.md 中的条目（支持列表或表格中的 [file.md](file.md) 链接）
    indexed: set[str] = set()
    try:
        content = mem_index.read_text(encoding="utf-8")
        for line in content.splitlines():
            for m in re.finditer(r"\[([^\]]+\.md)\]\(([^)]+\.md)\)", line):
                indexed.add(m.group(2))
    except Exception as exc:
        findings.append(Finding("ERROR", str(mem_index), f"无法读取 MEMORY.md: {exc}"))
        return findings

    # 索引中有但文件不存在的条目
    for name in indexed:
        if name not in actual_memories:
            findings.append(Finding("ERROR", str(mem_index), f"索引引用了不存在的文件 `{name}`"))

    # 文件存在但未被索引的孤立记忆
    for name in sorted(actual_memories - indexed):
        findings.append(Finding("WARN", str(memory_dir / name), f"未被 MEMORY.md 索引的孤立记忆文件"))

    # Agent Context 段引用的 memory 是否存在
    if agents_dir.is_dir():
        for agent_file in sorted(agents_dir.glob("*.md")):
            try:
                agent_content = agent_file.read_text(encoding="utf-8")
            except Exception:
                continue
            # 在 Context 段中找类似 "backend / api / database" 的记忆引用
            in_context = False
            for line in agent_content.splitlines():
                if line.strip().startswith("## Context"):
                    in_context = True
                    continue
                if in_context and line.strip().startswith("## "):
                    in_context = False
                    continue
                if in_context:
                    # 匹配类似 "api / backend / architecture" 的记忆名称模式
                    tokens = re.findall(r"\b([a-z][a-z-]*[a-z])\.md\b", line)
                    for token in tokens:
                        ref = f"{token}.md"
                        if ref not in actual_memories:
                            findings.append(
                                Finding("WARN", str(agent_file), f"Context 引用了不存在的记忆文件 `{ref}`")
                            )

    # 记忆文件过期检测：超过 30 天未更新发出 WARN
    now = time.time()
    stale_seconds = 30 * 24 * 3600
    for name in sorted(actual_memories):
        fpath = memory_dir / name
        try:
            mtime = fpath.stat().st_mtime
            age_days = (now - mtime) / 86400
            if age_days > 30:
                findings.append(
                    Finding("WARN", str(fpath), f"记忆文件 {age_days:.0f} 天未更新，建议 review 内容是否仍然准确")
                )
        except Exception:
            pass

    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Agent OS Protocol Linter")
    parser.add_argument("--root", type=Path, default=REPO_ROOT_DEFAULT)
    parser.add_argument("--quiet", action="store_true", help="只输出错误数")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    workflows_dir = root / ".ai" / "workflows"
    tasks_dir = root / ".ai" / "tasks"
    agents_dir = root / ".ai" / "agents"

    findings: list[Finding] = []

    workflows, wf_findings = load_workflows(workflows_dir)
    findings.extend(wf_findings)

    valid_agents, cap_findings = load_capabilities(agents_dir)
    findings.extend(cap_findings)

    memory_dir = root / ".ai" / "memory"
    findings.extend(lint_memory(memory_dir, agents_dir))

    findings.extend(lint_tasks(tasks_dir, workflows, valid_agents))

    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]

    if not args.quiet:
        for f in findings:
            print(f.fmt())

    print(f"--- {len(errors)} error(s), {len(warns)} warning(s)")

    if errors:
        return 1
    if warns:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
