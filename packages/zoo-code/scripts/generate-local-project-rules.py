#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def safe_write(path: Path, text: str, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        return "skipped_existing"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "written"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=".zoo-agent/project-profile.json")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    profile_path = Path(args.profile)
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig")) if profile_path.exists() else {}
    commands = profile.get("commands", {}) if isinstance(profile, dict) else {}
    files = {
        "AGENTS.md": f"# Project Agent Rules\n\nlanguage: {profile.get('language', 'unknown')}\nframework: {profile.get('framework', 'unknown')}\npackage_manager: {profile.get('package_manager', 'unknown')}\n\nDo not read secrets. Unknown facts stay unknown.\n",
        ".roo/rules/00-project-context.md": f"# Project Context\n\nsource_roots: {profile.get('source_roots', 'unknown')}\ntest_roots: {profile.get('test_roots', 'unknown')}\n",
        ".roo/rules/10-project-architecture.md": "# Project Architecture\n\narchitecture: unknown\nDo not invent architecture boundaries.\n",
        ".roo/rules/20-project-quality-commands.md": f"# Project Quality Commands\n\ntest: {commands.get('test', 'unknown')}\nlint: {commands.get('lint', 'unknown')}\ntypecheck: {commands.get('typecheck', 'unknown')}\nbuild: {commands.get('build', 'unknown')}\n",
        ".roo/rules/30-risk-zones.md": "# Risk Zones\n\nauth: unknown\ndata: unknown\npayments: unknown\nmigrations: unknown\ngenerated_files: unknown\nproduction_config: unknown\n",
        ".roo/rules-agent-executor/10-project-integration-surfaces.md": "# Project Integration Surfaces\n\nroutes: unknown\nregistries: unknown\nfactories: unknown\nproviders: unknown\n",
        ".roo/rules-agent-reviewer/10-project-review-hotspots.md": "# Project Review Hotspots\n\nsecurity: unknown\narchitecture: unknown\ntesting: unknown\nrelease: unknown\n",
    }
    report = {}
    for rel, text in files.items():
        if args.dry_run:
            report[rel] = "would_write" if args.overwrite or not Path(rel).exists() else "would_skip_existing"
        else:
            report[rel] = safe_write(Path(rel), text, args.overwrite)
    print(json.dumps({"status": "pass", "files": report}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
