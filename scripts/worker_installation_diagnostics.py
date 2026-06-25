#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from claude_code_worker_detector import detect_claude_code_cli
from codex_worker_adapter_hardened import detect_codex_cli
from runtime_common import project_root, utc_now, write_json


def version_check(command: list[str], *, timeout: int = 4) -> dict[str, Any]:
    if not shutil.which(command[0]):
        return {'available': False, 'summary': f'{command[0]} not found'}
    try:
        proc = subprocess.run(
            command,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=timeout,
        )
        text = (proc.stdout or proc.stderr).strip().splitlines()
        return {'available': True, 'returncode': proc.returncode, 'summary': text[0][:120] if text else 'detected'}
    except subprocess.TimeoutExpired:
        return {'available': True, 'returncode': 124, 'summary': 'version check timed out'}
    except Exception as exc:
        return {'available': True, 'returncode': 1, 'summary': f'check failed: {type(exc).__name__}'}


def git_status(project: Path) -> dict[str, Any]:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    return {'is_git_repo': proc.returncode == 0, 'root': '<PROJECT_ROOT>' if proc.returncode == 0 else ''}


def write_permission(project: Path) -> dict[str, Any]:
    target = project / '.zoo-agent' / 'workers' / '.write-test'
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('ok', encoding='utf-8')
        target.unlink(missing_ok=True)
        return {'writable': True, 'path': '.zoo-agent/workers'}
    except Exception as exc:
        return {'writable': False, 'path': '.zoo-agent/workers', 'reason': type(exc).__name__}


def installation_diagnostics(project: Path) -> dict[str, Any]:
    return {
        'schema_version': '1.0',
        'generated_by': 'worker_installation_diagnostics.py',
        'generated_at': utc_now(),
        'os': {'system': platform.system(), 'release': platform.release()},
        'python': {'version': platform.python_version(), 'executable': '<PYTHON>'},
        'git': version_check(['git', '--version']),
        'node': version_check(['node', '--version']),
        'codex_cli': detect_codex_cli(),
        'claude_code_cli': detect_claude_code_cli(),
        'project_root': '<PROJECT_ROOT>',
        'git_repo': git_status(project),
        'zoo_agent_write_permission': write_permission(project),
        'actions_taken': ['diagnostic only; no installation performed', 'no network download performed'],
    }


def write_installation_diagnostics(project: Path) -> dict[str, Any]:
    payload = installation_diagnostics(project)
    write_json(project / '.zoo-agent' / 'workers' / 'installation_diagnostics.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Run worker installation diagnostics without installing anything.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_installation_diagnostics(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
