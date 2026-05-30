#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    return "run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize a Zoo Agent run ledger and artifact graph.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--created-by-mode", default="agent-orchestrator")
    parser.add_argument("--model", default="GPT-5.5")
    args = parser.parse_args()

    run_id = args.run_id or new_run_id()
    run_dir = Path(".zoo-agent") / "runs" / run_id
    ts = now()
    ledger = {
        "schema_version": "2.0",
        "run_id": run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.created_by_mode,
        "model": args.model,
        "created_at": ts,
        "updated_at": ts,
        "current_state": "intake",
        "allowed_next_states": ["goal_bound", "blocked"],
        "input_artifacts": [],
        "output_artifacts": ["artifact-graph"],
        "gate_status": "not_applicable",
        "transitions": [],
    }
    graph = {
        "schema_version": "2.0",
        "run_id": run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.created_by_mode,
        "model": args.model,
        "created_at": ts,
        "updated_at": ts,
        "input_artifacts": [],
        "output_artifacts": [],
        "gate_status": "not_applicable",
        "artifacts": [],
        "edges": [],
    }
    if args.dry_run:
        print(json.dumps({"status": "dry-run", "run_dir": str(run_dir), "run_ledger": ledger, "artifact_graph": graph}, indent=2))
        return 0
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run-ledger.json").write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    (run_dir / "artifact-graph.json").write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "run_id": run_id, "goal_id": args.goal_id, "run_dir": str(run_dir)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
