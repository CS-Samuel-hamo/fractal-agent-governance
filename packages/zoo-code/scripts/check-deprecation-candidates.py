#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def age_days(value: str) -> int:
    if not value:
        return 0
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Find governance deprecation candidates.")
    parser.add_argument("--lessons-dir", default=".zoo-agent/lessons")
    parser.add_argument("--skill-invocations")
    parser.add_argument("--rule-false-positive-file")
    parser.add_argument("--local-rule-conflicts")
    parser.add_argument("--gate-exceptions")
    parser.add_argument("--output")
    args = parser.parse_args()
    candidates = []
    lessons_dir = Path(args.lessons_dir)
    for path in sorted(lessons_dir.glob("lesson-*.json")) if lessons_dir.exists() else []:
        data = load_json(path)
        if data.get("status") not in {"deprecated", "installed", "approved"} and age_days(data.get("updated_at", data.get("created_at", ""))) > 90 and data.get("recurrence_count", 0) <= 1:
            candidates.append({"type": "lesson", "id": data.get("lesson_id"), "reason": "older than 90 days without recurrence"})
    if args.skill_invocations and Path(args.skill_invocations).exists():
        rows = load_json(Path(args.skill_invocations))
        rows = rows.get("invocations", rows if isinstance(rows, list) else [])
        by_skill: dict[str, list[str]] = {}
        for row in rows:
            by_skill.setdefault(row.get("skill", "unknown"), []).append(row.get("outcome", "unknown"))
        for skill, outcomes in by_skill.items():
            if len(outcomes) >= 5 and outcomes[-5:] == ["irrelevant"] * 5:
                candidates.append({"type": "skill", "id": skill, "reason": "five consecutive irrelevant invocations"})
    for label, file_path, reason in [
        ("rule", args.rule_false_positive_file, "repeated false positives"),
        ("local-rule", args.local_rule_conflicts, "conflicts with project profile"),
        ("script-gate", args.gate_exceptions, "multiple human exceptions after gate block"),
    ]:
        if file_path and Path(file_path).exists():
            data = load_json(Path(file_path))
            count = data.get("count", len(data) if isinstance(data, list) else 1)
            if count >= 2:
                candidates.append({"type": label, "id": Path(file_path).stem, "reason": reason, "count": count})
    report = {"status": "pass", "candidate_count": len(candidates), "candidates": candidates}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
