#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=".zoo-agent/metrics/run-metrics.jsonl")
    args = parser.parse_args()
    path = Path(args.file)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []
    summary = {
        "run_count": len(rows),
        "fallback_count": sum(1 for r in rows if r.get("fallback_used")),
        "escalation_count": sum(1 for r in rows if r.get("escalation_used")),
        "quality_gate_pass_count": sum(1 for r in rows if r.get("quality_gate_status") == "pass"),
        "final_status_counts": {},
    }
    for r in rows:
        key = r.get("final_status", "unknown")
        summary["final_status_counts"][key] = summary["final_status_counts"].get(key, 0) + 1
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
