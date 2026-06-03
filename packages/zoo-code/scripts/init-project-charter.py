#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def values(items: list[str] | None) -> list[str]:
    return items if items else ["unknown"]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def md_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- unknown"


def charter_data(args: argparse.Namespace, existing: dict[str, Any]) -> dict[str, Any]:
    ts = now()
    return {
        "schema_version": "1.0",
        "generated_by": "init-project-charter.py",
        "project_name": args.project_name,
        "mission": args.mission,
        "target_users": values(args.target_user),
        "non_users": values(args.non_user),
        "product_goals": values(args.product_goal),
        "technical_goals": values(args.technical_goal),
        "non_goals": values(args.non_goal),
        "success_criteria": values(args.success_criteria),
        "quality_bar": values(args.quality_bar),
        "architecture_principles": values(args.architecture_principle),
        "data_security_constraints": values(args.data_security_constraint),
        "operational_constraints": values(args.operational_constraint),
        "risk_tolerance": args.risk_tolerance,
        "human_gates": values(args.human_gate),
        "fallback_abort_conditions": values(args.fallback_abort_condition),
        "decision_owners": values(args.decision_owner),
        "open_questions": values(args.open_question),
        "project_profile_path": ".zoo-agent/project-profile.json",
        "project_map_path": ".zoo-agent/project-map.json",
        "architecture_boundaries_path": ".zoo-agent/architecture-boundaries.json",
        "created_at": existing.get("created_at", ts),
        "updated_at": ts,
    }


def render_md(data: dict[str, Any]) -> str:
    return "\n".join([
        f"# {data['project_name']} Project Charter",
        "",
        "## Mission",
        data["mission"],
        "",
        "## Target Users",
        md_list(data["target_users"]),
        "",
        "## Non-Users",
        md_list(data["non_users"]),
        "",
        "## Product Goals",
        md_list(data["product_goals"]),
        "",
        "## Technical Goals",
        md_list(data["technical_goals"]),
        "",
        "## Non-Goals",
        md_list(data["non_goals"]),
        "",
        "## Success Criteria",
        md_list(data["success_criteria"]),
        "",
        "## Quality Bar",
        md_list(data["quality_bar"]),
        "",
        "## Architecture Principles",
        md_list(data["architecture_principles"]),
        "",
        "## Data And Security Constraints",
        md_list(data["data_security_constraints"]),
        "",
        "## Operational Constraints",
        md_list(data["operational_constraints"]),
        "",
        "## Risk Tolerance",
        data["risk_tolerance"],
        "",
        "## Human Gates",
        md_list(data["human_gates"]),
        "",
        "## Fallback / Abort Conditions",
        md_list(data["fallback_abort_conditions"]),
        "",
        "## Decision Owners",
        md_list(data["decision_owners"]),
        "",
        "## Open Questions",
        md_list(data["open_questions"]),
        "",
        "## Governance Links",
        f"- project_profile: `{data['project_profile_path']}`",
        f"- project_map: `{data['project_map_path']}`",
        f"- architecture_boundaries: `{data['architecture_boundaries_path']}`",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a project charter without reading secrets or editing business code beyond the requested charter files.")
    parser.add_argument("--project-name", default=Path.cwd().name)
    parser.add_argument("--mission", required=True)
    parser.add_argument("--target-user", action="append")
    parser.add_argument("--non-user", action="append")
    parser.add_argument("--product-goal", action="append")
    parser.add_argument("--technical-goal", action="append")
    parser.add_argument("--non-goal", action="append")
    parser.add_argument("--success-criteria", action="append")
    parser.add_argument("--quality-bar", action="append")
    parser.add_argument("--architecture-principle", action="append")
    parser.add_argument("--data-security-constraint", action="append")
    parser.add_argument("--operational-constraint", action="append")
    parser.add_argument("--risk-tolerance", default="unknown")
    parser.add_argument("--human-gate", action="append")
    parser.add_argument("--fallback-abort-condition", action="append")
    parser.add_argument("--decision-owner", action="append")
    parser.add_argument("--open-question", action="append")
    parser.add_argument("--output-json", default=".zoo-agent/project-charter.json")
    parser.add_argument("--output-md", default="docs/project-charter.md")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    out_json = Path(args.output_json)
    out_md = Path(args.output_md)
    existing = load_json(out_json)
    if not args.force and (out_json.exists() or out_md.exists()) and not args.dry_run:
        print(json.dumps({
            "status": "exists",
            "project_charter": str(out_json),
            "project_charter_md": str(out_md),
            "fix": "rerun with --force after reviewing existing charter",
        }, indent=2))
        return 2

    data = charter_data(args, existing)
    md = render_md(data)
    if args.dry_run:
        print(json.dumps({"project_charter": data, "project_charter_md": md}, indent=2))
        return 0
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    print(json.dumps({
        "status": "pass",
        "project_charter": str(out_json),
        "project_charter_md": str(out_md),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
