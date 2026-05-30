#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

MAINLINE = [
    "intake",
    "goal_bound",
    "project_profile_ready",
    "obligation_ready",
    "planned",
    "branch_scoped",
    "executing",
    "evidence_ready",
    "quality_gate_ready",
    "mechanical_review_ready",
    "semantic_review_ready",
    "parent_aggregated",
    "integration_ready",
    "integrated",
    "final_reported",
]

ALLOWED: dict[str, set[str]] = {a: {b, "blocked"} for a, b in zip(MAINLINE, MAINLINE[1:])}
ALLOWED["final_reported"] = set()
ALLOWED["blocked"] = {"remediate", "decompose", "escalate", "fallback", "abort"}
ALLOWED["remediate"] = {"executing", "blocked"}
ALLOWED["decompose"] = {"branch_scoped", "blocked"}
ALLOWED["escalate"] = {"blocked", "fallback", "abort"}
ALLOWED["fallback"] = {"remediate", "decompose", "abort"}
ALLOWED["abort"] = set()

REQUIRED_BY_STATE = {
    "goal_bound": {"goal_contract"},
    "project_profile_ready": {"goal_contract", "project_profile"},
    "obligation_ready": {"goal_contract", "project_profile", "obligation_ledger"},
    "planned": {"goal_contract", "project_profile", "obligation_ledger"},
    "branch_scoped": {"branch_state"},
    "executing": {"obligation_ledger"},
    "evidence_ready": {"completion_evidence"},
    "quality_gate_ready": {"quality_gate"},
    "mechanical_review_ready": {"mechanical_review"},
    "semantic_review_ready": {"review_report"},
    "parent_aggregated": {"parent_aggregation"},
    "integration_ready": {"quality_gate", "parent_aggregation"},
    "integrated": {"integration_report"},
    "final_reported": {"final_report"},
    "escalate": {"escalation"},
    "fallback": {"fallback_report"},
}

TYPE_HINTS = {
    "goal": "goal_contract",
    "project-profile": "project_profile",
    "project_profile": "project_profile",
    "obligation": "obligation_ledger",
    "branch-state": "branch_state",
    "branch_state": "branch_state",
    "worktree-map": "worktree_map",
    "worktree_map": "worktree_map",
    "path-locks": "path_locks",
    "path_locks": "path_locks",
    "evidence": "completion_evidence",
    "diagnostics": "diagnostics_report",
    "quality-gate": "quality_gate",
    "quality_gate": "quality_gate",
    "mechanical": "mechanical_review",
    "review-report": "review_report",
    "review_report": "review_report",
    "semantic": "review_report",
    "parent-aggregation": "parent_aggregation",
    "parent_aggregation": "parent_aggregation",
    "merge-queue": "merge_queue",
    "merge_queue": "merge_queue",
    "integration": "integration_report",
    "final-report": "final_report",
    "final_report": "final_report",
    "escalation": "escalation",
    "fallback": "fallback_report",
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def artifact_type(spec: str) -> tuple[str, str]:
    if "=" in spec:
        left, right = spec.split("=", 1)
        return left.strip(), right.strip()
    low = spec.lower().replace("\\", "/")
    for hint, typ in TYPE_HINTS.items():
        if hint in low:
            return typ, spec
    return "artifact", spec


def artifact_id(spec: str) -> str:
    typ, path = artifact_type(spec)
    return f"{typ}:{path}"


def artifact_types(specs: list[str]) -> set[str]:
    return {artifact_type(x)[0] for x in specs}


def ledger_path(args: argparse.Namespace) -> Path:
    if args.ledger:
        return Path(args.ledger)
    if args.run_id:
        return Path(".zoo-agent") / "runs" / args.run_id / "run-ledger.json"
    raise SystemExit("--ledger or --run-id is required")


def graph_path(ledger: Path) -> Path:
    return ledger.parent / "artifact-graph.json"


def graph_types(graph: dict) -> set[str]:
    return {x.get("type") for x in graph.get("artifacts", []) if isinstance(x, dict)}


def add_artifacts(graph: dict, specs: list[str], run_id: str, goal_id: str, branch_id: str, mode: str, model: str, input_specs: list[str], gate_status: str) -> None:
    existing_ids = {x.get("artifact_id") for x in graph.get("artifacts", []) if isinstance(x, dict)}
    for spec in specs:
        typ, path = artifact_type(spec)
        aid = artifact_id(spec)
        if aid in existing_ids:
            continue
        graph.setdefault("artifacts", []).append({
            "artifact_id": aid,
            "type": typ,
            "path": path,
            "run_id": run_id,
            "goal_id": goal_id,
            "branch_id": branch_id,
            "created_by_mode": mode,
            "model": model,
            "created_at": now(),
            "input_artifacts": input_specs,
            "output_artifacts": specs,
            "gate_status": gate_status,
        })
        existing_ids.add(aid)


def missing_required(state: str, graph: dict, input_specs: list[str], output_specs: list[str]) -> list[str]:
    required = REQUIRED_BY_STATE.get(state, set())
    present = graph_types(graph) | artifact_types(input_specs) | artifact_types(output_specs)
    return sorted(required - present)


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a governed run-ledger state transition.")
    parser.add_argument("--ledger")
    parser.add_argument("--run-id")
    parser.add_argument("--state", required=True)
    parser.add_argument("--owner-mode", "--created-by-mode", dest="owner_mode", required=True)
    parser.add_argument("--model", default="unknown")
    parser.add_argument("--goal-id")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--input-artifact", action="append", default=[])
    parser.add_argument("--output-artifact", action="append", default=[])
    parser.add_argument("--gate-status", default="unknown")
    parser.add_argument("--checkpoint-ref", default="")
    parser.add_argument("--worktree-path", default="")
    parser.add_argument("--git-diff-stat", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ledger_file = ledger_path(args)
    ledger = load_json(ledger_file)
    if not ledger:
        print(json.dumps({"status": "fail", "error": "run_ledger_missing", "path": str(ledger_file)}, indent=2))
        return 2
    graph_file = graph_path(ledger_file)
    graph = load_json(graph_file)
    current = ledger.get("current_state", "intake")
    allowed = ALLOWED.get(current, set())
    if args.state not in allowed:
        print(json.dumps({"status": "fail", "error": "illegal_state_transition", "from": current, "to": args.state, "allowed": sorted(allowed)}, indent=2))
        return 2
    run_id = ledger.get("run_id", args.run_id or "unknown")
    goal_id = args.goal_id or ledger.get("goal_id", "unknown")
    if goal_id == "unknown" and args.state not in {"blocked", "abort"}:
        print(json.dumps({"status": "fail", "error": "goal_id_required", "state": args.state}, indent=2))
        return 2
    missing = missing_required(args.state, graph, args.input_artifact, args.output_artifact)
    if missing:
        print(json.dumps({"status": "fail", "error": "missing_required_artifacts", "state": args.state, "missing": missing}, indent=2))
        return 2
    transition = {
        "at": now(),
        "from": current,
        "to": args.state,
        "run_id": run_id,
        "goal_id": goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.owner_mode,
        "owner_mode": args.owner_mode,
        "model": args.model,
        "input_artifacts": args.input_artifact,
        "output_artifacts": args.output_artifact,
        "gate_status": args.gate_status,
    }
    if args.checkpoint_ref:
        transition["checkpoint_ref"] = args.checkpoint_ref
    if args.worktree_path:
        transition["worktree_path"] = args.worktree_path
    if args.git_diff_stat:
        transition["git_diff_stat"] = args.git_diff_stat
    ledger.setdefault("transitions", []).append(transition)
    ledger["current_state"] = args.state
    ledger["goal_id"] = goal_id
    ledger["branch_id"] = args.branch_id
    ledger["updated_at"] = transition["at"]
    ledger["allowed_next_states"] = sorted(ALLOWED.get(args.state, set()))
    if graph:
        graph["run_id"] = run_id
        graph["goal_id"] = goal_id
        graph["updated_at"] = transition["at"]
        add_artifacts(graph, args.input_artifact + args.output_artifact, run_id, goal_id, args.branch_id, args.owner_mode, args.model, args.input_artifact, args.gate_status)
        for src in args.input_artifact:
            for dst in args.output_artifact:
                graph.setdefault("edges", []).append({"from": artifact_id(src), "to": artifact_id(dst), "state": args.state, "created_at": transition["at"]})
    if args.dry_run:
        print(json.dumps({"status": "ok", "would_write": str(ledger_file), "transition": transition}, indent=2))
        return 0
    ledger_file.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    if graph:
        graph_file.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "transition": transition}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
