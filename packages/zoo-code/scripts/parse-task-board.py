#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_board_common import (
    branch_state_map,
    load_json,
    normalize_status,
    now,
    parse_task_docs,
    parse_tasks_md,
    resolve_run_dir,
    task_board_map,
    write_json,
)


def worktree_for(worktree_map: dict, branch_id: str) -> str:
    for item in worktree_map.get("branches", []):
        if item.get("branch_id") == branch_id:
            return str(item.get("worktree_path") or "")
    return ""


def build_proposed(run: Path, run_id: str) -> dict:
    parsed = parse_tasks_md(run / "TASKS.md")
    docs = parse_task_docs(run)
    old_board = load_json(run / "task-board.json", {})
    branch_state = load_json(run / "branch-state.json", {"branches": []})
    worktree_map = load_json(run / "worktree-map.json", {"branches": []})
    ledger = load_json(run / "run-ledger.json", {})
    old_by_id = task_board_map(old_board)
    state_by_id = branch_state_map(branch_state)
    tasks = []
    for doc_name, info in docs.items():
        bid = info["branch_id"]
        state = state_by_id.get(bid, {})
        old = old_by_id.get(bid, {})
        proposed = parsed["tree_statuses"].get(doc_name) or info.get("user_override") or state.get("status") or old.get("status") or "planned"
        row = dict(old)
        row.update(info)
        row.update({
            "branch_id": bid,
            "parent_branch_id": info.get("parent_branch_id") or state.get("parent_branch_id") or old.get("parent_branch_id") or "",
            "title": info.get("title") or state.get("title") or old.get("title") or bid,
            "previous_status": normalize_status(state.get("status") or old.get("status") or info.get("status") or "planned"),
            "status": normalize_status(proposed),
            "worktree_path": info.get("worktree_path") or state.get("worktree_path") or old.get("worktree_path") or worktree_for(worktree_map, bid),
            "owned_paths": info.get("owned_paths") or state.get("owned_paths") or old.get("owned_paths") or [],
            "shared_paths": info.get("shared_paths") or state.get("shared_paths") or old.get("shared_paths") or [],
            "provides": info.get("provides") or state.get("provides") or old.get("provides") or [],
            "consumes": info.get("consumes") or state.get("consumes") or old.get("consumes") or [],
            "acceptance_criteria": info.get("acceptance_criteria") or state.get("acceptance_criteria") or old.get("acceptance_criteria") or [],
            "verification_plan": info.get("verification_plan") or state.get("verification_plan") or old.get("verification_plan") or [],
            "risk_level": str(info.get("risk_level") or state.get("risk_level") or old.get("risk_level") or "unknown").lower(),
            "evidence": info.get("evidence") or state.get("evidence") or old.get("completion_evidence") or "pending",
        })
        tasks.append(row)
    goal_id = str(ledger.get("goal_id") or old_board.get("goal_id") or "unknown")
    return {
        "schema_version": "1.1",
        "run_id": run_id,
        "goal_id": goal_id,
        "source": "TASKS.md",
        "created_at": now(),
        "current_user_intent": parsed["current_user_intent"],
        "user_control": parsed["user_control"],
        "tasks": tasks,
        "parse_only": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse TASKS.md and tasks/*.md into task-board.proposed.json without mutating runtime state.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    proposed = build_proposed(run, run_id)
    out = Path(args.output) if args.output else run / "task-board.proposed.json"
    write_json(out, proposed)
    print(json.dumps({"status": "pass", "run_id": run_id, "output": str(out), "task_count": len(proposed["tasks"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
