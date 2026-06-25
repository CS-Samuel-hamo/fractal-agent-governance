#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def temp_repo(name: str) -> Path:
    base = Path(tempfile.gettempdir())
    if not base.exists():
        base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix=f'leaf-convergence-{name}-', dir=str(base))).resolve()
    (repo / '.zoo-agent').mkdir(parents=True)
    return repo


def write_backend(repo: Path, status: str) -> None:
    write_json(repo / '.zoo-agent' / 'backend' / 'codex-backend-profile.json', {'health_status': status})


def write_leaf(repo: Path, run_id: str, leaf: dict) -> Path:
    leaf.setdefault('schema_version', '1.0')
    leaf.setdefault('generated_by', 'test_leaf_convergence_runtime.py')
    leaf.setdefault('run_id', run_id)
    leaf.setdefault('parent_goal_id', 'goal-test')
    leaf.setdefault('denied_files', ['.env', '.env.*', '**/*.pem', '**/*.key'])
    leaf.setdefault('test_commands', [])
    leaf.setdefault('rollback_note', 'discard isolated worktree')
    path = repo / '.zoo-agent' / 'runs' / run_id / 'leaf-tasks' / f'{leaf["leaf_id"]}.json'
    write_json(path, leaf)
    return path


def controller(repo: Path, run_id: str, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'leaf_convergence_controller.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            *extra,
        ],
        repo,
        check=check,
    )


def test_infinite_decomposition_prevention() -> None:
    repo = temp_repo('no-infinite')
    write_backend(repo, 'unknown')
    run_id = 'run-no-infinite'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Clarify unknown surface',
            'task_type': 'docs',
            'risk_level': 'low',
            'owned_resources': ['unknown'],
            'allowed_files': [],
            'provides': ['unknown'],
            'consumes': [],
            'acceptance': [],
            'test_policy': 'not_applicable',
            'preferred_route': 'dry_run_only',
            'execution_mode': 'dry_run_only',
            'execution_allowed': False,
        },
    )
    controller(repo, run_id)
    report = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-convergence-report.json')
    item = report['resolutions'][0]
    assert item['resolution_path'].count('refine') <= 1
    assert item['final_resolution'] in {'merge', 'defer', 'collapse', 'execute'}


def test_no_acceptance_leaf_records_readiness() -> None:
    repo = temp_repo('missing-acceptance')
    write_backend(repo, 'unknown')
    run_id = 'run-missing-acceptance'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Update docs/a.md with bounded wording',
            'task_type': 'docs',
            'risk_level': 'low',
            'owned_resources': ['docs-a'],
            'allowed_files': ['docs/a.md'],
            'provides': ['docs-a'],
            'consumes': [],
            'acceptance': [],
            'test_policy': 'not_applicable',
            'preferred_route': 'dry_run_only',
            'execution_mode': 'dry_run_only',
            'execution_allowed': False,
        },
    )
    run(
        [
            sys.executable,
            str(ROOT / 'scripts' / 'check_task_readiness.py'),
            '--workspace',
            str(repo),
            '--run-id',
            run_id,
            '--leaf-id',
            'leaf-001',
        ],
        repo,
    )
    readiness = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-tasks' / 'leaf-001-readiness.json')
    assert readiness['readiness']['verdict'] == 'BLOCKED_MISSING_ACCEPTANCE'
    assert readiness['resolution']['resolution_path'][0] == 'refine'


def test_unresolved_leaf_defers_to_backlog() -> None:
    repo = temp_repo('defer')
    write_backend(repo, 'unknown')
    run_id = 'run-defer'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Implement bounded change for src/app.py',
            'task_type': 'code',
            'risk_level': 'low',
            'owned_resources': ['src-app'],
            'allowed_files': ['src/app.py'],
            'provides': ['src-app'],
            'consumes': [],
            'acceptance': ['Function behavior is covered by a focused test.'],
            'test_policy': 'required',
            'preferred_route': 'fast',
            'execution_mode': 'actual_allowed',
            'execution_allowed': True,
        },
    )
    controller(repo, run_id)
    backlog = load(repo / '.zoo-agent' / 'runs' / run_id / 'follow-up-backlog.json')
    assert backlog['items'][0]['leaf_id'] == 'leaf-001'
    assert (
        load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-convergence-report.json')['resolutions'][0][
            'final_resolution'
        ]
        == 'defer'
    )


def test_merge_scenario() -> None:
    repo = temp_repo('merge')
    write_backend(repo, 'healthy')
    run_id = 'run-merge'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Coordinate unknown parent resource',
            'task_type': 'code',
            'risk_level': 'low',
            'owned_resources': ['unknown'],
            'allowed_files': ['src/app.py'],
            'provides': ['unknown'],
            'consumes': ['unknown'],
            'acceptance': ['Parent resource is clarified.'],
            'test_policy': 'required',
            'preferred_route': 'dry_run_only',
            'execution_mode': 'dry_run_only',
            'execution_allowed': False,
        },
    )
    controller(repo, run_id)
    merged = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-merge-to-parent.json')
    assert merged['items'][0]['leaf_id'] == 'leaf-001'


def test_micro_task_collapse() -> None:
    repo = temp_repo('collapse')
    write_backend(repo, 'unknown')
    run_id = 'run-collapse'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Append exact line to README.md as a minimal micro task',
            'task_type': 'docs',
            'risk_level': 'low',
            'owned_resources': ['readme'],
            'allowed_files': ['README.md'],
            'provides': ['readme'],
            'consumes': [],
            'acceptance': ['README.md contains the exact validation line.'],
            'test_policy': 'not_applicable',
            'preferred_route': 'dry_run_only',
            'execution_mode': 'dry_run_only',
            'execution_allowed': False,
            'collapse_hint': True,
        },
    )
    controller(repo, run_id)
    micro = load(repo / '.zoo-agent' / 'runs' / run_id / 'micro-tasks.json')
    assert micro['items'][0]['leaf_id'] == 'leaf-001'


def test_codex_execution_valid_leaf() -> None:
    repo = temp_repo('execute')
    write_backend(repo, 'healthy')
    run_id = 'run-execute'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Implement bounded change for src/app.py',
            'task_type': 'code',
            'risk_level': 'low',
            'owned_resources': ['src-app'],
            'allowed_files': ['src/app.py'],
            'provides': ['src-app'],
            'consumes': [],
            'acceptance': ['Code change is bounded and testable.'],
            'test_policy': 'required',
            'preferred_route': 'fast',
            'execution_mode': 'actual_allowed',
            'execution_allowed': True,
        },
    )
    controller(repo, run_id)
    report = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-convergence-report.json')
    assert report['resolutions'][0]['final_resolution'] == 'execute'
    queue = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-execution-queue.json')
    assert queue['items'][0]['requires_explicit_confirmation'] is True


def test_loop_detection() -> None:
    repo = temp_repo('loop')
    write_backend(repo, 'unknown')
    run_id = 'run-loop'
    write_leaf(
        repo,
        run_id,
        {
            'leaf_id': 'leaf-001',
            'objective': 'Clarify vague task',
            'task_type': 'docs',
            'risk_level': 'low',
            'owned_resources': ['unknown'],
            'allowed_files': [],
            'provides': ['unknown'],
            'consumes': [],
            'acceptance': [],
            'test_policy': 'not_applicable',
            'preferred_route': 'dry_run_only',
            'execution_mode': 'dry_run_only',
            'execution_allowed': False,
        },
    )
    proc = controller(repo, run_id, '--max-resolution-depth', '1', check=False)
    assert proc.returncode == 10
    report = load(repo / '.zoo-agent' / 'runs' / run_id / 'leaf-convergence-report.json')
    assert report['status'] == 'convergence_failure'


def main() -> int:
    tests = [
        test_infinite_decomposition_prevention,
        test_no_acceptance_leaf_records_readiness,
        test_unresolved_leaf_defers_to_backlog,
        test_merge_scenario,
        test_micro_task_collapse,
        test_codex_execution_valid_leaf,
        test_loop_detection,
    ]
    for test in tests:
        print(f'== {test.__name__} ==')
        test()
    print('leaf convergence runtime tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
