#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ["before_behavior", "expected_new_behavior", "regression_prompt", "pass_condition", "rollback_condition"]
SENSITIVE_PATTERNS = ["model-routing", "human-exception", "security", "70-security", "75-human-exception", "25-model-routing"]


def load(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8-sig"))
    text = path.read_text(encoding="utf-8", errors="replace")
    data = {"raw": text}
    for field in REQUIRED + ["approved_by", "human_approval"]:
        marker = field.replace("_", " ")
        for line in text.splitlines():
            if line.lower().startswith(field.lower() + ":") or line.lower().startswith(marker.lower() + ":"):
                data[field] = line.split(":", 1)[1].strip()
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check governance regression evidence before installing governance changes.")
    parser.add_argument("--file", required=True)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--output")
    args = parser.parse_args()
    path = Path(args.file)
    issues = []
    if not path.exists():
        issues.append({"severity": "blocker", "issue": f"missing regression file: {path}"})
        data = {}
    else:
        data = load(path)
        for field in REQUIRED:
            if not str(data.get(field, "")).strip():
                issues.append({"severity": "blocker", "issue": f"missing {field}"})
    sensitive = any(any(pattern in p.lower() for pattern in SENSITIVE_PATTERNS) for p in args.changed_path)
    if sensitive and not str(data.get("human_approval", "")).strip():
        issues.append({"severity": "blocker", "issue": "sensitive governance change requires human_approval"})
    report = {"status": "pass" if not issues else "fail", "issues": issues, "sensitive_change": sensitive}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
