#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

AGENT_IGNORE_LINES = [
    "# Agent runtime artifacts",
    ".zoo-agent/runs/",
    ".zoo-agent/evals/",
    ".zoo-agent/metrics/",
    ".zoo-agent/tmp/",
    ".zoo-agent/**/codex-final-message.md",
    ".zoo-agent/**/codex-results/",
    ".zoo-agent/**/codex-tasks/",
    "",
    "# Test/cache artifacts",
    "__pycache__/",
    ".pytest_cache/",
    "*.pyc",
]


def build_patch(project: Path) -> str:
    gitignore = project / ".gitignore"
    existing = set()
    if gitignore.exists():
        existing = {line.strip() for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()}
    additions = [line for line in AGENT_IGNORE_LINES if not line or line.strip() not in existing]
    if not additions:
        return "# .gitignore already contains agent bootstrap ignore rules.\n"
    if gitignore.exists():
        body = "\n".join("+" + line for line in ["", *additions])
        return f"*** Begin Patch\n*** Update File: .gitignore\n@@\n{body}\n*** End Patch\n"
    body = "\n".join("+" + line for line in additions)
    return f"*** Begin Patch\n*** Add File: .gitignore\n{body}\n*** End Patch\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a .gitignore patch for Zoo agent runtime artifacts.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    patch = build_patch(project)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(patch, encoding="utf-8")
        print(output)
    else:
        print(patch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
