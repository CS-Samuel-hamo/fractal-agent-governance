#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = ["branch_id", "git_branch", "worktree_path", "base_branch", "status", "owned_paths", "shared_paths", "checkpoint_refs", "merge_queue_item"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate worktree-map.json.")
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "worktree-map.json"
    issues = []
    data = {}
    if not path.exists():
        issues.append({"severity": "blocker", "issue": "missing_worktree_map", "path": str(path)})
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        seen = set()
        for item in data.get("branches", []):
            missing = [f for f in REQUIRED if f not in item]
            if missing:
                issues.append({"branch_id": item.get("branch_id", "unknown"), "severity": "blocker", "issue": "missing_fields", "fields": missing})
            bid = item.get("branch_id")
            if bid in seen:
                issues.append({"branch_id": bid, "severity": "blocker", "issue": "duplicate_branch_id"})
            seen.add(bid)
            if item.get("status") in {"created", "active", "review", "queued"} and not Path(str(item.get("worktree_path", ""))).exists():
                issues.append({"branch_id": bid, "severity": "blocker", "issue": "active_worktree_path_missing", "path": item.get("worktree_path")})
    status = "pass" if not any(i.get("severity") == "blocker" for i in issues) else "fail"
    report = {"status": status, "path": str(path), "branch_count": len(data.get("branches", [])) if data else 0, "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
