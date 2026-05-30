#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
from pathlib import Path


def any_match(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, p.replace("\\", "/")) for p in patterns)


def normalize(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def lock_path(run_id: str | None, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    if run_id:
        return Path(".zoo-agent") / "runs" / run_id / "path-locks.json"
    return Path(".zoo-agent") / "path-locks.json"


def load_locks(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def branch_patterns(data: dict, branch_id: str | None) -> tuple[list[str], list[str], list[str]]:
    if "locks" in data:
        locks = data.get("locks", [])
        if branch_id:
            for item in locks:
                if item.get("branch_id") == branch_id:
                    return item.get("owned_paths", []), item.get("shared_paths", []), item.get("forbidden_paths", data.get("forbidden_paths", []))
        owned = []
        shared = []
        forbidden = data.get("forbidden_paths", [])
        for item in locks:
            owned.extend(item.get("owned_paths", []))
            shared.extend(item.get("shared_paths", []))
            forbidden.extend(item.get("forbidden_paths", []))
        return owned, shared, forbidden
    return data.get("owned_paths", []), data.get("shared_paths", []), data.get("forbidden_paths", [])


def rough_overlap(a: str, b: str) -> bool:
    a = normalize(a).rstrip("*")
    b = normalize(b).rstrip("*")
    return bool(a and b and (a.startswith(b) or b.startswith(a) or a == b))


def lock_conflicts(data: dict) -> list[dict]:
    conflicts = []
    locks = data.get("locks", [])
    for i, left in enumerate(locks):
        for right in locks[i + 1:]:
            for a in left.get("owned_paths", []):
                for b in right.get("owned_paths", []):
                    if rough_overlap(a, b):
                        shared = set(left.get("shared_paths", [])) & set(right.get("shared_paths", []))
                        conflicts.append({"type": "owned_path_overlap", "left": left.get("branch_id"), "right": right.get("branch_id"), "path_a": a, "path_b": b, "shared_declared": bool(shared)})
    return conflicts


def main() -> int:
    parser = argparse.ArgumentParser(description="Check changed files against path locks.")
    parser.add_argument("--run-id")
    parser.add_argument("--branch-id")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--locks")
    parser.add_argument("--check-conflicts", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    path = lock_path(args.run_id, args.locks)
    if not path.exists():
        report = {"status": "fail", "error": "path_locks_missing", "path": str(path)}
    else:
        data = load_locks(path)
        owned, shared, forbidden = branch_patterns(data, args.branch_id)
        violations = []
        for f in args.changed_file:
            n = normalize(f)
            if any_match(n, forbidden):
                violations.append({"file": n, "type": "forbidden_path"})
            elif not any_match(n, owned) and not any_match(n, shared):
                violations.append({"file": n, "type": "unowned_path"})
        conflicts = lock_conflicts(data) if args.check_conflicts else []
        violations.extend([c for c in conflicts if not c.get("shared_declared")])
        report = {"status": "pass" if not violations else "fail", "path": str(path), "branch_id": args.branch_id, "violations": violations, "conflicts": conflicts}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
