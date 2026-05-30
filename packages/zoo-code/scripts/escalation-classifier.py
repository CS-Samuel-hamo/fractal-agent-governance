#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

REASONS = [
    "requirement_conflict",
    "architecture_unknown",
    "data_source_unknown",
    "test_strategy_unknown",
    "security_or_auth_risk",
    "migration_risk",
    "quality_gate_repeated_fail",
    "review_loop_exhausted",
    "decomposition_depth_exceeded",
    "dependency_blocked",
    "obligation_unresolved",
    "cost_budget_exceeded",
    "human_decision_required",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an escalation record.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", default="unknown")
    parser.add_argument("--reason", required=True, choices=REASONS)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--created-by-mode", default="unknown")
    parser.add_argument("--created-by-model", default="unknown")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    escalation_id = f"esc-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{args.reason}"
    data = {
        "escalation_id": escalation_id,
        "run_id": args.run_id,
        "branch_id": args.branch_id,
        "reason": args.reason,
        "summary": args.summary,
        "status": "open",
        "created_by_mode": args.created_by_mode,
        "created_by_model": args.created_by_model,
        "closure_policy": "DeepSeek must not close escalation; GPT or human required",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    out = Path(".zoo-agent") / "escalations" / f"{escalation_id}.json"
    text = json.dumps(data, indent=2)
    if args.dry_run:
        print(text)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "path": str(out), "escalation_id": escalation_id}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
