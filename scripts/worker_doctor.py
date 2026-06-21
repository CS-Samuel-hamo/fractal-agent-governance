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
from worker_environment_report import build_environment_report, write_environment_report  # noqa: E402
from worker_installation_diagnostics import write_installation_diagnostics  # noqa: E402
from worker_registry import write_worker_registry  # noqa: E402


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
    actual_available = any(item.get('available') and item.get('supports_actual_execution') and item.get('provider') not in {'mock'} for item in workers)
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
                'why_unavailable': '' if item.get('available') else str(item.get('unavailable_reason') or item.get('reason') or 'not detected or not enabled'),
                'suggested_fix': item.get('suggested_fix') or ('No fix required.' if item.get('available') else 'Use preview/dry-run, or install the relevant CLI later.'),
            }
            for item in workers
        ],
        'system_status': {
            'project_map': 'supported' if any('repo_scan' in (item.get('capabilities') or []) and item.get('available') for item in workers) else 'limited',
            'preview': 'supported' if any(item.get('supports_preview') and item.get('available') for item in workers) else 'unavailable',
            'actual_code_execution': 'available' if actual_available else 'unavailable',
            'autopilot': 'standard with safe fallback' if workers else 'not ready',
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
        reason = f", {worker.get('why_unavailable')}" if not worker.get('available') else ''
        lines.append(f"* {worker.get('role')}: {status}, {worker.get('health')}. {worker.get('safe_capability')}{reason}")
    system = payload.get('system_status') or {}
    lines.extend(
        [
            '',
            'System status:',
            '',
            f"* Project map: {system.get('project_map', 'unknown')}",
            f"* Preview: {system.get('preview', 'unknown')}",
            f"* Actual code execution: {system.get('actual_code_execution', 'unknown')}",
            f"* Autopilot: {system.get('autopilot', 'unknown')}",
            '',
            'Reports:',
            '',
            '* .zoo-agent/workers/worker_doctor_report.json',
            '* .zoo-agent/workers/worker_environment_report.md',
        ]
    )
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnose worker availability without installing or executing external work.')
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
