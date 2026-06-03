#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

HIGH_RISK = {
    "auth", "permission", "payment", "pii", "security", "credential",
    "secret", "migration", "production config", "prod config",
    "breaking public api", "destructive", "release",
}
LEVEL3 = {
    "cross-module", "cross module", "multiple modules", "fractal",
    "worktree", "parallel", "parent aggregation", "merge queue",
    "proc/data-source", "data-source mismatch",
}
LEVEL2 = {
    "api", "service", "dto", "schema", "registry", "provider",
    "shared type", "public behavior", "integration", "contract",
}


def contains_any(text: str, needles: set[str]) -> list[str]:
    low = text.lower()
    return sorted(item for item in needles if item in low)


def classify(description: str, files: list[str], file_count: int | None) -> dict:
    count = file_count if file_count is not None else len(files)
    evidence: list[str] = []
    high = contains_any(description, HIGH_RISK)
    l3 = contains_any(description, LEVEL3)
    l2 = contains_any(description, LEVEL2)

    if high:
        level = 4
        evidence.extend(f"high-risk:{item}" for item in high)
    elif l3 or count > 8:
        level = 3
        evidence.extend(f"fractal:{item}" for item in l3)
        if count > 8:
            evidence.append("file-count>8")
    elif l2:
        level = 2
        evidence.extend(f"multi-surface:{item}" for item in l2)
    elif count <= 3:
        level = 0
        evidence.append("1-3-files")
    elif count <= 10:
        level = 1
        evidence.append("3-10-files")
    else:
        level = 3
        evidence.append("file-count>10")

    names = {
        0: "Level 0 Micro Edit",
        1: "Level 1 Routine Coding",
        2: "Level 2 Multi-surface Feature",
        3: "Level 3 Fractal Workstream",
        4: "Level 4 High-risk / Irreversible",
    }
    return {
        "governance_level": f"Level {level}",
        "level": level,
        "level_name": names[level],
        "file_count": count,
        "evidence": evidence,
        "blocking_factors": high if level == 4 else [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify task complexity for Zoo governance routing.")
    parser.add_argument("--task-id", default="")
    parser.add_argument("--description", default="")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--file-count", type=int)
    parser.add_argument("--json-output")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    args = parser.parse_args()

    result = classify(args.description, args.changed_file, args.file_count)
    if args.task_id:
        result["task_id"] = args.task_id
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['level_name']} ({result['governance_level']})")
        if result["evidence"]:
            print("Evidence:")
            for item in result["evidence"]:
                print(f" - {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
