#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


KNOWN_RISKS = [
    'local_command_execution_risk',
    'full_access_danger',
    'sandbox_complexity',
    'network_access_risk',
    'windows_sandbox_fragility',
    'wsl_windows_path_split',
    'cloud_model_capacity',
    'timeout_or_slow_thinking',
    'context_compaction_loss',
    'agents_md_drift',
    'config_precedence_complexity',
    'mcp_experimental_surface',
    'auth_data_policy_complexity',
    'install_update_supply_chain_risk',
    'token_cost_uncertainty',
]


def run_version(timeout: int = 2) -> dict[str, Any]:
    command = shutil.which('codex') or shutil.which('codex.cmd') or shutil.which('codex.exe') or 'codex'
    try:
        proc = subprocess.run(
            [command, '--version'],
            cwd=ROOT,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'NO_COLOR': '1'},
        )
        return {
            'command': command,
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
            'version': proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else '',
        }
    except Exception as exc:
        return {
            'command': command,
            'returncode': 127,
            'stdout': '',
            'stderr': f'{type(exc).__name__}: {exc}',
            'version': '',
        }


def platform_name() -> str:
    if sys.platform.startswith('win'):
        return 'windows'
    if sys.platform == 'darwin':
        return 'macos'
    if 'microsoft' in platform.release().lower():
        return 'wsl'
    if sys.platform.startswith('linux'):
        return 'linux'
    return 'unknown'


def latest_health(project: Path) -> dict[str, Any]:
    backend = project / '.zoo-agent' / 'backend'
    for name in ['codex-health-full.json', 'codex-health-quick.json']:
        payload = load_json(backend / name)
        if payload:
            payload['_path'] = str(backend / name)
            return payload
    return {}


def recommended_usage(health_status: str, risks: list[str]) -> dict[str, Any]:
    allow_fast = health_status in {'healthy', 'healthy_with_warnings'}
    allow_parallel = health_status == 'healthy' and 'windows_sandbox_fragility' not in risks
    return {
        'allow_fast_actual': allow_fast,
        'allow_parallel_actual': allow_parallel,
        'allow_governed_actual': False,
        'require_worktree': True,
        'require_scope_guard': True,
        'require_delivery_gate': True,
        'default_to_dry_run': not allow_fast,
    }


def build_profile(project: Path, *, codex_home: str = '', health_ttl_minutes: int = 60) -> dict[str, Any]:
    version = run_version()
    health = latest_health(project)
    verdict = str(health.get('verdict') or health.get('health_status') or 'unknown')
    health_status = {
        'HEALTHY': 'healthy',
        'HEALTHY_WITH_WARNINGS': 'healthy_with_warnings',
        'UNHEALTHY': 'unhealthy',
    }.get(verdict, verdict.lower() if verdict else 'unknown')
    risks = list(KNOWN_RISKS)
    if platform_name() != 'windows' and 'windows_sandbox_fragility' in risks:
        risks.remove('windows_sandbox_fragility')
    return {
        'schema_version': '1.0',
        'generated_by': 'detect_codex_backend_profile.py',
        'generated_at': utc_now(),
        'backend': 'codex_cli',
        'version': version.get('version', ''),
        'codex_home': codex_home or os.environ.get('CODEX_HOME', ''),
        'platform': platform_name(),
        'shell': os.environ.get('ComSpec') or os.environ.get('SHELL') or '',
        'sandbox_default': 'unknown',
        'network_default': 'unknown',
        'approval_policy': 'unknown',
        'trusted_directory_required': True,
        'supports_exec': version.get('returncode') == 0,
        'supports_output_last_message': True,
        'supports_workspace_cd': True,
        'health_status': health_status,
        'last_health_check_at': health.get('generated_at', ''),
        'health_ttl_minutes': health_ttl_minutes,
        'known_risks': risks,
        'recommended_usage': recommended_usage(health_status, risks),
        'fallbacks': [
            'dry_run_only',
            'manual_codex_task_pack',
            'deepseek_executor',
            'gpt_planning_only',
            'human_intervention',
        ],
        'health_source': health.get('_path', ''),
        'codex_version_probe': {
            'returncode': version.get('returncode'),
            'command': version.get('command'),
        },
        'secrets_read': False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Detect Codex CLI backend capability and risk profile.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', ''))
    parser.add_argument('--health-ttl-minutes', type=int, default=60)
    parser.add_argument('--output', default='')
    args = parser.parse_args()

    project = project_root(args.workspace)
    profile = build_profile(project, codex_home=args.codex_home, health_ttl_minutes=args.health_ttl_minutes)
    output = Path(args.output).resolve() if args.output else project / '.zoo-agent' / 'backend' / 'codex-backend-profile.json'
    write_json(output, profile)
    print(json.dumps(profile, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
