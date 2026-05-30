#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

LEVEL_NAMES = {
    0: "Micro Edit",
    1: "Routine Coding",
    2: "Multi-surface Feature",
    3: "Fractal Workstream",
    4: "High-risk / Irreversible Change",
}

SURFACE_KEYWORDS = {
    "api", "route", "service", "dto", "schema", "registry", "provider", "factory",
    "repository", "mapper", "validator", "migration", "ui", "job", "queue", "event",
}
HIGH_RISK_KEYWORDS = {
    "auth", "authorization", "permission", "payment", "pii", "credential", "secret",
    "migration", "production", "prod config", "security", "destructive", "private key",
}
ARCH_KEYWORDS = {"architecture", "boundary", "dependency direction", "new dependency", "shared type", "public api"}
USER_AMBIGUITY = {"unknown", "unclear", "ambiguous", "maybe", "tbd", "conflict"}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def truthy(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8-sig"))


def keyword_hits(text: str, words: set[str]) -> list[str]:
    low = text.lower()
    return sorted(w for w in words if w in low)


def decide(args: argparse.Namespace, data: dict) -> tuple[int, list[str], list[str], list[str]]:
    task_text = " ".join([args.task or "", json.dumps(data, ensure_ascii=False)]).lower()
    surface_hits = set(args.surface or []) | set(data.get("surfaces", [])) | set(keyword_hits(task_text, SURFACE_KEYWORDS))
    high_risk_hits = set(args.risk or []) | set(data.get("risks", [])) | set(keyword_hits(task_text, HIGH_RISK_KEYWORDS))
    arch_hits = set(keyword_hits(task_text, ARCH_KEYWORDS))
    ambiguity_hits = set(keyword_hits(task_text, USER_AMBIGUITY))
    projected_files = args.projected_files if args.projected_files is not None else int(data.get("projected_file_count", 0) or 0)
    changed_surface_count = args.changed_surface_count if args.changed_surface_count is not None else len(surface_hits)
    shared_api = truthy(args.shared_api_impact) or truthy(data.get("shared_api_impact"))
    architecture_uncertain = truthy(args.architecture_uncertainty) or bool(arch_hits & {"architecture", "boundary", "dependency direction"})
    test_unknown = args.test_availability == "unknown" or str(data.get("test_availability", "")).lower() == "unknown"
    rollback_hard = args.rollback_ease == "hard" or str(data.get("rollback_ease", "")).lower() == "hard"
    patterns_missing = args.existing_pattern_availability == "unknown" or str(data.get("existing_pattern_availability", "")).lower() == "unknown"
    owned_unclear = args.owned_paths_clarity == "unclear" or str(data.get("owned_paths_clarity", "")).lower() == "unclear"
    behavior_ambiguous = truthy(args.user_facing_behavior_ambiguity) or bool(ambiguity_hits)

    rationale: list[str] = []
    blocked: list[str] = []

    if high_risk_hits:
        rationale.append("high_risk_signal:" + ",".join(sorted(high_risk_hits)))
        blocked.append("no_lightweight_path_for_high_risk")
        return 4, rationale, required_gates(4), blocked
    if rollback_hard:
        rationale.append("rollback_hard")
        return 4, rationale, required_gates(4), ["rollback_requires_high_risk_controls"]

    if projected_files > 8:
        rationale.append(f"projected_file_count>{projected_files}")
    if architecture_uncertain:
        rationale.append("architecture_uncertainty")
    if test_unknown:
        rationale.append("test_availability_unknown")
    if patterns_missing:
        rationale.append("existing_pattern_unknown")
    if owned_unclear:
        rationale.append("owned_paths_unclear")
    if behavior_ambiguous:
        rationale.append("user_facing_behavior_ambiguity_or_unknown")
    if any(x in task_text for x in ["proc", "processor", "data-source", "data source"]):
        rationale.append("proc_or_data_source_signal")

    if projected_files > 8 or architecture_uncertain or test_unknown or patterns_missing or owned_unclear or behavior_ambiguous or "proc_or_data_source_signal" in rationale:
        return 3, rationale, required_gates(3), blocked

    if shared_api or changed_surface_count >= 2 or surface_hits:
        if shared_api:
            rationale.append("shared_type_or_api_impact")
        if changed_surface_count >= 2:
            rationale.append(f"changed_surface_count={changed_surface_count}")
        if surface_hits:
            rationale.append("surfaces:" + ",".join(sorted(surface_hits)))
        return 2, rationale, required_gates(2), blocked

    if projected_files <= 1 and not args.behavior_change:
        rationale.append("no_behavior_change_or_single_file_micro_edit")
        return 0, rationale, required_gates(0), ["high_risk_paths_forbidden"]

    rationale.append("small_existing_pattern_change")
    return 1, rationale, required_gates(1), blocked


def required_gates(level: int) -> list[str]:
    gates = {
        0: ["high_risk_path_guard", "diff_summary"],
        1: ["mini_obligation_check", "targeted_test", "mechanical_review"],
        2: ["goal_lite", "obligation_ledger", "gpt_planner_approval", "quality_gate", "gpt_reviewer"],
        3: ["goal_contract", "root_branch", "fractal_decomposition", "parent_aggregation", "integration_gate"],
        4: ["full_governance", "adr_gate", "security_gate", "release_readiness", "rollback_plan", "human_gate_if_required"],
    }
    merged: list[str] = []
    for i in range(level + 1):
        for gate in gates[i]:
            if gate not in merged:
                merged.append(gate)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify AI-native governance intensity for a run.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--goal-id", default="unknown")
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--task", default="")
    parser.add_argument("--input")
    parser.add_argument("--output")
    parser.add_argument("--changed-surface-count", type=int)
    parser.add_argument("--projected-files", type=int)
    parser.add_argument("--surface", action="append", default=[])
    parser.add_argument("--risk", action="append", default=[])
    parser.add_argument("--shared-api-impact")
    parser.add_argument("--architecture-uncertainty")
    parser.add_argument("--test-availability", choices=["available", "unknown", "none"], default="available")
    parser.add_argument("--rollback-ease", choices=["easy", "moderate", "hard"], default="easy")
    parser.add_argument("--existing-pattern-availability", choices=["available", "unknown", "none"], default="available")
    parser.add_argument("--owned-paths-clarity", choices=["clear", "unclear"], default="clear")
    parser.add_argument("--user-facing-behavior-ambiguity")
    parser.add_argument("--behavior-change", action="store_true")
    parser.add_argument("--created-by-mode", default="agent-orchestrator")
    parser.add_argument("--model", default="GPT-5.5")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = load_json(args.input)
    level, rationale, gates, blocked = decide(args, data)
    report = {
        "schema_version": "1.0",
        "run_id": args.run_id,
        "goal_id": args.goal_id,
        "branch_id": args.branch_id,
        "created_by_mode": args.created_by_mode,
        "model": args.model,
        "created_at": now(),
        "input_artifacts": [args.input] if args.input else [],
        "output_artifacts": ["governance-intensity"],
        "gate_status": "pass",
        "level": level,
        "level_name": LEVEL_NAMES[level],
        "rationale": rationale,
        "required_gates": gates,
        "triggered_gates": [],
        "blocked_shortcuts": blocked,
    }
    target = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "governance-intensity.json"
    if not args.dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
