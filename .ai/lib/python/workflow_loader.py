#!/usr/bin/env python3
"""
Workflow Loader

`.ai/workflows/*.yaml` 的唯一解析器。
所有消费者（lint / cockpit / hooks）都通过这里读取流程定义，
通过动态扫描 `.ai/agents/*.md` 来确定合法 Agent，
避免硬编码 VALID_STATES、VALID_OWNERS、artifact 列表等"多份真值"。

支持 `extends: <base-id>` 字段：子 workflow 继承 base，再按字段深合并覆盖。

CLI：
  python3 .ai/lib/python/workflow_loader.py states            # 所有 workflow 的合法 state 并集（含 blocked）
  python3 .ai/lib/python/workflow_loader.py owners            # 所有合法 agent 名
  python3 .ai/lib/python/workflow_loader.py outputs <state>   # 该 state 应有的 outputs（across workflows，取并集）
  python3 .ai/lib/python/workflow_loader.py next <wf> <state> <verdict?>
                                                         # 计算下一 state（用于 hook 决策）
  python3 .ai/lib/python/workflow_loader.py show <wf>         # 展开 extends 后的完整 yaml（json 输出）
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[3]

# 有效深度枚举值（由低到高）
VALID_DEPTHS = ("light", "quick", "standard", "thorough", "full")

DEPTH_RANK = {d: i for i, d in enumerate(VALID_DEPTHS)}


def _deep_merge(base: dict, override: dict) -> dict:
    """深合并：dict 字段递归合并，其他类型 override 覆盖 base。"""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve_extends(raw: dict[str, dict]) -> dict[str, dict]:
    """按 extends 链展开 base，返回完整 workflow 字典。"""
    resolved: dict[str, dict] = {}
    visiting: set[str] = set()

    def resolve(wid: str) -> dict:
        if wid in resolved:
            return resolved[wid]
        if wid in visiting:
            raise ValueError(f"workflow `{wid}` 的 extends 链存在循环引用")
        if wid not in raw:
            raise ValueError(f"workflow `{wid}` 不存在（被 extends 引用）")
        visiting.add(wid)
        data = raw[wid]
        base_id = data.get("extends")
        if base_id:
            base = resolve(base_id)
            merged = _deep_merge(base, {k: v for k, v in data.items() if k != "extends"})
            # id / name / description / entry / terminal 子 workflow 优先
            merged["id"] = data["id"]
            merged.pop("extends", None)
        else:
            merged = copy.deepcopy(data)
        visiting.discard(wid)
        resolved[wid] = merged
        return merged

    for wid in raw:
        resolve(wid)
    return resolved


def load_raw_workflows(workflows_dir: Path) -> tuple[dict[str, dict], list[str]]:
    """加载未展开的 raw workflow。返回 (workflows_by_id, errors)。"""
    workflows: dict[str, dict] = {}
    errors: list[str] = []
    if not workflows_dir.is_dir():
        errors.append(f"workflows 目录不存在: {workflows_dir}")
        return workflows, errors
    for path in sorted(workflows_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{path}: YAML 解析失败 {exc}")
            continue
        if not isinstance(data, dict):
            errors.append(f"{path}: 根节点必须是 mapping")
            continue
        wid = data.get("id")
        if not wid:
            errors.append(f"{path}: 缺 id")
            continue
        if wid in workflows:
            errors.append(f"{path}: id `{wid}` 重复")
            continue
        workflows[wid] = data
    return workflows, errors


def load_workflows(workflows_dir: Path) -> tuple[dict[str, dict], list[str]]:
    """加载并展开 extends 的 workflows。返回 (resolved_by_id, errors)。"""
    raw, errors = load_raw_workflows(workflows_dir)
    try:
        resolved = _resolve_extends(raw)
    except ValueError as exc:
        errors.append(str(exc))
        return {}, errors
    return resolved, errors


def load_capabilities(agents_dir: Path) -> tuple[set[str], list[str]]:
    """扫描 agents 目录下的 md 文件以确定合法的 agent 列表。"""
    if not agents_dir.is_dir():
        return set(), [f"agents 目录不存在: {agents_dir}"]
    
    agents = set()
    for path in agents_dir.glob("*.md"):
        if path.name == "README.md":
            continue
        agents.add(path.stem)
    
    return agents, []


def collect_all_states(workflows: dict[str, dict]) -> set[str]:
    states: set[str] = {"blocked"}
    for wf in workflows.values():
        for step_name in (wf.get("steps") or {}).keys():
            states.add(step_name)
    return states


def collect_step_owners(step: dict) -> set[str]:
    owners: set[str] = set()
    if step.get("owner") and step["owner"] != "current_agent":
        owners.add(step["owner"])
    for o in step.get("owners") or []:
        owners.add(o)
    return owners


def outputs_for_state(workflows: dict[str, dict], state: str) -> list[str]:
    """该 state 在任一 workflow 中声明的 outputs 的并集（保持顺序，去重）。"""
    seen: dict[str, None] = {}
    for wf in workflows.values():
        step = (wf.get("steps") or {}).get(state)
        if not step:
            continue
        for out in step.get("outputs") or []:
            seen.setdefault(out, None)
    return list(seen.keys())


# transitions 中表示"回滚到上游"的 verdict——计算 cumulative 时不走这些边，
# 否则 may-analysis 会把下游 outputs 污染回 implementation。
BACK_EDGE_VERDICTS = {"changes_requested", "failed", "rejected", "back"}


def cumulative_outputs(workflow: dict) -> dict[str, list[str]]:
    """对单个 workflow 计算"进入 state s 时必有的 outputs"。

    语义：从 entry 出发，沿"正向"边（next + 非回滚 transitions）传播 step.outputs 的并集。
    s 自己的 outputs 不计入（进入 s 时尚未执行 s）。
    """
    steps = workflow.get("steps") or {}
    cumulative: dict[str, set[str]] = {s: set() for s in steps}
    changed = True
    while changed:
        changed = False
        for s, step in steps.items():
            full = cumulative[s] | set(step.get("outputs") or [])
            successors: list[str] = []
            if step.get("next"):
                successors.append(step["next"])
            for verdict, v in (step.get("transitions") or {}).items():
                if verdict in BACK_EDGE_VERDICTS:
                    continue
                successors.append(v)
            for nxt in successors:
                if nxt not in cumulative:
                    continue
                merged = cumulative[nxt] | full
                if merged != cumulative[nxt]:
                    cumulative[nxt] = merged
                    changed = True
    return {s: sorted(v) for s, v in cumulative.items()}


def state_requirements(workflows: dict[str, dict]) -> dict[str, dict[str, list[str]]]:
    """所有 workflow 的 per-state 累积 outputs。返回 {wf_id: {state: [outputs]}}。"""
    return {wid: cumulative_outputs(wf) for wid, wf in workflows.items()}


def next_state(workflow: dict, state: str, verdict: str | None = None) -> str | None:
    """根据 workflow 定义计算从 state 经 verdict 流转到的下一 state。"""
    step = (workflow.get("steps") or {}).get(state) or {}
    trans = step.get("transitions") or {}
    if verdict and verdict in trans:
        return trans[verdict]
    nxt = step.get("next")
    if nxt:
        return nxt
    return None


def next_owner(workflow: dict, state: str) -> str | None:
    step = (workflow.get("steps") or {}).get(state) or {}
    if step.get("owner"):
        return step["owner"]
    owners = step.get("owners") or []
    return owners[0] if owners else None


def step_is_active(step: dict, depth: str) -> bool:
    """判断 step 在给定深度下是否激活。"""
    min_depth = step.get("min_depth", "quick")
    return DEPTH_RANK.get(depth, 0) >= DEPTH_RANK.get(min_depth, 0)


def active_steps(workflow: dict, depth: str) -> list[str]:
    """返回该深度下所有激活的 step 名称（按拓扑顺序）。"""
    steps = workflow.get("steps") or {}
    active: list[str] = []
    for name in steps:
        sd = steps[name] or {}
        if step_is_active(sd, depth):
            active.append(name)
    return active


def checkpoint_steps(workflow: dict, depth: str) -> list[str]:
    """返回该深度下所有人工卡点 step 名称。"""
    steps = workflow.get("steps") or {}
    checkpoints: list[str] = []
    for name in steps:
        sd = steps[name] or {}
        if step_is_active(sd, depth) and sd.get("checkpoint") is True:
            checkpoints.append(name)
    return checkpoints


def resolve_next_active(
    workflow: dict,
    state: str,
    depth: str,
    verdict: str | None = None,
) -> str | None:
    """从 state 出发，沿 next/transitions 链找到下一个激活的 step。

    如果下一步不活跃，继续沿链向前查找，直到找到活跃 step 或到达终点。
    """
    steps = workflow.get("steps") or {}
    visited: set[str] = set()
    current = state
    while True:
        nxt = next_state(workflow, current, verdict)
        if nxt is None:
            return None
        if nxt in visited:
            return None  # 防止无限循环
        visited.add(nxt)
        sd = steps.get(nxt) or {}
        if step_is_active(sd, depth):
            return nxt
        # 跳过不活跃 step，继续向前
        current = nxt
        verdict = None


def _cli_states(workflows: dict[str, dict]) -> int:
    for s in sorted(collect_all_states(workflows)):
        print(s)
    return 0


def _cli_owners(workflows_dir: Path) -> int:
    agents_dir = workflows_dir.parent / "agents"
    agents, _ = load_capabilities(agents_dir)
    for a in sorted(agents):
        print(a)
    return 0


def _cli_outputs(workflows: dict[str, dict], state: str) -> int:
    for out in outputs_for_state(workflows, state):
        print(out)
    return 0


def _cli_next(
    workflows: dict[str, dict], wf_id: str, state: str, verdict: str | None, depth: str | None = None
) -> int:
    if depth is None and verdict in VALID_DEPTHS:
        depth = verdict
        verdict = None

    wf = workflows.get(wf_id)
    if not wf:
        print(f"workflow `{wf_id}` 不存在", file=sys.stderr)
        return 2

    if depth:
        if depth not in VALID_DEPTHS:
            print(f"depth `{depth}` 不在有效值 {VALID_DEPTHS} 中", file=sys.stderr)
            return 2
        nxt = resolve_next_active(wf, state, depth, verdict)
    else:
        nxt = next_state(wf, state, verdict)

    if nxt is None:
        return 1
    step = (wf.get("steps") or {}).get(nxt) or {}
    result: dict[str, Any] = {"state": nxt}
    owner = step.get("owner")
    owners = step.get("owners")
    if owner:
        result["owner"] = owner
    if owners:
        result["owners"] = owners
        if not owner:
            result["owner"] = owners[0]
    if step.get("mode"):
        result["mode"] = step["mode"]
    if step.get("dynamic_owners"):
        result["dynamic_owners"] = True
    print(json.dumps(result, ensure_ascii=False))
    return 0


def _cli_show(workflows: dict[str, dict], wf_id: str) -> int:
    wf = workflows.get(wf_id)
    if not wf:
        print(f"workflow `{wf_id}` 不存在", file=sys.stderr)
        return 2
    print(json.dumps(wf, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Workflow Loader CLI")
    parser.add_argument("--root", type=Path, default=REPO_ROOT_DEFAULT)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("states")
    sub.add_parser("owners")
    p_out = sub.add_parser("outputs")
    p_out.add_argument("state")
    p_next = sub.add_parser("next")
    p_next.add_argument("workflow")
    p_next.add_argument("state")
    p_next.add_argument("verdict", nargs="?", default=None)
    p_next.add_argument("depth", nargs="?", default=None)
    p_show = sub.add_parser("show")
    p_show.add_argument("workflow")
    sub.add_parser("state-requirements")
    sub.add_parser("depths")
    p_active = sub.add_parser("active-steps")
    p_active.add_argument("workflow")
    p_active.add_argument("depth")
    p_check = sub.add_parser("checkpoints")
    p_check.add_argument("workflow")
    p_check.add_argument("depth")
    args = parser.parse_args(argv)

    workflows_dir = args.root.resolve() / ".ai" / "workflows"
    workflows, errors = load_workflows(workflows_dir)
    if errors:
        for e in errors:
            print(f"[WARN] {e}", file=sys.stderr)
    if args.cmd == "states":
        return _cli_states(workflows)
    if args.cmd == "owners":
        return _cli_owners(workflows_dir)
    if args.cmd == "outputs":
        return _cli_outputs(workflows, args.state)
    if args.cmd == "next":
        return _cli_next(workflows, args.workflow, args.state, args.verdict, args.depth)
    if args.cmd == "show":
        return _cli_show(workflows, args.workflow)
    if args.cmd == "state-requirements":
        print(json.dumps(state_requirements(workflows), ensure_ascii=False))
        return 0
    if args.cmd == "depths":
        for d in VALID_DEPTHS:
            print(d)
        return 0
    if args.cmd == "active-steps":
        wf = workflows.get(args.workflow)
        if not wf:
            print(f"workflow `{args.workflow}` 不存在", file=sys.stderr)
            return 2
        if args.depth not in VALID_DEPTHS:
            print(f"depth `{args.depth}` 不在有效值 {VALID_DEPTHS} 中", file=sys.stderr)
            return 2
        for s in active_steps(wf, args.depth):
            print(s)
        return 0
    if args.cmd == "checkpoints":
        wf = workflows.get(args.workflow)
        if not wf:
            print(f"workflow `{args.workflow}` 不存在", file=sys.stderr)
            return 2
        if args.depth not in VALID_DEPTHS:
            print(f"depth `{args.depth}` 不在有效值 {VALID_DEPTHS} 中", file=sys.stderr)
            return 2
        for s in checkpoint_steps(wf, args.depth):
            print(s)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
