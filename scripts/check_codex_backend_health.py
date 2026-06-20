#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from detect_codex_backend_profile import build_profile  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402


def run_command(command: list[str], cwd: Path, *, timeout: int = 0) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout or None,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'NO_COLOR': '1'},
        )
        return {
            'command': [str(item) for item in command],
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip(),
            'stderr': proc.stderr.strip(),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in command],
            'returncode': 124,
            'stdout': exc.stdout if isinstance(exc.stdout, str) else '',
            'stderr': exc.stderr if isinstance(exc.stderr, str) else '',
            'timed_out': True,
        }
    except Exception as exc:
        return {
            'command': [str(item) for item in command],
            'returncode': 127,
            'stdout': '',
            'stderr': f'{type(exc).__name__}: {exc}',
        }


def codex_command() -> str:
    return shutil.which('codex') or shutil.which('codex.cmd') or shutil.which('codex.exe') or 'codex'


def is_fresh(payload: dict[str, Any], ttl_minutes: int) -> bool:
    generated = str(payload.get('generated_at') or '')
    if not generated:
        return False
    try:
        created = datetime.datetime.fromisoformat(generated.replace('Z', '+00:00'))
        if created.tzinfo is None:
            created = created.replace(tzinfo=datetime.timezone.utc)
        age = datetime.datetime.now(datetime.timezone.utc) - created.astimezone(datetime.timezone.utc)
        return age.total_seconds() <= ttl_minutes * 60
    except ValueError:
        return False


def disk_probe() -> dict[str, Any]:
    target = Path.cwd().anchor
    try:
        usage = shutil.disk_usage(str(target))
        return {
            'target': str(target),
            'free_gb': round(usage.free / (1024 ** 3), 3),
            'status': 'pass' if usage.free > 1024 ** 3 else 'warning_low_space',
        }
    except Exception as exc:
        return {'target': str(target), 'status': 'unknown', 'error': f'{type(exc).__name__}: {exc}'}


def health_payload(
    *,
    mode: str,
    project: Path,
    codex_home: str,
    ttl_minutes: int,
    timeout_seconds: int,
    no_output_timeout_seconds: int,
    skip_real_codex: bool,
) -> dict[str, Any]:
    backend = project / '.zoo-agent' / 'backend'
    full = load_json(backend / 'codex-health-full.json')
    quick: dict[str, Any] = {}
    blockers: list[str] = []
    warnings: list[str] = []
    command = codex_command()
    codex_home_exists = bool(codex_home and Path(codex_home).exists())
    if codex_home and not codex_home_exists:
        blockers.append('codex_home_unavailable')
    version = run_command([command, '--version'], ROOT, timeout=2 if mode == 'quick' else 60)
    if version.get('returncode') != 0:
        blockers.append('codex_not_installed_or_version_failed')
    disk = disk_probe()
    if disk.get('status') != 'pass':
        warnings.append(str(disk.get('status') or 'disk_warning'))
    full_fresh = is_fresh(full, ttl_minutes)

    worker_health: dict[str, Any] = {'status': 'skipped'}
    if mode == 'full':
        worker_command = [
            sys.executable,
            str(ROOT / 'scripts' / 'check_codex_worker_health.py'),
            '--codex-home',
            codex_home,
            '--timeout-seconds',
            str(timeout_seconds),
            '--no-output-timeout-seconds',
            str(no_output_timeout_seconds),
            '--output-dir',
            str(backend),
        ]
        if skip_real_codex:
            worker_command.append('--skip-real-codex')
        worker_result = run_command(worker_command, ROOT, timeout=timeout_seconds + 90)
        worker_latest = load_json(backend / 'codex-worker-health-latest.json')
        worker_health = {
            'command_result': worker_result,
            'latest': worker_latest,
        }
        verdict = str(worker_latest.get('verdict') or '')
        if verdict == 'UNHEALTHY':
            blockers.extend(str(item) for item in worker_latest.get('blockers') or ['worker_health_unhealthy'])
        elif verdict == 'HEALTHY_WITH_WARNINGS':
            warnings.extend(str(item) for item in worker_latest.get('warnings') or ['worker_health_warning'])
        elif verdict != 'HEALTHY':
            blockers.append('worker_health_missing_or_failed')
    elif not full_fresh:
        warnings.append('full_health_missing_or_stale')

    verdict = 'HEALTHY'
    if blockers:
        verdict = 'UNHEALTHY'
    elif warnings:
        verdict = 'HEALTHY_WITH_WARNINGS'
    execution_gate = {
        'HEALTHY': {
            'allow_actual': True,
            'allow_parallel_actual': True,
            'allowed_modes': ['fast_actual', 'parallel_actual_if_independent', 'dry_run', 'planning', 'decomposition', 'reporting'],
        },
        'HEALTHY_WITH_WARNINGS': {
            'allow_actual': True,
            'allow_single_low_risk_leaf_actual': True,
            'allow_parallel_actual': False,
            'allowed_modes': ['single_low_risk_leaf_actual', 'dry_run', 'planning', 'decomposition', 'reporting'],
        },
        'UNHEALTHY': {
            'allow_actual': False,
            'allow_parallel_actual': False,
            'allowed_modes': ['dry_run', 'planning', 'decomposition', 'reporting'],
        },
    }[verdict]

    return {
        'schema_version': '1.0',
        'generated_by': 'check_codex_backend_health.py',
        'generated_at': utc_now(),
        'mode': mode,
        'verdict': verdict,
        'health_status': verdict.lower(),
        'workspace': str(project),
        'codex_home': {
            'path': codex_home,
            'exists': codex_home_exists,
            'auth_files_read': False,
        },
        'codex_version': version,
        'disk': disk,
        'full_health_fresh': full_fresh,
        'health_ttl_minutes': ttl_minutes,
        'worker_health': worker_health,
        'execution_gate': execution_gate,
        'blockers': sorted(set(blockers)),
        'warnings': sorted(set(warnings)),
        'secrets_read': False,
    }


def write_markdown(path: Path, payload: dict[str, Any], profile: dict[str, Any]) -> None:
    lines = [
        '# Codex Backend Health',
        '',
        f"- mode: {payload['mode']}",
        f"- verdict: {payload['verdict']}",
        f"- generated_at: {payload['generated_at']}",
        f"- profile_health_status: {profile.get('health_status')}",
        f"- allow_fast_actual: {profile.get('recommended_usage', {}).get('allow_fast_actual')}",
        f"- allow_parallel_actual: {profile.get('recommended_usage', {}).get('allow_parallel_actual')}",
        f"- health_execution_gate: {payload.get('execution_gate', {}).get('allowed_modes')}",
        '',
        '## Blockers',
        '',
    ]
    lines.extend([f"- {item}" for item in payload.get('blockers') or []] or ['- none'])
    lines.extend(['', '## Warnings', ''])
    lines.extend([f"- {item}" for item in payload.get('warnings') or []] or ['- none'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Check cached Codex backend health for the CLI runtime.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--mode', choices=['quick', 'full'], default='quick')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME', ''))
    parser.add_argument('--health-ttl-minutes', type=int, default=60)
    parser.add_argument('--timeout-seconds', type=int, default=240)
    parser.add_argument('--no-output-timeout-seconds', type=int, default=120)
    parser.add_argument('--skip-real-codex', action='store_true')
    args = parser.parse_args()

    project = project_root(args.workspace)
    backend = project / '.zoo-agent' / 'backend'
    backend.mkdir(parents=True, exist_ok=True)
    payload = health_payload(
        mode=args.mode,
        project=project,
        codex_home=args.codex_home,
        ttl_minutes=args.health_ttl_minutes,
        timeout_seconds=args.timeout_seconds,
        no_output_timeout_seconds=args.no_output_timeout_seconds,
        skip_real_codex=args.skip_real_codex,
    )
    health_path = backend / f"codex-health-{args.mode}.json"
    write_json(health_path, payload)
    profile = build_profile(project, codex_home=args.codex_home, health_ttl_minutes=args.health_ttl_minutes)
    write_json(backend / 'codex-backend-profile.json', profile)
    if args.mode == 'full':
        write_markdown(backend / 'codex-health-full.md', payload, profile)
    print(json.dumps({'verdict': payload['verdict'], 'mode': args.mode, 'health_json': str(health_path), 'profile_json': str(backend / 'codex-backend-profile.json'), 'blockers': payload['blockers'], 'warnings': payload['warnings']}, ensure_ascii=True, indent=2))
    return 0 if payload['verdict'] in {'HEALTHY', 'HEALTHY_WITH_WARNINGS'} else 20


if __name__ == '__main__':
    raise SystemExit(main())
