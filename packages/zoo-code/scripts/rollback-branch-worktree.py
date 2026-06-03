#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TARGET_STATES = {"needs_decomposition", "fallback", "abandoned", "aborted"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif ch in {"-", "_", "."}:
            out.append("-")
    return "".join(out).strip("-") or "branch"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_dir(args: argparse.Namespace) -> Path:
    return Path(args.run_dir) if args.run_dir else Path(".zoo-agent") / "runs" / args.run_id


def branch_entry(data: dict, branch_id: str) -> dict:
    for item in data.get("branches", []):
        if item.get("branch_id") == branch_id:
            return item
    return {}


def queue_entries(data: dict, branch_id: str) -> list[dict]:
    return [item for item in data.get("queue", []) if item.get("branch_id") == branch_id]


def checkpoint_refs(worktree_entry: dict, ledger_branch: dict) -> list[str]:
    refs = []
    refs.extend(worktree_entry.get("checkpoint_refs", []))
    if ledger_branch.get("checkpoint_ref"):
        refs.append(ledger_branch["checkpoint_ref"])
    return sorted({str(x) for x in refs if str(x).strip()})


def add_graph_artifact(graph: dict, path: str, run_id: str, goal_id: str, branch_id: str, status: str) -> None:
    artifact_id = f"rollback_plan:{path}"
    graph.setdefault("artifacts", [])
    graph["artifacts"] = [
        item for item in graph["artifacts"]
        if not (isinstance(item, dict) and item.get("artifact_id") == artifact_id)
    ]
    graph["artifacts"].append({
        "artifact_id": artifact_id,
        "type": "rollback_plan",
        "path": path,
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": branch_id,
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "input_artifacts": ["run-ledger", "worktree-map", "merge-queue"],
        "output_artifacts": [path],
        "gate_status": status,
    })
    graph["updated_at"] = now()


def update_ledger(ledger: dict, branch_id: str, path: str, target_state: str, reason: str) -> None:
    ts = now()
    for branch in ledger.get("branches", []):
        if branch.get("branch_id") == branch_id:
            branch["state"] = target_state
            branch["rollback_status"] = "planned"
            branch["rollback_plan"] = path
            branch["rollback_reason"] = reason
            branch["merge_queue_status"] = "blocked_rollback_required"
            branch["updated_at"] = ts
    ledger.setdefault("transitions", []).append({
        "at": ts,
        "from": ledger.get("current_state", "planned"),
        "to": target_state,
        "run_id": ledger.get("run_id", "unknown"),
        "goal_id": ledger.get("goal_id", "unknown"),
        "branch_id": branch_id,
        "created_by_mode": "agent-orchestrator",
        "owner_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "input_artifacts": ["run-ledger", "worktree-map", "merge-queue"],
        "output_artifacts": [path],
        "gate_status": "blocked",
        "decision": "rollback_or_redecomposition_planned",
        "reason": reason,
    })
    ledger["updated_at"] = ts


def update_merge_queue(merge_queue: dict, branch_id: str, target_state: str, reason: str, path: str) -> None:
    ts = now()
    for item in merge_queue.get("queue", []):
        if item.get("branch_id") == branch_id:
            item["status"] = f"blocked_{target_state}"
            item["rollback_plan"] = path
            item["rollback_reason"] = reason
            item["direct_merge_allowed"] = False
            item["updated_at"] = ts
    merge_queue.setdefault("rejected", []).append({
        "branch_id": branch_id,
        "status": f"blocked_{target_state}",
        "reason": reason,
        "rollback_plan": path,
        "created_at": ts,
    })
    merge_queue["updated_at"] = ts


def main() -> int:
    parser = argparse.ArgumentParser(description="Record non-destructive rollback/redecomposition plan for a branch worktree.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--target-state", choices=sorted(TARGET_STATES), default="needs_decomposition")
    parser.add_argument("--run-dir")
    parser.add_argument("--next-action", default="re-run branch-manager from parent objective")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = run_dir(args)
    ledger = load_json(base / "run-ledger.json", {"run_id": args.run_id, "goal_id": "unknown", "branches": [], "transitions": []})
    worktrees = load_json(base / "worktree-map.json", {"branches": []})
    merge_queue = load_json(base / "merge-queue.json", {"queue": [], "rejected": []})
    graph = load_json(base / "artifact-graph.json", {"run_id": args.run_id, "goal_id": ledger.get("goal_id", "unknown"), "artifacts": [], "edges": []})
    wt = branch_entry(worktrees, args.branch_id)
    ledger_branch = branch_entry(ledger, args.branch_id)
    refs = checkpoint_refs(wt, ledger_branch)
    goal_id = ledger.get("goal_id", graph.get("goal_id", "unknown"))
    plan_path = str(base / "branches" / slug(args.branch_id) / "rollback-plan.json")
    queue_state = queue_entries(merge_queue, args.branch_id)
    plan = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": "agent-orchestrator",
        "model": "GPT-5.5",
        "created_at": now(),
        "status": "planned",
        "target_state": args.target_state,
        "reason": args.reason,
        "worktree_path": wt.get("worktree_path", ledger_branch.get("worktree_path", "")),
        "git_branch": wt.get("git_branch", ""),
        "checkpoint_refs": refs,
        "rollback_available": bool(refs),
        "merge_queue_entries": queue_state,
        "filesystem_action_executed": False,
        "destructive_git_command_executed": False,
        "required_human_or_runtime_actions": [
            "restore the recorded Zoo Code checkpoint or discard the isolated worktree changes",
            "keep the branch out of serial merge queue until parent aggregation is recomputed",
            "ask GPT branch-manager to re-scope, split, serialize, or fallback from the parent objective",
        ],
        "next_action": args.next_action,
    }

    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0

    write_json(Path(plan_path), plan)
    update_ledger(ledger, args.branch_id, plan_path, args.target_state, args.reason)
    update_merge_queue(merge_queue, args.branch_id, args.target_state, args.reason, plan_path)
    add_graph_artifact(graph, plan_path, args.run_id, goal_id, args.branch_id, "blocked")
    write_json(base / "run-ledger.json", ledger)
    write_json(base / "merge-queue.json", merge_queue)
    write_json(base / "artifact-graph.json", graph)
    print(json.dumps({"status": "planned", "path": plan_path, "target_state": args.target_state, "rollback_available": bool(refs)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
