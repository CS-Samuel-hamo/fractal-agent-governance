#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--state", default="intake")
    parser.add_argument("--active-branch", default="root")
    parser.add_argument("--completed-branch", action="append", default=[])
    parser.add_argument("--blocked-branch", action="append", default=[])
    parser.add_argument("--next-state", action="append", default=[])
    parser.add_argument("--blocker", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--required-human-action", action="append", default=[])
    parser.add_argument("--owner-mode", default="agent-orchestrator")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    path = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "status.json"
    status = {
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "current_state": args.state,
        "active_branch": args.active_branch,
        "completed_branches": args.completed_branch,
        "blocked_branches": args.blocked_branch,
        "next_allowed_states": args.next_state or ["project_profile", "obligation_discovery", "planning", "quality_gate", "review", "integration"],
        "owner_mode": args.owner_mode,
        "last_updated": now(),
        "blockers": args.blocker,
        "risks": args.risk,
        "required_human_actions": args.required_human_action,
    }
    text = json.dumps(status, indent=2)
    if not args.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
