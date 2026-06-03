#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

SCOPES = {"global", "project", "language", "framework", "mode"}
ASSETS = {"none", "rule", "skill", "script", "local-rule", "project-profile", "adr"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(text: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in text).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:64] or "lesson"


def recommend(recurrence: int, severity: str, failure_type: str) -> str:
    ft = failure_type.lower()
    high = severity.lower() in {"high", "critical", "blocker"}
    if "architecture" in ft:
        return "adr"
    if "project" in ft or "local" in ft:
        return "project-profile"
    if any(k in ft for k in ["gate", "machine", "detect", "missing field", "schema"]):
        return "script"
    if recurrence >= 3 or high:
        if any(k in ft for k in ["workflow", "process", "handoff"]):
            return "skill"
        return "rule"
    if recurrence >= 2:
        return "skill"
    return "none"


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract lesson candidate from event/postmortem evidence.")
    parser.add_argument("--event-file")
    parser.add_argument("--source-event-id", default="")
    parser.add_argument("--run-id", default="unknown")
    parser.add_argument("--branch-id", default="unknown")
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--symptom", default="")
    parser.add_argument("--root-cause", default="unknown")
    parser.add_argument("--recurrence-count", type=int, default=1)
    parser.add_argument("--scope", choices=sorted(SCOPES), default="global")
    parser.add_argument("--recommended-asset", choices=sorted(ASSETS))
    parser.add_argument("--proposed-change", default="event only")
    parser.add_argument("--expected-behavior-change", default="unknown")
    parser.add_argument("--regression-prompt", default="unknown")
    parser.add_argument("--regression-check", default="unknown")
    parser.add_argument("--rollback-plan", default="restore previous governance asset from backup")
    parser.add_argument("--confidence", default="medium")
    parser.add_argument("--owner-mode", default="agent-integrator")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    event_text = ""
    if args.event_file and Path(args.event_file).exists():
        event_text = Path(args.event_file).read_text(encoding="utf-8", errors="replace")
    source_event_id = args.source_event_id or ("event-" + hashlib.sha1((event_text or args.failure_type).encode("utf-8")).hexdigest()[:12])
    lesson_id = "lesson-" + slug(f"{args.failure_type}-{source_event_id}")
    asset = args.recommended_asset or recommend(args.recurrence_count, "medium", args.failure_type)
    status = "candidate" if args.recurrence_count >= 2 or asset != "none" else "candidate"
    lesson = {
        "lesson_id": lesson_id,
        "source_event_id": source_event_id,
        "run_id": args.run_id,
        "branch_id": args.branch_id,
        "failure_type": args.failure_type,
        "symptom": args.symptom or event_text[:500] or "unknown",
        "root_cause": args.root_cause,
        "recurrence_count": args.recurrence_count,
        "scope": args.scope,
        "recommended_asset": asset,
        "proposed_change": args.proposed_change,
        "expected_behavior_change": args.expected_behavior_change,
        "regression_prompt": args.regression_prompt,
        "regression_check": args.regression_check,
        "rollback_plan": args.rollback_plan,
        "confidence": args.confidence,
        "status": status,
        "owner_mode": args.owner_mode,
        "approved_by": "",
        "installed_at": "",
        "created_at": now(),
        "updated_at": now(),
    }
    lessons_dir = Path(".zoo-agent") / "lessons"
    index_path = lessons_dir / "lesson-index.json"
    if not args.dry_run:
        lessons_dir.mkdir(parents=True, exist_ok=True)
        (lessons_dir / f"{lesson_id}.json").write_text(json.dumps(lesson, indent=2) + "\n", encoding="utf-8")
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8-sig"))
            except Exception:
                index = {"lessons": []}
        else:
            index = {"lessons": []}
        index["lessons"] = [x for x in index.get("lessons", []) if x.get("lesson_id") != lesson_id]
        index["lessons"].append({"lesson_id": lesson_id, "failure_type": args.failure_type, "status": status, "recommended_asset": asset, "updated_at": lesson["updated_at"]})
        index["updated_at"] = now()
        index_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "lesson": lesson, "index_path": str(index_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
