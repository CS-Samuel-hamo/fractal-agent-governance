#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_ROOT = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "ROADMAP.md",
]

REQUIRED_PACKAGE = [
    "packages/zoo-code/README.md",
    "packages/zoo-code/.roomodes",
    "packages/zoo-code/.roo/commands/agent-run.md",
    "packages/zoo-code/.roo/rules",
    "packages/zoo-code/scripts",
]

REQUIRED_EXAMPLES = [
    "examples/implicit-work-discovery",
    "examples/fractal-branch-summary",
    "examples/proc-data-source-mismatch",
    "examples/worktree-parallel-exploration",
]

REQUIRED_EVALS = [
    "evals/implicit-work-discovery/cases",
    "evals/integration-surface/cases",
    "evals/fractal-decomposition/cases",
    "evals/routing/cases",
    "evals/review-quality/cases",
    "evals/parallel-branch/cases",
]

REQUIRED_LAUNCH = [
    "launch/zoo-discord-post.md",
    "launch/reddit-zoo-code.md",
    "launch/reddit-roo-code.md",
    "launch/github-discussion-proposal.md",
    "launch/linkedin-post.md",
    "launch/hackernews-showhn.md",
    "launch/chinese-post.md",
]

REQUIRED_MEDIA = [
    "media/architecture.mmd",
    "media/demo-script-implicit-work-discovery.md",
    "media/demo-script-fractal-decomposition.md",
    "media/demo-script-worktree-parallelism.md",
]

README_SECTIONS = [
    "Problem",
    "What This Project Provides",
    "Architecture",
    "Quick Start",
    "Demos",
    "Why This Is Different",
    "Installation",
    "Safety",
    "Limitations",
    "Roadmap",
    "Not Official Zoo Code Disclaimer",
]

FORBIDDEN_PATTERNS = [
    ".env",
    ".env.*",
    "*.key",
    "*.pem",
    "secrets",
    "secrets/*",
    "credentials",
    "credentials/*",
    "backups",
    "backups/*",
    ".zoo-agent/runs/*",
    ".zoo-agent/metrics/*",
    ".zoo-agent/evals/*",
]


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def require_path(rel: str) -> None:
    if not (ROOT / rel).exists():
        fail(f"missing {rel}")


def check_forbidden_files() -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for pattern in FORBIDDEN_PATTERNS:
            if fnmatch.fnmatch(rel, pattern):
                fail(f"forbidden file pattern: {rel}")


def check_eval_cases() -> None:
    required_keys = [
        "case_id:",
        "category:",
        "input_task:",
        "fixture:",
        "expected_obligations:",
        "expected_surfaces:",
        "expected_routing:",
        "expected_decomposition:",
        "expected_escalations:",
        "forbidden_actions:",
        "scoring:",
    ]
    for suite in REQUIRED_EVALS:
        case_dir = ROOT / suite
        cases = sorted(case_dir.glob("*.yaml"))
        if not cases:
            fail(f"missing eval cases in {suite}")
        for case in cases:
            text = case.read_text(encoding="utf-8")
            missing = [key for key in required_keys if key not in text]
            if missing:
                fail(f"{case.relative_to(ROOT)} missing keys: {missing}")


def main() -> None:
    for rel in REQUIRED_ROOT + REQUIRED_PACKAGE + REQUIRED_EXAMPLES + REQUIRED_EVALS + REQUIRED_LAUNCH + REQUIRED_MEDIA:
        require_path(rel)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for section in README_SECTIONS:
        if section not in readme:
            fail(f"README missing section: {section}")
    if "not an official zoo code project" not in readme.lower():
        fail("README missing not-official disclaimer")

    package_readme = (ROOT / "packages/zoo-code/README.md").read_text(encoding="utf-8")
    for phrase in [
        "This package contains the Zoo Code adapter.",
        "global",
        "not copied into business repositories",
        "dry-run",
        "Reload VS Code / Zoo Code",
        "provider profiles",
    ]:
        if phrase not in package_readme:
            fail(f"packages/zoo-code/README.md missing phrase: {phrase}")

    check_eval_cases()
    check_forbidden_files()
    print("[ OK ] open-source package validation passed")


if __name__ == "__main__":
    main()
