#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATE_REQUIREMENTS = {
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
}

ORDER = [
    "intake", "goal_bound", "project_profile_ready", "obligation_ready", "planned",
    "branch_scoped", "executing", "evidence_ready", "quality_gate_ready",
    "mechanical_review_ready", "semantic_review_ready", "parent_aggregated",
    "integration_ready", "integrated", "final_reported",
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def resolve(path: str, cwd: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else cwd / p


def graph_items(graph: dict) -> list[dict]:
    items = [x for x in graph.get("artifacts", []) if isinstance(x, dict)]
    items.extend(x for x in graph.get("nodes", []) if isinstance(x, dict))
    return items


def normalize_type(value: str) -> str:
    return str(value or "").replace("-", "_")


def artifact_types(graph: dict) -> set[str]:
    return {normalize_type(x.get("type")) for x in graph_items(graph)}


def looks_like_file_ref(path: str) -> bool:
    text = str(path or "")
    return (
        bool(text)
        and ("/" in text or "\\" in text or text.startswith(".") or Path(text).is_absolute() or bool(Path(text).suffix))
    )


def should_check_path(item: dict) -> bool:
    path = item.get("path")
    if not path:
        return False
    typ = normalize_type(item.get("type"))
    if typ in {"input", "skill"}:
        return looks_like_file_ref(str(path))
    return True


def all_required_for_state(state: str) -> set[str]:
    if state not in ORDER:
        return STATE_REQUIREMENTS.get(state, set())
    idx = ORDER.index(state)
    needed: set[str] = set()
    for prior in ORDER[: idx + 1]:
        needed |= STATE_REQUIREMENTS.get(prior, set())
    return needed


def transition_missing(transition: dict, present: set[str]) -> list[str]:
    state = transition.get("to")
    required = STATE_REQUIREMENTS.get(state, set())
    transition_types = set()
    for spec in transition.get("input_artifacts", []) + transition.get("output_artifacts", []):
        if "=" in spec:
            transition_types.add(spec.split("=", 1)[0].strip())
        else:
            low = str(spec).lower()
            for typ in STATE_REQUIREMENTS.get(state, set()):
                if typ.replace("_", "-") in low or typ in low:
                    transition_types.add(typ)
    return sorted(required - present - transition_types)


def graph_path_refs(graph: dict, project_root: Path) -> set[str]:
    refs: set[str] = set()
    for item in graph_items(graph):
        path_value = item.get("path")
        if not path_value:
            continue
        path = Path(str(path_value))
        refs.add(str(path_value).replace("\\", "/"))
        if path.is_absolute():
            try:
                refs.add(path.relative_to(project_root).as_posix())
            except ValueError:
                refs.add(path.as_posix())
        else:
            refs.add(path.as_posix())
            refs.add(str((project_root / path).resolve()).replace("\\", "/"))
    return refs


def find_orphans(run_dir: Path, graph: dict, project_root: Path, run_id: str) -> list[dict]:
    issues = []
    graph_paths = graph_path_refs(graph, project_root)
    for pattern, label in [("*branch*.json", "orphan_branch"), ("*review*.json", "orphan_review")]:
        for path in run_dir.glob(pattern):
            absolute = path if path.is_absolute() else project_root / path
            rel = absolute.relative_to(project_root).as_posix() if absolute.is_relative_to(project_root) else str(path).replace("\\", "/")
            if rel not in graph_paths and str(path) not in graph_paths:
                issues.append({"type": label, "path": rel})
    lessons_dir = project_root / ".zoo-agent/lessons"
    if lessons_dir.exists():
        for path in lessons_dir.glob("lesson-*.json"):
            if path.name == "lesson-index.json":
                continue
            data = load(path)
            if data.get("run_id") == run_id:
                rel = path.relative_to(project_root).as_posix()
                if rel not in graph_paths and str(path) not in graph_paths:
                    issues.append({"type": "orphan_lesson", "path": rel, "lesson_id": data.get("lesson_id")})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check run-ledger, artifact graph, and runtime artifacts for backbone consistency.")
    parser.add_argument("--run-id")
    parser.add_argument("--run-dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else Path(".zoo-agent") / "runs" / (args.run_id or "")
    ledger_path = run_dir / "run-ledger.json"
    graph_path = run_dir / "artifact-graph.json"
    project_root = Path.cwd()
    issues = []
    ledger = load(ledger_path)
    graph = load(graph_path)
    if not ledger:
        issues.append({"type": "missing_run_ledger", "path": str(ledger_path)})
    if not graph:
        issues.append({"type": "missing_artifact_graph", "path": str(graph_path)})
    run_id = ledger.get("run_id") or graph.get("run_id") or args.run_id or "unknown"
    goal_id = ledger.get("goal_id", "unknown")
    if not goal_id or goal_id == "unknown":
        issues.append({"type": "missing_goal_id", "run_id": run_id})
    if ledger and graph and ledger.get("run_id") != graph.get("run_id"):
        issues.append({"type": "ledger_graph_run_id_mismatch", "ledger": ledger.get("run_id"), "graph": graph.get("run_id")})
    if ledger and graph and ledger.get("goal_id") != graph.get("goal_id"):
        issues.append({"type": "ledger_graph_goal_id_mismatch", "ledger": ledger.get("goal_id"), "graph": graph.get("goal_id")})
    artifacts = graph_items(graph) if graph else []
    strict_artifacts = [x for x in graph.get("artifacts", []) if isinstance(x, dict)] if graph else []
    legacy_nodes = [x for x in graph.get("nodes", []) if isinstance(x, dict)] if graph else []
    present = artifact_types(graph)
    for item in strict_artifacts:
        if item.get("run_id") != run_id:
            issues.append({"type": "artifact_wrong_run_id", "artifact_id": item.get("artifact_id"), "run_id": item.get("run_id")})
        if item.get("goal_id") != goal_id:
            issues.append({"type": "artifact_wrong_goal_id", "artifact_id": item.get("artifact_id"), "goal_id": item.get("goal_id")})
        path = item.get("path")
        if should_check_path(item) and not resolve(path, project_root).exists():
            issues.append({"type": "artifact_graph_missing_file", "artifact_id": item.get("artifact_id"), "path": path})
        if item.get("type") in {"quality_gate", "mechanical_review", "review_report", "integration_report"} and not item.get("input_artifacts"):
            issues.append({"type": "gate_did_not_record_inputs", "artifact_id": item.get("artifact_id"), "artifact_type": item.get("type")})
    for item in legacy_nodes:
        if item.get("run_id") not in (None, run_id):
            issues.append({"type": "artifact_wrong_run_id", "artifact_id": item.get("artifact_id"), "run_id": item.get("run_id")})
        if item.get("goal_id") not in (None, goal_id):
            issues.append({"type": "artifact_wrong_goal_id", "artifact_id": item.get("artifact_id"), "goal_id": item.get("goal_id")})
        path = item.get("path")
        if should_check_path(item) and not resolve(path, project_root).exists():
            issues.append({"type": "artifact_graph_missing_file", "artifact_id": item.get("artifact_id"), "path": path})
        if item.get("type") in {"quality_gate", "mechanical_review", "review_report", "integration_report"} and not item.get("input_artifacts"):
            issues.append({"type": "gate_did_not_record_inputs", "artifact_id": item.get("artifact_id"), "artifact_type": item.get("type")})
    state = ledger.get("current_state", "intake") if ledger else "unknown"
    missing_for_state = sorted(all_required_for_state(state) - present)
    if missing_for_state and state not in {"intake", "blocked", "abort"}:
        issues.append({"type": "current_state_missing_required_artifacts", "state": state, "missing": missing_for_state})
    for transition in ledger.get("transitions", []) if ledger else []:
        missing = transition_missing(transition, present)
        if missing:
            issues.append({"type": "transition_skipped_required_artifact", "to": transition.get("to"), "missing": missing})
    if graph:
        issues.extend(find_orphans(run_dir, graph, project_root, run_id))
    report = {"status": "pass" if not issues else "fail", "run_id": run_id, "goal_id": goal_id, "current_state": state, "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
