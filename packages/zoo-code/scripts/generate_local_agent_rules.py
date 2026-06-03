#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates" / "project-local" / "roo-rules"


def as_text(value) -> str:
    if not value:
        return "unknown"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "unknown"
    return str(value)


def render(template: str, profile: dict, goal: str) -> str:
    mapping = {
        "PROJECT_ROOT": profile.get("project_root", ""),
        "PROJECT_TYPE": profile.get("project_type", "unknown"),
        "GOAL": goal or "unknown",
        "LANGUAGE": as_text(profile.get("language")),
        "FRAMEWORK": as_text(profile.get("framework")),
        "UNKNOWNS": as_text(profile.get("unknowns")),
        "SOURCE_ROOTS": as_text(profile.get("source_roots")),
        "TEST_ROOTS": as_text(profile.get("test_roots")),
        "API_ENTRYPOINTS": as_text(profile.get("api_entrypoints")),
        "REGISTRY_PATTERNS": as_text(profile.get("registry_patterns")),
        "DOMAIN_TYPE_LOCATIONS": as_text(profile.get("domain_type_locations")),
        "TEST_COMMANDS": as_text(profile.get("test_commands")),
        "LINT_COMMANDS": as_text(profile.get("lint_commands")),
        "TYPECHECK_COMMANDS": as_text(profile.get("typecheck_commands")),
        "BUILD_COMMANDS": as_text(profile.get("build_commands")),
        "FORBIDDEN_PATHS": as_text(profile.get("forbidden_paths")),
        "RISK_ZONES": as_text(profile.get("risk_zones")),
    }
    for key, value in mapping.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def generate(project: Path, profile: dict, goal: str, suffix: str) -> list[Path]:
    output_dir = project / ".roo" / "rules"
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for src in TEMPLATE_DIR.glob("*.md"):
        target = output_dir / f"{src.name}{suffix}"
        text = render(src.read_text(encoding="utf-8"), profile, goal)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate project-local Zoo/Roo rule drafts.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--profile", default="")
    parser.add_argument("--goal", default="")
    parser.add_argument("--suffix", default=".new")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    profile_path = Path(args.profile) if args.profile else project / ".zoo-agent" / "project-profile.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    for path in generate(project, profile, args.goal, args.suffix):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
