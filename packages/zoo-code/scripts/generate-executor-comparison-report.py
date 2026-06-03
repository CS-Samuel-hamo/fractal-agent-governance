#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a markdown executor comparison report.")
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--score", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    bench = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
    score = json.loads(Path(args.score).read_text(encoding="utf-8"))
    lines = [
        "# Executor Comparison Report",
        "",
        f"- cases: {score.get('case_count', 0)}",
        f"- completed: {score.get('completed', 0)}",
        f"- scope violations: {score.get('scope_violations', 0)}",
        f"- review blockers: {score.get('review_blockers', 0)}",
        f"- manual interventions: {score.get('manual_interventions', 0)}",
        "",
        "## Cases",
    ]
    for record in bench.get("records", []):
        lines.append(f"- {record.get('case')}: {record.get('executor_used')} / {record.get('final_status')}")
    output = Path(args.output) if args.output else Path(args.benchmark).with_suffix(".md")
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
