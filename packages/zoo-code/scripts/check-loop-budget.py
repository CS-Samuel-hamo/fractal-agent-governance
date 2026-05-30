#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import json
from datetime import datetime, timezone
from pathlib import Path

QUALITY_RANK = {"unknown": 0, "fail": 1, "warnings": 2, "pass": 3}
RISK_RANK = {"unknown": 0, "high": 1, "medium": 2, "low": 3, "closed": 4}


def state_path(run_id: str) -> Path:
    return Path(".zoo-agent") / "runs" / run_id / "loop-state.json"


def load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {"schema_version": "1.1", "branches": {}}


def branch_default(branch_id: str) -> dict:
    return {
        "branch_id": branch_id,
        "remediation_count": 0,
        "review_count": 0,
        "needs_decomposition_count": 0,
        "curator_update_count": 0,
        "max_remediation_loops": 2,
        "max_review_loops": 2,
        "max_needs_decomposition": 1,
        "max_depth": 3,
        "stalled_count": 0,
        "regressing_count": 0,
        "last_metrics": {},
        "convergence_status": "unknown",
    }


def within_owned(files: list[str], owned: list[str]) -> bool:
    if not files or not owned:
        return True
    return all(any(fnmatch.fnmatch(f.replace("\\", "/"), p.replace("\\", "/")) for p in owned) for f in files)


def classify(prev: dict, metrics: dict, owned_ok: bool) -> str:
    if not prev:
        return "improving" if owned_ok else "regressing"
    improved = False
    regressed = False
    if metrics["coverage"] > prev.get("coverage", -1):
        improved = True
    if metrics["coverage"] < prev.get("coverage", metrics["coverage"]):
        regressed = True
    if metrics["unknowns"] < prev.get("unknowns", 10**9):
        improved = True
    if metrics["unknowns"] > prev.get("unknowns", metrics["unknowns"]):
        regressed = True
    if QUALITY_RANK.get(metrics["quality"], 0) > QUALITY_RANK.get(prev.get("quality", "unknown"), 0):
        improved = True
    if QUALITY_RANK.get(metrics["quality"], 0) < QUALITY_RANK.get(prev.get("quality", metrics["quality"]), 0):
        regressed = True
    if RISK_RANK.get(metrics["risk"], 0) > RISK_RANK.get(prev.get("risk", "unknown"), 0):
        improved = True
    if RISK_RANK.get(metrics["risk"], 0) < RISK_RANK.get(prev.get("risk", metrics["risk"]), 0):
        regressed = True
    if metrics["required_obligations_open"] < prev.get("required_obligations_open", 10**9):
        improved = True
    if metrics["required_obligations_open"] > prev.get("required_obligations_open", metrics["required_obligations_open"]):
        regressed = True
    if metrics["required_obligations_closed"] > prev.get("required_obligations_closed", -1):
        improved = True
    if metrics["required_obligations_closed"] < prev.get("required_obligations_closed", metrics["required_obligations_closed"]):
        regressed = True
    if not owned_ok:
        regressed = True
    if regressed:
        return "regressing"
    return "improving" if improved else "stalled"


def main() -> int:
    parser = argparse.ArgumentParser(description="Update/check loop budget and convergence state.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--event", choices=["remediation", "review", "needs_decomposition", "curator_update", "check"], default="check")
    parser.add_argument("--depth", type=int, default=0)
    parser.add_argument("--goal-coverage", type=float, default=0.0)
    parser.add_argument("--unknowns", type=int, default=0)
    parser.add_argument("--quality", choices=sorted(QUALITY_RANK), default="unknown")
    parser.add_argument("--risk", choices=sorted(RISK_RANK), default="unknown")
    parser.add_argument("--required-obligations-open", type=int, default=0)
    parser.add_argument("--required-obligations-closed", type=int, default=0)
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--owned-path", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = state_path(args.run_id)
    data = load(path)
    branch = data.setdefault("branches", {}).setdefault(args.branch_id, branch_default(args.branch_id))
    if args.event == "remediation":
        branch["remediation_count"] += 1
    elif args.event == "review":
        branch["review_count"] += 1
    elif args.event == "needs_decomposition":
        branch["needs_decomposition_count"] += 1
    elif args.event == "curator_update":
        branch["curator_update_count"] += 1
    metrics = {
        "coverage": args.goal_coverage,
        "unknowns": args.unknowns,
        "quality": args.quality,
        "risk": args.risk,
        "required_obligations_open": args.required_obligations_open,
        "required_obligations_closed": args.required_obligations_closed,
    }
    owned_ok = within_owned(args.changed_file, args.owned_path)
    status = classify(branch.get("last_metrics", {}), metrics, owned_ok)
    branch["convergence_status"] = status
    branch["last_metrics"] = metrics
    branch["last_checked_at"] = datetime.now(timezone.utc).isoformat()
    branch["depth"] = args.depth
    branch["stalled_count"] = branch.get("stalled_count", 0) + 1 if status == "stalled" else 0
    branch["regressing_count"] = branch.get("regressing_count", 0) + 1 if status == "regressing" else 0
    violations = []
    if branch["remediation_count"] > branch["max_remediation_loops"]:
        violations.append("remediation_loop_exhausted")
    if branch["review_count"] > branch["max_review_loops"]:
        violations.append("review_loop_exhausted")
    if branch["needs_decomposition_count"] > branch["max_needs_decomposition"]:
        violations.append("needs_decomposition_exhausted")
    if args.depth > branch["max_depth"]:
        violations.append("max_depth_exceeded")
    if branch["stalled_count"] >= 2:
        violations.append("stalled_twice")
    if branch["regressing_count"] >= 1:
        violations.append("regressing")
    if not owned_ok:
        violations.append("changed_files_outside_owned_paths")
    report = {"status": "escalate" if violations else "pass", "run_id": args.run_id, "branch_id": args.branch_id, "convergence_status": status, "violations": violations, "branch": branch}
    if not args.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not violations else 2


if __name__ == "__main__":
    raise SystemExit(main())
