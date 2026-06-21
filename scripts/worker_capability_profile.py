#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, write_json  # noqa: E402


CAPABILITIES = [
    'repo_scan',
    'project_map_update',
    'docs_edit',
    'code_edit',
    'tests_edit',
    'refactor',
    'analysis',
    'command_execution',
    'safe_preview',
    'actual_execution',
    'long_context',
    'low_cost',
    'high_reliability',
    'local_only',
]


def codex_available() -> bool:
    return bool(shutil.which('codex'))


def worker_profiles() -> dict[str, dict[str, Any]]:
    codex_is_available = codex_available()
    return {
        'mock_worker': {
            'worker_name': 'mock_worker',
            'provider': 'mock',
            'worker_type': 'mock',
            'capabilities': ['docs_edit', 'code_edit', 'tests_edit', 'safe_preview', 'actual_execution', 'low_cost', 'high_reliability'],
            'best_for': ['controlled tests', 'dogfood', 'safe fixture execution'],
            'avoid_for': ['production-quality implementation judgment'],
            'risk_limit': 'low',
            'supports_actual_execution': True,
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'free',
            'reliability_score': 0.95,
            'available': True,
            'health': 'healthy',
        },
        'dry_run_worker': {
            'worker_name': 'dry_run_worker',
            'provider': 'dry_run',
            'worker_type': 'dry_run',
            'capabilities': ['repo_scan', 'analysis', 'safe_preview', 'project_map_update', 'low_cost', 'high_reliability'],
            'best_for': ['preview', 'analysis', 'safe fallback'],
            'avoid_for': ['actual file edits'],
            'risk_limit': 'high',
            'supports_actual_execution': False,
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'free',
            'reliability_score': 0.98,
            'available': True,
            'health': 'healthy',
        },
        'codex_worker_existing_adapter': {
            'worker_name': 'codex_worker_existing_adapter',
            'provider': 'codex',
            'worker_type': 'code',
            'capabilities': ['docs_edit', 'code_edit', 'tests_edit', 'refactor', 'analysis', 'command_execution', 'safe_preview', 'actual_execution', 'long_context'],
            'best_for': ['bounded code edits', 'tests', 'local patch generation'],
            'avoid_for': ['blocked zones', 'unbounded project execution'],
            'risk_limit': 'medium',
            'supports_actual_execution': True,
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'unknown',
            'reliability_score': 0.72 if codex_is_available else 0.0,
            'available': codex_is_available,
            'health': 'healthy' if codex_is_available else 'unavailable',
        },
        'claude_worker_stub': {
            'worker_name': 'claude_worker_stub',
            'provider': 'claude',
            'worker_type': 'analysis',
            'capabilities': ['analysis', 'long_context', 'safe_preview'],
            'best_for': ['future long-context review'],
            'avoid_for': ['actual execution until configured'],
            'risk_limit': 'low',
            'supports_actual_execution': False,
            'supports_preview': True,
            'supports_session': False,
            'cost_class': 'unknown',
            'reliability_score': 0.0,
            'available': False,
            'health': 'unavailable',
        },
        'local_worker_stub': {
            'worker_name': 'local_worker_stub',
            'provider': 'local',
            'worker_type': 'analysis',
            'capabilities': ['repo_scan', 'analysis', 'safe_preview', 'local_only'],
            'best_for': ['future local analysis'],
            'avoid_for': ['actual execution until configured'],
            'risk_limit': 'low',
            'supports_actual_execution': False,
            'supports_preview': True,
            'supports_session': False,
            'cost_class': 'free',
            'reliability_score': 0.0,
            'available': False,
            'health': 'unavailable',
        },
    }


def profile_for(worker_name: str) -> dict[str, Any]:
    return worker_profiles().get(worker_name, {})


def main() -> int:
    parser = argparse.ArgumentParser(description='Render worker capability profiles.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = {'schema_version': '1.0', 'capabilities': CAPABILITIES, 'profiles': list(worker_profiles().values())}
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'workers' / 'worker_capability_profiles.json'
    write_json(output, payload)
    print(json.dumps({'status': 'ok', 'profiles': str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
