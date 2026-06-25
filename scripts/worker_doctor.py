#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json
from worker_environment_report import write_environment_report
from worker_installation_diagnostics import write_installation_diagnostics
from worker_registry import write_worker_registry


def has_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text)


def codex_login_status() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ['codex.cmd' if sys.platform == 'win32' else 'codex', 'login', 'status'],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=20,
        )
        text = (proc.stdout or proc.stderr).strip()
        return {
            'checked': True,
            'returncode': proc.returncode,
            'status': text[:200],
            'logged_in': proc.returncode == 0 and 'logged in' in text.lower(),
        }
    except Exception as exc:
        return {'checked': False, 'logged_in': False, 'status': type(exc).__name__}


def codex_sandbox_smoke(project: Path, *, force: bool = False) -> dict[str, Any]:
    if not force:
        return {'checked': False, 'status': 'not run; no path risk detected'}
    if not any(
        item.get('provider') == 'codex' and item.get('available')
        for item in (write_worker_registry(project).get('workers') or [])
    ):
        return {'checked': False, 'status': 'codex unavailable'}
    try:
        proc = subprocess.run(
            [
                'codex.cmd' if sys.platform == 'win32' else 'codex',
                'exec',
                '--cd',
                str(project),
                '--sandbox',
                'read-only',
                '--skip-git-repo-check',
                'Respond with OK only.',
            ],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=15,
        )
        stderr = proc.stderr[-1000:]
        failed = any(marker in stderr.lower() for marker in ['windows sandbox', 'spawn setup refresh', 'sandbox'])
        return {
            'checked': True,
            'returncode': proc.returncode,
            'sandbox_failed': failed,
            'status': 'failed' if failed else ('ok' if proc.returncode == 0 else 'nonzero'),
        }
    except subprocess.TimeoutExpired:
        return {'checked': True, 'returncode': 124, 'sandbox_failed': True, 'status': 'timeout'}
    except Exception as exc:
        return {'checked': True, 'returncode': 1, 'sandbox_failed': True, 'status': type(exc).__name__}


def product_role(worker: dict[str, Any]) -> str:
    role = str(worker.get('role') or worker.get('worker_type') or 'Worker')
    mapping = {
        'analysis': 'Analysis Worker',
        'code': 'Code Worker',
        'test': 'Test Worker',
        'docs': 'Docs Worker',
        'mock': 'Mock Worker',
        'dry_run': 'Dry-run Worker',
    }
    return mapping.get(role, role if role.endswith('Worker') else f'{role.title()} Worker')


def safe_capabilities(worker: dict[str, Any]) -> str:
    if worker.get('supports_actual_execution'):
        return 'bounded file changes when explicitly allowed'
    if 'repo_scan' in (worker.get('capabilities') or []):
        return 'repo scan and project map support'
    if worker.get('supports_preview'):
        return 'preview and analysis only'
    return 'not available'


def doctor_payload(project: Path) -> dict[str, Any]:
    diagnostics = write_installation_diagnostics(project)
    registry = write_worker_registry(project)
    workers = [item for item in registry.get('workers') or [] if isinstance(item, dict)]
    actual_available = any(
        item.get('available') and item.get('supports_actual_execution') and item.get('provider') not in {'mock'}
        for item in workers
    )
    login = codex_login_status()
    non_ascii = has_non_ascii(str(project))
    smoke = codex_sandbox_smoke(project, force=non_ascii)
    payload = {
        'schema_version': '1.0',
        'generated_by': 'worker_doctor.py',
        'generated_at': utc_now(),
        'workers': [
            {
                'name': item.get('name', ''),
                'role': product_role(item),
                'available': bool(item.get('available')),
                'health': item.get('health', 'unavailable'),
                'safe_capability': safe_capabilities(item),
                'why_unavailable': ''
                if item.get('available')
                else str(item.get('unavailable_reason') or item.get('reason') or 'not detected or not enabled'),
                'suggested_fix': item.get('suggested_fix')
                or (
                    'No fix required.'
                    if item.get('available')
                    else 'Use preview/dry-run, or install the relevant CLI later.'
                ),
            }
            for item in workers
        ],
        'system_status': {
            'project_map': 'supported'
            if any('repo_scan' in (item.get('capabilities') or []) and item.get('available') for item in workers)
            else 'limited',
            'preview': 'supported'
            if any(item.get('supports_preview') and item.get('available') for item in workers)
            else 'unavailable',
            'actual_code_execution': 'available' if actual_available else 'unavailable',
            'autopilot': 'standard with safe fallback' if workers else 'not ready',
        },
        'codex_diagnostics': {
            'login_status': login,
            'sandbox_smoke': smoke,
            'non_ascii_project_path': non_ascii,
            'recommended_fallback': 'bounded docs fallback'
            if smoke.get('sandbox_failed') or non_ascii
            else 'codex worker',
        },
        'artifacts': {
            'worker_registry': '.zoo-agent/workers/worker_registry.json',
            'installation_diagnostics': '.zoo-agent/workers/installation_diagnostics.json',
            'environment_report': '.zoo-agent/workers/worker_environment_report.md',
        },
    }
    write_json(project / '.zoo-agent' / 'workers' / 'worker_doctor_report.json', payload)
    write_environment_report(project, registry=registry, diagnostics=diagnostics)
    return payload


def render_doctor(payload: dict[str, Any]) -> str:
    lines = ['Workers:', '']
    for worker in payload.get('workers') or []:
        status = 'available' if worker.get('available') else 'unavailable'
        reason = f', {worker.get("why_unavailable")}' if not worker.get('available') else ''
        lines.append(
            f'* {worker.get("role")}: {status}, {worker.get("health")}. {worker.get("safe_capability")}{reason}'
        )
    system = payload.get('system_status') or {}
    codex = payload.get('codex_diagnostics') or {}
    login = codex.get('login_status') or {}
    smoke = codex.get('sandbox_smoke') or {}
    lines.extend(
        [
            '',
            'System status:',
            '',
            f'* Project map: {system.get("project_map", "unknown")}',
            f'* Preview: {system.get("preview", "unknown")}',
            f'* Actual code execution: {system.get("actual_code_execution", "unknown")}',
            f'* Autopilot: {system.get("autopilot", "unknown")}',
            '',
            'Codex diagnostics:',
            '',
            f'* Login: {"logged in" if login.get("logged_in") else login.get("status", "unknown")}',
            f'* Sandbox smoke: {smoke.get("status", "not checked")}',
            f'* Non-ASCII project path: {"yes" if codex.get("non_ascii_project_path") else "no"}',
            f'* Recommended fallback: {codex.get("recommended_fallback", "unknown")}',
            '',
            'Reports:',
            '',
            '* .zoo-agent/workers/worker_doctor_report.json',
            '* .zoo-agent/workers/worker_environment_report.md',
        ]
    )
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Diagnose worker availability without installing or executing external work.'
    )
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = doctor_payload(project)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_doctor(payload))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
