#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from task_board_common import (
    ALLOWED_STATUSES,
    branch_state_map,
    load_json,
    normalize_status,
    now,
    resolve_run_dir,
    stamp,
    write_json,
)


def run_script(name: str, args: list[str], allow_fail: bool = False) -> int:
    script = Path(__file__).with_name(name)
    result = subprocess.run([sys.executable, str(script), *args], text=True, check=False)
    if result.returncode != 0 and not allow_fail:
        raise SystemExit(result.returncode)
    return result.returncode


def project_root_for_run(run: Path) -> Path:
    resolved = run.resolve()
    if resolved.parent.name == "runs" and resolved.parent.parent.name == ".zoo-agent":
        return resolved.parent.parent.parent
    return Path.cwd().resolve()


def sync_project_task_board_to_run(run: Path) -> str:
    project = project_root_for_run(run)
    project_tasks = project / ".zoo-agent" / "TASKS.md"
    run_tasks = run / "TASKS.md"
    if project_tasks.exists() and (not run_tasks.exists() or project_tasks.stat().st_mtime > run_tasks.stat().st_mtime):
        run_tasks.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(project_tasks, run_tasks)
        return "project_to_run"
    if run_tasks.exists() and (not project_tasks.exists() or run_tasks.stat().st_mtime > project_tasks.stat().st_mtime):
        project_tasks.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(run_tasks, project_tasks)
        return "run_to_project"
    return "unchanged"


def write_current_run(run: Path, run_id: str, goal_id: str) -> None:
    project = project_root_for_run(run)
    write_json(project / ".zoo-agent" / "current-run.json", {
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


def ensure_parse_diff(run: Path, run_id: str) -> dict:
    run_script("parse-task-board.py", ["--run-id", run_id, "--run-dir", str(run)])
    code = run_script("diff-task-board.py", ["--run-id", run_id, "--run-dir", str(run)], allow_fail=True)
    diff = load_json(run / "task-board.diff.json", {})
    if code != 0 and (diff.get("invalid_transitions") or diff.get("required_user_decisions")):
        print(json.dumps({
            "status": "blocked",
            "reason": "invalid_transitions_or_required_decisions",
            "diff": str(run / "task-board.diff.md"),
            "invalid_transitions": diff.get("invalid_transitions", []),
            "required_user_decisions": diff.get("required_user_decisions", []),
        }, indent=2))
        raise SystemExit(2)
    return diff


def update_branch_state(run: Path, proposed: dict, run_id: str, goal_id: str) -> tuple[dict, list[dict]]:
    branch_state = load_json(run / "branch-state.json", {"branches": []})
    state_by_id = branch_state_map(branch_state)
    changed = []
    branch_state.setdefault("branches", [])
    for task in proposed.get("tasks", []):
        bid = task.get("branch_id")
        if not bid:
            continue
        item = state_by_id.get(bid)
        if not item:
            item = {"branch_id": bid, "parent_branch_id": task.get("parent_branch_id", ""), "title": task.get("title", bid)}
            branch_state["branches"].append(item)
            state_by_id[bid] = item
        previous = normalize_status(item.get("status") or task.get("previous_status") or "planned")
        status = normalize_status(task.get("status"))
        if status not in ALLOWED_STATUSES:
            status = "needs_user_decision"
        item.update({
            "status": status,
            "user_override": status,
            "task_doc": task.get("task_doc", ""),
            "owned_paths": task.get("owned_paths", item.get("owned_paths", [])),
            "shared_paths": task.get("shared_paths", item.get("shared_paths", [])),
            "provides": task.get("provides", item.get("provides", [])),
            "consumes": task.get("consumes", item.get("consumes", [])),
            "acceptance_criteria": task.get("acceptance_criteria", item.get("acceptance_criteria", [])),
            "verification_plan": task.get("verification_plan", item.get("verification_plan", [])),
            "risk_level": task.get("risk_level", item.get("risk_level", "unknown")),
            "evidence": task.get("evidence", item.get("evidence", "pending")),
            "updated_at": now(),
        })
        if previous != status:
            changed.append({"branch_id": bid, "from": previous, "to": status})
    branch_state.update({"schema_version": "1.1", "run_id": run_id, "goal_id": goal_id, "updated_at": now()})
    return branch_state, changed


def update_worktree_map(worktree_map: dict, status_by_branch: dict[str, str]) -> tuple[dict, list[dict]]:
    affected = []
    for item in worktree_map.get("branches", []):
        bid = item.get("branch_id")
        status = status_by_branch.get(bid)
        if not status:
            continue
        previous = item.get("status")
        if status in {"abandoned", "retained", "redo_needed", "paused"}:
            item["status"] = status
        if previous != item.get("status"):
            affected.append({"branch_id": bid, "from": previous, "to": item.get("status"), "worktree_path": item.get("worktree_path", "")})
        item["updated_at"] = now()
    worktree_map["updated_at"] = now()
    return worktree_map, affected


def update_merge_queue(queue: dict, status_by_branch: dict[str, str]) -> tuple[dict, list[dict]]:
    affected = []
    queue["direct_merge_allowed"] = False
    for item in queue.get("queue", []):
        bid = item.get("branch_id")
        status = status_by_branch.get(bid)
        if not status:
            continue
        previous = item.get("status")
        if status == "abandoned":
            item["status"] = "blocked_abandoned"
        elif status == "redo_needed":
            item["status"] = "blocked_redo_needed"
        elif status == "paused":
            item["status"] = "paused"
        elif status == "retained":
            item["status"] = "retained_for_parent_aggregation"
        if previous != item.get("status"):
            affected.append({"branch_id": bid, "from": previous, "to": item.get("status")})
        item["updated_at"] = now()
    if any(x["to"] in {"blocked_abandoned", "blocked_redo_needed", "paused"} for x in affected):
        queue["redirect_impact"] = "reorder_required"
    else:
        queue["redirect_impact"] = queue.get("redirect_impact", "unchanged")
    queue["updated_at"] = now()
    return queue, affected


def redirect_plan(run_id: str, goal_id: str, proposed: dict, status_by_branch: dict[str, str]) -> dict:
    intent = proposed.get("current_user_intent", {})
    return {
        "schema_version": "1.1",
        "redirect_plan_id": f"task-board-{stamp()}",
        "run_id": run_id,
        "goal_id": goal_id,
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "source": "TASKS.md",
        "current_user_intent": intent,
        "user_new_direction": intent.get("当前最重要目标") or proposed.get("user_control", {}).get("direction", "apply task board edits"),
        "keep": sorted([bid for bid, status in status_by_branch.items() if status == "retained"]),
        "drop_abandon": sorted([bid for bid, status in status_by_branch.items() if status == "abandoned"]),
        "redo_replan": sorted([bid for bid, status in status_by_branch.items() if status == "redo_needed"]),
        "needs_user_decision": sorted([bid for bid, status in status_by_branch.items() if status == "needs_user_decision"]),
        "resume_command": f"/agent-run continue run {run_id} using TASKS.md after resume-safety-check",
    }


def render_redirect_md(plan: dict) -> str:
    lines = ["# Redirect Plan", "", "## Current User Intent", ""]
    for k, v in plan.get("current_user_intent", {}).items():
        lines.append(f"- {k}: {v}")
    for title, key in [("Keep", "keep"), ("Drop / Abandon", "drop_abandon"), ("Redo / Replan", "redo_replan"), ("Needs User Decision", "needs_user_decision")]:
        lines.extend(["", f"## {title}", ""])
        lines.extend([f"- {x}" for x in plan.get(key, [])] or ["- none"])
    lines.extend(["", "## Resume Command", "", f"`{plan['resume_command']}`", ""])
    return "\n".join(lines)


def update_ledger(ledger: dict, run_id: str, goal_id: str, changed: list[dict], diff: dict) -> tuple[dict, str, str]:
    previous = ledger.get("current_state", "unknown")
    new_state = "resume_safety_check"
    ledger.update({
        "schema_version": ledger.get("schema_version", "1.1"),
        "run_id": ledger.get("run_id", run_id),
        "goal_id": ledger.get("goal_id", goal_id),
        "previous_state": previous,
        "current_state": new_state,
        "next_allowed_states": ["resume_ready", "resume_blocked"],
        "task_board": "TASKS.md",
        "task_board_diff": "task-board.diff.json",
        "updated_at": now(),
    })
    ledger.setdefault("transitions", []).append({
        "at": now(),
        "from": previous,
        "to": new_state,
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": "agent-orchestrator",
        "owner_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "input_artifacts": ["TASKS.md", "task-board.proposed.json", "task-board.diff.json"],
        "output_artifacts": ["task-board.json", "branch-state.json", "redirect-plan.json"],
        "gate_status": "not_applicable",
        "decision": "task_board_applied_requires_resume_safety_check",
        "changed_branches": changed,
        "stale_plan_warnings": diff.get("stale_plan_warnings", []),
    })
    return ledger, previous, new_state


def update_graph(run: Path, run_id: str, goal_id: str) -> None:
    graph = load_json(run / "artifact-graph.json", {"artifacts": [], "edges": []})
    artifact = {
        "artifact_id": f"task_board_apply:{stamp()}",
        "type": "task_board_apply",
        "path": str(run / "task-board.diff.json"),
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": "root",
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "input_artifacts": ["TASKS.md", "task-board.proposed.json"],
        "output_artifacts": ["task-board.json", "branch-state.json", "worktree-map.json", "merge-queue.json", "redirect-plan.json"],
        "gate_status": "not_applicable",
    }
    graph.setdefault("artifacts", []).append(artifact)
    graph["updated_at"] = now()
    write_json(run / "artifact-graph.json", graph)


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply task board through parse -> diff -> apply, then require resume-safety-check.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    task_board_sync = sync_project_task_board_to_run(run)
    diff = ensure_parse_diff(run, run_id)
    proposed = load_json(run / "task-board.proposed.json", {"tasks": []})
    ledger = load_json(run / "run-ledger.json", {"run_id": run_id, "goal_id": proposed.get("goal_id", "unknown"), "transitions": []})
    goal_id = str(ledger.get("goal_id") or proposed.get("goal_id") or "unknown")
    branch_state, changed = update_branch_state(run, proposed, run_id, goal_id)
    status_by_branch = {item.get("branch_id"): item.get("status") for item in branch_state.get("branches", [])}
    worktree_map, affected_worktrees = update_worktree_map(load_json(run / "worktree-map.json", {"branches": []}), status_by_branch)
    merge_queue, affected_queue = update_merge_queue(load_json(run / "merge-queue.json", {"queue": []}), status_by_branch)
    plan = redirect_plan(run_id, goal_id, proposed, status_by_branch)
    ledger, previous_state, new_state = update_ledger(ledger, run_id, goal_id, changed, diff)
    event = {
        "event_type": "task_board_apply",
        "run_id": run_id,
        "goal_id": goal_id,
        "created_at": now(),
        "previous_state": previous_state,
        "new_state": new_state,
        "changed_branches": changed,
        "affected_worktrees": affected_worktrees,
        "affected_merge_queue_items": affected_queue,
        "invalid_transitions_rejected": diff.get("invalid_transitions", []),
        "required_user_decisions": diff.get("required_user_decisions", []),
        "applied_by": "agent-orchestrator",
        "project_task_board_sync": task_board_sync,
    }
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "event": event, "redirect_plan": plan}, indent=2))
        return 0
    proposed["parse_only"] = False
    proposed["applied_at"] = now()
    write_json(run / "task-board.json", proposed)
    write_json(run / "branch-state.json", branch_state)
    write_json(run / "worktree-map.json", worktree_map)
    write_json(run / "merge-queue.json", merge_queue)
    write_json(run / "run-ledger.json", ledger)
    write_json(run / "redirect-plan.json", plan)
    (run / "redirect-plan.md").write_text(render_redirect_md(plan), encoding="utf-8")
    write_json(run / "events" / f"task-board-apply-{stamp()}.json", event)
    sync_project_task_board_to_run(run)
    write_current_run(run, run_id, goal_id)
    update_graph(run, run_id, goal_id)
    run_script("generate-progress-snapshot.py", ["--run-id", run_id, "--output-dir", str(run)], allow_fail=True)
    print(json.dumps({"status": "pass", "run_id": run_id, "next_required": "resume-safety-check", "redirect_plan": str(run / "redirect-plan.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
