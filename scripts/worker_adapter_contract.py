#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


CONTRACT_FIELDS = [
    'worker_name',
    'adapter_version',
    'supports_health_check',
    'supports_preview',
    'supports_actual_execution',
    'supports_repo_scan',
    'requires_external_binary',
    'requires_network',
    'reads_secrets',
    'modifies_files',
    'can_run_commands',
    'safe_default_mode',
]


def worker_contract(
    worker_name: str,
    *,
    adapter_version: str = '0.96.2',
    supports_health_check: bool = True,
    supports_preview: bool = True,
    supports_actual_execution: bool = False,
    supports_repo_scan: bool = False,
    requires_external_binary: bool = False,
    requires_network: bool = False,
    reads_secrets: bool = False,
    modifies_files: bool = False,
    can_run_commands: bool = False,
    safe_default_mode: str = 'preview',
) -> dict[str, Any]:
    return {
        'worker_name': worker_name,
        'adapter_version': adapter_version,
        'supports_health_check': bool(supports_health_check),
        'supports_preview': bool(supports_preview),
        'supports_actual_execution': bool(supports_actual_execution),
        'supports_repo_scan': bool(supports_repo_scan),
        'requires_external_binary': bool(requires_external_binary),
        'requires_network': bool(requires_network),
        'reads_secrets': bool(reads_secrets),
        'modifies_files': bool(modifies_files),
        'can_run_commands': bool(can_run_commands),
        'safe_default_mode': safe_default_mode if safe_default_mode in {'preview', 'dry_run', 'unavailable'} else 'preview',
    }


def validate_contract(contract: dict[str, Any], profile: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    for field in CONTRACT_FIELDS:
        if field not in contract:
            errors.append(f'missing_contract_field:{field}')
    if contract.get('reads_secrets') is not False:
        errors.append('reads_secrets_must_be_false')
    if contract.get('requires_network') and contract.get('safe_default_mode') != 'unavailable':
        errors.append('network_worker_must_default_unavailable')
    if contract.get('supports_actual_execution') and not contract.get('modifies_files') and contract.get('safe_default_mode') == 'unavailable':
        errors.append('actual_worker_marked_unavailable')
    if profile:
        if profile.get('supports_actual_execution') and not contract.get('supports_actual_execution'):
            errors.append('profile_contract_actual_execution_conflict')
        if profile.get('supports_preview') and not contract.get('supports_preview'):
            errors.append('profile_contract_preview_conflict')
        if 'repo_scan' in (profile.get('capabilities') or []) and not contract.get('supports_repo_scan'):
            errors.append('profile_contract_repo_scan_conflict')
    return errors


def default_contracts() -> dict[str, dict[str, Any]]:
    return {
        'mock_worker': worker_contract(
            'mock_worker',
            supports_actual_execution=True,
            modifies_files=True,
            safe_default_mode='preview',
        ),
        'dry_run_worker': worker_contract(
            'dry_run_worker',
            supports_actual_execution=False,
            supports_repo_scan=True,
            safe_default_mode='dry_run',
        ),
        'local_scanner_worker': worker_contract(
            'local_scanner_worker',
            supports_actual_execution=False,
            supports_repo_scan=True,
            requires_external_binary=False,
            modifies_files=False,
            can_run_commands=False,
            safe_default_mode='preview',
        ),
        'codex_worker_existing_adapter': worker_contract(
            'codex_worker_existing_adapter',
            supports_actual_execution=False,
            requires_external_binary=True,
            modifies_files=True,
            can_run_commands=True,
            safe_default_mode='unavailable',
        ),
        'remote_openai_worker': worker_contract(
            'remote_openai_worker',
            adapter_version='1.0.6',
            supports_actual_execution=True,
            requires_network=True,
            modifies_files=True,
            can_run_commands=False,
            safe_default_mode='unavailable',
        ),
        'bounded_docs_writer': worker_contract(
            'bounded_docs_writer',
            adapter_version='1.0.6',
            supports_actual_execution=True,
            requires_external_binary=False,
            modifies_files=True,
            can_run_commands=False,
            safe_default_mode='preview',
        ),
        'claude_worker_stub': worker_contract(
            'claude_worker_stub',
            supports_actual_execution=False,
            requires_external_binary=True,
            safe_default_mode='unavailable',
        ),
        'local_worker_stub': worker_contract(
            'local_worker_stub',
            supports_actual_execution=False,
            supports_repo_scan=True,
            safe_default_mode='unavailable',
        ),
    }


def contract_for(worker_name: str) -> dict[str, Any]:
    return default_contracts().get(worker_name, worker_contract(worker_name, supports_preview=False, safe_default_mode='unavailable'))


def write_contracts(project: Path, profiles: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    contracts = default_contracts()
    rows = []
    for name, contract in contracts.items():
        profile = (profiles or {}).get(name, {})
        if profile.get('supports_actual_execution') and not contract.get('supports_actual_execution'):
            contract = {
                **contract,
                'supports_actual_execution': True,
                'modifies_files': bool(contract.get('modifies_files') or name in {'codex_worker_existing_adapter', 'mock_worker'}),
                'safe_default_mode': 'preview',
            }
        rows.append({**contract, 'validation_errors': validate_contract(contract, profile)})
    payload = {
        'schema_version': '1.0',
        'generated_by': 'worker_adapter_contract.py',
        'generated_at': utc_now(),
        'contracts': rows,
    }
    write_json(project / '.zoo-agent' / 'workers' / 'worker_adapter_contracts.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Render worker adapter contracts.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_contracts(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not any(row.get('validation_errors') for row in payload.get('contracts') or []) else 1


if __name__ == '__main__':
    raise SystemExit(main())
