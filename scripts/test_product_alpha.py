#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(
    cmd: list[str], cwd: Path, *, env: dict[str, str] | None = None, check: bool = True
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


def payload(proc: subprocess.CompletedProcess[str]) -> dict:
    return json.loads(proc.stdout)


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='product-alpha-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Product Alpha\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'product-alpha@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Product Alpha'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_public_payload(text: str) -> dict:
    parsed = json.loads(text)
    assert sorted(parsed) == ['mode', 'result', 'task'], parsed
    forbidden = ['planner', 'executor', 'verifier', 'scheduler', 'goal_state', 'pipeline_loop.py']
    lowered = text.lower()
    for item in forbidden:
        assert item not in lowered, f'public output leaked internal term: {item}'
    return parsed


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='product-alpha-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)

    for required in [
        'README.md',
        'INSTALL.md',
        'QUICKSTART.md',
        'EXAMPLES.md',
        'ARCHITECTURE.md',
        'CLI_REFERENCE.md',
        'docs/product-mind-model.md',
    ]:
        assert (ROOT / required).exists(), f'missing product document: {required}'

    expected_version = (
        (ROOT / 'VERSION').read_text(encoding='utf-8-sig').strip() if (ROOT / 'VERSION').exists() else '0.9.'
    )
    version = run([sys.executable, str(AGENT), '--version'], ROOT, env=env).stdout
    assert expected_version in version

    help_text = run([sys.executable, str(AGENT), '--help'], ROOT, env=env).stdout.lower()
    for visible in ['agent "<task>"', 'status', 'undo', 'preview', 'apply']:
        assert visible in help_text
    for hidden in ['planner', 'executor', 'verifier', 'scheduler', 'backend list', 'pipeline "']:
        assert hidden not in help_text

    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)

    preview = assert_public_payload(
        run(
            [
                sys.executable,
                str(AGENT),
                'add a short README note',
                '--workspace',
                str(repo),
                '--allowed-file',
                'README.md',
                '--preview',
            ],
            repo,
            env=env,
        ).stdout
    )
    assert preview['mode'] == 'preview'
    assert preview['result'] == 'PREVIEW_READY'

    default_preview = assert_public_payload(
        run(
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
        ).stdout
    )
    assert default_preview['mode'] == 'preview'

    applied = assert_public_payload(
        run(
            [
                sys.executable,
                str(AGENT),
                'add a controlled README line',
                '--workspace',
                str(repo),
                '--allowed-file',
                'README.md',
                '--apply',
            ],
            repo,
            env=env,
        ).stdout
    )
    assert applied['mode'] == 'apply'

    status = assert_public_payload(
        run([sys.executable, str(AGENT), 'status', '--workspace', str(repo), '--no-write'], repo, env=env).stdout
    )
    assert status['mode'] == 'status'

    undo = assert_public_payload(
        run([sys.executable, str(AGENT), 'undo', '--workspace', str(repo)], repo, env=env).stdout
    )
    assert undo['mode'] == 'preview'

    debug = run([sys.executable, str(AGENT), 'debug', 'status', '--workspace', str(repo)], repo, env=env)
    assert any(term in debug.stdout for term in ['goal_state', 'loop_state', 'runtime_status'])

    print('product alpha tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
