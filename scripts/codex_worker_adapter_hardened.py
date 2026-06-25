#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json
from worker_adapter_contract import worker_contract
from worker_interface import worker_result


def resolve_codex_command() -> str:
    if sys.platform == 'win32':
        for name in ['codex.cmd', 'codex.exe', 'codex.bat']:
            found = shutil.which(name)
            if found:
                return found
    found = shutil.which('codex')
    if found:
        return found
    if sys.platform == 'win32':
        for name in ['codex.ps1', 'codex']:
            found = shutil.which(name)
            if found:
                return found
    return ''


def detect_codex_cli() -> dict[str, Any]:
    executable = resolve_codex_command()
    if not executable:
        return {'available': False, 'status': 'unavailable', 'reason': 'codex CLI not found', 'version': ''}
    version = ''
    status = 'healthy'
    reason = 'codex CLI detected'
    try:
        proc = subprocess.run(
            [executable, '--version'],
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
            timeout=5,
        )
        version = (
            (proc.stdout or proc.stderr).strip().splitlines()[0][:120] if (proc.stdout or proc.stderr).strip() else ''
        )
        if proc.returncode != 0:
            status = 'degraded'
            reason = 'codex CLI detected but version check returned non-zero'
    except subprocess.TimeoutExpired:
        status = 'degraded'
        reason = 'codex CLI version check timed out'
    except PermissionError:
        return {'available': False, 'status': 'unavailable', 'reason': 'codex CLI permission denied', 'version': ''}
    except Exception as exc:
        status = 'degraded'
        reason = f'codex CLI version check failed: {type(exc).__name__}'
    return {'available': True, 'status': status, 'reason': reason, 'version': version}


def codex_contract(project: Path | None = None) -> dict[str, Any]:
    detection = detect_codex_cli()
    contract = worker_contract(
        'codex_worker_existing_adapter',
        supports_actual_execution=bool(detection.get('available') and detection.get('status') == 'healthy'),
        supports_repo_scan=False,
        requires_external_binary=True,
        requires_network=False,
        reads_secrets=False,
        modifies_files=True,
        can_run_commands=True,
        safe_default_mode='preview' if detection.get('available') else 'unavailable',
    )
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_contract.json', contract)
    return contract


def codex_health(project: Path | None = None) -> dict[str, Any]:
    detection = detect_codex_cli()
    payload = {
        'schema_version': '1.0',
        'generated_by': 'codex_worker_adapter_hardened.py',
        'generated_at': utc_now(),
        'worker_name': 'codex_worker_existing_adapter',
        'available': bool(detection.get('available')),
        'health': detection.get('status', 'unavailable'),
        'reason': detection.get('reason', ''),
        'version': detection.get('version', ''),
        'supports_actual_execution': bool(codex_contract().get('supports_actual_execution')),
        'reads_secrets': False,
        'raw_log_path': '',
    }
    if project:
        write_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_health.json', payload)
    return payload


def normalize_codex_status(command_result: dict[str, Any], worker_payload: dict[str, Any]) -> str:
    if not detect_codex_cli().get('available'):
        return 'unavailable'
    if command_result.get('returncode') != 0:
        text = f'{command_result.get("stdout_tail", "")}\n{command_result.get("stderr_tail", "")}'.lower()
        if 'timed out' in text or 'timeout' in text:
            return 'timeout'
        if 'scope' in text and 'violation' in text:
            return 'scope_violation'
        if 'permission' in text or 'denied' in text:
            return 'permission_denied'
        return 'failed'
    status = str(worker_payload.get('status') or '')
    if status in {'success', 'failed', 'timeout', 'no_delivery', 'blocked', 'skipped'}:
        return status
    return 'no_delivery' if not worker_payload.get('changed_files') and status not in {'skipped'} else 'success'


def execute(
    project: Path, *, action: dict[str, Any], routing_decision: dict[str, Any], step_number: int = 1
) -> dict[str, Any]:
    from worker_execution_adapter import execute_routed_worker  # local import avoids a cycle

    health = codex_health(project)
    if not health.get('available'):
        payload = worker_result(
            worker_name='codex_worker_existing_adapter',
            worker_type='code',
            provider='codex',
            status='unavailable',
            summary='Code worker is unavailable.',
            confidence=0.0,
            error_type='worker_unavailable',
            safe_for_user_output=True,
        )
        write_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_last_result.json', payload)
        return {'worker_result': payload, 'command_result': {}, 'final_result': {}, 'execution': {}}
    result = execute_routed_worker(project, action=action, routing_decision=routing_decision, step_number=step_number)
    worker_payload = result.get('worker_result') or {}
    status = normalize_codex_status(result.get('command_result') or {}, worker_payload)
    hardened = {
        **worker_payload,
        'status': status,
        'error_type': '' if status in {'success', 'skipped'} else status,
        'safe_for_user_output': True,
    }
    write_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_last_result.json', hardened)
    result['worker_result'] = hardened
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect hardened Codex worker adapter.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = codex_health(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
