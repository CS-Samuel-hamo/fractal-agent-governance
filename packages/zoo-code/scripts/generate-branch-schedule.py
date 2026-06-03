#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from task_board_common import branch_id, child_counts, clean_list, load_json, normalize_status, now, parent_id, resolve_run_dir, write_json


NON_EXECUTABLE = {"abandoned", "retained", "redo_needed", "paused", "needs_user_decision"}
HIGH_RISK = {"high", "critical"}
SENSITIVE = {"security", "auth", "payment", "pii", "migration"}


def ensure_resource_locks(run: Path, run_id: str) -> dict:
    path = run / "resource-locks.json"
    if not path.exists():
        script = Path(__file__).with_name("generate-resource-locks.py")
        subprocess.run([sys.executable, str(script), "--run-id", run_id, "--run-dir", str(run)], check=True)
    return load_json(path, {"resources": []})


def branches(run: Path) -> list[dict]:
    board = load_json(run / "task-board.json", {})
    if board.get("tasks"):
        return board["tasks"]
    state = load_json(run / "branch-state.json", {"branches": []})
    return state.get("branches", [])


def resources_by_branch(locks: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for resource in locks.get("resources", []):
        rid = resource.get("resource_id")
        for bid in set(resource.get("providers", []) + resource.get("consumers", []) + clean_list(resource.get("owner_branch"))):
            if bid:
                out.setdefault(bid, set()).add(rid)
    return out


def branch_denials(branch: dict, children: dict[str, int]) -> list[str]:
    reasons = []
    bid = branch_id(branch)
    status = normalize_status(branch.get("status"))
    if children.get(bid):
        reasons.append("branch_not_leaf")
    if status in NON_EXECUTABLE:
        reasons.append("branch_status_not_executable")
    if not clean_list(branch.get("owned_paths")):
        reasons.append("missing_worktree_isolation")
    if not clean_list(branch.get("acceptance_criteria")):
        reasons.append("missing_acceptance_criteria")
    if not clean_list(branch.get("verification_plan")):
        reasons.append("missing_verification_plan")
    if str(branch.get("risk_level", "unknown")).lower() in HIGH_RISK:
        reasons.append("high_or_critical_risk")
    flags = {str(x).lower() for x in clean_list(branch.get("sensitive_flags") or branch.get("risk_tags"))}
    if flags & SENSITIVE:
        reasons.append("security_auth_payment_pii_migration")
    if str(branch.get("contract_status", "stable")).lower() not in {"stable", "approved", "locked", "declared", "not_required"}:
        reasons.append("provides_contract_unstable")
    return reasons


def resource_conflict(left: str, right: str, by_branch: dict[str, set[str]], locks: dict) -> list[str]:
    shared = by_branch.get(left, set()) & by_branch.get(right, set())
    blockers = []
    by_id = {x.get("resource_id"): x for x in locks.get("resources", [])}
    for rid in sorted(shared):
        resource = by_id.get(rid, {})
        if resource.get("lock_type") != "read_only":
            blockers.append(rid)
    return blockers


def has_pair_denial(denials: list[dict], left: str, right: str, reason: str) -> bool:
    pair = {left, right}
    for denial in denials:
        if set(denial.get("branches", [])) == pair and denial.get("reason") == reason:
            return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate branch-schedule.json with explicit parallel denials.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--approval-owner", default="agent-planner")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    ledger = load_json(run / "run-ledger.json", {})
    goal_id = ledger.get("goal_id", "unknown")
    items = branches(run)
    children = child_counts(items)
    locks = ensure_resource_locks(run, run_id)
    by_resource = resources_by_branch(locks)
    candidates = []
    serial = []
    denials = []
    for item in items:
        bid = branch_id(item)
        reasons = branch_denials(item, children)
        if reasons:
            serial.append({"branch_id": bid, "reason": ", ".join(reasons)})
            denials.append({
                "branches": [bid],
                "reason": ", ".join(reasons),
                "blocking_resources": [],
                "blocking_dependencies": clean_list(item.get("dependencies")),
                "how_to_make_parallel_safe": "make branch a low/medium-risk leaf with stable contracts, owned resources, acceptance criteria, verification plan, worktree isolation, and resource locks",
            })
        else:
            candidates.append(item)
    groups = []
    used: set[str] = set()
    for i, left in enumerate(candidates):
        lid = branch_id(left)
        if lid in used:
            continue
        group = [lid]
        used.add(lid)
        for right in candidates[i + 1:]:
            rid = branch_id(right)
            if rid in used:
                continue
            conflict = resource_conflict(lid, rid, by_resource, locks)
            if conflict:
                denials.append({
                    "branches": [lid, rid],
                    "reason": "resource_lock_conflict",
                    "blocking_resources": conflict,
                    "blocking_dependencies": [],
                    "how_to_make_parallel_safe": "serialize these branches or split/approve shared resource ownership at parent aggregation",
                })
                continue
            group.append(rid)
            used.add(rid)
        if len(group) > 1:
            groups.append({
                "group_id": f"parallel-{len(groups)+1:03d}",
                "branches": group,
                "reason": "leaf branches with non-conflicting resource locks",
                "required_worktrees": group,
                "resource_locks": sorted(set().union(*(by_resource.get(x, set()) for x in group))),
                "risk_level": "low_or_medium",
                "approved_by": args.approval_owner,
            })
        else:
            serial.append({"branch_id": lid, "reason": "no safe parallel sibling found"})
    parallel_relevant = [
        item for item in items
        if not children.get(branch_id(item)) and normalize_status(item.get("status")) not in NON_EXECUTABLE
    ]
    for i, left in enumerate(parallel_relevant):
        lid = branch_id(left)
        for right in parallel_relevant[i + 1:]:
            rid = branch_id(right)
            conflict = resource_conflict(lid, rid, by_resource, locks)
            if conflict and not has_pair_denial(denials, lid, rid, "resource_lock_conflict"):
                denials.append({
                    "branches": [lid, rid],
                    "reason": "resource_lock_conflict",
                    "blocking_resources": conflict,
                    "blocking_dependencies": [],
                    "how_to_make_parallel_safe": "serialize these branches or split/approve shared resource ownership at parent aggregation",
                })
    schedule = {
        "schema_version": "1.1",
        "run_id": run_id,
        "goal_id": goal_id,
        "generated_at": now(),
        "parallel_candidates": [branch_id(x) for x in candidates],
        "parallel_groups": groups,
        "serial_branches": serial,
        "parallel_denials": denials,
        "requires_gpt_approval": True,
        "direct_parallel_merge_allowed": False,
        "requires_merge_queue": True,
        "branches": [
            {
                "branch_id": branch_id(x),
                "parent_branch_id": parent_id(x),
                "status": normalize_status(x.get("status")),
                "owned_paths": clean_list(x.get("owned_paths")),
                "shared_paths": clean_list(x.get("shared_paths")),
                "provides": clean_list(x.get("provides")),
                "consumes": clean_list(x.get("consumes")),
                "acceptance_criteria": clean_list(x.get("acceptance_criteria")),
                "verification_plan": clean_list(x.get("verification_plan")),
                "risk_level": str(x.get("risk_level", "unknown")).lower(),
                "execution_mode": "parallel" if any(branch_id(x) in g["branches"] for g in groups) else "serial_or_not_scheduled",
                "parallel_denial_reasons": [d for d in denials if branch_id(x) in d.get("branches", [])],
            }
            for x in items
        ],
    }
    write_json(run / "branch-schedule.json", schedule)
    print(json.dumps({"status": "pass", "run_id": run_id, "parallel_groups": groups, "parallel_denials": denials, "output": str(run / "branch-schedule.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
