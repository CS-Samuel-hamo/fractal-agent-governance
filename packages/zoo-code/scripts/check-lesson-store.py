#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED = ["lesson_id", "source_event_id", "run_id", "branch_id", "failure_type", "symptom", "root_cause", "recurrence_count", "scope", "recommended_asset", "proposed_change", "expected_behavior_change", "regression_prompt", "regression_check", "rollback_plan", "confidence", "status", "owner_mode", "approved_by", "installed_at"]
SCOPES = {"global", "project", "language", "framework", "mode"}
ASSETS = {"none", "rule", "skill", "script", "local-rule", "project-profile", "adr"}
STATUSES = {"candidate", "approved", "installed", "rejected", "deprecated"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in {"", "unknown", "todo", "tbd"}
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate lesson store structure.")
    parser.add_argument("--lessons-dir", default=".zoo-agent/lessons")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.lessons_dir)
    issues = []
    lessons = []
    index = root / "lesson-index.json"
    if not index.exists():
        issues.append({"severity": "blocker", "issue": f"missing {index}"})
    lesson_files = [p for p in sorted(root.glob("lesson-*.json")) if p.name != "lesson-index.json"] if root.exists() else []
    for path in lesson_files:
        data = load(path)
        lessons.append(data)
        for field in REQUIRED:
            if field not in data:
                issues.append({"lesson_id": data.get("lesson_id", path.stem), "severity": "blocker", "issue": f"missing {field}"})
        if data.get("scope") not in SCOPES:
            issues.append({"lesson_id": data.get("lesson_id", path.stem), "severity": "blocker", "issue": "invalid scope"})
        if data.get("recommended_asset") not in ASSETS:
            issues.append({"lesson_id": data.get("lesson_id", path.stem), "severity": "blocker", "issue": "invalid recommended_asset"})
        if data.get("status") not in STATUSES:
            issues.append({"lesson_id": data.get("lesson_id", path.stem), "severity": "blocker", "issue": "invalid status"})
        if data.get("status") in {"approved", "installed"}:
            for field in ["regression_prompt", "regression_check", "rollback_plan", "approved_by"]:
                if not present(data.get(field)):
                    issues.append({"lesson_id": data.get("lesson_id", path.stem), "severity": "blocker", "issue": f"approved/installed lesson lacks {field}"})
    report = {"status": "pass" if not any(i["severity"] == "blocker" for i in issues) else "fail", "lesson_count": len(lessons), "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
