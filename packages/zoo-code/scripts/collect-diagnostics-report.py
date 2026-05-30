#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Write diagnostics-report.json from available IDE diagnostics counts.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--before-errors", type=int)
    parser.add_argument("--before-warnings", type=int)
    parser.add_argument("--after-errors", type=int)
    parser.add_argument("--after-warnings", type=int)
    parser.add_argument("--new-error", action="append", default=[])
    parser.add_argument("--new-warning", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    unknown = any(x is None for x in [args.before_errors, args.before_warnings, args.after_errors, args.after_warnings])
    before = {"error_count": args.before_errors or 0, "warning_count": args.before_warnings or 0}
    after = {"error_count": args.after_errors or 0, "warning_count": args.after_warnings or 0}
    new_error_count = len(args.new_error) if args.new_error else max(0, after["error_count"] - before["error_count"])
    new_warning_count = len(args.new_warning) if args.new_warning else max(0, after["warning_count"] - before["warning_count"])
    status = "unknown" if unknown else ("fail" if new_error_count > 0 else ("warning" if new_warning_count > 0 else "pass"))
    report = {
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": "agent-executor",
        "model": "unknown",
        "created_at": now(),
        "input_artifacts": [],
        "output_artifacts": ["diagnostics-report"],
        "gate_status": status,
        "before": before,
        "after": after,
        "new_errors": args.new_error,
        "new_warnings": args.new_warning,
        "status": status,
    }
    target = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "diagnostics-report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if status in {"pass", "warning", "unknown"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
