#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path, run_id: str) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {"schema_version": "1.0", "run_id": run_id, "branches": [], "updated_at": now()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or plan a branch worktree and update worktree-map.json.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--git-branch", required=True)
    parser.add_argument("--worktree-path", required=True)
    parser.add_argument("--base-branch", default="HEAD")
    parser.add_argument("--owned-path", action="append", default=[])
    parser.add_argument("--shared-path", action="append", default=[])
    parser.add_argument("--checkpoint-ref", action="append", default=[])
    parser.add_argument("--create", action="store_true", help="Run git worktree add. Default only records planned map.")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "worktree-map.json"
    target = Path(args.worktree_path).expanduser()
    status = "planned"
    command = ["git", "worktree", "add", "-b", args.git_branch, str(target), args.base_branch]
    if args.create:
        if target.exists():
            print(json.dumps({"status": "fail", "error": "worktree_path_exists", "path": str(target)}, indent=2))
            return 2
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if result.returncode != 0:
            print(json.dumps({"status": "fail", "error": "git_worktree_add_failed", "output": result.stdout}, indent=2))
            return 2
        status = "created"
    data = load(path, args.run_id)
    entry = {
        "branch_id": args.branch_id,
        "git_branch": args.git_branch,
        "worktree_path": str(target),
        "base_branch": args.base_branch,
        "status": status,
        "owned_paths": args.owned_path,
        "shared_paths": args.shared_path,
        "checkpoint_refs": args.checkpoint_ref,
        "merge_queue_item": "",
        "updated_at": now(),
    }
    data["branches"] = [x for x in data.get("branches", []) if x.get("branch_id") != args.branch_id]
    data["branches"].append(entry)
    data["updated_at"] = now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "worktree_map": str(path), "entry": entry, "command": command if not args.create else []}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
