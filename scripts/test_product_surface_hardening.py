#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'

ABSOLUTE_PATH_RE = re.compile(r'[A-Za-z]:[\\/]')
DEFAULT_FORBIDDEN = [
    'goal_state_manager',
    'runtime_status.py',
    'global_loop_state',
    'loop_state',
    'scheduler',
    'planner',
    'executor',
    'verifier',
    'aggregation',
    'execution_result',
    'pipeline_loop.py',
]
DOC_FORBIDDEN = [
    'goal_state_manager',
    'runtime_status.py',
    'global_loop_state',
    'loop_state',
    'scheduler',
    'planner',
    'executor',
    'verifier',
    'aggregation',
    'backend list',
    'backend switch',
    'agent run ',
    'agent pipeline',
    'agent goal',
]


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
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


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f'expected JSON product output, got: {proc.stdout}') from exc


def assert_product_payload(text: str) -> dict:
    assert not ABSOLUTE_PATH_RE.search(text), f'absolute path leaked in product output: {text}'
    lowered = text.lower()
    for term in DEFAULT_FORBIDDEN:
        assert term not in lowered, f'internal runtime term leaked in product output: {term}'
    parsed = payload(type('Completed', (), {'stdout': text})())
    assert sorted(parsed) == ['mode', 'result', 'task'], parsed
    return parsed


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='product-surface-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Product Surface\n\nInitial text.\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'surface@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Product Surface Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_docs_clean() -> None:
    public_docs = [
        'README.md',
        'INSTALL.md',
        'QUICKSTART.md',
        'EXAMPLES.md',
        'CLI_REFERENCE.md',
        'ARCHITECTURE.md',
        'docs/README.md',
        'docs/product-mind-model.md',
    ]
    for rel in public_docs:
        text = (ROOT / rel).read_text(encoding='utf-8')
        assert '.py' not in text, f'{rel} exposes script file paths'
        assert not ABSOLUTE_PATH_RE.search(text), f'{rel} exposes a local absolute path'
        lowered = text.lower()
        for term in DOC_FORBIDDEN:
            assert term not in lowered, f'{rel} exposes internal or old product term: {term}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='product-surface-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)

    assert_docs_clean()
    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)

    no_bootstrap_preview = run(
        [
            sys.executable,
            str(AGENT),
            'fix README typo',
            '--workspace',
            str(repo),
            '--allowed-file',
            'README.md',
        ],
        repo,
        env=env,
    )
    first = assert_product_payload(no_bootstrap_preview.stdout)
    assert first['mode'] == 'preview'

    status = run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env)
    assert_product_payload(status.stdout)

    undo = run([sys.executable, str(AGENT), 'undo', '--workspace', str(repo)], repo, env=env)
    assert_product_payload(undo.stdout)

    for typo in ['rum', 'runn']:
        typo_result = run([sys.executable, str(AGENT), typo], repo, env=env, check=False)
        assert typo_result.returncode != 0
        typo_payload = assert_product_payload(typo_result.stdout)
        assert 'try: agent "' in typo_payload['result']

    debug_status = run([sys.executable, str(AGENT), 'debug', 'status', '--workspace', str(repo)], repo, env=env)
    assert any(term in debug_status.stdout for term in ['runtime_status', 'goal_state', 'loop_state'])

    debug_trace = run([sys.executable, str(AGENT), 'debug', 'trace', '--workspace', str(repo)], repo, env=env)
    assert debug_trace.returncode == 0

    print('product surface hardening tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
