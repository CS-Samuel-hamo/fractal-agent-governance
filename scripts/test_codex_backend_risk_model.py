#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(
    cmd: list[str], cwd: Path, *, check: bool = True, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='codex-backend-risk-')).resolve()
    (repo / 'README.md').write_text('# Risk\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'risk@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Risk Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def write_backend_profile(
    repo: Path, *, health_status: str, allow_fast_actual: bool, allow_parallel_actual: bool
) -> Path:
    profile_path = repo / '.zoo-agent' / 'backend' / 'codex-backend-profile.json'
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'backend': 'codex_cli',
        'version': 'test',
        'codex_home': str(repo / 'fake-codex-home'),
        'platform': 'windows',
        'shell': 'powershell',
        'sandbox_default': 'workspace-write',
        'network_default': 'disabled',
        'approval_policy': 'on-request',
        'trusted_directory_required': True,
        'supports_exec': True,
        'supports_output_last_message': True,
        'supports_workspace_cd': True,
        'health_status': health_status,
        'last_health_check_at': utc_now(),
        'health_ttl_minutes': 60,
        'known_risks': ['windows_sandbox_fragility', 'timeout_or_slow_thinking'],
        'recommended_usage': {
            'allow_fast_actual': allow_fast_actual,
            'allow_parallel_actual': allow_parallel_actual,
            'allow_governed_actual': False,
            'require_worktree': True,
            'require_scope_guard': True,
            'require_delivery_gate': True,
            'default_to_dry_run': not allow_fast_actual,
        },
        'fallbacks': ['dry_run_only', 'manual_codex_task_pack', 'gpt_planning_only'],
    }
    profile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    health_path = repo / '.zoo-agent' / 'backend' / 'codex-health-full.json'
    health_path.write_text(
        json.dumps({'health_verdict': health_status.upper(), 'generated_at': utc_now()}, indent=2), encoding='utf-8'
    )
    return profile_path


def test_profile_and_cached_health(repo: Path, env: dict[str, str]) -> None:
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_codex_backend_health.py'),
            '--workspace',
            str(repo),
            '--mode',
            'full',
            '--skip-real-codex',
            '--codex-home',
            env['CODEX_HOME'],
        ],
        ROOT,
        env=env,
    )
    profile_path = repo / '.zoo-agent' / 'backend' / 'codex-backend-profile.json'
    health_path = repo / '.zoo-agent' / 'backend' / 'codex-health-full.json'
    assert profile_path.exists()
    assert health_path.exists()
    profile = load(profile_path)
    assert profile['backend'] == 'codex_cli'
    assert profile['recommended_usage']['require_scope_guard'] is True
    assert profile['recommended_usage']['require_delivery_gate'] is True
    assert 'token_cost_uncertainty' in profile['known_risks']
    before = health_path.stat().st_mtime_ns
    run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-cache',
            '--task-id',
            'task-cache',
            '--dry-run',
            'fix README typo',
        ],
        repo,
        env=env,
    )
    after = health_path.stat().st_mtime_ns
    assert before == after, 'dry-run fast path should not repeat full health check'
    report = load(repo / '.zoo-agent' / 'runs' / 'run-cache' / 'cli-runtime' / 'task-cache.json')
    assert report['route'] == 'fast'
    assert 'implementation-queue.json' not in [p.name for p in (repo / '.zoo-agent' / 'runs' / 'run-cache').glob('*')]


def test_failure_taxonomy(env: dict[str, str]) -> None:
    timeout = run(
        [sys.executable, str(ROOT / 'scripts' / 'classify_codex_failure.py'), '--worker-status', 'timeout'],
        ROOT,
        check=False,
        env=env,
    )
    payload = json.loads(timeout.stdout)
    assert payload['failure_type'] == 'timeout'
    assert payload['is_backend_failure'] is True
    no_delivery = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'classify_codex_failure.py'),
            '--delivery-outcome',
            'no_delivery',
        ],
        ROOT,
        check=False,
        env=env,
    )
    payload = json.loads(no_delivery.stdout)
    assert payload['failure_type'] == 'no_delivery'
    assert payload['is_task_failure'] is True
    scope = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'classify_codex_failure.py'),
            '--delivery-outcome',
            'unsafe',
            '--scope-guard-status',
            'fail',
        ],
        ROOT,
        check=False,
        env=env,
    )
    payload = json.loads(scope.stdout)
    assert payload['failure_type'] == 'scope_violation'
    assert payload['is_backend_failure'] is False


def test_unhealthy_profile_policy(repo: Path, env: dict[str, str]) -> None:
    missing_home = str(repo / 'missing-codex-home')
    proc = run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_codex_backend_health.py'),
            '--workspace',
            str(repo),
            '--mode',
            'full',
            '--skip-real-codex',
            '--codex-home',
            missing_home,
        ],
        ROOT,
        check=False,
        env=env,
    )
    assert proc.returncode == 20
    profile = load(repo / '.zoo-agent' / 'backend' / 'codex-backend-profile.json')
    assert profile['health_status'] == 'unhealthy'
    assert profile['recommended_usage']['allow_fast_actual'] is False
    assert profile['recommended_usage']['default_to_dry_run'] is True


def test_route_blocks_actual_fast_with_fresh_unhealthy_profile(repo: Path, env: dict[str, str]) -> None:
    health_path = repo / '.zoo-agent' / 'backend' / 'codex-health-full.json'
    write_backend_profile(repo, health_status='unhealthy', allow_fast_actual=False, allow_parallel_actual=False)
    before = health_path.stat().st_mtime_ns
    proc = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--workspace',
            str(repo),
            '--run-id',
            'run-unhealthy-actual',
            '--task-id',
            'task-unhealthy-actual',
            '--allow-ambiguous-fast',
            '--timeout-seconds',
            '5',
            'fix README typo',
        ],
        repo,
        check=False,
        env=env,
    )
    assert proc.returncode == 21
    after = health_path.stat().st_mtime_ns
    assert before == after, 'fresh unhealthy cache should block actual run without repeating full health'
    report = load(repo / '.zoo-agent' / 'runs' / 'run-unhealthy-actual' / 'cli-runtime' / 'task-unhealthy-actual.json')
    assert report['route'] == 'fast'
    execution = report['execution']
    assert execution['status'] == 'blocked_codex_backend_health_check_required'
    assert execution['codex_launched'] is False
    assert execution.get('backend_check_run') == {}
    assert execution['failure_classification']['is_backend_failure'] is True


def test_route_blocks_parallel_actual_with_warning_profile(repo: Path, env: dict[str, str]) -> None:
    docs = repo / 'docs'
    docs.mkdir(exist_ok=True)
    (docs / 'a.md').write_text('# A\n', encoding='utf-8')
    (docs / 'b.md').write_text('# B\n', encoding='utf-8')
    run(['git', 'add', 'docs/a.md', 'docs/b.md'], repo, env=env)
    run(['git', 'commit', '-m', 'add docs'], repo, env=env)
    health_path = repo / '.zoo-agent' / 'backend' / 'codex-health-full.json'
    write_backend_profile(
        repo, health_status='healthy_with_warnings', allow_fast_actual=True, allow_parallel_actual=False
    )
    before = health_path.stat().st_mtime_ns
    task = 'update docs/a.md\nupdate docs/b.md'
    proc = run(
        [
            sys.executable,
            str(AGENT),
            'run',
            '--parallel',
            '--workspace',
            str(repo),
            '--run-id',
            'run-warning-parallel',
            '--task-id',
            'task-warning-parallel',
            '--timeout-seconds',
            '5',
            task,
        ],
        repo,
        check=False,
        env=env,
    )
    assert proc.returncode == 21
    after = health_path.stat().st_mtime_ns
    assert before == after, 'fresh warning cache should deny parallel actual without repeating full health'
    report = load(repo / '.zoo-agent' / 'runs' / 'run-warning-parallel' / 'cli-runtime' / 'task-warning-parallel.json')
    assert report['route'] == 'parallel'
    assert report['classification']['independent'] is True
    execution = report['execution']
    assert execution['status'] == 'blocked_codex_backend_not_healthy_for_parallel'
    assert execution['parallel_denial_reason'] == 'backend_health_not_healthy_for_parallel'
    assert execution.get('backend_check_run') == {}


def test_safe_config_templates() -> None:
    config = (ROOT / 'templates' / 'codex' / 'config.safe.toml.example').read_text(encoding='utf-8')
    rules = (ROOT / 'templates' / 'codex' / 'rules.safe.example').read_text(encoding='utf-8')
    assert 'danger_full_access_default = false' in config
    assert 'network_access = false' in config
    assert 'API keys' in config
    assert 'Full Access' not in rules or 'automatically' in rules


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='codex-home-risk-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    repo = init_repo(env)
    test_profile_and_cached_health(repo, env)
    test_failure_taxonomy(env)
    test_unhealthy_profile_policy(repo, env)
    test_route_blocks_actual_fast_with_fresh_unhealthy_profile(repo, env)
    test_route_blocks_parallel_actual_with_warning_profile(repo, env)
    test_safe_config_templates()
    print('codex backend risk model tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
