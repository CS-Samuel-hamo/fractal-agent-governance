#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Record Zoo Code checkpoint reference as rollback evidence.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--state", required=True)
    parser.add_argument("--checkpoint-ref", default="unknown")
    parser.add_argument("--worktree-path", default="")
    parser.add_argument("--git-diff-stat", default="unknown")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--note", default="checkpoint available in Zoo Code UI if exposed")
    parser.add_argument("--output")
    args = parser.parse_args()
    target = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "checkpoint-refs.json"
    data = json.loads(target.read_text(encoding="utf-8-sig")) if target.exists() else {"run_id": args.run_id, "checkpoints": []}
    entry = {
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": "agent-orchestrator",
        "model": "unknown",
        "created_at": now(),
        "input_artifacts": [],
        "output_artifacts": ["checkpoint_ref"],
        "gate_status": "pass" if args.checkpoint_ref != "unknown" else "unknown",
        "state": args.state,
        "checkpoint_ref": args.checkpoint_ref,
        "worktree_path": args.worktree_path,
        "git_diff_stat": args.git_diff_stat,
        "changed_files": args.changed_file,
        "note": args.note,
    }
    data["checkpoints"].append(entry)
    data["updated_at"] = now()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "path": str(target), "entry": entry}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
