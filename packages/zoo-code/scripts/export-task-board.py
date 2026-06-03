#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DONE = {"done", "completed", "merged", "integrated", "final_reported", "retained"}
BLOCKED = {"blocked", "needs_decomposition", "needs_user_decision", "fail", "failed"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def latest_run_dir() -> Path | None:
    root = Path(".zoo-agent") / "runs"
    if not root.exists():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir()]
    return sorted(dirs, key=lambda p: p.stat().st_mtime)[-1] if dirs else None


def run_dir(run_id: str | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id
    latest = latest_run_dir()
    return latest if latest else Path(".zoo-agent") / "runs" / "run-unknown"


def project_root_for_run(run: Path) -> Path:
    resolved = run.resolve()
    if resolved.parent.name == "runs" and resolved.parent.parent.name == ".zoo-agent":
        return resolved.parent.parent.parent
    return Path.cwd().resolve()


def write_current_run(project: Path, run: Path, run_id: str, goal_id: str) -> None:
    zoo = project / ".zoo-agent"
    write_json(zoo / "current-run.json", {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "run_dir": str(run),
        "project_task_board": ".zoo-agent/TASKS.md",
        "run_task_board": str(run / "TASKS.md"),
        "task_board_json": str(run / "task-board.json"),
        "branch_state": str(run / "branch-state.json"),
        "updated_at": now(),
    })


def sync_project_task_board(project: Path, run: Path) -> None:
    run_tasks = run / "TASKS.md"
    project_tasks = project / ".zoo-agent" / "TASKS.md"
    if not run_tasks.exists():
        return
    project_tasks.parent.mkdir(parents=True, exist_ok=True)
    if not project_tasks.exists() or project_tasks.stat().st_mtime <= run_tasks.stat().st_mtime:
        shutil.copy2(run_tasks, project_tasks)


def slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", ".", " "}:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-") or "branch"


def clean_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x).strip()]
    return [str(value)] if str(value).strip() else []


def branch_id(item: dict) -> str:
    return str(item.get("branch_id") or item.get("id") or item.get("title") or "root")


def title(item: dict) -> str:
    return str(item.get("title") or item.get("name") or branch_id(item))


def parent_id(item: dict) -> str:
    return str(item.get("parent_branch_id") or item.get("parent_id") or "")


def flatten_progress(nodes: list[dict]) -> list[dict]:
    out: list[dict] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        copied = dict(node)
        copied.pop("children", None)
        out.append(copied)
        out.extend(flatten_progress(node.get("children", [])))
    return out


def source_branches(run: Path) -> list[dict]:
    progress = load_json(run / "progress.json", {})
    branch_state = load_json(run / "branch-state.json", {})
    schedule = load_json(run / "branch-schedule.json", {})
    ledger = load_json(run / "run-ledger.json", {})
    merged: dict[str, dict] = {}
    sources: list[list[dict]] = []
    if isinstance(progress.get("tree"), list):
        sources.append(flatten_progress(progress["tree"]))
    for data in [branch_state, schedule, ledger]:
        value = data.get("branches") if isinstance(data, dict) else []
        if isinstance(value, list):
            sources.append([x for x in value if isinstance(x, dict)])
    if not sources and ledger:
        sources.append([{
            "branch_id": ledger.get("branch_id", "root"),
            "title": ledger.get("goal_summary", "Root"),
            "status": ledger.get("current_state", "unknown"),
            "parent_branch_id": "",
        }])
    for source in sources:
        for item in source:
            bid = branch_id(item)
            row = merged.setdefault(bid, {"branch_id": bid})
            row.update({k: v for k, v in item.items() if v not in (None, "", [])})
    return list(merged.values())


def worktree_for(worktree_map: dict, bid: str) -> str:
    for item in worktree_map.get("branches", []):
        if item.get("branch_id") == bid:
            return str(item.get("worktree_path", ""))
    return ""


def existing_override(task_path: Path) -> str:
    if not task_path.exists():
        return ""
    text = task_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(?mi)^-\s*user_override:\s*(.+?)\s*$", text)
    if match:
        return match.group(1).strip()
    return ""


def normalize_status(status: str) -> str:
    text = str(status or "planned").strip().lower()
    aliases = {
        "retain": "retained",
        "redo": "redo_needed",
        "drop": "abandoned",
        "abandon": "abandoned",
        "active": "active",
        "executing": "active",
        "complete": "done",
        "completed": "done",
    }
    return aliases.get(text, text)


def board_status(branch: dict) -> str:
    override = normalize_status(str(branch.get("user_override", "")))
    if override:
        return override
    return normalize_status(str(branch.get("status") or branch.get("state") or "planned"))


def depth(branches: list[dict], bid: str, seen: set[str] | None = None) -> int:
    seen = seen or set()
    if bid in seen:
        return 0
    seen.add(bid)
    by_id = {branch_id(b): b for b in branches}
    parent = parent_id(by_id.get(bid, {}))
    if not parent or parent not in by_id:
        return 0
    return 1 + depth(branches, parent, seen)


def active_path(branches: list[dict], active: str) -> list[str]:
    by_id = {branch_id(b): b for b in branches}
    out: list[str] = []
    cur = active
    seen: set[str] = set()
    while cur and cur not in seen:
        seen.add(cur)
        out.append(cur)
        cur = parent_id(by_id.get(cur, {}))
    return list(reversed(out))


def branch_doc(run: Path, branch: dict, worktree_map: dict) -> Path:
    return run / "tasks" / f"{slug(branch_id(branch))}.md"


def list_md(values: list[str]) -> str:
    return "\n".join(f"- {x}" for x in values) if values else "- none"


def render_branch_doc(run: Path, branch: dict, worktree_map: dict) -> str:
    bid = branch_id(branch)
    status = board_status(branch)
    branch_override = normalize_status(str(branch.get("user_override", "")))
    override = branch_override or existing_override(branch_doc(run, branch, worktree_map)) or status
    worktree = str(branch.get("worktree_path") or branch.get("worktree") or worktree_for(worktree_map, bid))
    owned = clean_list(branch.get("owned_paths"))
    shared = clean_list(branch.get("shared_paths"))
    provides = clean_list(branch.get("provides"))
    consumes = clean_list(branch.get("consumes"))
    acceptance = clean_list(branch.get("acceptance_criteria"))
    verification = clean_list(branch.get("verification_plan"))
    evidence = str(branch.get("evidence") or "pending")
    return f"""# {title(branch)}

- branch_id: {bid}
- parent_branch_id: {parent_id(branch)}
- status: {status}
- user_override: {override}
- branch_type: {branch.get("branch_type") or branch.get("type") or ("root" if not parent_id(branch) else "task")}
- risk: {branch.get("risk") or branch.get("risk_level") or "unknown"}
- quality_gate: {branch.get("quality_gate") or branch.get("quality_gate_status") or "unknown"}
- evidence: {evidence}
- worktree_path: {worktree}

## Objective
{branch.get("purpose") or branch.get("summary") or title(branch)}

## Owned Paths
{list_md(owned)}

## Shared Paths
{list_md(shared)}

## Provides
{list_md(provides)}

## Consumes
{list_md(consumes)}

## Acceptance Criteria
{list_md(acceptance)}

## Verification Plan
{list_md(verification)}

## User Override
Set `user_override` above to one of: active, retained, abandoned, redo_needed, paused, blocked, needs_user_decision, done.

## Evidence Notes
{evidence}
"""


def render_tree_lines(branches: list[dict]) -> list[str]:
    by_parent: dict[str, list[dict]] = {}
    for branch in branches:
        by_parent.setdefault(parent_id(branch), []).append(branch)
    roots = by_parent.get("", []) or [b for b in branches if not parent_id(b)] or branches[:1]
    lines: list[str] = []

    def walk(branch: dict, level: int) -> None:
        bid = branch_id(branch)
        marker = board_status(branch)
        rel = f"tasks/{slug(bid)}.md"
        lines.append(f"{'  ' * level}- [{marker}] {title(branch)} -> {rel}")
        for child in sorted(by_parent.get(bid, []), key=lambda x: title(x).lower()):
            if branch_id(child) != bid:
                walk(child, level + 1)

    for root in sorted(roots, key=lambda x: title(x).lower()):
        walk(root, 0)
    return lines


def render_tasks_md(run_id: str, goal_id: str, branches: list[dict], active: str, parallel: str, next_mode: str, direction: str) -> str:
    path = active_path(branches, active)
    return "\n".join([
        "# Agent Task Board",
        "",
        "<!-- Edit bracket statuses or User Control values, then run apply-task-board.py. Do not edit runtime JSON by hand. -->",
        "",
        "## Run",
        f"- run_id: {run_id}",
        f"- goal_id: {goal_id}",
        "",
        "## Current User Intent",
        "- 当前最重要目标: review current run state",
        "- 明确不要做: do not continue stale plans, do not merge, do not delete worktrees",
        "- 当前优先级: preserve valid evidence, block unsafe work, ask when intent conflicts",
        f"- 并发策略: {parallel}",
        "- 允许保留的成果: branches marked retained with evidence",
        "- 必须废弃的方向: branches marked abandoned",
        f"- 当前 governance intensity: {next_mode}",
        "- 当前 redirect status: unchanged",
        "",
        "## Current Active Path",
        " > ".join(path) if path else active,
        "",
        "## User Control",
        f"- parallel: {parallel}",
        f"- next_mode: {next_mode}",
        f"- focus: {active}",
        f"- direction: {direction}",
        "",
        "## Tree",
        *render_tree_lines(branches),
        "",
        "## Allowed Status Markers",
        "- active",
        "- retained",
        "- abandoned",
        "- redo_needed",
        "- paused",
        "- blocked",
        "- needs_user_decision",
        "- done",
        "",
        "## Resume Command",
        f"`/agent-run continue run {run_id} using TASKS.md`",
        "",
    ]) + "\n"


def update_artifact_graph(run: Path, run_id: str, goal_id: str) -> None:
    graph_path = run / "artifact-graph.json"
    graph = load_json(graph_path, {"run_id": run_id, "goal_id": goal_id, "artifacts": [], "edges": []})
    project = project_root_for_run(run)
    paths = [
        str(project / ".zoo-agent" / "TASKS.md"),
        str(project / ".zoo-agent" / "current-run.json"),
        str(run / "TASKS.md"),
        str(run / "task-board.json"),
        str(run / "branch-state.json"),
    ]
    graph.update({
        "run_id": run_id,
        "goal_id": goal_id,
        "created_by_mode": graph.get("created_by_mode") or "agent-orchestrator",
        "model": graph.get("model") or "unknown",
        "created_at": graph.get("created_at") or now(),
        "input_artifacts": graph.get("input_artifacts") or ["branch-state", "run-ledger", "project-task-board"],
        "output_artifacts": graph.get("output_artifacts") or paths,
        "gate_status": graph.get("gate_status") or "not_applicable",
    })
    graph["artifacts"] = [
        item for item in graph.get("artifacts", [])
        if not (isinstance(item, dict) and item.get("type") in {"project_task_board", "current_run", "task_board", "task_node", "branch_state"})
    ]
    artifact_specs = [
        ("project_task_board", str(project / ".zoo-agent" / "TASKS.md"), "root"),
        ("current_run", str(project / ".zoo-agent" / "current-run.json"), "root"),
        ("task_board", str(run / "TASKS.md"), "root"),
        ("task_board", str(run / "task-board.json"), "root"),
        ("branch_state", str(run / "branch-state.json"), "root"),
    ]
    for artifact_type, p, branch in artifact_specs:
        if not Path(p).exists():
            continue
        graph.setdefault("artifacts", []).append({
            "artifact_id": f"{artifact_type}:{p}",
            "type": artifact_type,
            "path": p,
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": branch,
            "created_by_mode": "agent-orchestrator",
            "model": "unknown",
            "created_at": now(),
            "input_artifacts": ["branch-state", "run-ledger", "branch-schedule", "worktree-map", "merge-queue"],
            "output_artifacts": paths,
            "gate_status": "not_applicable",
        })
    for task_file in sorted((run / "tasks").glob("*.md")):
        graph.setdefault("artifacts", []).append({
            "artifact_id": f"task_node:{task_file}",
            "type": "task_node",
            "path": str(task_file),
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": task_file.stem,
            "created_by_mode": "agent-orchestrator",
            "model": "unknown",
            "created_at": now(),
            "input_artifacts": ["task-board"],
            "output_artifacts": [str(task_file)],
            "gate_status": "not_applicable",
        })
    graph["updated_at"] = now()
    write_json(graph_path, graph)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export run artifacts to human-editable TASKS.md and tasks/<branch>.md files.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--parallel", default="unchanged")
    parser.add_argument("--next-mode", default="unchanged")
    parser.add_argument("--direction", default="review current task board")
    args = parser.parse_args()
    run = run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    ledger = load_json(run / "run-ledger.json", {})
    progress = load_json(run / "progress.json", {})
    worktree_map = load_json(run / "worktree-map.json", {})
    branches = source_branches(run)
    if not branches:
        print(json.dumps({"status": "fail", "error": "no_branches_found", "run_dir": str(run)}, indent=2))
        return 2
    goal_id = str(ledger.get("goal_id") or progress.get("goal_id") or "unknown")
    active = str(progress.get("current_branch") or ledger.get("branch_id") or branch_id(branches[0]))
    task_rows = []
    for branch in branches:
        bid = branch_id(branch)
        doc_path = branch_doc(run, branch, worktree_map)
        doc_text = render_branch_doc(run, branch, worktree_map)
        doc_path.parent.mkdir(parents=True, exist_ok=True)
        doc_path.write_text(doc_text, encoding="utf-8")
        task_rows.append({
            "branch_id": bid,
            "parent_branch_id": parent_id(branch),
            "title": title(branch),
            "status": board_status(branch),
            "task_doc": str(doc_path),
            "depth": depth(branches, bid),
            "worktree_path": str(branch.get("worktree_path") or worktree_for(worktree_map, bid)),
            "risk": str(branch.get("risk") or branch.get("risk_level") or "unknown"),
            "risk_level": str(branch.get("risk_level") or branch.get("risk") or "unknown"),
            "owned_paths": clean_list(branch.get("owned_paths")),
            "shared_paths": clean_list(branch.get("shared_paths")),
            "provides": clean_list(branch.get("provides")),
            "consumes": clean_list(branch.get("consumes")),
            "acceptance_criteria": clean_list(branch.get("acceptance_criteria")),
            "verification_plan": clean_list(branch.get("verification_plan")),
            "contract_status": str(branch.get("contract_status") or branch.get("provides_consumes_status") or "unknown"),
            "quality_gate": str(branch.get("quality_gate") or branch.get("quality_gate_status") or "unknown"),
            "completion_evidence": str(branch.get("evidence") or branch.get("completion_evidence") or "pending"),
        })
    board = {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "created_at": now(),
        "active_path": active_path(branches, active),
        "user_control": {
            "parallel": args.parallel,
            "next_mode": args.next_mode,
            "focus": active,
            "direction": args.direction,
        },
        "tasks": task_rows,
    }
    tasks_path = run / "TASKS.md"
    board_path = run / "task-board.json"
    preserve_user_tasks = tasks_path.exists() and board_path.exists() and tasks_path.stat().st_mtime > board_path.stat().st_mtime
    if not preserve_user_tasks:
        tasks_path.write_text(render_tasks_md(run_id, goal_id, branches, active, args.parallel, args.next_mode, args.direction), encoding="utf-8")
    write_json(board_path, board)
    project = project_root_for_run(run)
    write_current_run(project, run, run_id, goal_id)
    sync_project_task_board(project, run)
    update_artifact_graph(run, run_id, goal_id)
    print(json.dumps({
        "status": "pass",
        "run_id": run_id,
        "project_tasks_md": str(project / ".zoo-agent" / "TASKS.md"),
        "tasks_md": str(run / "TASKS.md"),
        "task_board": str(run / "task-board.json"),
        "task_count": len(task_rows),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
