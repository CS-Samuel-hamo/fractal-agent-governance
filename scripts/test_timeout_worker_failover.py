from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import pipeline_executor
from bounded_docs_writer import apply_docs_patch, is_safe_docs_target
from remote_ai_worker_adapter import health as remote_health


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def repo(name: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()
    (root / 'project_beginning_prompt.md').write_text(
        'Build a research workflow. Include literature mapping, evidence tracking, validation, and uncertainty controls.',
        encoding='utf-8',
    )
    (root / 'docs').mkdir()
    (root / 'docs' / 'research_workflow.md').write_text('# Research workflow\n\nExisting notes.\n', encoding='utf-8')
    return root


def timeout_attempt(*args: Any, **kwargs: Any) -> dict[str, Any]:
    leaf = kwargs['leaf']
    return {
        'attempt': kwargs.get('attempt_no', 1),
        'task_dir': str(kwargs.get('task_dir')),
        'backend_result': {'backend': 'codex', 'status': 'failed', 'returncode': 124},
        'worker_status': {'status': 'failed', 'returncode': 124},
        'delivery': {
            'delivery_outcome': 'blocked',
            'reason': 'backend_worker_timeout',
            'scope_guard_status': 'pass',
            'business_changed_files': [],
            'runtime_changed_files': [],
            'denied_files_touched': [],
            'out_of_scope_files': [],
        },
        'execution_model': pipeline_executor.build_execution_result_model(
            task_id=str(leaf.get('leaf_id') or 'leaf'),
            backend_returncode=124,
            worker_status='timeout',
            business_changed_files=[],
            expected_files=pipeline_executor.expected_files_for_leaf(leaf),
            retry_count=0,
            notes='backend_worker_timeout',
        ),
    }


def test_codex_timeout_docs_failover_writes_target() -> None:
    project = repo('timeout-docs-failover')
    leaf = {
        'leaf_id': 'leaf-001',
        'objective': '根据 project_beginning_prompt.md 扩展 docs/research_workflow.md，加入文献、证据和验证流程',
        'risk_level': 'low',
        'allowed_files': ['docs/research_workflow.md'],
        'denied_files': ['.env', '.env.*', 'secrets/**'],
    }
    original = pipeline_executor.execute_leaf_once
    pipeline_executor.execute_leaf_once = timeout_attempt
    try:
        result = pipeline_executor.resilient_execute_leaf(
            workspace=project,
            task_dir=project / '.zoo-agent' / 'runs' / 'unit' / 'pipeline' / 'executor-task-packs' / 'leaf-001',
            leaf=leaf,
            plan={'run_id': 'unit'},
            sandbox='workspace-write',
            timeout_seconds=30,
            max_retries=0,
            backend_name='codex',
            docs_failover_enabled=True,
        )
    finally:
        pipeline_executor.execute_leaf_once = original
    final_delivery = result['final_delivery']
    assert_true(final_delivery['delivery_outcome'] == 'delivered', 'docs failover did not deliver')
    assert_true(
        final_delivery['business_changed_files'] == ['docs/research_workflow.md'], 'changed file evidence missing'
    )
    assert_true(result['fallback_used'] == 'bounded_docs_writer', 'bounded docs fallback was not used')
    text = (project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8')
    assert_true('文献、证据和验证流程' in text, 'research workflow section missing')


def test_bounded_docs_writer_rejects_unsafe_targets_and_avoids_duplicates() -> None:
    project = repo('bounded-docs-safety')
    objective = '根据 project_beginning_prompt.md 扩展 docs/research_workflow.md，加入文献、证据和验证流程'
    first = apply_docs_patch(project, objective=objective, target_files=['docs/research_workflow.md'])
    second = apply_docs_patch(project, objective=objective, target_files=['docs/research_workflow.md'])
    blocked = apply_docs_patch(project, objective='read token', target_files=['.env'])
    assert_true(first['status'] == 'success', 'first docs patch should succeed')
    assert_true(second['status'] == 'skipped', 'duplicate docs patch should be skipped')
    assert_true(blocked['status'] == 'blocked', 'secret-like target should be blocked')
    assert_true(is_safe_docs_target('docs/research_workflow.md'), 'safe docs path rejected')
    assert_true(not is_safe_docs_target('src/app.py'), 'source path accepted as docs target')


def test_remote_worker_health_does_not_store_key() -> None:
    project = repo('remote-worker-key-safety')
    old_key = os.environ.get('OPENAI_API_KEY')
    old_enabled = os.environ.get('AGENT_ENABLE_REMOTE_AI_WORKER')
    os.environ['OPENAI_API_KEY'] = 'sk-test-secret-value'
    os.environ['AGENT_ENABLE_REMOTE_AI_WORKER'] = 'true'
    try:
        payload = remote_health(project)
    finally:
        if old_key is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = old_key
        if old_enabled is None:
            os.environ.pop('AGENT_ENABLE_REMOTE_AI_WORKER', None)
        else:
            os.environ['AGENT_ENABLE_REMOTE_AI_WORKER'] = old_enabled
    text = json.dumps(payload, ensure_ascii=False)
    artifact = (project / '.zoo-agent' / 'workers' / 'remote_openai_worker_health.json').read_text(encoding='utf-8')
    assert_true(payload['available'] is True, 'remote worker should be available when explicitly enabled with key')
    assert_true('sk-test-secret-value' not in text, 'API key leaked in payload')
    assert_true('sk-test-secret-value' not in artifact, 'API key leaked in artifact')


def main() -> int:
    test_codex_timeout_docs_failover_writes_target()
    test_bounded_docs_writer_rejects_unsafe_targets_and_avoids_duplicates()
    test_remote_worker_health_does_not_store_key()
    print('timeout worker failover tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
