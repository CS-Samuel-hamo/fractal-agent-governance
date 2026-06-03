#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TEMPLATE = ROOT / "templates" / "project-local"
RECOMMENDED_CODEX_HOME = Path("D:/AI_DEV/codex_home")
SECRET_MARKERS = (".env", "secret", "token", "credential", "private", ".pem", ".key")
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
    "",
]
AGENTS_REQUIRED_GROUPS = [
    ("secret", ".env", "credential"),
    ("production config",),
    ("git reset --hard",),
    ("/agent-run",),
    ("scope guard", "assigned task scope"),
]


def is_sensitive(path: Path) -> bool:
    lower = path.name.lower()
    return any(marker in lower for marker in SECRET_MARKERS)


def safe_top_level(project: Path) -> list[str]:
    names = []
    for item in project.iterdir():
        if is_sensitive(item):
            continue
        names.append(item.name)
    return sorted(names)


def project_is_empty(project: Path) -> bool:
    return not [item for item in project.iterdir() if item.name not in {".git"}]


def detect_type(project: Path, mode: str, force_new: bool) -> str:
    if mode == "new":
        return "empty_new_project" if project_is_empty(project) or force_new else "existing_non_git_project"
    if mode == "existing":
        return "existing_git_project" if (project / ".git").exists() else "existing_non_git_project"
    if (project / ".git").exists():
        return "existing_git_project"
    if project_is_empty(project):
        return "empty_new_project"
    return "existing_non_git_project"


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_stack(project: Path) -> dict:
    language: list[str] = []
    framework: list[str] = []
    package_manager = ""
    test_commands: list[str] = []
    lint_commands: list[str] = []
    typecheck_commands: list[str] = []
    build_commands: list[str] = []
    unknowns: list[str] = []

    if (project / "package.json").exists():
        language.append("javascript/typescript")
        package_manager = "npm"
        package = load_json(project / "package.json")
        scripts = package.get("scripts", {}) if isinstance(package.get("scripts"), dict) else {}
        if "test" in scripts:
            test_commands.append("npm test")
        if "lint" in scripts:
            lint_commands.append("npm run lint")
        if "typecheck" in scripts:
            typecheck_commands.append("npm run typecheck")
        if "build" in scripts:
            build_commands.append("npm run build")
        deps = {**(package.get("dependencies", {}) or {}), **(package.get("devDependencies", {}) or {})}
        for name, label in [("react", "react"), ("next", "nextjs"), ("vue", "vue"), ("vite", "vite"), ("express", "express")]:
            if name in deps:
                framework.append(label)
    if (project / "pnpm-lock.yaml").exists():
        package_manager = "pnpm"
    elif (project / "yarn.lock").exists():
        package_manager = "yarn"

    py_markers = ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg"]
    if any((project / marker).exists() for marker in py_markers) or list(project.glob("*.py")):
        language.append("python")
        if not package_manager:
            package_manager = "python"
        if (project / "tests").exists():
            test_commands.append("python -m pytest")
    if (project / "Cargo.toml").exists():
        language.append("rust")
        package_manager = "cargo"
        test_commands.append("cargo test")
        build_commands.append("cargo build")
    if (project / "go.mod").exists():
        language.append("go")
        package_manager = "go"
        test_commands.append("go test ./...")

    if not language:
        unknowns.append("language")
    if not test_commands:
        unknowns.append("test_commands")
    if not framework:
        framework.append("unknown")

    return {
        "language": sorted(set(language)),
        "framework": sorted(set(framework)),
        "package_manager": package_manager or "unknown",
        "test_commands": sorted(set(test_commands)),
        "lint_commands": sorted(set(lint_commands)),
        "typecheck_commands": sorted(set(typecheck_commands)),
        "build_commands": sorted(set(build_commands)),
        "unknowns": unknowns,
    }


def common_dirs(project: Path, names: list[str]) -> list[str]:
    return [name for name in names if (project / name).exists()]


def codex_cli_version(codex_home: str) -> tuple[bool, str]:
    codex = shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe")
    if not codex:
        return False, "codex CLI not found"
    env = os.environ.copy()
    if codex_home:
        env["CODEX_HOME"] = codex_home
    try:
        cmd = ["cmd", "/c", "codex", "--version"] if os.name == "nt" else [codex, "--version"]
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, env=env)
        return proc.returncode == 0, proc.stdout.strip()
    except Exception as error:
        return False, str(error)


def codex_home_status(codex_home_arg: str) -> tuple[str, bool, list[str]]:
    warnings: list[str] = []
    codex_home = codex_home_arg or os.environ.get("CODEX_HOME", "")
    if not codex_home and os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                value, _ = winreg.QueryValueEx(key, "CODEX_HOME")
                codex_home = str(value)
                warnings.append("CODEX_HOME was found in the user environment but is not set in this process.")
        except Exception:
            pass
    if not codex_home and RECOMMENDED_CODEX_HOME.exists():
        codex_home = str(RECOMMENDED_CODEX_HOME)
        warnings.append("CODEX_HOME is not set in this process; recommended D drive CODEX_HOME exists.")
    elif not codex_home:
        warnings.append("CODEX_HOME is not set; recommended D:\\AI_DEV\\codex_home.")
    return codex_home, bool(codex_home and Path(codex_home).exists()), warnings


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_json_protected(path: Path, data: dict, protect_existing: bool) -> Path:
    target = path
    if protect_existing and path.exists():
        target = path.with_name(path.name + ".new")
    write_json(target, data)
    return target


def render_template(path: Path, profile: dict, goal: str) -> str:
    text = path.read_text(encoding="utf-8")
    mapping = {
        "PROJECT_ROOT": profile.get("project_root", ""),
        "PROJECT_TYPE": profile.get("project_type", "unknown"),
        "GOAL": goal or "unknown",
        "LANGUAGE": ", ".join(profile.get("language", [])) or "unknown",
        "FRAMEWORK": ", ".join(profile.get("framework", [])) or "unknown",
        "UNKNOWNS": ", ".join(profile.get("unknowns", [])) or "unknown",
        "SOURCE_ROOTS": ", ".join(profile.get("source_roots", [])) or "unknown",
        "TEST_ROOTS": ", ".join(profile.get("test_roots", [])) or "unknown",
        "API_ENTRYPOINTS": ", ".join(profile.get("api_entrypoints", [])) or "unknown",
        "REGISTRY_PATTERNS": ", ".join(profile.get("registry_patterns", [])) or "unknown",
        "DOMAIN_TYPE_LOCATIONS": ", ".join(profile.get("domain_type_locations", [])) or "unknown",
        "TEST_COMMANDS": ", ".join(profile.get("test_commands", [])) or "unknown",
        "LINT_COMMANDS": ", ".join(profile.get("lint_commands", [])) or "unknown",
        "TYPECHECK_COMMANDS": ", ".join(profile.get("typecheck_commands", [])) or "unknown",
        "BUILD_COMMANDS": ", ".join(profile.get("build_commands", [])) or "unknown",
        "FORBIDDEN_PATHS": ", ".join(profile.get("forbidden_paths", [])) or "unknown",
        "RISK_ZONES": ", ".join(profile.get("risk_zones", [])) or "unknown",
    }
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def write_no_overwrite(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path
    if path.exists() and not path.name.endswith(".new"):
        target = path.with_name(path.name + ".new")
    target.write_text(text, encoding="utf-8")
    return target


def agent_gitignore_text() -> str:
    return "\n".join(AGENT_IGNORE_LINES)


def file_has_required_groups(path: Path, groups: list[tuple[str, ...]]) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    return all(any(term.lower() in text for term in group) for group in groups)


def missing_agent_ignore_lines(project: Path) -> list[str]:
    gitignore = project / ".gitignore"
    required = [line for line in AGENT_IGNORE_LINES if line.strip() and not line.strip().startswith("#")]
    if not gitignore.exists():
        return required
    existing = {line.strip() for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()}
    return [line for line in required if line.strip() not in existing]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def bootstrap_run_id() -> str:
    return "bootstrap-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_helper(project: Path, script_name: str, args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name), *args],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return proc.returncode, proc.stdout.strip()


def seed_run_runtime(run: Path, run_id: str, goal: str) -> list[str]:
    written: list[str] = []
    ts = now()
    goal_summary = goal or "Plan first safe Level 0/1 task"
    if not (run / "run-ledger.json").exists():
        write_json(run / "run-ledger.json", {
            "schema_version": "2.0",
            "run_id": run_id,
            "goal_id": "bootstrap",
            "branch_id": "root",
            "goal_summary": goal_summary,
            "created_by_mode": "agent-orchestrator",
            "model": "GPT-5.5",
            "created_at": ts,
            "updated_at": ts,
            "current_state": "intake",
            "allowed_next_states": ["goal_bound", "blocked"],
            "transitions": [],
        })
        written.append(f".zoo-agent/runs/{run_id}/run-ledger.json")
    if not (run / "artifact-graph.json").exists():
        write_json(run / "artifact-graph.json", {
            "schema_version": "2.0",
            "run_id": run_id,
            "goal_id": "bootstrap",
            "branch_id": "root",
            "created_by_mode": "agent-orchestrator",
            "model": "GPT-5.5",
            "created_at": ts,
            "updated_at": ts,
            "artifacts": [],
            "edges": [],
        })
        written.append(f".zoo-agent/runs/{run_id}/artifact-graph.json")
    if not (run / "branch-state.json").exists():
        write_json(run / "branch-state.json", {
            "schema_version": "1.1",
            "run_id": run_id,
            "goal_id": "bootstrap",
            "updated_at": ts,
            "branches": [{
                "branch_id": "root",
                "parent_branch_id": "",
                "title": goal_summary,
                "status": "planned",
                "branch_type": "root",
                "risk_level": "low",
                "purpose": goal_summary,
                "owned_paths": [],
                "shared_paths": [],
                "acceptance_criteria": ["Bootstrap report reviewed", "First Level 0/1 trial task selected"],
                "verification_plan": ["Run project bootstrap validation", "Run targeted test command when first task is generated"],
                "evidence": "pending",
                "updated_at": ts,
            }],
        })
        written.append(f".zoo-agent/runs/{run_id}/branch-state.json")
    return written


def runtime_task_board(run: Path, run_id: str) -> dict:
    branch_state = load_json(run / "branch-state.json")
    ledger = load_json(run / "run-ledger.json")
    branches = branch_state.get("branches") if isinstance(branch_state.get("branches"), list) else []
    if not branches:
        branches = [{
            "branch_id": ledger.get("branch_id") or "root",
            "parent_branch_id": "",
            "title": ledger.get("goal_summary") or "Bootstrap task board",
            "status": "planned",
            "branch_type": "root",
            "risk_level": "low",
            "purpose": ledger.get("goal_summary") or "Review bootstrap task board",
            "owned_paths": [],
            "shared_paths": [],
            "acceptance_criteria": [],
            "verification_plan": [],
            "evidence": "pending",
        }]
    tasks = []
    for branch in branches:
        bid = str(branch.get("branch_id") or branch.get("id") or "root")
        tasks.append({
            "branch_id": bid,
            "parent_branch_id": str(branch.get("parent_branch_id") or ""),
            "title": str(branch.get("title") or branch.get("purpose") or bid),
            "status": str(branch.get("status") or "planned"),
            "worktree_path": str(branch.get("worktree_path") or ""),
            "owned_paths": branch.get("owned_paths") if isinstance(branch.get("owned_paths"), list) else [],
            "shared_paths": branch.get("shared_paths") if isinstance(branch.get("shared_paths"), list) else [],
            "provides": branch.get("provides") if isinstance(branch.get("provides"), list) else [],
            "consumes": branch.get("consumes") if isinstance(branch.get("consumes"), list) else [],
            "acceptance_criteria": branch.get("acceptance_criteria") if isinstance(branch.get("acceptance_criteria"), list) else [],
            "verification_plan": branch.get("verification_plan") if isinstance(branch.get("verification_plan"), list) else [],
            "risk_level": str(branch.get("risk_level") or branch.get("risk") or "unknown"),
            "evidence": str(branch.get("evidence") or "pending"),
        })
    return {
        "schema_version": "1.1",
        "run_id": run_id,
        "goal_id": str(ledger.get("goal_id") or "bootstrap"),
        "source": "bootstrap_runtime_backfill",
        "created_at": now(),
        "active_path": [tasks[0]["branch_id"]] if tasks else [],
        "user_control": {
            "parallel": "auto",
            "next_mode": "agent-orchestrator",
            "focus": tasks[0]["branch_id"] if tasks else "root",
            "direction": "review bootstrap task board",
        },
        "tasks": tasks,
    }


def ensure_run_task_boards(project: Path, goal: str, project_type: str) -> list[str]:
    written: list[str] = []
    if project_type not in {"existing_git_project", "empty_new_project"}:
        return written
    runs_root = project / ".zoo-agent" / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    runs = sorted([item for item in runs_root.iterdir() if item.is_dir()])
    if not runs:
        run_id = bootstrap_run_id()
        run = runs_root / run_id
        run.mkdir(parents=True, exist_ok=True)
        written.extend(seed_run_runtime(run, run_id, goal))
        runs = [run]

    for run in runs:
        run_id = run.name
        if (run / "TASKS.md").exists() and (run / "task-board.json").exists():
            continue
        if (run / "TASKS.md").exists() and not (run / "task-board.json").exists():
            written.extend(seed_run_runtime(run, run_id, goal))
            task_docs = sorted((run / "tasks").glob("*.md")) if (run / "tasks").exists() else []
            if task_docs:
                for script_name, helper_args in [
                    ("parse-task-board.py", ["--run-id", run_id]),
                    ("apply-task-board.py", ["--run-id", run_id]),
                ]:
                    code, output = run_helper(project, script_name, helper_args)
                    if code != 0:
                        summary = output.splitlines()[0] if output else "no output"
                        written.append(f".zoo-agent/runs/{run_id}/task-board.json backfill failed via {script_name}: {summary}")
                        break
                else:
                    written.append(f".zoo-agent/runs/{run_id}/task-board.json")
            else:
                write_json(run / "task-board.json", runtime_task_board(run, run_id))
                written.append(f".zoo-agent/runs/{run_id}/task-board.json")
                for script_name, helper_args in [
                    ("generate-progress-snapshot.py", ["--run-id", run_id]),
                    ("render-progress-tree.py", ["--run-id", run_id]),
                ]:
                    code, output = run_helper(project, script_name, helper_args)
                    if code != 0:
                        summary = output.splitlines()[0] if output else "no output"
                        written.append(f".zoo-agent/runs/{run_id}/progress export failed via {script_name}: {summary}")
                        break
            continue
        written.extend(seed_run_runtime(run, run_id, goal))
        for script_name, helper_args in [
            ("generate-progress-snapshot.py", ["--run-id", run_id]),
            ("render-progress-tree.py", ["--run-id", run_id]),
            ("export-task-board.py", ["--run-id", run_id, "--direction", "review bootstrap task board"]),
            ("check-task-board-consistency.py", ["--run-id", run_id]),
        ]:
            code, output = run_helper(project, script_name, helper_args)
            if code != 0:
                summary = output.splitlines()[0] if output else "no output"
                written.append(f".zoo-agent/runs/{run_id}/TASKS.md export failed via {script_name}: {summary}")
                break
        else:
            written.extend([
                f".zoo-agent/runs/{run_id}/progress.json",
                f".zoo-agent/runs/{run_id}/progress.md",
                f".zoo-agent/runs/{run_id}/progress-tree.md",
                f".zoo-agent/runs/{run_id}/TASKS.md",
                f".zoo-agent/runs/{run_id}/task-board.json",
            ])
    return written


def latest_task_board_run(project: Path) -> Path | None:
    runs_root = project / ".zoo-agent" / "runs"
    if not runs_root.exists():
        return None
    runs = [
        item for item in runs_root.iterdir()
        if item.is_dir() and (item / "TASKS.md").exists() and (item / "task-board.json").exists()
    ]
    return sorted(runs, key=lambda p: p.stat().st_mtime)[-1] if runs else None


def expose_current_task_board(project: Path) -> list[str]:
    written: list[str] = []
    run = latest_task_board_run(project)
    if not run:
        return written
    run_id = run.name
    ledger = load_json(run / "run-ledger.json")
    board = load_json(run / "task-board.json")
    goal_id = str(ledger.get("goal_id") or board.get("goal_id") or "unknown")
    write_json(project / ".zoo-agent" / "current-run.json", {
        "schema_version": "1.0",
        "run_id": run_id,
        "goal_id": goal_id,
        "run_dir": str(run),
        "project_task_board": ".zoo-agent/TASKS.md",
        "run_task_board": str(run / "TASKS.md"),
        "task_board_json": str(run / "task-board.json"),
        "branch_state": str(run / "branch-state.json"),
        "updated_at": now(),
    })
    written.append(".zoo-agent/current-run.json")
    project_tasks = project / ".zoo-agent" / "TASKS.md"
    run_tasks = run / "TASKS.md"
    if run_tasks.exists() and (not project_tasks.exists() or project_tasks.stat().st_mtime <= run_tasks.stat().st_mtime):
        shutil.copy2(run_tasks, project_tasks)
        written.append(".zoo-agent/TASKS.md")
    return written


def ensure_project_map(project: Path, project_type: str) -> list[str]:
    written: list[str] = []
    if project_type not in {"existing_git_project", "empty_new_project"}:
        return written
    code, output = run_helper(project, "generate-project-map.py", ["--root", str(project)])
    if code != 0:
        summary = output.splitlines()[0] if output else "no output"
        written.append(f".zoo-agent/project-map.json generation failed: {summary}")
        return written
    written.extend([
        ".zoo-agent/project-map.json",
        ".zoo-agent/project-map.md",
        ".zoo-agent/architecture-boundaries.json",
    ])
    return written


def build_profile(project: Path, project_type: str, goal: str, stack_hint: str, codex_ready: bool) -> dict:
    stack = detect_stack(project)
    if stack_hint:
        stack["framework"] = sorted(set([*stack["framework"], stack_hint]))
    forbidden = [".env", ".env.*", "**/*.pem", "**/*.key", "secrets/**", "credentials/**"]
    risk_zones = common_dirs(project, ["database", "migrations", "infra", "deploy", "production", "auth", "security"])
    source_roots = common_dirs(project, ["src", "app", "lib", "packages", "services"])
    test_roots = common_dirs(project, ["tests", "test", "__tests__", "spec"])
    api_entrypoints = common_dirs(project, ["api", "routes", "controllers"])
    unknowns = sorted(set(stack["unknowns"] + ([] if source_roots else ["source_roots"])))
    return {
        "project_root": str(project),
        "project_type": project_type,
        "language": stack["language"],
        "framework": stack["framework"],
        "package_manager": stack["package_manager"],
        "test_commands": stack["test_commands"],
        "lint_commands": stack["lint_commands"],
        "typecheck_commands": stack["typecheck_commands"],
        "build_commands": stack["build_commands"],
        "source_roots": source_roots,
        "test_roots": test_roots,
        "api_entrypoints": api_entrypoints,
        "registry_patterns": [],
        "domain_type_locations": [],
        "risk_zones": risk_zones,
        "forbidden_paths": forbidden,
        "codex_worker_ready": codex_ready,
        "zoo_governance_ready": True,
        "unknowns": unknowns,
    }


def run_task_board_ready(project: Path) -> bool:
    runs_root = project / ".zoo-agent" / "runs"
    if not runs_root.exists():
        return False
    runs = [item for item in runs_root.iterdir() if item.is_dir()]
    if not runs:
        return False
    return all((run / "TASKS.md").exists() and (run / "task-board.json").exists() for run in runs)


def build_readiness(project: Path, profile: dict, codex_home_ready: bool, codex_cli_ready: bool, warnings: list[str]) -> dict:
    blocking: list[str] = []
    if profile["project_type"] == "existing_non_git_project":
        blocking.append("Existing non-Git project: confirm before running git init or Codex worker.")
    if not codex_cli_ready:
        blocking.append("Codex CLI is not available.")
    if not codex_home_ready:
        warnings.append("CODEX_HOME is missing or does not exist.")
    test_known = bool(profile.get("test_commands"))
    if not test_known:
        warnings.append("Test command is unknown.")
    project_charter_ready = (project / ".zoo-agent" / "project-charter.json").exists() or (project / "docs" / "project-charter.md").exists()
    project_map_ready = (project / ".zoo-agent" / "project-map.json").exists()
    architecture_boundaries_ready = (project / ".zoo-agent" / "architecture-boundaries.json").exists()
    task_board_ready = run_task_board_ready(project) if profile["project_type"] in {"existing_git_project", "empty_new_project"} else False
    project_task_board_ready = (project / ".zoo-agent" / "TASKS.md").exists() and (project / ".zoo-agent" / "current-run.json").exists()
    if not project_charter_ready:
        warnings.append("Project charter is missing; required before non-trivial coding and Level 2+ work.")
    if not project_map_ready:
        warnings.append("Project map is missing; generate before multi-module or architecture-sensitive work.")
    if not architecture_boundaries_ready:
        warnings.append("Architecture boundaries are missing; generate before architecture-sensitive work.")
    if profile["project_type"] in {"existing_git_project", "empty_new_project"} and not task_board_ready:
        warnings.append("Run task board is missing or incomplete; apply bootstrap or run progress/task-board export before continuing an old run.")
    if profile["project_type"] in {"existing_git_project", "empty_new_project"} and not project_task_board_ready:
        warnings.append("Project task board entry is missing; apply bootstrap to create .zoo-agent/TASKS.md and current-run.json.")
    safe = not blocking and profile["project_type"] in {"existing_git_project", "empty_new_project"} and codex_cli_ready
    return {
        "git_ready": (project / ".git").exists() or profile["project_type"] == "empty_new_project",
        "project_profile_ready": True,
        "project_charter_ready": project_charter_ready,
        "project_map_ready": project_map_ready,
        "architecture_boundaries_ready": architecture_boundaries_ready,
        "run_task_board_ready": task_board_ready,
        "project_task_board_ready": project_task_board_ready,
        "agents_md_ready": (project / "AGENTS.md").exists() or (project / "AGENTS.md.new").exists(),
        "local_rules_ready": (project / ".roo" / "rules").exists(),
        "gitignore_ready": (project / ".gitignore").exists() or (project / ".gitignore.agent.patch").exists(),
        "codex_home_ready": codex_home_ready,
        "codex_cli_ready": codex_cli_ready,
        "test_command_known": test_known,
        "safe_for_level_0_1_trial": safe,
        "blocking_issues": blocking,
        "warnings": sorted(set(warnings)),
        "next_actions": [
            "Review .zoo-agent/bootstrap-report.md.",
            "Apply or commit bootstrap governance files only after review.",
            "Use Level 0/1 Codex Worker only for tightly scoped, low-risk tasks.",
        ],
    }


def report(profile: dict, readiness: dict, codex_version: str, written: list[str]) -> str:
    def line_list(values: list[str]) -> str:
        return "\n".join(f"- {value}" for value in values) if values else "- unknown"
    return f"""# Project Bootstrap Report

## Project Type

{profile['project_type']}

## Detected Stack

- language: {', '.join(profile['language']) or 'unknown'}
- framework: {', '.join(profile['framework']) or 'unknown'}
- package_manager: {profile['package_manager']}

## Governance Files

{line_list(written)}

## Architecture Context

- project_charter_ready: {readiness['project_charter_ready']}
- project_map_ready: {readiness['project_map_ready']}
- architecture_boundaries_ready: {readiness['architecture_boundaries_ready']}
- run_task_board_ready: {readiness['run_task_board_ready']}
- project_task_board_ready: {readiness['project_task_board_ready']}

## Codex Worker Readiness

- CODEX_HOME ready: {readiness['codex_home_ready']}
- Codex CLI ready: {readiness['codex_cli_ready']}
- Codex CLI version: {codex_version or 'unknown'}
- safe_for_level_0_1_trial: {readiness['safe_for_level_0_1_trial']}

## Test / Lint / Build Commands

- tests: {', '.join(profile['test_commands']) or 'unknown'}
- lint: {', '.join(profile['lint_commands']) or 'unknown'}
- typecheck: {', '.join(profile['typecheck_commands']) or 'unknown'}
- build: {', '.join(profile['build_commands']) or 'unknown'}

## Risk Zones

{line_list(profile['risk_zones'])}

## Forbidden Paths

{line_list(profile['forbidden_paths'])}

## Unknowns

{line_list(profile['unknowns'])}

## Recommended First Task

Start with a Level 0/1 task that touches only one source file and one test file. If no safe target is obvious, ask Zoo/GPT to plan first tasks before invoking Codex Worker.

## Next Actions

{line_list(readiness['next_actions'])}
"""


def local_rules_summary(profile: dict) -> str:
    return "\n".join([
        "# Local Rules Summary",
        "",
        f"- project_type: {profile['project_type']}",
        f"- language: {', '.join(profile['language']) or 'unknown'}",
        f"- tests: {', '.join(profile['test_commands']) or 'unknown'}",
        f"- forbidden_paths: {', '.join(profile['forbidden_paths'])}",
        "",
    ])


def apply_existing(project: Path, profile: dict, goal: str) -> list[str]:
    written: list[str] = []
    agents = render_template(LOCAL_TEMPLATE / "AGENTS.md", profile, goal)
    agents_path = project / "AGENTS.md"
    if not agents_path.exists():
        written.append(str(write_no_overwrite(agents_path, agents).relative_to(project)))
    elif file_has_required_groups(agents_path, AGENTS_REQUIRED_GROUPS):
        written.append("AGENTS.md exists; no draft generated")
    else:
        written.append(str(write_no_overwrite(project / "AGENTS.md.new", agents).relative_to(project)))
    if (project / ".gitignore").exists():
        if missing_agent_ignore_lines(project):
            patch_proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "generate_project_gitignore_patch.py"), "--project", str(project), "--output", str(project / ".gitignore.agent.patch")],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if patch_proc.returncode == 0:
                written.append(".gitignore.agent.patch")
        else:
            written.append(".gitignore already contains agent ignore rules")
    else:
        written.append(str(write_no_overwrite(project / ".gitignore", agent_gitignore_text()).relative_to(project)))
    for src in (LOCAL_TEMPLATE / "roo-rules").glob("*.md"):
        text = render_template(src, profile, goal)
        rule_target = project / ".roo" / "rules" / src.name
        if rule_target.exists():
            written.append(f"{rule_target.relative_to(project)} exists; no draft generated")
            continue
        written.append(str(write_no_overwrite(rule_target, text).relative_to(project)))
    return written


def apply_new(project: Path, profile: dict, goal: str, no_git_init: bool) -> list[str]:
    written: list[str] = []
    if not no_git_init and not (project / ".git").exists():
        subprocess.run(["git", "init"], cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        written.append(".git/")
    readme = f"# {project.name}\n\nProject goal: {goal or 'unknown'}\n\nThis repository was bootstrapped with Zoo Agent Governance.\n"
    written.append(str(write_no_overwrite(project / "README.md", readme).relative_to(project)))
    written.append(str(write_no_overwrite(project / "AGENTS.md", (LOCAL_TEMPLATE / "AGENTS.md").read_text(encoding="utf-8")).relative_to(project)))
    written.append(str(write_no_overwrite(project / ".gitignore", agent_gitignore_text()).relative_to(project)))
    for src in ["00-project-context.md", "20-project-quality-commands.md"]:
        text = render_template(LOCAL_TEMPLATE / "roo-rules" / src, profile, goal)
        written.append(str(write_no_overwrite(project / ".roo" / "rules" / src, text).relative_to(project)))
    tasks = "# Tasks\n\n- [ ] Confirm project goal and stack.\n- [ ] Ask Zoo/GPT to plan first Level 0/1 tasks.\n- [ ] Generate Codex Task Pack for the first safe leaf task.\n"
    written.append(str(write_no_overwrite(project / "TASKS.md", tasks).relative_to(project)))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap an existing or new project for Zoo Governance.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--mode", choices=["auto", "existing", "new"], default="auto")
    parser.add_argument("--goal", default="")
    parser.add_argument("--stack", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-new-project", action="store_true")
    parser.add_argument("--no-git-init", action="store_true")
    parser.add_argument("--codex-home", default="")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    if not project.exists():
        project.mkdir(parents=True)
    if not project.is_dir():
        print(f"Project is not a directory: {project}", file=sys.stderr)
        return 2

    project_type = detect_type(project, args.mode, args.force_new_project)
    if project_type == "existing_non_git_project" and args.mode != "new":
        print("Existing non-Git project detected. Bootstrap will only write reports; confirm before git init.")
    codex_home, codex_home_ready, codex_home_warnings = codex_home_status(args.codex_home)
    codex_cli_ready, codex_version = codex_cli_version(codex_home)
    profile = build_profile(project, project_type, args.goal, args.stack, codex_cli_ready and codex_home_ready)

    out_dir = project / ".zoo-agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    if args.apply:
        if project_type == "empty_new_project":
            written.extend(apply_new(project, profile, args.goal, args.no_git_init))
            profile["project_type"] = "empty_new_project"
        elif project_type == "existing_git_project":
            written.extend(apply_existing(project, profile, args.goal))
        else:
            written.append("reports only; non-Git project requires confirmation")
        written.extend(ensure_run_task_boards(project, args.goal, project_type))
        written.extend(expose_current_task_board(project))
        written.extend(ensure_project_map(project, project_type))
    else:
        written.append("dry-run report only; rerun with --apply to write safe governance files")
        written.append("dry-run only; run TASKS.md/task-board export is not written until --apply")
        written.append("dry-run only; project-map/architecture-boundaries are not generated until --apply")

    profile["generated_at"] = datetime.now(timezone.utc).isoformat()
    profile["top_level_scan"] = safe_top_level(project)
    protect_profile = project_type in {"existing_git_project", "existing_non_git_project"}
    profile_path = write_json_protected(out_dir / "project-profile.json", profile, protect_profile)
    written.append(str(profile_path.relative_to(project)))
    readiness = build_readiness(project, profile, codex_home_ready, codex_cli_ready, codex_home_warnings)
    write_json(out_dir / "project-readiness.json", readiness)
    written.append(str((out_dir / "project-readiness.json").relative_to(project)))
    (out_dir / "bootstrap-report.md").write_text(report(profile, readiness, codex_version, written), encoding="utf-8")
    (out_dir / "local-rules-summary.md").write_text(local_rules_summary(profile), encoding="utf-8")

    print(out_dir / "bootstrap-report.md")
    print(f"project_type={profile['project_type']}")
    print(f"safe_for_level_0_1_trial={readiness['safe_for_level_0_1_trial']}")
    if readiness["blocking_issues"]:
        print("blocking_issues=" + "; ".join(readiness["blocking_issues"]))
    if readiness["warnings"]:
        print("warnings=" + "; ".join(readiness["warnings"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
