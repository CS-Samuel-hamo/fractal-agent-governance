#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_VERSION = "0.3.11-governance-closure-codex-parallel"
LAUNCHER_PACKAGE_VERSION = "0.3.11"

EXPECTED_MODES = {
    "agent-orchestrator",
    "agent-planner",
    "agent-executor",
    "agent-reviewer",
    "agent-integrator",
}

RETIRED_VISIBLE_MODES = {
    "agent-branch-manager",
    "agent-curator",
    "agent-project-profiler",
    "agent-plan-drafter",
    "agent-branch-clerk",
    "agent-mechanical-reviewer",
    "agent-integration-clerk",
    "agent-curator-draft",
    "agent-codex-worker",
}

REQUIRED_FILES = [
    "AGENTS.md",
    "README.md",
    ".roomodes",
    ".roo/commands/agent-run.md",
    ".roo/commands/progress.md",
    ".roo/commands/redirect.md",
    ".roo/commands/codex-task.md",
    ".roo/commands/agent-bootstrap.md",
    ".roo/commands/codex-run.md",
    ".roo/commands/codex-ingest.md",
    ".roo/commands/codex-review.md",
    ".roo/rules/07-governance-intensity-routing.md",
    ".roo/rules/10-adaptive-execution-routing.md",
    ".roo/rules/52-learning-loop-governance.md",
    ".roo/rules-agent-orchestrator/07-executor-selection.md",
    ".roo/rules-agent-planner/03-fast-path-and-codex-routing.md",
    ".roo/rules-agent-planner/20-fractal-branch-governance.md",
    ".roo/rules-agent-executor/20-codex-worker-bridge.md",
    ".roo/rules-agent-reviewer/03-codex-result-review.md",
    ".roo/rules-agent-reviewer/20-mechanical-reviewer-fold-in.md",
    ".roo/rules-agent-integrator/03-codex-worker-merge-policy.md",
    ".roo/rules-agent-integrator/20-governance-curation-fold-in.md",
    ".roo/rules-agent-curator/02-lesson-promotion-policy.md",
    ".roo/rules-agent-codex-worker/01-codex-task-pack.md",
    ".roo/skills-agent-codex-worker/codex-task-pack-generation/SKILL.md",
    ".roo/skills-agent-codex-worker/codex-result-ingestion/SKILL.md",
    "docs/agent-governance/final-operating-model.md",
    "docs/agent-governance/zoo-as-governance-layer.md",
    "docs/agent-governance/codex-cli-as-execution-worker.md",
    "docs/agent-governance/adaptive-fast-path-policy.md",
    "docs/agent-governance/codex-cli-worker-bridge.md",
    "docs/agent-governance/codex-task-pack-schema.md",
    "docs/agent-governance/executor-selection-policy.md",
    "docs/agent-governance/scope-guard-policy.md",
    "docs/agent-governance/codex-cli-install-and-auth.md",
    "docs/agent-governance/codex-cli-sandbox-policy.md",
    "docs/agent-governance/project-bootstrap.md",
    "docs/agent-governance/existing-project-onboarding.md",
    "docs/agent-governance/new-project-onboarding.md",
    "docs/agent-governance/bootstrap-safety-policy.md",
    "docs/agent-governance/one-click-project-setup.md",
    "docs/agent-governance/learning-trigger-policy.md",
    "docs/agent-governance/executor-benchmark-policy.md",
    "docs/agent-governance/zoo-codex-hybrid-eval.md",
    "templates/codex/AGENTS.md",
    "templates/codex/TASKS.yaml",
    "templates/codex/ACCEPTANCE.md",
    "templates/codex/CODEX_TASK_PROMPT.md",
    "templates/codex/PROGRESS.md",
    "templates/codex/BLOCKERS.md",
    "templates/codex/config.toml.example",
    "templates/codex/rules/default.rules.example",
    "templates/project-local/AGENTS.md",
    "templates/project-local/gitignore.agent.patch",
    "templates/project-local/roo-rules/00-project-context.md",
    "templates/project-local/roo-rules/10-project-architecture.md",
    "templates/project-local/roo-rules/20-project-quality-commands.md",
    "templates/project-local/roo-rules/30-risk-zones.md",
    "scripts/classify-task-complexity.py",
    "scripts/select-executor.py",
    "scripts/check-fast-path-eligibility.py",
    "scripts/generate-codex-task-pack.py",
    "scripts/check-codex-scope.py",
    "scripts/run-codex-worker.py",
    "scripts/collect-codex-result.py",
    "scripts/check-codex-evidence.py",
    "scripts/render-codex-task-prompt.py",
    "scripts/compare-codex-zoo-result.py",
    "scripts/bootstrap_project.py",
    "scripts/check_project_readiness.py",
    "scripts/generate_local_agent_rules.py",
    "scripts/generate_project_gitignore_patch.py",
    "scripts/create_first_codex_smoke_task.py",
    "scripts/run-executor-benchmark.py",
    "scripts/score-executor-benchmark.py",
    "scripts/generate-executor-comparison-report.py",
    "scripts/install-global-zoo-agent-kit.py",
    "launcher/vscode-zoo-agent-run-launcher/package.json",
    "launcher/vscode-zoo-agent-run-launcher/extension.js",
]

REQUIRED_LAUNCHER_COMMANDS = {
    "agentGovernance.generateCodexTaskPack",
    "agentGovernance.runCodexWorker",
    "agentGovernance.openCodexTaskPrompt",
    "agentGovernance.copyCodexTaskPrompt",
    "agentGovernance.collectCodexResult",
    "agentGovernance.runCodexScopeGuard",
    "agentGovernance.openCodexResult",
    "agentGovernance.runExecutorBenchmark",
    "agentGovernance.bootstrapProject",
    "agentGovernance.openBootstrapReport",
    "agentGovernance.rerunBootstrap",
    "agentGovernance.commitBootstrapFiles",
    "agentGovernance.openProjectReadiness",
}


def fail(message: str) -> None:
    print(f"[FAIL] {message}")
    sys.exit(1)


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path.relative_to(ROOT)} missing frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        fail(f"{path.relative_to(ROOT)} unclosed frontmatter")
    result: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip().strip("'\"")
    return result


def require_text(path: Path, phrases: list[str]) -> None:
    text = path.read_text(encoding="utf-8").lower()
    for phrase in phrases:
        if phrase.lower() not in text:
            fail(f"{path.relative_to(ROOT)} missing phrase: {phrase}")


def main() -> int:
    missing = [rel for rel in REQUIRED_FILES if not (ROOT / rel).exists()]
    if missing:
        fail("missing required files: " + ", ".join(missing))

    roomodes = (ROOT / ".roomodes").read_text(encoding="utf-8")
    slugs = set(re.findall(r"(?m)^-\s+slug:\s*([A-Za-z0-9-]+)\s*$", roomodes))
    missing_modes = EXPECTED_MODES - slugs
    if missing_modes:
        fail("missing modes: " + ", ".join(sorted(missing_modes)))
    retired_modes = RETIRED_VISIBLE_MODES & slugs
    if retired_modes:
        fail("retired modes still visible: " + ", ".join(sorted(retired_modes)))

    for skill in (ROOT / ".roo").glob("skills-*/**/SKILL.md"):
        fm = parse_frontmatter(skill)
        for key in ("name", "description", "version"):
            if not fm.get(key):
                fail(f"{skill.relative_to(ROOT)} missing {key}")

    require_text(ROOT / ".roo/commands/agent-run.md", [
        "task complexity",
        "select executor",
        "Codex Task Pack",
        "fast path skip rules",
        "learning trigger",
        "scope guard",
        "merge queue",
        "Project Bootstrap",
        "/agent-bootstrap",
        "project-readiness.json",
    ])
    require_text(ROOT / ".roo/rules/00-core-agent-contract.md", [
        "Implicit Agent Run Dispatch",
        "treat every ordinary user request as `/agent-run <verbatim user request>`",
        "Do not pre-classify whether the request is coding",
        "`/agent-run` is the default workflow bus",
    ])
    require_text(ROOT / ".roo/rules/07-governance-intensity-routing.md", ["Level 0", "Level 4", "adaptive fast path"])
    require_text(ROOT / ".roo/rules/10-adaptive-execution-routing.md", ["executor-selection.json", "Level 3", "Level 4"])
    require_text(ROOT / ".roo/rules/52-learning-loop-governance.md", ["Do not learn on every step", "scope violation"])
    require_text(ROOT / ".roo/rules-agent-planner/20-fractal-branch-governance.md", ["Planner absorbs the former branch-manager capability"])
    require_text(ROOT / ".roo/rules-agent-executor/20-codex-worker-bridge.md", ["Executor absorbs the former Codex worker bridge capability"])
    require_text(ROOT / ".roo/rules-agent-reviewer/20-mechanical-reviewer-fold-in.md", ["Reviewer absorbs the former mechanical-reviewer capability"])
    require_text(ROOT / ".roo/rules-agent-integrator/20-governance-curation-fold-in.md", ["Integrator absorbs the former curator"])

    package = json.loads((ROOT / "launcher/vscode-zoo-agent-run-launcher/package.json").read_text(encoding="utf-8"))
    if package.get("version") != LAUNCHER_PACKAGE_VERSION:
        fail(f"launcher package version must be {LAUNCHER_PACKAGE_VERSION}, got {package.get('version')!r}")
    commands = {item.get("command") for item in package.get("contributes", {}).get("commands", [])}
    missing_commands = REQUIRED_LAUNCHER_COMMANDS - commands
    if missing_commands:
        fail("launcher missing commands: " + ", ".join(sorted(missing_commands)))
    extension_text = (ROOT / "launcher/vscode-zoo-agent-run-launcher/extension.js").read_text(encoding="utf-8")
    for phrase in REQUIRED_LAUNCHER_COMMANDS:
        if phrase not in extension_text:
            fail(f"launcher extension missing registration: {phrase}")

    eval_cases = list((ROOT / "evals/executor-comparison").glob("*.yaml"))
    if len(eval_cases) < 10:
        fail("executor-comparison requires at least 10 eval case templates")

    print(f"[ OK ] validated {KIT_VERSION}: {len(slugs)} modes, {len(eval_cases)} executor evals, Codex bridge assets present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
