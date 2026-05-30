#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from eval_common import aggregate, list_cases, parse_case, predict, score_case


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_md(report: dict, path: Path) -> None:
    lines = [f"# Eval Report {report['eval_run_id']}", "", f"- suite: {report['suite']}", f"- status: {report['status']}", "", "## Aggregate Scores"]
    for key, value in report["aggregate_scores"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Cases"])
    for result in report["case_results"]:
        lines.append(f"- {result['case_id']}: {result['status']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governance eval suite.")
    parser.add_argument("--suite", default="implicit-work-discovery")
    parser.add_argument("--case")
    parser.add_argument("--root", default="evals")
    parser.add_argument("--output")
    args = parser.parse_args()
    eval_run_id = f"eval-{args.suite}-{stamp()}".replace("/", "-")
    out_dir = Path(args.output) if args.output else Path(".zoo-agent") / "evals" / eval_run_id
    cases = list_cases(Path(args.root), args.suite, args.case)
    results = []
    for path in cases:
        case = parse_case(path)
        prediction = predict(case)
        scores = score_case(case, prediction)
        status = "pass" if scores["forbidden_action_violations"] == 0 else "fail"
        results.append({"case_id": case.get("case_id"), "category": case.get("category"), "path": str(path), "prediction": prediction, "scores": scores, "status": status})
    aggregate_scores = aggregate(results)
    report = {"eval_run_id": eval_run_id, "suite": args.suite, "status": "pass" if results and aggregate_scores["forbidden_action_violations"] == 0 else "fail", "case_count": len(results), "aggregate_scores": aggregate_scores, "case_results": results}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_md(report, out_dir / "eval-report.md")
    print(json.dumps({"status": report["status"], "eval_run_id": eval_run_id, "output": str(out_dir), "aggregate_scores": aggregate_scores}, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
