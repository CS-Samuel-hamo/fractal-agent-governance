#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail on diagnostics regressions.")
    parser.add_argument("--run-id")
    parser.add_argument("--file")
    parser.add_argument("--governance-level", type=int, default=2)
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file) if args.file else Path(".zoo-agent") / "runs" / (args.run_id or "") / "diagnostics-report.json"
    issues = []
    if not path.exists():
        report = {"status": "unknown", "issues": [{"severity": "warning", "issue": "diagnostics_report_missing", "path": str(path)}]}
    else:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if data.get("new_errors") or data.get("status") == "fail":
            issues.append({"severity": "blocker", "issue": "new_error_diagnostics", "new_errors": data.get("new_errors", [])})
        if data.get("new_warnings") and args.governance_level >= 3:
            issues.append({"severity": "major", "issue": "new_warning_diagnostics_require_gpt_review", "new_warnings": data.get("new_warnings", [])})
        report = {"status": "fail" if any(i["severity"] == "blocker" for i in issues) else "pass", "issues": issues, "path": str(path)}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] in {"pass", "unknown"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
