#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = Path("D:/AI_DEV/temp")


def run(cmd: list[str], cwd: Path, check: bool = True, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    print("$", " ".join(map(str, cmd)))
    try:
        proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    except OSError as error:
        proc = subprocess.CompletedProcess(cmd, 1, f"ERROR: {error}\n")
    print(proc.stdout)
    if check and proc.returncode:
        raise SystemExit(proc.returncode)
    return proc


def assert_run_task_board(repo: Path, run_id: str | None = None) -> None:
    runs_root = repo / ".zoo-agent" / "runs"
    if not runs_root.exists():
        raise SystemExit("missing .zoo-agent/runs after bootstrap")
    runs = [runs_root / run_id] if run_id else sorted(item for item in runs_root.iterdir() if item.is_dir())
    if not runs:
        raise SystemExit("missing bootstrap run directory")
    for run_dir in runs:
        if not (run_dir / "TASKS.md").exists():
            raise SystemExit(f"missing run task board: {run_dir / 'TASKS.md'}")
        if not (run_dir / "task-board.json").exists():
            raise SystemExit(f"missing structured task board: {run_dir / 'task-board.json'}")


def assert_project_task_board(repo: Path) -> None:
    if not (repo / ".zoo-agent" / "current-run.json").exists():
        raise SystemExit("missing .zoo-agent/current-run.json")
    if not (repo / ".zoo-agent" / "TASKS.md").exists():
        raise SystemExit("missing .zoo-agent/TASKS.md")


def main() -> int:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    repo = TEST_ROOT / f"v3.10-codex-cli-worker-smoke-test-{stamp}"
    repo.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.setdefault("CODEX_HOME", str(repo / ".codex-home"))
    Path(env["CODEX_HOME"]).mkdir(parents=True, exist_ok=True)
    print("Smoke repo:", repo)
    print("Smoke CODEX_HOME:", env["CODEX_HOME"])
    run(["git", "init"], repo, env=env)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / "example.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "tests" / "test_example.py").write_text("from src.example import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
    run(["git", "add", "."], repo, env=env)
    run(["git", "commit", "-m", "init"], repo, check=False, env=env)

    classify_simple = run([
        "python", str(ROOT / "scripts" / "classify-task-complexity.py"),
        "--description", "simple bugfix", "--changed-file", "src/example.py", "--format", "json",
    ], repo, env=env)
    simple_data = json.loads(classify_simple.stdout)
    if simple_data["level"] not in (0, 1):
        raise SystemExit("simple bugfix should classify as Level 0/1")

    classify_cross = run([
        "python", str(ROOT / "scripts" / "classify-task-complexity.py"),
        "--description", "cross-module feature touching services and providers", "--file-count", "12", "--format", "json",
    ], repo, env=env)
    cross_data = json.loads(classify_cross.stdout)
    if cross_data["level"] != 3:
        raise SystemExit("cross-module work should classify as Level 3")

    run(["python", str(ROOT / "scripts" / "select-executor.py"), "--run-id", "run-test", "--task-id", "task-l1", "--governance-level", "Level 1", "--format", "json"], repo, env=env)
    run(["python", str(ROOT / "scripts" / "select-executor.py"), "--run-id", "run-test", "--task-id", "task-l3", "--governance-level", "Level 3", "--format", "json"], repo, env=env)
    run(["python", str(ROOT / "scripts" / "select-executor.py"), "--run-id", "run-test", "--task-id", "task-l4", "--governance-level", "Level 4", "--format", "json"], repo, env=env)

    out = repo / ".zoo-agent" / "runs" / "run-test" / "codex-tasks" / "task-001"
    run([
        "python", str(ROOT / "scripts" / "generate-codex-task-pack.py"),
        "--run-id", "run-test",
        "--task-id", "task-001",
        "--objective", "Change add to include a small explanatory comment",
        "--allowed-file", "src/**",
        "--allowed-file", "tests/**",
        "--denied-file", ".env",
        "--denied-file", "pyproject.toml",
        "--acceptance", "Scope guard passes",
        "--test-command", "python -m pytest",
    ], repo, env=env)
    for required in ["AGENTS.md", "TASKS.yaml", "ACCEPTANCE.md", "CODEX_TASK_PROMPT.md", "check_codex_scope.py"]:
        if not (out / required).exists():
            raise SystemExit(f"missing task pack file: {required}")

    (repo / "src" / "example.py").write_text("def add(a, b):\n    # simple integer addition\n    return a + b\n", encoding="utf-8")
    (repo / "src" / "__pycache__").mkdir()
    (repo / "tests" / "__pycache__").mkdir()
    (repo / ".pytest_cache").mkdir()
    (repo / "src" / "__pycache__" / "example.pyc").write_bytes(b"cache")
    (repo / "tests" / "__pycache__" / "test_example.pyc").write_bytes(b"cache")
    run(["python", str(ROOT / "scripts" / "check-codex-scope.py"), "--task-id", "task-001", "--tasks", str(out / "TASKS.yaml")], repo, env=env)

    (repo / "pyproject.toml").write_text("[tool]\n", encoding="utf-8")
    denied = run(["python", str(ROOT / "scripts" / "check-codex-scope.py"), "--task-id", "task-001", "--tasks", str(out / "TASKS.yaml")], repo, check=False, env=env)
    if denied.returncode == 0:
        raise SystemExit("Expected scope guard failure for denied file")

    run([
        "python", str(ROOT / "scripts" / "collect-codex-result.py"),
        "--run-id", "run-test",
        "--task-id", "task-001",
        "--task-dir", str(out),
        "--workspace", str(repo),
    ], repo, check=False, env=env)
    result = repo / ".zoo-agent" / "runs" / "run-test" / "codex-results" / "task-001" / "result.json"
    if not result.exists():
        raise SystemExit("missing collected result.json")
    if not (repo / ".zoo-agent" / "runs" / "run-test" / "artifact-graph.json").exists():
        raise SystemExit("missing artifact graph")

    # Project Bootstrap: existing Git project should not modify business files or overwrite existing governance files.
    (repo / "AGENTS.md").write_text("# Existing AGENTS\n\nDo not overwrite this file.\n", encoding="utf-8")
    existing_profile = repo / ".zoo-agent" / "project-profile.json"
    existing_profile.write_text('{"project_type":"preexisting"}\n', encoding="utf-8")
    legacy_run = repo / ".zoo-agent" / "runs" / "legacy-tasksonly"
    legacy_run.mkdir(parents=True, exist_ok=True)
    legacy_run_tasks = legacy_run / "TASKS.md"
    legacy_run_tasks.write_text("# Legacy Tasks\n\n- keep this human-edited board\n", encoding="utf-8")
    source_before = (repo / "src" / "example.py").read_text(encoding="utf-8")
    run(["python", str(ROOT / "scripts" / "bootstrap_project.py"), "--project", str(repo), "--mode", "existing", "--dry-run"], repo, env=env)
    run(["python", str(ROOT / "scripts" / "bootstrap_project.py"), "--project", str(repo), "--mode", "existing", "--apply"], repo, env=env)
    for required in [
        ".zoo-agent/project-profile.json",
        ".zoo-agent/project-readiness.json",
        ".zoo-agent/bootstrap-report.md",
        ".zoo-agent/project-map.json",
        ".zoo-agent/project-map.md",
        ".zoo-agent/architecture-boundaries.json",
    ]:
        if not (repo / required).exists():
            raise SystemExit(f"missing bootstrap artifact: {required}")
    assert_run_task_board(repo, "run-test")
    assert_run_task_board(repo, "legacy-tasksonly")
    assert_project_task_board(repo)
    if "keep this human-edited board" not in legacy_run_tasks.read_text(encoding="utf-8"):
        raise SystemExit("bootstrap overwrote legacy TASKS.md")
    if (repo / "src" / "example.py").read_text(encoding="utf-8") != source_before:
        raise SystemExit("bootstrap modified existing project business code")
    if "Do not overwrite this file." not in (repo / "AGENTS.md").read_text(encoding="utf-8"):
        raise SystemExit("bootstrap overwrote existing AGENTS.md")
    if not (repo / "AGENTS.md.new").exists():
        raise SystemExit("bootstrap did not draft AGENTS.md.new for existing AGENTS.md")
    if existing_profile.read_text(encoding="utf-8") != '{"project_type":"preexisting"}\n':
        raise SystemExit("bootstrap overwrote existing project-profile.json")
    if not (repo / ".zoo-agent" / "project-profile.json.new").exists():
        raise SystemExit("bootstrap did not draft project-profile.json.new for existing profile")

    # Project Bootstrap: empty new project should create governance shell only.
    new_repo = TEST_ROOT / f"v3.10-project-bootstrap-new-{stamp}"
    new_repo.mkdir(parents=True, exist_ok=False)
    run(["python", str(ROOT / "scripts" / "bootstrap_project.py"), "--project", str(new_repo), "--mode", "new", "--goal", "test project", "--apply"], new_repo, env=env)
    for required in [
        ".git",
        "README.md",
        "AGENTS.md",
        ".gitignore",
        ".zoo-agent/project-profile.json",
        ".zoo-agent/bootstrap-report.md",
        ".zoo-agent/project-map.json",
        ".zoo-agent/project-map.md",
        ".zoo-agent/architecture-boundaries.json",
    ]:
        if not (new_repo / required).exists():
            raise SystemExit(f"missing new project bootstrap artifact: {required}")
    assert_run_task_board(new_repo)
    assert_project_task_board(new_repo)
    if (new_repo / "src").exists() or (new_repo / "app").exists() or (new_repo / "lib").exists():
        raise SystemExit("new project bootstrap generated business module code")

    # Project Bootstrap: existing Git project with no local governance files should create real files, not only .new drafts.
    no_rules_repo = TEST_ROOT / f"v3.10-project-bootstrap-existing-no-rules-{stamp}"
    no_rules_repo.mkdir(parents=True, exist_ok=False)
    run(["git", "init"], no_rules_repo, env=env)
    run(["python", str(ROOT / "scripts" / "bootstrap_project.py"), "--project", str(no_rules_repo), "--mode", "existing", "--apply"], no_rules_repo, env=env)
    for required in [
        "AGENTS.md",
        ".gitignore",
        ".roo/rules/00-project-context.md",
        ".roo/rules/10-project-architecture.md",
        ".roo/rules/20-project-quality-commands.md",
        ".roo/rules/30-risk-zones.md",
    ]:
        if not (no_rules_repo / required).exists():
            raise SystemExit(f"missing existing project local governance file: {required}")
    for unexpected in ["AGENTS.md.new", ".roo/rules/00-project-context.md.new"]:
        if (no_rules_repo / unexpected).exists():
            raise SystemExit(f"unexpected draft for missing local governance file: {unexpected}")
    assert_project_task_board(no_rules_repo)
    current = json.loads((no_rules_repo / ".zoo-agent" / "current-run.json").read_text(encoding="utf-8"))
    current_run = Path(current["run_dir"])
    project_tasks = no_rules_repo / ".zoo-agent" / "TASKS.md"
    project_tasks.write_text(project_tasks.read_text(encoding="utf-8").replace("- [planned]", "- [paused]"), encoding="utf-8")
    run(["python", str(ROOT / "scripts" / "apply-task-board.py"), "--run-id", current["run_id"]], no_rules_repo, env=env)
    branch_state = json.loads((current_run / "branch-state.json").read_text(encoding="utf-8"))
    root_branch = next((item for item in branch_state.get("branches", []) if item.get("branch_id") == "root"), {})
    if root_branch.get("status") != "paused":
        raise SystemExit("project-level TASKS.md edit did not apply to branch-state.json")

    # Project Bootstrap: existing complete local governance files should not create noisy .new drafts.
    complete_rules_repo = TEST_ROOT / f"v3.10-project-bootstrap-existing-complete-rules-{stamp}"
    complete_rules_repo.mkdir(parents=True, exist_ok=False)
    run(["git", "init"], complete_rules_repo, env=env)
    complete_agents = "\n".join([
        "# Existing Agent Rules",
        "Do not modify secret, .env, or credential files.",
        "Do not modify production config.",
        "Do not run git reset --hard.",
        "Route ordinary coding requests through /agent-run.",
        "Before finishing, run scope guard within assigned task scope.",
        "",
    ])
    (complete_rules_repo / "AGENTS.md").write_text(complete_agents, encoding="utf-8")
    (complete_rules_repo / ".gitignore").write_text("\n".join([
        ".zoo-agent/runs/",
        ".zoo-agent/evals/",
        ".zoo-agent/metrics/",
        ".zoo-agent/tmp/",
        ".zoo-agent/**/codex-final-message.md",
        ".zoo-agent/**/codex-results/",
        ".zoo-agent/**/codex-tasks/",
        "__pycache__/",
        ".pytest_cache/",
        "*.pyc",
        "",
    ]), encoding="utf-8")
    (complete_rules_repo / ".roo" / "rules").mkdir(parents=True)
    for rule in ["00-project-context.md", "10-project-architecture.md", "20-project-quality-commands.md", "30-risk-zones.md"]:
        (complete_rules_repo / ".roo" / "rules" / rule).write_text("# Existing Rule\n\nKeep this file.\n", encoding="utf-8")
    run(["python", str(ROOT / "scripts" / "bootstrap_project.py"), "--project", str(complete_rules_repo), "--mode", "existing", "--apply"], complete_rules_repo, env=env)
    for unexpected in [
        "AGENTS.md.new",
        ".gitignore.agent.patch",
        ".roo/rules/00-project-context.md.new",
        ".roo/rules/10-project-architecture.md.new",
        ".roo/rules/20-project-quality-commands.md.new",
        ".roo/rules/30-risk-zones.md.new",
    ]:
        if (complete_rules_repo / unexpected).exists():
            raise SystemExit(f"unexpected draft for complete local governance file: {unexpected}")

    benchmark = repo / ".zoo-agent" / "executor-benchmark.json"
    score = repo / ".zoo-agent" / "executor-benchmark.score.json"
    run(["python", str(ROOT / "scripts" / "run-executor-benchmark.py"), "--case-dir", str(ROOT / "evals" / "executor-comparison"), "--output", str(benchmark)], repo, env=env)
    run(["python", str(ROOT / "scripts" / "score-executor-benchmark.py"), "--input", str(benchmark), "--output", str(score)], repo, env=env)
    run(["python", str(ROOT / "scripts" / "generate-executor-comparison-report.py"), "--benchmark", str(benchmark), "--score", str(score)], repo, env=env)

    codex = shutil.which("codex")
    print("Codex CLI available:", bool(codex))
    if codex:
        version_cmd = ["cmd", "/c", "codex", "--version"] if sys.platform == "win32" else ["codex", "--version"]
        run(version_cmd, repo, check=False, env=env)
    else:
        print("WARNING: Codex CLI not found; skipping real codex exec.")
    run(["python", str(ROOT / "scripts" / "run-codex-worker.py"), "--task-dir", str(out), "--workspace", str(repo), "--dry-run"], repo, env=env)

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
