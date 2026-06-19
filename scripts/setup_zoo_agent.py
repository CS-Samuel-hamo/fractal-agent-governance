#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GLOBAL_ROO = Path.home() / ".roo"
DEFAULT_KIT = DEFAULT_GLOBAL_ROO / "agent-governance-kit"
KIT_VERSION = "0.3.11-architecture-feedback-hardening-windows-probes"


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {
        "command": [str(part) for part in command],
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
    }


def print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def write_report(project: Path, payload: dict) -> None:
    out_dir = project / ".zoo-agent"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "one-touch-setup-report.json"
    md_path = out_dir / "one-touch-setup-report.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# One-Touch Zoo Agent Setup Report",
        "",
        f"- status: {payload.get('status')}",
        f"- kit_version: {payload.get('kit_version')}",
        f"- project: {payload.get('project')}",
        f"- generated_at: {payload.get('generated_at')}",
        f"- backup_root: {payload.get('backup_root')}",
        "",
        "## Steps",
        "",
    ]
    for step in payload.get("steps", []):
        lines.extend([
            f"### {step.get('name')}",
            "",
            f"- status: {step.get('status')}",
            f"- returncode: {step.get('returncode', 'n/a')}",
            "",
        ])
        if step.get("stdout"):
            lines.extend(["```text", str(step["stdout"])[:12000], "```", ""])
    lines.extend([
        "## Next",
        "",
        "- Reload the project so local `.roo` command and rule files are re-read.",
        "- Review `.zoo-agent/architecture-compatibility-report.md` before trusting refreshed architecture facts.",
        "- Use `agent run <input>` for normal CLI runtime work after setup.",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def add_optional(command: list[str], flag: str, value: str) -> None:
    if value:
        command.extend([flag, value])


def json_from_stdout(result: dict) -> dict:
    try:
        data = json.loads(result.get("stdout") or "")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-touch setup: sync global Zoo/Roo kit and bootstrap a new or existing project."
    )
    parser.add_argument("--project", default=".")
    parser.add_argument("--mode", choices=["auto", "existing", "new"], default="auto")
    parser.add_argument("--goal", default="")
    parser.add_argument("--stack", default="")
    parser.add_argument("--codex-home", default=os.environ.get("CODEX_HOME", ""))
    parser.add_argument("--global-roo", default=str(DEFAULT_GLOBAL_ROO))
    parser.add_argument("--kit-root", default=str(DEFAULT_KIT))
    parser.add_argument("--backup-root", default="")
    parser.add_argument("--force-new-project", action="store_true")
    parser.add_argument("--no-git-init", action="store_true")
    parser.add_argument("--skip-global-sync", action="store_true")
    parser.add_argument("--skip-project-bootstrap", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_root = Path(args.backup_root).resolve() if args.backup_root else Path(args.global_roo).resolve() / "backups" / f"one-touch-setup-{timestamp}"
    steps: list[dict] = []
    payload = {
        "schema_version": "1.0",
        "generated_by": "setup_zoo_agent.py",
        "generated_at": now(),
        "kit_version": KIT_VERSION,
        "project": str(project),
        "global_roo": str(Path(args.global_roo).resolve()),
        "kit_root": str(Path(args.kit_root).resolve()),
        "backup_root": str(backup_root),
        "dry_run": args.dry_run,
        "steps": steps,
        "status": "running",
    }

    validate_script = ROOT / "scripts" / "validate_starter_pack.py"
    sync_script = ROOT / "scripts" / "sync_zoo_entrypoints.py"
    bootstrap_script = ROOT / "scripts" / "agent_bootstrap.py"

    if args.dry_run:
        payload["status"] = "dry_run"
        if not args.skip_validation:
            steps.append({"name": "starter_pack_validation", "status": "would_run", "command": [sys.executable, str(validate_script)]})
        if not args.skip_global_sync:
            steps.append({
                "name": "global_and_kit_sync",
                "status": "would_run",
                "command": [
                    sys.executable,
                    str(sync_script),
                    "--global-roo",
                    args.global_roo,
                    "--kit-root",
                    args.kit_root,
                    "--backup-root",
                    str(backup_root),
                    "--dry-run",
                ],
            })
        if not args.skip_project_bootstrap:
            steps.append({"name": "project_bootstrap", "status": "would_run", "command": [sys.executable, str(bootstrap_script), "--project", str(project), "--mode", args.mode, "--dry-run"]})
        print_json(payload)
        return 0

    if not args.skip_validation:
        validation = run_command([sys.executable, str(validate_script)], ROOT)
        steps.append({"name": "starter_pack_validation", "status": "ok" if validation["returncode"] == 0 else "failed", **validation})
        if validation["returncode"] != 0:
            payload["status"] = "failed_validation"
            print_json(payload)
            return validation["returncode"]

    if not args.skip_global_sync:
        sync_command = [
            sys.executable,
            str(sync_script),
            "--global-roo",
            args.global_roo,
            "--kit-root",
            args.kit_root,
            "--backup-root",
            str(backup_root),
        ]
        sync_result = run_command(sync_command, ROOT)
        steps.append({"name": "global_and_kit_sync", "status": "ok" if sync_result["returncode"] == 0 else "failed", **sync_result})
        if sync_result["returncode"] != 0:
            payload["status"] = "failed_global_sync"
            print_json(payload)
            return sync_result["returncode"]

    if not args.skip_project_bootstrap:
        bootstrap_command = [
            sys.executable,
            str(bootstrap_script),
            "--project",
            str(project),
            "--mode",
            args.mode,
        ]
        add_optional(bootstrap_command, "--goal", args.goal)
        add_optional(bootstrap_command, "--stack", args.stack)
        add_optional(bootstrap_command, "--codex-home", args.codex_home)
        if args.force_new_project:
            bootstrap_command.append("--force-new-project")
        if args.no_git_init:
            bootstrap_command.append("--no-git-init")
        bootstrap_result = run_command(bootstrap_command, ROOT)
        steps.append({"name": "project_bootstrap", "status": "ok" if bootstrap_result["returncode"] == 0 else "failed", **bootstrap_result})
        bootstrap_payload = json_from_stdout(bootstrap_result)
        if bootstrap_payload.get("architecture_compatibility"):
            payload["architecture_compatibility"] = bootstrap_payload.get("architecture_compatibility")
        if bootstrap_payload.get("status"):
            payload["project_bootstrap_status"] = bootstrap_payload.get("status")
        if bootstrap_result["returncode"] != 0:
            payload["status"] = "failed_project_bootstrap"
            if project.exists():
                write_report(project, payload)
            print_json(payload)
            return bootstrap_result["returncode"]

    compatibility_status = (payload.get("architecture_compatibility") or {}).get("status", "")
    project_bootstrap_status = str(payload.get("project_bootstrap_status") or "")
    if args.skip_project_bootstrap:
        payload["status"] = "global_ready_project_bootstrap_skipped"
    elif compatibility_status == "blocked" or "architecture_blocks" in project_bootstrap_status:
        payload["status"] = "ready_with_architecture_blocks"
    elif compatibility_status == "needs_review" or "needs_architecture_review" in project_bootstrap_status:
        payload["status"] = "ready_needs_architecture_review"
    else:
        payload["status"] = "ready"
    if project.exists():
        write_report(project, payload)
    print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
