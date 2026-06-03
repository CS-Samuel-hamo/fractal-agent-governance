#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_board_common import branch_id, clean_list, load_json, normalize_status, now, resolve_run_dir, slug, write_json


RESOURCE_TYPES = [
    ("proc_data_source", ["proc", "processor", "data-source", "data source", "source selector"]),
    ("dto_schema", ["dto", "schema", "validator", "mapper", "type", "enum"]),
    ("api_contract", ["api", "route", "endpoint", "contract", "command"]),
    ("database_table", ["table", "database", "migration"]),
    ("event", ["event", "handler"]),
    ("queue", ["queue", "topic", "stream"]),
    ("feature_flag", ["feature flag", "flag"]),
    ("test_fixture", ["fixture", "snapshot", "golden", "mock"]),
    ("release_note", ["release", "changelog"]),
    ("config", ["config", "env var", "environment variable"]),
]


def infer_type(name: str, fallback: str = "unknown") -> str:
    low = name.lower()
    for typ, needles in RESOURCE_TYPES:
        if any(x in low for x in needles):
            return typ
    return fallback


def load_branches(run: Path) -> list[dict]:
    board = load_json(run / "task-board.json", {})
    if board.get("tasks"):
        return board["tasks"]
    branch_state = load_json(run / "branch-state.json", {})
    if branch_state.get("branches"):
        return branch_state["branches"]
    branch_schedule = load_json(run / "branch-schedule.json", {})
    if branch_schedule.get("branches"):
        return branch_schedule["branches"]
    path_locks = load_json(run / "path-locks.json", {})
    if path_locks.get("locks"):
        return path_locks["locks"]
    run_ledger = load_json(run / "run-ledger.json", {})
    return run_ledger.get("branches", [])


def add_resource(resources: dict[str, dict], name: str, typ: str, branch: dict, lock_type: str, status: str = "stable") -> None:
    bid = branch_id(branch)
    rid = f"{typ}:{slug(name)}"
    item = resources.setdefault(rid, {
        "resource_id": rid,
        "type": typ,
        "name": name,
        "owner_branch": bid,
        "lock_type": lock_type,
        "consumers": [],
        "providers": [],
        "status": status,
        "risk_level": str(branch.get("risk_level") or branch.get("risk") or "unknown").lower(),
        "notes": "",
    })
    if lock_type == "exclusive" and item.get("owner_branch") != bid:
        item.setdefault("conflicting_owners", sorted({item.get("owner_branch"), bid}))
        item["lock_type"] = "shared_requires_parent_approval"
        item["status"] = "changing"
    if lock_type != "exclusive":
        item["lock_type"] = "shared_requires_parent_approval"
    if bid not in item.get("providers", []):
        item.setdefault("providers", []).append(bid)


def build(run: Path, run_id: str) -> dict:
    ledger = load_json(run / "run-ledger.json", {})
    resources: dict[str, dict] = {}
    for branch in load_branches(run):
        status = normalize_status(branch.get("status"))
        if status in {"abandoned"}:
            continue
        for path in clean_list(branch.get("owned_paths")):
            add_resource(resources, path, "path", branch, "exclusive")
        for path in clean_list(branch.get("shared_paths")):
            add_resource(resources, path, "path", branch, "shared_requires_parent_approval")
        for provided in clean_list(branch.get("provides")):
            add_resource(resources, provided, infer_type(provided), branch, "exclusive", status=str(branch.get("contract_status", "stable")))
        for consumed in clean_list(branch.get("consumes")):
            rid = f"{infer_type(consumed)}:{slug(consumed)}"
            item = resources.setdefault(rid, {
                "resource_id": rid,
                "type": infer_type(consumed),
                "name": consumed,
                "owner_branch": "",
                "lock_type": "read_only",
                "consumers": [],
                "providers": [],
                "status": "unknown",
                "risk_level": str(branch.get("risk_level") or "unknown").lower(),
                "notes": "consumed resource; provider must be discovered or declared",
            })
            bid = branch_id(branch)
            if bid not in item["consumers"]:
                item["consumers"].append(bid)
    for item in resources.values():
        if item.get("providers") and item.get("consumers"):
            item["lock_type"] = "shared_requires_parent_approval"
        if item.get("conflicting_owners"):
            item["status"] = "changing"
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": ledger.get("goal_id", "unknown"),
        "created_at": now(),
        "resources": sorted(resources.values(), key=lambda x: x["resource_id"]),
        "path_locks_compatibility": "resource-locks enhances path-locks; path-locks may remain for file-only tools",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate resource-locks.json for path and semantic resources.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    locks = build(run, run_id)
    out = Path(args.output) if args.output else run / "resource-locks.json"
    write_json(out, locks)
    print(json.dumps({"status": "pass", "run_id": run_id, "output": str(out), "resource_count": len(locks["resources"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
