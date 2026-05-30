#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

QUALITY = {"unknown": 0, "fail": 1, "warnings": 2, "pass": 3}
RISK = {"unknown": 0, "critical": 1, "high": 2, "medium": 3, "low": 4, "closed": 5}
ROLLBACK = {"hard": 0, "moderate": 1, "easy": 2}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {"history": []}


def classify(prev: dict, cur: dict) -> str:
    if not prev:
        return "improved"
    improved = False
    regressed = False
    comparisons = [
        (cur["goal_coverage"], prev.get("goal_coverage", cur["goal_coverage"]), "higher"),
        (cur["unknown_count"], prev.get("unknown_count", cur["unknown_count"]), "lower"),
        (RISK.get(cur["risk"], 0), RISK.get(prev.get("risk", cur["risk"]), 0), "higher"),
        (QUALITY.get(cur["quality"], 0), QUALITY.get(prev.get("quality", cur["quality"]), 0), "higher"),
        (cur["integration_cost"], prev.get("integration_cost", cur["integration_cost"]), "lower"),
        (ROLLBACK.get(cur["rollback_ease"], 0), ROLLBACK.get(prev.get("rollback_ease", cur["rollback_ease"]), 0), "higher"),
        (cur["required_obligations_open"], prev.get("required_obligations_open", cur["required_obligations_open"]), "lower"),
    ]
    for current, previous, direction in comparisons:
        if direction == "higher":
            improved = improved or current > previous
            regressed = regressed or current < previous
        else:
            improved = improved or current < previous
            regressed = regressed or current > previous
    if regressed:
        return "regressing"
    return "improved" if improved else "stalled"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check adaptive governance feedback convergence.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--goal-coverage", type=float, required=True)
    parser.add_argument("--unknown-count", type=int, required=True)
    parser.add_argument("--risk", choices=sorted(RISK), default="unknown")
    parser.add_argument("--quality", choices=sorted(QUALITY), default="unknown")
    parser.add_argument("--integration-cost", type=float, default=0.0)
    parser.add_argument("--rollback-ease", choices=sorted(ROLLBACK), default="easy")
    parser.add_argument("--required-obligations-open", type=int, default=0)
    parser.add_argument("--output")
    parser.add_argument("--created-by-mode", default="agent-orchestrator")
    parser.add_argument("--model", default="GPT-5.5")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    target = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "feedback-convergence.json"
    data = load(target)
    history = data.get("history", [])
    current = {
        "at": now(),
        "goal_coverage": args.goal_coverage,
        "unknown_count": args.unknown_count,
        "risk": args.risk,
        "quality": args.quality,
        "integration_cost": args.integration_cost,
        "rollback_ease": args.rollback_ease,
        "required_obligations_open": args.required_obligations_open,
    }
    status = classify(history[-1] if history else {}, current)
    stalled_count = (data.get("stalled_count", 0) + 1) if status == "stalled" else 0
    regressing_count = (data.get("regressing_count", 0) + 1) if status == "regressing" else 0
    next_action = "continue"
    gate_status = "pass"
    if stalled_count >= 2:
        next_action = "escalate"
        gate_status = "fail"
    if status == "regressing":
        next_action = "stop_or_fallback_or_redesign"
        gate_status = "fail"
    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.created_by_mode,
        "model": args.model,
        "created_at": data.get("created_at", current["at"]),
        "updated_at": current["at"],
        "input_artifacts": [],
        "output_artifacts": ["feedback-convergence"],
        "gate_status": gate_status,
        "convergence_status": status,
        "stalled_count": stalled_count,
        "regressing_count": regressing_count,
        "next_allowed_action": next_action,
        "history": history + [current],
    }
    if not args.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if gate_status == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
