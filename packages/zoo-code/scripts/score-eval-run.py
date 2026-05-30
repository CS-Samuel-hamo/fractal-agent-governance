#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from eval_common import aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description="Score an eval run report.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
    scores = aggregate(data.get("case_results", []))
    report = {"status": "pass", "eval_run_id": data.get("eval_run_id"), "suite": data.get("suite"), "aggregate_scores": scores}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
