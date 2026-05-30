#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

REQUIRED = ["branch_id", "parent_branch_id", "depth", "max_depth", "objective", "owned_paths", "acceptance_criteria", "exit_condition"]
ACTIVE_STATES = {"active", "review"}


def parse_branch(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    data = {"file": str(path)}
    keys = REQUIRED + ["status", "parent_branch", "recursion_exit_condition", "remediation_loop_count", "needs_decomposition_count", "max_depth", "depth", "last_state_change_at", "modified_after_done"]
    for key in keys:
        m = re.search(rf"(?im)^\s*[-*]?\s*{re.escape(key)}\s*:\s*(.+)$", text)
        if m: data[key] = m.group(1).strip()
    if "exit_condition" not in data and "recursion_exit_condition" in data: data["exit_condition"] = data["recursion_exit_condition"]
    if "parent_branch_id" not in data and "parent_branch" in data: data["parent_branch_id"] = data["parent_branch"]
    data["has_completion_evidence"] = bool(re.search(r"(?i)completion evidence|completion_summary|evidence log", text))
    data["has_aggregation_matrices"] = bool(re.search(r"(?i)objective coverage matrix|dependency matrix|ownership matrix|risk matrix|integration matrix", text))
    return data


def as_int(value: object, default: int) -> int:
    s = str(value if value is not None else default).strip()
    return int(s) if s.isdigit() else default


def load(root: Path) -> list[dict]:
    run_root = root / ".zoo-agent/runs"
    if run_root.exists():
        states = sorted(run_root.glob("*/branch-state.json"))
        if states:
            data = json.loads(states[-1].read_text(encoding="utf-8-sig"))
            return data.get("branches", data) if isinstance(data, dict) else data
    json_path = root / ".zoo-agent/branch-state.json"
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8-sig"))
        return data.get("branches", data) if isinstance(data, dict) else data
    branch_dir = root / "docs/agent-governance/branch-state"
    return [parse_branch(p) for p in sorted(branch_dir.glob("*.md"))] if branch_dir.exists() else []


def evaluate(root: Path) -> dict:
    branches = load(root)
    issues = []
    for b in branches:
        bid = b.get("branch_id", b.get("file", "unknown"))
        missing = [f for f in REQUIRED if not b.get(f)]
        if missing: issues.append({"branch": bid, "type": "missing_fields", "fields": missing})
        if b.get("status") == "done" and not b.get("has_completion_evidence"): issues.append({"branch": bid, "type": "done_without_evidence"})
        if b.get("dependencies") and b.get("unclosed_dependencies"):
            issues.append({"branch": bid, "type": "unclosed_dependencies", "dependencies": b.get("unclosed_dependencies")})
        if as_int(b.get("remediation_loop_count"), 0) > 2: issues.append({"branch": bid, "type": "remediation_loop_budget_exceeded", "limit": 2})
        if as_int(b.get("needs_decomposition_count"), 0) > 1: issues.append({"branch": bid, "type": "needs_decomposition_budget_exceeded", "limit": 1})
        depth, max_depth = as_int(b.get("depth"), 0), as_int(b.get("max_depth"), 3)
        if depth > max_depth: issues.append({"branch": bid, "type": "max_depth_exceeded", "depth": depth, "max_depth": max_depth})
        if b.get("status") in ACTIVE_STATES and not b.get("last_state_change_at"): issues.append({"branch": bid, "type": "active_or_review_without_last_state_change"})
        if b.get("status") == "done" and str(b.get("modified_after_done", "")).lower() in {"true", "yes", "1"}: issues.append({"branch": bid, "type": "done_branch_modified_after_done"})
        if any(o.get("parent_branch_id") == b.get("branch_id") for o in branches) and not b.get("has_aggregation_matrices"): issues.append({"branch": bid, "type": "parent_missing_aggregation_matrices"})
    return {"status": "pass" if not issues else "fail", "branch_count": len(branches), "loop_limits": {"remediation_loop_count": 2, "needs_decomposition_count": 1}, "issues": issues}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--output")
    args = ap.parse_args(); report = evaluate(Path.cwd()); text = json.dumps(report, indent=2)
    if args.output and not args.dry_run:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text); return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
