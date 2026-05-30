#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:48] or "goal"


def values(items: list[str] | None) -> list[str]:
    return items if items else ["unknown"]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .zoo-agent/goals/<goal-id>.json.")
    parser.add_argument("--goal-id")
    parser.add_argument("--run-id", default="unknown")
    parser.add_argument("--root-goal", required=True)
    parser.add_argument("--user-intent", default="unknown")
    parser.add_argument("--business-outcome", default="unknown")
    parser.add_argument("--technical-outcome", default="unknown")
    parser.add_argument("--non-goal", action="append")
    parser.add_argument("--assumption", action="append")
    parser.add_argument("--constraint", action="append")
    parser.add_argument("--success-criteria", action="append")
    parser.add_argument("--failure-criteria", action="append")
    parser.add_argument("--abort-condition", action="append")
    parser.add_argument("--risk-tolerance", default="unknown")
    parser.add_argument("--quality-bar", default="unknown")
    parser.add_argument("--max-depth", type=int, default=3)
    parser.add_argument("--max-loop-budget", type=int, default=2)
    parser.add_argument("--human-gate-required", action="store_true")
    parser.add_argument("--fallback-policy", default="fallback ladder required when stalled twice, regressing once, or over budget")
    parser.add_argument("--owner", default="agent-orchestrator")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    goal_id = args.goal_id or f"goal-{slug(args.root_goal)}"
    ts = now()
    out = Path(".zoo-agent") / "goals" / f"{goal_id}.json"
    existing = {}
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    data = {
        "goal_id": goal_id,
        "run_id": args.run_id,
        "root_goal": args.root_goal,
        "user_intent": args.user_intent,
        "business_outcome": args.business_outcome,
        "technical_outcome": args.technical_outcome,
        "non_goals": values(args.non_goal),
        "assumptions": values(args.assumption),
        "constraints": values(args.constraint),
        "success_criteria": values(args.success_criteria),
        "failure_criteria": values(args.failure_criteria),
        "abort_conditions": values(args.abort_condition),
        "risk_tolerance": args.risk_tolerance,
        "quality_bar": args.quality_bar,
        "max_depth": args.max_depth,
        "max_loop_budget": args.max_loop_budget,
        "human_gate_required": bool(args.human_gate_required),
        "fallback_policy": args.fallback_policy,
        "owner": args.owner,
        "created_at": existing.get("created_at", ts),
        "updated_at": ts,
    }
    text = json.dumps(data, indent=2)
    if args.dry_run:
        print(text)
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "goal_id": goal_id, "path": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
