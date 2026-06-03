#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from task_board_common import load_json, now, resolve_run_dir, write_json


EXECUTABLE_STATUSES = {"planned", "active", "blocked", "needs_review", "done"}


def ensure_locks(run: Path, run_id: str) -> Path:
    path = run / "resource-locks.json"
    if not path.exists():
        script = Path(__file__).with_name("generate-resource-locks.py")
        subprocess.run([sys.executable, str(script), "--run-id", run_id, "--run-dir", str(run)], check=True)
    return path


def branch_statuses(run: Path) -> dict[str, str]:
    state = load_json(run / "branch-state.json", {"branches": []})
    return {item.get("branch_id"): str(item.get("status", "planned")).lower() for item in state.get("branches", [])}


def check(run: Path, run_id: str) -> dict:
    locks = load_json(ensure_locks(run, run_id), {"resources": []})
    statuses = branch_statuses(run)
    issues = []
    warnings = []
    for resource in locks.get("resources", []):
        owners = set(resource.get("providers", []))
        if resource.get("owner_branch"):
            owners.add(resource["owner_branch"])
        executable_owners = sorted([x for x in owners if statuses.get(x, "planned") in EXECUTABLE_STATUSES])
        consumers = sorted([x for x in resource.get("consumers", []) if statuses.get(x, "planned") in EXECUTABLE_STATUSES])
        if resource.get("lock_type") == "exclusive" and len(executable_owners) > 1:
            issues.append({"severity": "blocker", "type": "exclusive_resource_multi_owner", "resource_id": resource.get("resource_id"), "owners": executable_owners})
        if resource.get("lock_type") == "shared_requires_parent_approval" and len(set(executable_owners + consumers)) > 1:
            issues.append({"severity": "blocker", "type": "semantic_resource_conflict", "resource_id": resource.get("resource_id"), "branches": sorted(set(executable_owners + consumers)), "required_action": "parent approval or serialize branches"})
        if resource.get("status") == "unknown" and resource.get("lock_type") != "read_only":
            issues.append({"severity": "blocker", "type": "resource_status_unknown", "resource_id": resource.get("resource_id")})
        if resource.get("risk_level") in {"high", "critical"} and resource.get("lock_type") != "read_only":
            warnings.append({"severity": "warning", "type": "high_risk_resource_lock", "resource_id": resource.get("resource_id")})
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at": now(),
        "status": "fail" if issues else "pass",
        "issues": issues,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check path and semantic resource locks before parallel execution or resume.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    report = check(run, run_id)
    out = Path(args.output) if args.output else run / "resource-lock-check.json"
    write_json(out, report)
    print(json.dumps({"status": report["status"], "run_id": run_id, "output": str(out), "issues": report["issues"]}, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
