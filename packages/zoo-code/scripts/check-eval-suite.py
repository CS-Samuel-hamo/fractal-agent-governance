#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from eval_common import list_cases, parse_case, resolve_eval_root

REQUIRED = ["case_id", "category", "input_task", "fixture", "expected_obligations", "expected_surfaces", "expected_routing", "expected_decomposition", "expected_escalations", "forbidden_actions", "scoring"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate eval suite case files.")
    parser.add_argument("--suite", default="full")
    parser.add_argument("--root", default="evals")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = resolve_eval_root(Path(args.root))
    issues = []
    suites = [p.name for p in root.iterdir() if p.is_dir()] if args.suite == "full" and root.exists() else [args.suite]
    for suite in suites:
        cases = list_cases(root, suite)
        if len(cases) < 3:
            issues.append({"suite": suite, "severity": "blocker", "issue": "suite_has_fewer_than_3_cases", "count": len(cases)})
        for path in cases:
            data = parse_case(path)
            for field in REQUIRED:
                if field not in data:
                    issues.append({"suite": suite, "case": str(path), "severity": "blocker", "issue": f"missing_{field}"})
            scoring = data.get("scoring", {})
            for field in ["required", "optional", "penalties"]:
                if field not in scoring:
                    issues.append({"suite": suite, "case": str(path), "severity": "blocker", "issue": f"missing_scoring_{field}"})
    report = {"status": "pass" if not issues else "fail", "suite": args.suite, "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
