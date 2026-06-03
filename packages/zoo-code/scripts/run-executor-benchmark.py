#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an executor benchmark run record from eval case templates.")
    parser.add_argument("--case-dir", default="evals/executor-comparison")
    parser.add_argument("--executor", default="hybrid")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    cases = sorted(Path(args.case_dir).glob("*.yaml"))
    records = []
    for case in cases:
        records.append({
            "case": case.stem,
            "executor_used": args.executor,
            "wall_time": None,
            "tool_call_count": None,
            "changed_file_count": None,
            "scope_violation_count": None,
            "tests_pass": None,
            "quality_gate_pass": None,
            "review_blocker_count": None,
            "manual_intervention_count": None,
            "architecture_drift": None,
            "final_status": "template_only",
        })
    result = {"created_at": dt.datetime.now(dt.timezone.utc).isoformat(), "records": records}
    output = Path(args.output) if args.output else Path(".zoo-agent") / "executor-benchmark.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
