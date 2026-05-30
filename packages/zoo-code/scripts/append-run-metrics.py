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
    parser.add_argument("--task-type", default="unknown")
    parser.add_argument("--model-route", default="hybrid-gpt-deepseek")
    parser.add_argument("--final-status", default="unknown")
    parser.add_argument("--output", default=".zoo-agent/metrics/run-metrics.jsonl")
    parser.add_argument("--quality-gate-status", default="unknown")
    parser.add_argument("--review-verdict", default="unknown")
    parser.add_argument("--fallback-used", action="store_true")
    parser.add_argument("--escalation-used", action="store_true")
    parser.add_argument("--human-gate-used", action="store_true")
    args = parser.parse_args()
    row = {
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "task_type": args.task_type,
        "model_route": args.model_route,
        "fractal_depth": 0,
        "branch_count": 1,
        "obligation_count": 0,
        "required_obligation_closed_count": 0,
        "deferred_obligation_count": 0,
        "escalated_obligation_count": 0,
        "quality_gate_status": args.quality_gate_status,
        "review_verdict": args.review_verdict,
        "rework_loops": 0,
        "escalation_used": args.escalation_used,
        "fallback_used": args.fallback_used,
        "human_gate_used": args.human_gate_used,
        "open_risks": 0,
        "final_status": args.final_status,
        "estimated_gpt_calls": 0,
        "estimated_deepseek_calls": 0,
        "created_at": now(),
        "completed_at": now(),
    }
    out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    print(json.dumps({"status": "pass", "output": str(out), "row": row}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
