#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


RESOLVED = {"merged", "abandoned", "archived"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan or perform safe worktree cleanup from worktree-map.json.")
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--branch-id", action="append", default=[])
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "worktree-map.json"
    if not path.exists():
        print(json.dumps({"status": "fail", "error": "missing_worktree_map", "path": str(path)}, indent=2))
        return 2
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    actions = []
    issues = []
    selected = set(args.branch_id)
    for item in data.get("branches", []):
        if selected and item.get("branch_id") not in selected:
            continue
        if item.get("status") not in RESOLVED:
            issues.append({"branch_id": item.get("branch_id"), "issue": "status_not_resolved", "status": item.get("status")})
            continue
        if not item.get("checkpoint_refs"):
            issues.append({"branch_id": item.get("branch_id"), "issue": "missing_checkpoint_ref"})
            continue
        worktree = item.get("worktree_path")
        actions.append({"branch_id": item.get("branch_id"), "command": ["git", "worktree", "remove", worktree], "worktree_path": worktree})
    if args.execute and not issues:
        for action in actions:
            result = subprocess.run(action["command"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            action["returncode"] = result.returncode
            action["output"] = result.stdout
            if result.returncode != 0:
                issues.append({"branch_id": action["branch_id"], "issue": "git_worktree_remove_failed"})
                break
    status = "pass" if not issues else "fail"
    print(json.dumps({"status": status, "dry_run": not args.execute, "actions": actions, "issues": issues}, indent=2))
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
