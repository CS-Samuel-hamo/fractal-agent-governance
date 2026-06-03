#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

SENSITIVE = {"security", "auth", "authorization", "payment", "pii", "migration", "credentials", "production_config"}
HIGH_RISK = {"high", "critical"}
GPT_APPROVERS = {"agent-orchestrator", "agent-planner"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def norm(pattern: str) -> str:
    return pattern.replace("\\", "/").strip("/").rstrip("*")


def overlap(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    return bool(a and b and (a == b or a.startswith(b) or b.startswith(a)))


def branch_map(schedule: dict) -> dict[str, dict]:
    return {b.get("branch_id"): b for b in schedule.get("branches", []) if b.get("branch_id")}


def group_branches(schedule: dict, branches: dict[str, dict]) -> list[tuple[str, list[dict]]]:
    groups = []
    for group in schedule.get("parallel_groups", []):
        ids = group.get("branches", [])
        groups.append((group.get("group_id", "unknown"), [branches[i] for i in ids if i in branches]))
    return groups


def check_group(group_id: str, items: list[dict]) -> list[dict]:
    issues = []
    if len(items) <= 1:
        return issues
    for b in items:
        bid = b.get("branch_id", "unknown")
        if str(b.get("risk_level", "unknown")).lower() in HIGH_RISK:
            issues.append({"group_id": group_id, "branch_id": bid, "severity": "blocker", "issue": "high_or_critical_risk_for_parallel"})
        if SENSITIVE & {str(x).lower() for x in b.get("sensitive_flags", [])}:
            issues.append({"group_id": group_id, "branch_id": bid, "severity": "blocker", "issue": "sensitive_work_for_parallel"})
        for field in ["acceptance_criteria", "verification_plan", "owned_paths"]:
            if not b.get(field):
                issues.append({"group_id": group_id, "branch_id": bid, "severity": "blocker", "issue": f"missing_{field}"})
        if not b.get("worktree"):
            issues.append({"group_id": group_id, "branch_id": bid, "severity": "blocker", "issue": "missing_worktree_isolation"})
        if b.get("dependencies"):
            same_group = set(b.get("dependencies", [])) & {x.get("branch_id") for x in items}
            if same_group:
                issues.append({"group_id": group_id, "branch_id": bid, "severity": "blocker", "issue": "depends_on_parallel_sibling", "dependencies": sorted(same_group)})
    for i, left in enumerate(items):
        for right in items[i + 1:]:
            left_shared = set(left.get("shared_paths", []))
            right_shared = set(right.get("shared_paths", []))
            for a in left.get("owned_paths", []):
                for b in right.get("owned_paths", []):
                    if overlap(a, b):
                        shared_ok = any(overlap(a, s) or overlap(b, s) for s in left_shared & right_shared)
                        issues.append({"group_id": group_id, "left": left.get("branch_id"), "right": right.get("branch_id"), "severity": "blocker" if not shared_ok else "major", "issue": "owned_paths_overlap", "path_a": a, "path_b": b, "shared_declared": shared_ok})
    return issues


def check_group_approval(schedule: dict) -> list[dict]:
    issues = []
    for group in schedule.get("parallel_groups", []):
        group_id = group.get("group_id", "unknown")
        owner = group.get("decision_owner") or schedule.get("parallel_allowed_by")
        if owner not in GPT_APPROVERS:
            issues.append({"group_id": group_id, "severity": "blocker", "issue": "parallel_group_not_gpt_approved", "decision_owner": owner})
        if group.get("approval_status", "approved") != "approved":
            issues.append({"group_id": group_id, "severity": "blocker", "issue": "parallel_group_approval_missing"})
        if group.get("requires_worktree") is not True:
            issues.append({"group_id": group_id, "severity": "blocker", "issue": "parallel_group_missing_worktree_requirement"})
        if group.get("requires_checkpoint_before_execution") is not True:
            issues.append({"group_id": group_id, "severity": "blocker", "issue": "parallel_group_missing_checkpoint_requirement"})
    if schedule.get("direct_parallel_merge_allowed") is True:
        issues.append({"severity": "blocker", "issue": "direct_parallel_merge_allowed"})
    if schedule.get("requires_merge_queue") is False:
        issues.append({"severity": "blocker", "issue": "merge_queue_not_required"})
    return issues


def check_provides_consumes(schedule: dict, branches: dict[str, dict]) -> list[dict]:
    issues = []
    provided = {item for b in branches.values() for item in b.get("provides", [])}
    for b in branches.values():
        missing = [c for c in b.get("consumes", []) if c not in provided and c not in b.get("dependencies", [])]
        if missing:
            issues.append({"branch_id": b.get("branch_id"), "severity": "major", "issue": "consumes_not_provided", "items": missing})
        if (b.get("provides") or b.get("consumes")) and b.get("contracts_stable") is False:
            issues.append({"branch_id": b.get("branch_id"), "severity": "blocker", "issue": "provides_consumes_not_stable"})
    return issues


def resource_branches(resource_locks: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for resource in resource_locks.get("resources", []):
        rid = resource.get("resource_id")
        if not rid:
            continue
        branches = set(resource.get("providers", []) + resource.get("consumers", []))
        if resource.get("owner_branch"):
            branches.add(resource.get("owner_branch"))
        for bid in branches:
            out.setdefault(bid, set()).add(rid)
    return out


def check_resource_locks(schedule: dict, resource_locks: dict) -> list[dict]:
    if not resource_locks:
        return [{"severity": "blocker", "issue": "missing_resource_locks"}]
    by_branch = resource_branches(resource_locks)
    by_id = {x.get("resource_id"): x for x in resource_locks.get("resources", [])}
    issues = []
    for group in schedule.get("parallel_groups", []):
        ids = group.get("branches", [])
        for bid in ids:
            if not by_branch.get(bid):
                issues.append({
                    "group_id": group.get("group_id", "unknown"),
                    "branch_id": bid,
                    "severity": "blocker",
                    "issue": "branch_missing_resource_lock",
                })
        for i, left in enumerate(ids):
            for right in ids[i + 1:]:
                shared = by_branch.get(left, set()) & by_branch.get(right, set())
                for rid in sorted(shared):
                    resource = by_id.get(rid, {})
                    if resource.get("lock_type") != "read_only":
                        issues.append({
                            "group_id": group.get("group_id", "unknown"),
                            "left": left,
                            "right": right,
                            "severity": "blocker",
                            "issue": "resource_lock_conflict",
                            "resource_id": rid,
                            "resource_type": resource.get("type", "unknown"),
                        })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether branch schedule is safe for parallel execution.")
    parser.add_argument("--run-id")
    parser.add_argument("--schedule")
    parser.add_argument("--path-locks")
    parser.add_argument("--resource-locks")
    parser.add_argument("--output")
    args = parser.parse_args()
    schedule_path = Path(args.schedule) if args.schedule else Path(".zoo-agent") / "runs" / (args.run_id or "") / "branch-schedule.json"
    locks_path = Path(args.path_locks) if args.path_locks else Path(".zoo-agent") / "runs" / (args.run_id or "") / "path-locks.json"
    resource_locks_path = Path(args.resource_locks) if args.resource_locks else Path(".zoo-agent") / "runs" / (args.run_id or "") / "resource-locks.json"
    issues = []
    schedule = load(schedule_path)
    if not schedule:
        issues.append({"severity": "blocker", "issue": "missing_branch_schedule", "path": str(schedule_path)})
    branches = branch_map(schedule)
    issues.extend(check_group_approval(schedule))
    for group_id, items in group_branches(schedule, branches):
        issues.extend(check_group(group_id, items))
    issues.extend(check_provides_consumes(schedule, branches))
    issues.extend(check_resource_locks(schedule, load(resource_locks_path)))
    if not locks_path.exists():
        issues.append({"severity": "blocker", "issue": "missing_path_locks", "path": str(locks_path)})
    else:
        locks = load(locks_path)
        lock_branches = {x.get("branch_id") for x in locks.get("locks", [])}
        for bid in branches:
            if bid not in lock_branches:
                issues.append({"branch_id": bid, "severity": "blocker", "issue": "branch_missing_path_lock"})
    status = "pass" if not any(i.get("severity") == "blocker" for i in issues) else "fail"
    report = {"status": status, "schedule": str(schedule_path), "path_locks": str(locks_path), "resource_locks": str(resource_locks_path), "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
