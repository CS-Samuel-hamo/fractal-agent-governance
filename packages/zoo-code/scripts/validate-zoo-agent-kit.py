#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT_VERSION = "0.3.7"
EXPECTED_MODES = {
    "agent-orchestrator", "agent-planner", "agent-branch-manager", "agent-executor",
    "agent-reviewer", "agent-integrator", "agent-curator", "agent-project-profiler",
    "agent-plan-drafter", "agent-branch-clerk", "agent-mechanical-reviewer",
    "agent-integration-clerk", "agent-curator-draft",
}
REQUIRED_FILES = [
    "AGENTS.md", "README.md", "CODEX_GLOBAL_INSTALL_PROMPT.md", ".roomodes",
    ".roo/commands/agent-run.md", ".roo/commands/goal.md", ".roo/commands/status.md", ".roo/commands/risk.md",
    ".roo/commands/loop.md", ".roo/commands/escalate.md", ".roo/commands/fallback.md", ".roo/commands/decision.md",
    ".roo/commands/release.md", ".roo/commands/incident.md", ".roo/commands/lesson.md",
    ".roo/commands/evolve.md", ".roo/commands/regression.md", ".roo/commands/eval.md",
    ".roo/rules/06-ai-native-adaptive-governance.md", ".roo/rules/07-governance-intensity-routing.md",
    ".roo/rules/08-triggered-gates-policy.md",
    ".roo/rules/24-codebase-indexing-for-pattern-discovery.md", ".roo/rules/54-checkpoint-runtime.md",
    ".roo/rules/56-git-worktree-runtime.md", ".roo/rules/63-diagnostics-quality-gate.md",
    ".roo/rules/15-goal-contract.md", ".roo/rules/20-fractal-branch-agent-protocol.md", ".roo/rules/25-model-routing-policy.md",
    ".roo/rules/26-implicit-work-discovery-policy.md", ".roo/rules/32-delivery-management.md",
    ".roo/rules/35-anti-local-optimization-loop.md", ".roo/rules/35-loop-budget-and-convergence.md",
    ".roo/rules/42-risk-management.md", ".roo/rules/45-escalation-and-fallback.md",
    ".roo/rules/05-runtime-backbone.md", ".roo/rules/52-learning-loop-governance.md", ".roo/rules/55-closed-loop-runtime.md",
    ".roo/rules/57-parallel-branch-execution.md", ".roo/rules/60-code-quality-gates.md",
    ".roo/rules/70-security-and-data-governance.md", ".roo/rules/75-human-exception-policy.md",
    ".roo/rules/80-testing-standards.md", ".roo/rules/82-qa-strategy.md",
    ".roo/rules/90-architecture-boundaries.md", ".roo/rules/92-architecture-review-and-adr.md",
    ".roo/rules/95-release-governance.md", ".roo/rules/96-operational-readiness.md",
    ".roo/rules-agent-executor/02-obligation-expansion.md", ".roo/rules-agent-reviewer/02-obligation-coverage-review.md",
    ".roo/rules-agent-mechanical-reviewer/02-obligation-ledger-check.md",
    ".roo/rules-agent-curator/02-lesson-promotion-policy.md",
    ".roo/rules-agent-curator-draft/02-lesson-candidate-drafting.md",
    ".roo/rules-agent-orchestrator/00-runtime-state-machine.md",
    ".roo/rules-agent-orchestrator/06-parallel-branch-scheduling.md", ".roo/rules-agent-orchestrator/06-worktree-scheduling.md",
    ".roo/rules-agent-branch-manager/02-parallel-branch-safety.md",
    ".roo/rules-agent-integrator/02-merge-queue-policy.md",
    "docs/agent-governance/professional-sdlc-role-map.md",
    "docs/agent-governance/learning-loop.md", "docs/agent-governance/lesson-store-schema.md",
    "docs/agent-governance/skill-evolution-policy.md", "docs/agent-governance/governance-regression-policy.md",
    "docs/agent-governance/skill-versioning-policy.md", "docs/agent-governance/deprecation-policy.md",
    "docs/agent-governance/parallel-branch-execution-policy.md", "docs/agent-governance/branch-scheduler-schema.md",
    "docs/agent-governance/path-lock-policy.md", "docs/agent-governance/merge-queue-policy.md",
    "docs/agent-governance/integration-backbone.md", "docs/agent-governance/runtime-artifact-map.md",
    "docs/agent-governance/state-transition-policy.md",
    "docs/agent-governance/zoo-boomerang-vs-fractal-governance.md",
    "docs/agent-governance/fractal-recursive-decomposition-runtime.md",
    "docs/agent-governance/fractal-depth-control.md", "docs/agent-governance/needs-decomposition-policy.md",
    "docs/agent-governance/git-worktree-runtime.md", "docs/agent-governance/worktree-branch-lifecycle.md",
    "docs/agent-governance/checkpoint-runtime-policy.md", "docs/agent-governance/diagnostics-quality-gate.md",
    "docs/agent-governance/codebase-indexing-integration.md",
    "docs/agent-governance/ai-native-governance-principles.md",
    "docs/agent-governance/governance-intensity-levels.md",
    "docs/agent-governance/adaptive-gate-policy.md", "docs/agent-governance/feedback-control-loop.md",
    "docs/agent-governance/parallel-exploration-vs-integration.md",
    "docs/agent-governance/evaluation-system.md", "docs/agent-governance/eval-suite-schema.md",
    "docs/agent-governance/eval-metrics.md", "docs/agent-governance/eval-case-authoring.md",
    "docs/agent-governance/implicit-work-discovery.md", "docs/agent-governance/obligation-ledger-schema.md",
    "docs/agent-governance/impact-surface-taxonomy.md", "docs/agent-governance/deepseek-execution-compensation-policy.md",
    "docs/agent-governance/goal-contract.md", "docs/agent-governance/product-intake-template.md",
    "docs/agent-governance/delivery-management.md", "docs/agent-governance/risk-register-policy.md",
    "docs/agent-governance/status-report-template.md", "docs/agent-governance/loop-budget-and-convergence.md",
    "docs/agent-governance/escalation-policy.md", "docs/agent-governance/fallback-ladder.md",
    "docs/agent-governance/problem-classifier.md", "docs/agent-governance/architecture-review-policy.md",
    "docs/agent-governance/adr-template.md", "docs/agent-governance/decision-record-policy.md",
    "docs/agent-governance/qa-strategy.md", "docs/agent-governance/test-plan-template.md",
    "docs/agent-governance/regression-scope-policy.md", "docs/agent-governance/security-governance.md",
    "docs/agent-governance/data-classification-policy.md", "docs/agent-governance/threat-model-template.md",
    "docs/agent-governance/human-exception-policy.md", "docs/agent-governance/release-governance.md",
    "docs/agent-governance/release-readiness-checklist.md", "docs/agent-governance/change-risk-classification.md",
    "docs/agent-governance/rollback-policy.md", "docs/agent-governance/operational-readiness.md",
    "docs/agent-governance/observability-checklist.md", "docs/agent-governance/runbook-template.md",
    "docs/agent-governance/incident-postmortem-template.md", "docs/agent-governance/local-project-rules.md",
    "docs/agent-governance/agents-md-template.md", "docs/agent-governance/project-local-rules-template.md",
    "docs/agent-governance/metrics-policy.md", "docs/agent-governance/evidence-trail-policy.md",
    "scripts/generate-project-profile.py", "scripts/generate-obligation-ledger.py", "scripts/check-obligation-ledger.py",
    "scripts/quality-gate.py", "scripts/check-agent-completion-evidence.py", "scripts/check-fractal-branch-state.py",
    "scripts/init-agent-run.py", "scripts/update-run-ledger.py", "scripts/check-artifact-graph.py",
    "scripts/check-runtime-consistency.py",
    "scripts/check-governance-change.py", "scripts/check-path-locks.py", "scripts/init-goal-contract.py",
    "scripts/classify-governance-intensity.py", "scripts/check-triggered-gates.py",
    "scripts/check-feedback-convergence.py",
    "scripts/create-branch-worktree.py", "scripts/check-worktree-map.py", "scripts/cleanup-worktrees.py",
    "scripts/record-checkpoint-ref.py", "scripts/collect-diagnostics-report.py", "scripts/check-diagnostics-regression.py",
    "scripts/check-goal-coverage.py", "scripts/check-loop-budget.py", "scripts/escalation-classifier.py",
    "scripts/generate-fallback-report.py", "scripts/update-status-board.py", "scripts/check-risk-register.py",
    "scripts/check-adr-required.py", "scripts/check-test-plan.py", "scripts/check-test-adequacy.py",
    "scripts/check-security-gate.py", "scripts/check-human-exception.py", "scripts/check-release-readiness.py",
    "scripts/check-operational-readiness.py", "scripts/generate-local-project-rules.py",
    "scripts/append-run-metrics.py", "scripts/summarize-agent-metrics.py",
    "scripts/extract-lessons.py", "scripts/check-lesson-store.py", "scripts/check-governance-regression.py",
    "scripts/check-skill-versioning.py", "scripts/check-skill-invocations.py", "scripts/check-deprecation-candidates.py",
    "scripts/check-parallel-branch-safety.py", "scripts/update-merge-queue.py",
    "scripts/run-evals.py", "scripts/score-eval-run.py", "scripts/generate-eval-report.py",
    "scripts/check-eval-suite.py", "scripts/eval_common.py",
    "launcher/vscode-zoo-agent-run-launcher/package.json", "launcher/vscode-zoo-agent-run-launcher/extension.js",
]
REQUIRED_SKILLS = [
    ".roo/skills-agent-executor/project-profile-discovery/SKILL.md",
    ".roo/skills-agent-executor/existing-pattern-mining/SKILL.md",
    ".roo/skills-agent-executor/language-specific-code-style/SKILL.md",
    ".roo/skills-agent-executor/implicit-work-discovery/SKILL.md",
    ".roo/skills-agent-executor/obligation-expansion/SKILL.md",
    ".roo/skills-agent-reviewer/security-review/SKILL.md",
    ".roo/skills-agent-reviewer/test-quality-review/SKILL.md",
    ".roo/skills-agent-reviewer/architecture-boundary-review/SKILL.md",
    ".roo/skills-agent-reviewer/fractal-aggregation-review/SKILL.md",
    ".roo/skills-agent-reviewer/obligation-coverage-review/SKILL.md",
    ".roo/skills-agent-reviewer/architecture-decision-review/SKILL.md",
    ".roo/skills-agent-reviewer/test-adequacy-review/SKILL.md",
    ".roo/skills-agent-reviewer/operational-readiness-review/SKILL.md",
    ".roo/skills-agent-mechanical-reviewer/mechanical-review/SKILL.md",
    ".roo/skills-agent-mechanical-reviewer/obligation-ledger-check/SKILL.md",
    ".roo/skills-agent-planner/test-strategy-planning/SKILL.md",
    ".roo/skills-agent-integrator/release-readiness-review/SKILL.md",
    ".roo/skills-agent-curator/incident-postmortem/SKILL.md",
    ".roo/skills-agent-curator-draft/lesson-extraction/SKILL.md",
    ".roo/skills-agent-curator-draft/skill-change-proposal/SKILL.md",
    ".roo/skills-agent-curator/governance-regression-review/SKILL.md",
    ".roo/skills-agent-curator/governance-deprecation-review/SKILL.md",
]
MODE_RE = re.compile(r"(?m)^-\s+slug:\s*([A-Za-z0-9-]+)\s*$")
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
EXPECTED_EVAL_SUITES = {
    "implicit-work-discovery", "integration-surface", "fractal-decomposition", "routing",
    "review-quality", "learning-loop", "parallel-branch",
}


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    sys.exit(1)


def parse_fm(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path.relative_to(ROOT)} missing frontmatter")
    end = text.find("\n---", 4)
    if end < 0:
        fail(f"{path.relative_to(ROOT)} unclosed frontmatter")
    data: dict[str, str] = {}
    for line in text[4:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            data[k.strip()] = v.strip().strip("'\"")
    return data


def main() -> None:
    for rel in REQUIRED_FILES + REQUIRED_SKILLS:
        if not (ROOT / rel).exists():
            fail(f"missing {rel}")
    slugs = set(MODE_RE.findall((ROOT / ".roomodes").read_text(encoding="utf-8")))
    if slugs != EXPECTED_MODES:
        fail(f"mode mismatch expected={sorted(EXPECTED_MODES)} actual={sorted(slugs)}")
    skills = sorted((ROOT / ".roo").glob("skills-*/**/SKILL.md"))
    for sf in skills:
        fm = parse_fm(sf)
        name = fm.get("name", "")
        if name != sf.parent.name:
            fail(f"{sf.relative_to(ROOT)} name does not match directory")
        if not SKILL_NAME_RE.fullmatch(name):
            fail(f"invalid skill name {name}")
        if not fm.get("description"):
            fail(f"{sf.relative_to(ROOT)} missing description")
        for field in ["version", "scope", "applies_to", "last_updated", "deprecated_by"]:
            if field not in fm:
                fail(f"{sf.relative_to(ROOT)} missing {field}")
        if not fm.get("version"):
            fail(f"{sf.relative_to(ROOT)} missing version value")
    agent_run = (ROOT / ".roo/commands/agent-run.md").read_text(encoding="utf-8").lower()
    for phrase in ["goal contract", "obligation ledger", "feedback convergence", "fallback", "append metrics", "extract lessons", "governance regression", "deprecation candidates", "branch-schedule", "path-locks", "merge-queue", "worktree-map", "checkpoint", "diagnostics", "codebase indexing", "fractal recursive", "needs_decomposition", "boomerang", "only main workflow bus", "goal -> run -> project context", "no artifact, no transition", "governance intensity routing", "triggered gates", "level 0 micro edit", "level 4 high-risk", "parallel exploration"]:
        if phrase not in agent_run:
            fail(f"agent-run missing flow phrase: {phrase}")
    eval_root = ROOT / "evals"
    if not eval_root.exists():
        fail("missing evals directory")
    suites = {p.name for p in eval_root.iterdir() if p.is_dir()}
    missing_suites = EXPECTED_EVAL_SUITES - suites
    if missing_suites:
        fail(f"missing eval suites: {sorted(missing_suites)}")
    for suite in EXPECTED_EVAL_SUITES:
        count = len(list((eval_root / suite).glob("*.yaml")))
        if count < 3:
            fail(f"eval suite {suite} has fewer than 3 cases")
    suite_check = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check-eval-suite.py"), "--suite", "full", "--root", str(eval_root)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if suite_check.returncode != 0:
        fail("check-eval-suite.py failed: " + suite_check.stdout.strip())
    pkg = json.loads((ROOT / "launcher/vscode-zoo-agent-run-launcher/package.json").read_text(encoding="utf-8"))
    if pkg.get("version") != KIT_VERSION:
        fail(f"launcher package version must be {KIT_VERSION}, got {pkg.get('version')!r}")
    print(f"[ OK ] validated v3.7 pack: {len(slugs)} modes, {len(skills)} skills, required commands/rules/docs/scripts, launcher {KIT_VERSION}")


if __name__ == "__main__":
    main()
