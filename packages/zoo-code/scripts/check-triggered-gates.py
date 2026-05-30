#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

TRIGGERS = {
    "adr": {"public_api", "shared_type", "new_dependency", "architecture_boundary", "migration", "proc_data_source_strategy"},
    "security": {"auth", "permission", "pii", "payment", "credential", "external_network", "production_config"},
    "release": {"public_behavior_change", "migration", "feature_flag", "breaking_change"},
    "ops": {"backend", "api", "job", "database", "integration", "retry", "idempotency", "logging", "metrics", "alerting"},
    "curator": {"repeated_failure", "blocker", "major", "failure_recurrence", "rule_drift", "skill_drift"},
    "eval": {"governance_package_upgrade", "new_skill", "new_rule", "model_routing_change", "benchmark", "demo"},
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    return {}


def normalize(values: list[str]) -> set[str]:
    result = set()
    for value in values:
        for part in value.replace(",", " ").split():
            result.add(part.strip().lower().replace("-", "_"))
    return {x for x in result if x}


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute triggered governance gates for a run.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--intensity-file")
    parser.add_argument("--signal", action="append", default=[])
    parser.add_argument("--output")
    parser.add_argument("--created-by-mode", default="agent-orchestrator")
    parser.add_argument("--model", default="GPT-5.5")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base = Path(".zoo-agent") / "runs" / args.run_id
    intensity_path = Path(args.intensity_file) if args.intensity_file else base / "governance-intensity.json"
    intensity = load(intensity_path)
    signals = normalize(args.signal)
    for item in intensity.get("rationale", []):
        signals |= normalize([str(item)])
    if intensity.get("level", 0) >= 4:
        signals.add("high_risk_level")
    gate_results = {}
    triggered = []
    for gate, gate_signals in TRIGGERS.items():
        hits = sorted(signals & gate_signals)
        status = "triggered" if hits else "not_triggered"
        if gate == "security" and "high_risk_level" in signals:
            status = "triggered"
            hits.append("high_risk_level")
        gate_results[gate] = {"status": status, "signals": sorted(set(hits))}
        if status == "triggered":
            triggered.append(gate)
    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.created_by_mode,
        "model": args.model,
        "created_at": now(),
        "input_artifacts": [str(intensity_path)] if intensity_path.exists() else [],
        "output_artifacts": ["triggered-gates"],
        "gate_status": "pass",
        "signals": sorted(signals),
        "triggered_gates": triggered,
        "gates": gate_results,
    }
    target = Path(args.output) if args.output else base / "triggered-gates.json"
    if not args.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
