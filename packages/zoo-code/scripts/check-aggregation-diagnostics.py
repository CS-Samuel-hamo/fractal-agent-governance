#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from task_board_common import load_json, now, resolve_run_dir, write_json


def diagnostics_fail(data: dict) -> tuple[bool, list[dict]]:
    issues = []
    if not data:
        issues.append({"severity": "blocker", "type": "missing_aggregation_diagnostics"})
    if data.get("status") == "fail":
        issues.append({"severity": "blocker", "type": "aggregation_diagnostics_failed"})
    for item in data.get("diagnostics", []) + data.get("new_errors", []):
        if isinstance(item, dict):
            severity = str(item.get("severity", item.get("level", ""))).lower()
            if severity == "error":
                issues.append({"severity": "blocker", "type": "aggregation_error_diagnostic", "diagnostic": item})
        elif str(item).strip():
            issues.append({"severity": "blocker", "type": "aggregation_error_diagnostic", "diagnostic": str(item)})
    return bool(issues), issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check diagnostics after parent aggregation or merge candidate generation.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--diagnostics")
    parser.add_argument("--output")
    args = parser.parse_args()
    run = resolve_run_dir(args.run_id, args.run_dir)
    run_id = args.run_id or run.name
    path = Path(args.diagnostics) if args.diagnostics else run / "aggregation-diagnostics-report.json"
    data = load_json(path, {})
    failed, issues = diagnostics_fail(data)
    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at": now(),
        "diagnostics": str(path),
        "status": "fail" if failed else "pass",
        "issues": issues,
    }
    out = Path(args.output) if args.output else run / "aggregation-diagnostics-check.json"
    write_json(out, report)
    print(json.dumps({"status": report["status"], "run_id": run_id, "output": str(out), "issues": issues}, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
