#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate markdown eval report from JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    out = Path(args.output) if args.output else Path(args.input).with_suffix(".md")
    lines = [f"# Eval Report {data.get('eval_run_id', 'unknown')}", "", f"- suite: {data.get('suite', 'unknown')}", f"- status: {data.get('status', 'unknown')}", "", "## Aggregate Scores"]
    for key, value in data.get("aggregate_scores", {}).items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Cases"])
    for result in data.get("case_results", []):
        lines.append(f"- {result.get('case_id')}: {result.get('status')}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(out)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
