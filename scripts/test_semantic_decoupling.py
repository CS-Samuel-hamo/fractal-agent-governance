#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_core import RuntimeCore

FORBIDDEN_PREFIX = 'codex_'
FORBIDDEN_VERIFIER_TERMS = ['codex_', 'Codex', 'codex']


def run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    if proc.returncode:
        raise AssertionError(proc.stdout)
    return proc.stdout


def temp_repo(prefix: str) -> Path:
    base = Path(tempfile.gettempdir())
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=str(base))).resolve()
    (repo / 'README.md').write_text('# Semantic Decoupling\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'semantic@example.local'], repo)
    run(['git', 'config', 'user.name', 'Semantic Decoupling Test'], repo)
    run(['git', 'add', '.'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def execution_result_from(payload: dict[str, Any]) -> dict[str, Any]:
    result = payload.get('result') or payload.get('pipeline', {}).get('result') or {}
    final_ref = result.get('final_result_ref') or ''
    execution_ref = str(Path(final_ref).parent / 'execution_result.json') if final_ref else ''
    if not execution_ref:
        iterations = result.get('iterations') or []
        execution_ref = iterations[-1].get('execution_result_ref') if iterations else ''
    assert execution_ref and Path(execution_ref).exists(), payload
    return json.loads(Path(execution_ref).read_text(encoding='utf-8-sig'))


def assert_no_forbidden_prefix(payload: Any, path: str = '$') -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert not str(key).startswith(FORBIDDEN_PREFIX), f'forbidden key {path}.{key}'
            assert_no_forbidden_prefix(value, f'{path}.{key}')
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_no_forbidden_prefix(value, f'{path}[{index}]')


def leaf_schema(execution: dict[str, Any]) -> set[str]:
    leaves = execution.get('leaf_results') or []
    assert leaves, execution
    leaf = leaves[0]
    required = {
        'backend_type',
        'backend_status',
        'backend_returncode',
        'execution_status',
        'diff',
        'confidence',
        'execution_time',
        'notes',
    }
    assert required.issubset(set(leaf)), leaf
    return set(leaf)


def test_verifier_backend_agnostic_source() -> None:
    text = (ROOT / 'scripts' / 'pipeline_verifier.py').read_text(encoding='utf-8')
    for term in FORBIDDEN_VERIFIER_TERMS:
        assert term not in text


def test_mock_backend_execution_result_schema() -> None:
    repo = temp_repo('semantic-mock-')
    core = RuntimeCore(repo, backend='mock')
    payload = core.run_task(
        'append backend-neutral line',
        run_id='semantic-mock',
        dry_run=False,
        allow_actual=True,
        allowed_files=['README.md'],
    )
    execution = execution_result_from(payload)
    assert execution['execution_backend']['selected'] == 'mock'
    assert_no_forbidden_prefix(execution)
    leaf = execution['leaf_results'][0]
    assert leaf['backend_type'] == 'mock'
    assert leaf['delivery_outcome'] == 'delivered'


def test_codex_backend_dry_run_schema_equivalent() -> None:
    repo = temp_repo('semantic-codex-dry-')
    core = RuntimeCore(repo, backend='codex')
    payload = core.run_task(
        'dry-run backend-neutral line',
        run_id='semantic-codex-dry',
        dry_run=True,
        allow_actual=False,
        allowed_files=['README.md'],
    )
    execution = execution_result_from(payload)
    assert execution['execution_backend']['selected'] == 'codex'
    assert_no_forbidden_prefix(execution)
    mock_schema = leaf_schema(execution)
    assert {'backend_type', 'backend_status', 'backend_returncode', 'diff'}.issubset(mock_schema)


def test_runtime_core_has_no_backend_specific_import() -> None:
    text = (ROOT / 'scripts' / 'runtime_core.py').read_text(encoding='utf-8')
    assert 'codex_backend_plugin' not in text
    assert 'run_codex_worker' not in text


def test_verifier_result_has_backend_fields_only() -> None:
    repo = temp_repo('semantic-verifier-')
    core = RuntimeCore(repo, backend='mock')
    payload = core.run_pipeline(
        'append verifier neutral line',
        run_id='semantic-verifier',
        dry_run=False,
        allow_actual=True,
        allowed_files=['README.md'],
    )
    result = payload.get('result') or {}
    final_ref = result.get('final_result_ref')
    assert final_ref
    final_payload = json.loads(Path(final_ref).read_text(encoding='utf-8-sig'))
    assert final_payload['backend_invoked'] is False
    assert_no_forbidden_prefix(final_payload)


def main() -> int:
    test_verifier_backend_agnostic_source()
    test_mock_backend_execution_result_schema()
    test_codex_backend_dry_run_schema_equivalent()
    test_runtime_core_has_no_backend_specific_import()
    test_verifier_result_has_backend_fields_only()
    print('semantic decoupling tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
