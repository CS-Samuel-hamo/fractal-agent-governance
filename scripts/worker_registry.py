#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json
from worker_adapter_contract import contract_for, write_contracts
from worker_capability_profile import worker_profiles
from worker_interface import worker_result


@dataclass
class ProfileWorker:
    profile: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.profile.get('worker_name') or '')

    @property
    def worker_type(self) -> str:
        return str(self.profile.get('worker_type') or 'unknown')

    @property
    def provider(self) -> str:
        return str(self.profile.get('provider') or 'unknown')

    @property
    def capabilities(self) -> list[str]:
        return [str(item) for item in self.profile.get('capabilities') or []]

    def health(self) -> dict[str, Any]:
        return {
            'available': bool(self.profile.get('available')),
            'health': str(
                self.profile.get('health') or ('healthy' if self.profile.get('available') else 'unavailable')
            ),
            'reliability_score': float(self.profile.get('reliability_score') or 0.0),
        }

    def can_handle(self, task_profile: dict[str, Any]) -> bool:
        if not self.profile.get('available'):
            return False
        if task_profile.get('trust_zone') == 'blocked':
            return False
        if task_profile.get('requires_actual_execution') and not self.profile.get('supports_actual_execution'):
            return False
        required = required_capability(task_profile)
        return not required or required in self.capabilities

    def execute(self, task: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        _ = context
        if not self.can_handle(task):
            return worker_result(
                worker_name=self.name,
                worker_type=self.worker_type,
                provider=self.provider,
                status='blocked',
                summary='worker cannot safely handle this task',
                confidence=0.0,
                error_type='worker_cannot_handle_task',
            )
        return worker_result(
            worker_name=self.name,
            worker_type=self.worker_type,
            provider=self.provider,
            status='skipped',
            summary='execution is delegated through the existing execution adapter',
            confidence=0.5,
        )


def required_capability(task_profile: dict[str, Any]) -> str:
    task_type = str(task_profile.get('task_type') or '')
    if task_type == 'docs_update':
        return 'docs_edit'
    if task_type == 'test_update':
        return 'tests_edit'
    if task_type in {'code_edit', 'refactor'}:
        return 'code_edit' if task_type == 'code_edit' else 'refactor'
    if task_type in {'repo_scan', 'release_readiness'}:
        return 'repo_scan'
    if task_type == 'analysis':
        return 'analysis'
    return ''


def default_workers(project: Path | None = None) -> dict[str, ProfileWorker]:
    return {name: ProfileWorker(profile) for name, profile in worker_profiles(project).items()}


def registry_payload(project: Path) -> dict[str, Any]:
    workers = []
    profiles = worker_profiles(project)
    contracts_payload = write_contracts(project, profiles)
    contract_rows = {
        item.get('worker_name'): item for item in contracts_payload.get('contracts') or [] if isinstance(item, dict)
    }
    for profile in profiles.values():
        contract = contract_rows.get(profile.get('worker_name')) or contract_for(str(profile.get('worker_name') or ''))
        workers.append(
            {
                'name': profile.get('worker_name'),
                'provider': profile.get('provider'),
                'worker_type': profile.get('worker_type'),
                'role': {
                    'code': 'Code Worker',
                    'analysis': 'Analysis Worker',
                    'test': 'Test Worker',
                    'docs': 'Docs Worker',
                    'mock': 'Mock Worker',
                    'dry_run': 'Dry-run Worker',
                }.get(str(profile.get('worker_type') or ''), 'Worker'),
                'available': bool(profile.get('available')),
                'health': profile.get('health'),
                'capabilities': profile.get('capabilities') or [],
                'notes': '; '.join(profile.get('best_for') or []),
                'supports_actual_execution': bool(profile.get('supports_actual_execution')),
                'supports_preview': bool(profile.get('supports_preview')),
                'reliability_score': profile.get('reliability_score', 0.0),
                'contract': contract,
                'reason': profile.get('reason', ''),
                'unavailable_reason': profile.get('unavailable_reason', ''),
                'suggested_fix': 'Use preview/dry-run or install/enable the worker later.'
                if not profile.get('available')
                else 'No fix required.',
            }
        )
    return {
        'schema_version': '1.0',
        'generated_by': 'worker_registry.py',
        'generated_at': utc_now(),
        'workers': workers,
    }


def write_worker_registry(project: Path) -> dict[str, Any]:
    payload = registry_payload(project)
    write_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json', payload)
    return payload


def worker_by_name(name: str) -> ProfileWorker | None:
    if name in default_workers():
        return default_workers()[name]
    for worker in default_workers().values():
        if name and name == worker.provider:
            return worker
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect configured AI Project Operator workers.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--doctor', action='store_true')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = write_worker_registry(project)
    if args.doctor:
        healthy = [item for item in payload['workers'] if item.get('available')]
        print(
            json.dumps(
                {
                    'status': 'ok',
                    'available_workers': len(healthy),
                    'registry': '.zoo-agent/workers/worker_registry.json',
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
