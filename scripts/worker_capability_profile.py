#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from claude_code_worker_detector import claude_health  # noqa: E402
from codex_worker_adapter_hardened import codex_health  # noqa: E402
from remote_ai_worker_adapter import health as remote_openai_health  # noqa: E402
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
    'project_structure_scan',
    'manifest_scan',
    'test_file_scan',
    'docs_file_scan',
    'project_map_support',
]


def worker_profiles(project: Path | None = None) -> dict[str, dict[str, Any]]:
    codex = codex_health(project)
    claude = claude_health(project)
    remote_openai = remote_openai_health(project)
    codex_is_available = bool(codex.get('available'))
    claude_detected = bool(claude.get('available'))
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
        'local_scanner_worker': {
            'worker_name': 'local_scanner_worker',
            'provider': 'local_scanner',
            'worker_type': 'analysis',
            'capabilities': ['repo_scan', 'project_structure_scan', 'manifest_scan', 'test_file_scan', 'docs_file_scan', 'project_map_support', 'analysis', 'safe_preview', 'local_only', 'low_cost', 'high_reliability'],
            'best_for': ['safe repo scan', 'project map evidence', 'local metadata scan'],
            'avoid_for': ['actual file edits', 'LLM reasoning'],
            'risk_limit': 'high',
            'supports_actual_execution': False,
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'free',
            'reliability_score': 0.99,
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
            'supports_actual_execution': bool(codex.get('supports_actual_execution')),
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'unknown',
            'reliability_score': 0.72 if codex_is_available else 0.0,
            'available': codex_is_available,
            'health': codex.get('health') or ('healthy' if codex_is_available else 'unavailable'),
            'unavailable_reason': '' if codex_is_available else str(codex.get('reason') or 'codex CLI not found'),
            'reason': str(codex.get('reason') or ''),
        },
        'remote_openai_worker': {
            'worker_name': 'remote_openai_worker',
            'provider': 'openai_api',
            'worker_type': 'docs',
            'capabilities': ['docs_edit', 'analysis', 'safe_preview', 'actual_execution', 'long_context'],
            'best_for': ['bounded docs generation when explicitly enabled'],
            'avoid_for': ['unbounded source edits', 'secrets', 'blocked zones'],
            'risk_limit': 'low',
            'supports_actual_execution': bool(remote_openai.get('supports_actual_execution')),
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'unknown',
            'reliability_score': 0.78 if remote_openai.get('available') else 0.0,
            'available': bool(remote_openai.get('available')),
            'health': remote_openai.get('health') or 'unavailable',
            'unavailable_reason': '' if remote_openai.get('available') else str(remote_openai.get('reason') or 'remote AI worker disabled'),
            'reason': str(remote_openai.get('reason') or ''),
        },
        'bounded_docs_writer': {
            'worker_name': 'bounded_docs_writer',
            'provider': 'local_docs',
            'worker_type': 'docs',
            'capabilities': ['docs_edit', 'safe_preview', 'actual_execution', 'local_only', 'low_cost', 'high_reliability'],
            'best_for': ['low-risk single-file docs updates', 'safe docs fallback'],
            'avoid_for': ['source code edits', 'config changes', 'fictional citations or results'],
            'risk_limit': 'low',
            'supports_actual_execution': True,
            'supports_preview': True,
            'supports_session': True,
            'cost_class': 'free',
            'reliability_score': 0.93,
            'available': True,
            'health': 'healthy',
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
            'supports_session': bool(claude_detected),
            'cost_class': 'unknown',
            'reliability_score': 0.15 if claude_detected else 0.0,
            'available': bool(claude_detected),
            'health': 'degraded' if claude_detected else 'unavailable',
            'unavailable_reason': '' if claude_detected else str(claude.get('reason') or 'Claude Code CLI not detected'),
            'reason': str(claude.get('reason') or ''),
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
    payload = {'schema_version': '1.0', 'capabilities': CAPABILITIES, 'profiles': list(worker_profiles(project).values())}
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'workers' / 'worker_capability_profiles.json'
    write_json(output, payload)
    print(json.dumps({'status': 'ok', 'profiles': str(output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
