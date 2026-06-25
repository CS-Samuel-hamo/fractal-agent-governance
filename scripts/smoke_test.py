#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_ROO_ENTRYPOINTS = [
    'agent.cmd',
    'agent',
    'wrappers/agent.ps1',
    'wrappers/agent.sh',
    '.roo/commands/agent-bootstrap.md',
    '.roo/commands/agent-run.md',
    '.roo/commands/codex-task.md',
    '.roo/commands/codex-run.md',
    '.roo/commands/codex-ingest.md',
    '.roo/commands/codex-review.md',
    '.roo/commands/progress.md',
    '.roo/rules/01-ai-native-zoo-entrypoints.md',
    'scripts/agent.py',
    'scripts/set_goal.py',
    'scripts/get_goal.py',
    'scripts/check_goal_alignment.py',
    'scripts/loop_controller.py',
    'scripts/task_classifier.py',
    'scripts/route_task.py',
    'scripts/update_runtime_metrics.py',
    'scripts/init_project_instructions.py',
    'scripts/check_project_map_alignment.py',
    'scripts/runtime_status.py',
    'scripts/rollback_task.py',
    'scripts/reroute_task.py',
    'scripts/runtime_review.py',
    'docs/CLI_FIRST_AGENT_RUNTIME.md',
]


def run(cmd, cwd=None, check=True, env=None):
    print('$', ' '.join(map(str, cmd)))
    p = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    print(p.stdout)
    if check and p.returncode:
        raise SystemExit(p.returncode)
    return p


def load_agent_bootstrap_module():
    spec = importlib.util.spec_from_file_location('agent_bootstrap_smoke', ROOT / 'scripts' / 'agent_bootstrap.py')
    if spec is None or spec.loader is None:
        raise SystemExit('Unable to import agent_bootstrap.py for smoke assertions')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    for item in REQUIRED_ROO_ENTRYPOINTS:
        assert (ROOT / item).exists(), f'missing Roo/Zoo entrypoint: {item}'
    assert (ROOT / 'docs' / 'VIBE_CODING_CROSS_VALIDATION.md').exists(), 'missing Vibe Coding cross-validation doc'
    reviewer_rule = (ROOT / '.roo' / 'rules-agent-reviewer' / '02-ai-native-review.md').read_text(encoding='utf-8')
    integrator_rule = (ROOT / '.roo' / 'rules-agent-integrator' / '03-codex-worker-merge-policy.md').read_text(
        encoding='utf-8'
    )
    if 'goal alignment' not in reviewer_rule or 'repeatability' not in reviewer_rule:
        raise SystemExit('Expected reviewer rule to require Vibe Coding cross-validation dimensions')
    if 'goal alignment evidence' not in integrator_rule or 'conflict keys' not in integrator_rule:
        raise SystemExit('Expected integrator rule to require objective and concurrency checks')
    tmp = Path(tempfile.mkdtemp(prefix='zoo-codex-worker-smoke-'))
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(tmp / '.codex-home'))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    print('Smoke repo:', tmp)
    print('Smoke CODEX_HOME:', env['CODEX_HOME'])
    run(['git', 'init'], tmp, env=env)
    run(['git', 'config', 'user.email', 'zoo-smoke@example.local'], tmp, env=env)
    run(['git', 'config', 'user.name', 'Zoo Smoke'], tmp, env=env)
    (tmp / 'src').mkdir()
    (tmp / 'tests').mkdir()
    (tmp / '.zoo-agent' / 'goals').mkdir(parents=True)
    (tmp / 'src' / 'example.py').write_text('def add(a,b):\n    return a+b\n', encoding='utf-8')
    (tmp / 'tests' / 'test_example.py').write_text(
        'from src.example import add\n\ndef test_add():\n    assert add(1,2)==3\n', encoding='utf-8'
    )
    (tmp / '.zoo-agent' / 'project-charter.json').write_text(
        json.dumps(
            {
                'mission': 'Keep the sample project aligned while allowing bounded cleanup tasks.',
                'product_goals': ['Maintain a simple arithmetic API'],
                'technical_goals': ['Prefer small reversible changes'],
                'non_goals': ['Do not replace the project mission during routine review'],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (tmp / '.zoo-agent' / 'current-run.json').write_text(
        json.dumps(
            {
                'run_id': 'run-test',
                'goal_id': 'goal-main',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (tmp / '.zoo-agent' / 'goals' / 'goal-main.json').write_text(
        json.dumps(
            {
                'goal_id': 'goal-main',
                'root_goal': 'Preserve the sample arithmetic API while improving bounded implementation details.',
                'success_criteria': ['Local task changes do not rewrite the root goal'],
                'constraints': ['Treat cleanup requests as current tasks unless durable update is explicit'],
                'created_at': '2026-06-03T00:00:00Z',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    run(['git', 'add', '.'], tmp, env=env)
    run(['git', 'commit', '-m', 'init'], tmp, env=env)

    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'bootstrap',
            '--workspace',
            str(tmp),
            '--goal-id',
            'goal-main',
            '--goal',
            'Preserve the sample arithmetic API while improving bounded implementation details.',
            '--force',
        ],
        cwd=tmp,
        env=env,
    )
    runtime_marker = tmp / '.zoo-agent' / 'runtime-v4.json'
    if not runtime_marker.exists():
        raise SystemExit('Expected CLI-first runtime marker')
    runtime_payload = json.loads(runtime_marker.read_text(encoding='utf-8'))
    if runtime_payload.get('runtime_model', {}).get('codex_cli') != 'execution backend':
        raise SystemExit('Expected Codex CLI execution backend role in runtime marker')
    if not (tmp / 'AGENTS.md').exists():
        raise SystemExit('Expected bootstrap to create AGENTS.md')
    if not (tmp / '.zoo-agent' / 'code-standards.json').exists():
        raise SystemExit('Expected bootstrap to create code standards')
    if not (tmp / '.zoo-agent' / 'project-map.json').exists():
        raise SystemExit('Expected bootstrap to create initial project map')
    run(['python', str(ROOT / 'scripts' / 'agent.py'), 'standards', 'check', '--workspace', str(tmp)], cwd=tmp, env=env)
    run(['python', str(ROOT / 'scripts' / 'agent.py'), 'map', 'check', '--workspace', str(tmp)], cwd=tmp, env=env)
    run(['python', str(ROOT / 'scripts' / 'agent.py'), 'status', '--workspace', str(tmp)], cwd=tmp, env=env)
    (tmp / 'AGENTS.md').unlink()
    (tmp / '.zoo-agent' / 'code-standards.json').unlink()
    (tmp / '.zoo-agent' / 'project-map.json').unlink()
    (tmp / '.zoo-agent' / 'project-map.md').unlink()
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'bootstrap',
            '--workspace',
            str(tmp),
            '--goal-id',
            'goal-main',
            '--goal',
            'Preserve the sample arithmetic API while improving bounded implementation details.',
        ],
        cwd=tmp,
        env=env,
    )
    if not (tmp / 'AGENTS.md').exists():
        raise SystemExit('Expected already-bootstrapped bootstrap to repair missing AGENTS.md')
    if not (tmp / '.zoo-agent' / 'code-standards.json').exists():
        raise SystemExit('Expected already-bootstrapped bootstrap to repair missing code standards')
    if not (tmp / '.zoo-agent' / 'project-map.json').exists():
        raise SystemExit('Expected already-bootstrapped bootstrap to repair missing project map')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'bootstrap',
            '--workspace',
            str(tmp),
            '--goal-id',
            'goal-main',
            '--goal',
            'Preserve the sample arithmetic API while improving bounded implementation details.',
            '--refresh-instructions',
        ],
        cwd=tmp,
        env=env,
    )
    if not (tmp / 'AGENTS.md.new').exists():
        raise SystemExit('Expected refresh-instructions to write AGENTS.md.new proposal')
    if not (tmp / '.zoo-agent' / 'code-standards.json.new').exists():
        raise SystemExit('Expected refresh-instructions to write code-standards proposal')
    run(
        ['python', str(ROOT / 'scripts' / 'agent.py'), 'standards', 'promote', '--workspace', str(tmp)],
        cwd=tmp,
        env=env,
    )
    if (tmp / 'AGENTS.md.new').exists() or (tmp / '.zoo-agent' / 'code-standards.json.new').exists():
        raise SystemExit('Expected standards promote to consume proposals')
    run(['python', str(ROOT / 'scripts' / 'agent.py'), 'map', 'refresh', '--workspace', str(tmp)], cwd=tmp, env=env)
    if not (tmp / '.zoo-agent' / 'project-map.json.new').exists():
        raise SystemExit('Expected map refresh to write project-map proposal')
    run(['python', str(ROOT / 'scripts' / 'agent.py'), 'map', 'promote', '--workspace', str(tmp)], cwd=tmp, env=env)
    if (tmp / '.zoo-agent' / 'project-map.json.new').exists():
        raise SystemExit('Expected map promote to consume project-map proposal')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'get_goal.py'),
            '--workspace',
            str(tmp),
            '--goal-id',
            'goal-main',
            '--require',
        ],
        cwd=tmp,
        env=env,
    )
    alignment = run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_goal_alignment.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-cli',
            '--task-id',
            'task-align',
            '--goal-id',
            'goal-main',
            '--objective',
            'Preserve arithmetic API behavior while adding a bounded implementation comment',
        ],
        cwd=tmp,
        env=env,
    )
    alignment_payload = json.loads(alignment.stdout)
    if alignment_payload.get('status') not in {'pass', 'needs_review'}:
        raise SystemExit('Expected non-blocked goal alignment')
    classifier = run(
        [
            'python',
            str(ROOT / 'scripts' / 'task_classifier.py'),
            '--workspace',
            str(tmp),
            '--input-text',
            'Fix sample arithmetic API implementation comment',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
        ],
        cwd=tmp,
        env=env,
    )
    classifier_payload = json.loads(classifier.stdout)
    if classifier_payload.get('path') != 'fast':
        raise SystemExit('Expected CLI classifier fast path for bounded task')
    parallel_classifier = run(
        [
            'python',
            str(ROOT / 'scripts' / 'task_classifier.py'),
            '--workspace',
            str(tmp),
            '--input-text',
            'Update src/example.py\nUpdate tests/test_example.py',
        ],
        cwd=tmp,
        env=env,
    )
    parallel_payload = json.loads(parallel_classifier.stdout)
    if parallel_payload.get('path') != 'parallel' or not parallel_payload.get('independent'):
        raise SystemExit('Expected CLI classifier to detect independent parallel tasks')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'route_task.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-cli',
            '--task-id',
            'task-cli-fast',
            '--goal-id',
            'goal-main',
            '--fast',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--input-text',
            'Preserve sample arithmetic API with a bounded implementation comment',
            '--dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    cli_report = tmp / '.zoo-agent' / 'runs' / 'run-cli' / 'cli-runtime' / 'task-cli-fast.json'
    if not cli_report.exists():
        raise SystemExit('Expected CLI runtime report')
    cli_payload = json.loads(cli_report.read_text(encoding='utf-8'))
    if cli_payload.get('selected_path') != 'fast' or cli_payload.get('goal_id') != 'goal-main':
        raise SystemExit('Expected fast CLI route bound to goal-main')
    if not (tmp / '.zoo-agent' / 'runs' / 'run-cli' / 'goal-alignment' / 'task-cli-fast.json').exists():
        raise SystemExit('Expected CLI goal alignment artifact')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'run',
            '--workspace',
            str(tmp),
            '--run-id',
            'run-agent',
            '--task-id',
            'task-agent-fast',
            '--goal-id',
            'goal-main',
            '--fast',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--dry-run',
            'Preserve',
            'sample',
            'arithmetic',
            'API',
            'comment',
        ],
        cwd=tmp,
        env=env,
    )
    agent_report = tmp / '.zoo-agent' / 'runs' / 'run-agent' / 'cli-runtime' / 'task-agent-fast.json'
    if not agent_report.exists():
        raise SystemExit('Expected agent run to call CLI router')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'reroute',
            '--workspace',
            str(tmp),
            '--run-id',
            'run-agent',
            '--task-id',
            'task-agent-fast',
            '--path',
            'governed',
            '--dry-run',
            '--no-execute-governed-workers',
        ],
        cwd=tmp,
        env=env,
    )
    if not (tmp / '.zoo-agent' / 'runs' / 'run-agent' / 'route-audit' / 'task-agent-fast.json').exists():
        raise SystemExit('Expected reroute audit artifact')
    metrics_path = tmp / '.zoo-agent' / 'metrics' / 'agent-runtime-v4.json'
    metrics = json.loads(metrics_path.read_text(encoding='utf-8'))
    for metric_key in [
        'fast_path_rate',
        'parallel_execution_rate',
        'governed_path_rate',
        'codex_latency',
        'doc_overproduction_rate',
        'code_delivery_rate',
    ]:
        if metric_key not in metrics.get('metrics', {}):
            raise SystemExit(f'Expected runtime metric: {metric_key}')
    run(['git', 'add', '.zoo-agent', 'AGENTS.md'], tmp, env=env)
    run(['git', 'commit', '-m', 'cli runtime bootstrap'], tmp, env=env)

    rollback_worktree = tmp / '.zoo-agent' / 'worktrees' / 'run-rollback' / 'task-rollback' / 'attempt-1'
    run(
        ['git', 'worktree', 'add', '-b', 'zoo/rollback-smoke/task-rollback', str(rollback_worktree), 'HEAD'],
        tmp,
        env=env,
    )
    rollback_run_dir = tmp / '.zoo-agent' / 'runs' / 'run-rollback' / 'optimistic-runs'
    rollback_run_dir.mkdir(parents=True, exist_ok=True)
    (rollback_run_dir / 'task-rollback.json').write_text(
        json.dumps(
            {
                'run_id': 'run-rollback',
                'task_id': 'task-rollback',
                'attempts': [{'task_id': 'task-rollback', 'worktree': str(rollback_worktree)}],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'rollback',
            '--workspace',
            str(tmp),
            '--run-id',
            'run-rollback',
            '--task-id',
            'task-rollback',
            '--dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    if not rollback_worktree.exists():
        raise SystemExit('Expected rollback dry-run to keep worktree')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent.py'),
            'rollback',
            '--workspace',
            str(tmp),
            '--run-id',
            'run-rollback',
            '--task-id',
            'task-rollback',
            '--yes',
        ],
        cwd=tmp,
        env=env,
    )
    if rollback_worktree.exists():
        raise SystemExit('Expected rollback --yes to remove managed worktree')

    out = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'codex-tasks' / 'task-001'
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'generate_codex_task_pack.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-001',
            '--objective',
            'Change add to support integers and add a comment',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--denied-file',
            '.env',
            '--denied-file',
            'pyproject.toml',
            '--acceptance',
            'Scope guard passes',
            '--test-command',
            'python -m pytest',
        ],
        cwd=tmp,
        env=env,
    )
    assert (out / 'CODEX_TASK_PROMPT.md').exists(), 'missing task prompt'
    if 'goal_id: "goal-main"' not in (out / 'TASKS.yaml').read_text(encoding='utf-8'):
        raise SystemExit('Expected task pack TASKS.yaml to bind goal-main')
    task_metadata = json.loads((out / 'task-metadata.json').read_text(encoding='utf-8'))
    if task_metadata.get('goal_id') != 'goal-main':
        raise SystemExit('Expected task metadata to bind goal-main')
    fast_out = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'codex-tasks' / 'task-fast'
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'generate_codex_task_pack.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-fast',
            '--objective',
            'Fast path prompt smoke test',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
            '--prompt-template',
            'CODEX_TASK_PROMPT_FAST.md',
            '--output',
            str(fast_out),
        ],
        cwd=tmp,
        env=env,
    )
    assert 'Fast path contract' in (fast_out / 'CODEX_TASK_PROMPT.md').read_text(encoding='utf-8'), (
        'missing fast prompt content'
    )

    # Simulate allowed change
    (tmp / 'src' / 'example.py').write_text(
        'def add(a,b):\n    # simple integer addition\n    return a+b\n', encoding='utf-8'
    )
    (tmp / 'src' / '__pycache__').mkdir()
    (tmp / 'tests' / '__pycache__').mkdir()
    (tmp / '.pytest_cache').mkdir()
    (tmp / 'src' / '__pycache__' / 'example.pyc').write_bytes(b'cache')
    (tmp / 'tests' / '__pycache__' / 'test_example.pyc').write_bytes(b'cache')
    run(
        ['python', str(ROOT / 'scripts' / 'check_codex_scope.py'), 'task-001', '--tasks', str(out / 'TASKS.yaml')],
        cwd=tmp,
        env=env,
    )

    # Simulate denied change
    (tmp / 'pyproject.toml').write_text('[tool]\n', encoding='utf-8')
    p = run(
        ['python', str(ROOT / 'scripts' / 'check_codex_scope.py'), 'task-001', '--tasks', str(out / 'TASKS.yaml')],
        cwd=tmp,
        check=False,
        env=env,
    )
    if p.returncode == 0:
        raise SystemExit('Expected scope guard failure for denied file')

    # Collect result
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'collect_codex_result.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-001',
            '--task-dir',
            str(out),
            '--workspace',
            str(tmp),
        ],
        cwd=tmp,
        env=env,
    )
    collected_result_path = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'codex-results' / 'task-001' / 'result.json'
    collected_result = json.loads(collected_result_path.read_text(encoding='utf-8'))
    if not collected_result.get('environment_fingerprint', {}).get('python', {}).get('version'):
        raise SystemExit('Expected collected Codex result environment fingerprint')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'build_task_context.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-context-probe',
            '--workspace',
            str(tmp),
            '--user-request',
            'Review the entire project and clean up bounded issues',
            '--goal-id',
            'goal-main',
        ],
        cwd=tmp,
        env=env,
    )
    context_path = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'task-contexts' / 'task-context-probe.json'
    assert context_path.exists(), 'missing task context json'
    context_payload = json.loads(context_path.read_text(encoding='utf-8'))
    if context_payload['interpretation_policy'].get('default_interpretation') != 'current_user_request_is_current_task':
        raise SystemExit('Expected current-task interpretation policy')
    if context_payload['write_policy'].get('project_charter') != 'read_only':
        raise SystemExit('Expected read-only project charter policy')
    if context_payload['active_goal_context']['goal'].get('goal_id') != 'goal-main':
        raise SystemExit('Expected active goal in context envelope')
    context_pack = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'codex-tasks' / 'task-context-pack'
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'generate_codex_task_pack.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-context-pack',
            '--objective',
            'Task context copy smoke test',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--task-context',
            str(context_path),
            '--output',
            str(context_pack),
        ],
        cwd=tmp,
        env=env,
    )
    assert (context_pack / 'TASK_CONTEXT.json').exists(), 'missing copied TASK_CONTEXT.json'
    assert (context_pack / 'TASK_CONTEXT.md').exists(), 'missing copied TASK_CONTEXT.md'
    fast_select = run(
        [
            'python',
            str(ROOT / 'scripts' / 'select_execution_path.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-select-fast',
            '--objective',
            'Fix local rendering bug',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
        ],
        cwd=tmp,
        env=env,
    )
    fast_payload = json.loads(fast_select.stdout)
    if fast_payload.get('execution_graph', {}).get('chain_weight') != 'light':
        raise SystemExit('Expected light execution graph for fast path')
    if not fast_payload.get('execution_graph', {}).get('parallel_contract', {}).get('parallelizable'):
        raise SystemExit('Expected fast path to be parallelizable when conflict keys do not overlap')
    high_risk = run(
        [
            'python',
            str(ROOT / 'scripts' / 'select_execution_path.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-select-planned',
            '--objective',
            'Change authentication token validation',
            '--allowed-file',
            'src/auth/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
        ],
        cwd=tmp,
        env=env,
    )
    if '"recommended_path": "planned_worker"' not in high_risk.stdout:
        raise SystemExit('Expected planned_worker for hard-risk task')
    level2 = run(
        [
            'python',
            str(ROOT / 'scripts' / 'select_execution_path.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-select-level2',
            '--objective',
            'Implement a bounded service change',
            '--governance-level',
            '2',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
        ],
        cwd=tmp,
        env=env,
    )
    if '"reason": "governance_level_2"' not in level2.stdout:
        raise SystemExit('Expected governance_level_2 reason')
    level3 = run(
        [
            'python',
            str(ROOT / 'scripts' / 'select_execution_path.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-select-level3',
            '--objective',
            'Implement a multi-module workstream',
            '--governance-level',
            '3',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
        ],
        cwd=tmp,
        env=env,
    )
    if '"recommended_path": "fractal_governed"' not in level3.stdout:
        raise SystemExit('Expected fractal_governed for Level 3')
    level4 = run(
        [
            'python',
            str(ROOT / 'scripts' / 'select_execution_path.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-select-level4',
            '--objective',
            'Change production release flow',
            '--governance-level',
            '4',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
        ],
        cwd=tmp,
        env=env,
    )
    if '"recommended_path": "human_gate"' not in level4.stdout:
        raise SystemExit('Expected human_gate for Level 4')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_ai_native_task.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-dispatch-dry',
            '--workspace',
            str(tmp),
            '--objective',
            'Dispatcher dry run smoke test',
            '--goal-id',
            'goal-main',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
            '--dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    dispatch_context = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'task-contexts' / 'task-dispatch-dry.json'
    assert dispatch_context.exists(), 'missing dispatcher task context'
    selection = json.loads(
        (tmp / '.zoo-agent' / 'runs' / 'run-test' / 'executor-selection.json').read_text(encoding='utf-8')
    )
    if not selection.get('task_context', {}).get('json'):
        raise SystemExit('Expected task_context in executor selection')
    graph = selection.get('execution_graph') or {}
    if graph.get('chain') != 'optimistic_worker':
        raise SystemExit('Expected execution graph chain in dispatcher selection')
    if graph.get('judgment_node_count', 0) < 4:
        raise SystemExit('Expected execution graph judgment nodes')
    if graph.get('rollback_contract', {}).get('mode') != 'discard_isolated_worktree':
        raise SystemExit('Expected optimistic rollback mode')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_ai_native_task.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-dispatch-planned',
            '--workspace',
            str(tmp),
            '--objective',
            'Change authentication token validation',
            '--goal-id',
            'goal-main',
            '--allowed-file',
            'src/auth/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
        ],
        cwd=tmp,
        env=env,
    )
    planned_pack = (
        tmp / '.zoo-agent' / 'runs' / 'run-test' / 'codex-tasks' / 'task-dispatch-planned' / 'CODEX_TASK_PROMPT.md'
    )
    assert planned_pack.exists(), 'missing planned dispatcher task pack'
    assert (planned_pack.parent / 'TASK_CONTEXT.json').exists(), 'missing planned task context copy'
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_ai_native_task.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-dispatch-fractal',
            '--workspace',
            str(tmp),
            '--objective',
            'Implement a multi-module workstream',
            '--governance-level',
            '3',
            '--goal-id',
            'goal-main',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
        ],
        cwd=tmp,
        env=env,
    )
    fractal = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'fractal-workstreams' / 'task-dispatch-fractal.json'
    assert fractal.exists(), 'missing fractal workstream artifact'
    leaf_index = (
        tmp
        / '.zoo-agent'
        / 'runs'
        / 'run-test'
        / 'fractal-workstreams'
        / 'task-dispatch-fractal'
        / 'leaf-tasks'
        / 'leaf-tasks.json'
    )
    assert leaf_index.exists(), 'missing leaf skeleton index'
    leaf_payload = json.loads(leaf_index.read_text(encoding='utf-8'))
    if leaf_payload.get('leaf_count', 0) < 1:
        raise SystemExit('Expected at least one leaf skeleton')
    first_leaf_path = Path(leaf_payload['leaves'][0]['json'])
    first_leaf = json.loads(first_leaf_path.read_text(encoding='utf-8'))
    if 'run_ai_native_task.py' not in ' '.join(first_leaf.get('dispatcher_command', [])):
        raise SystemExit('Expected leaf dispatcher command')
    if '--goal-id' not in first_leaf.get('dispatcher_command', []):
        raise SystemExit('Expected leaf dispatcher command to preserve goal id')
    if first_leaf.get('recommended_governance_level') != 1:
        raise SystemExit('Expected leaf governance level 1')
    if not first_leaf.get('execution_graph'):
        raise SystemExit('Expected leaf execution graph')
    if not first_leaf.get('conflict_keys'):
        raise SystemExit('Expected leaf conflict keys')
    if first_leaf.get('rollback_mode') != 'discard_isolated_worktree':
        raise SystemExit('Expected leaf rollback mode')
    if 'conflict_keys' not in leaf_payload['leaves'][0]:
        raise SystemExit('Expected leaf index conflict keys')
    broad_parallel_check = run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_codex_worker_concurrency.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-test',
            '--leaf-index',
            str(leaf_index),
            '--max-workers',
            '2',
        ],
        cwd=tmp,
        check=False,
        env=env,
    )
    if broad_parallel_check.returncode == 0 or 'parallel_denial_reason' not in broad_parallel_check.stdout:
        raise SystemExit('Expected broad generated leaf to be blocked by conservative parallel policy')
    broad_scheduler = run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_codex_parallel_workers.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-test',
            '--leaf-index',
            str(leaf_index),
            '--max-workers',
            '2',
            '--dry-run',
        ],
        cwd=tmp,
        check=False,
        env=env,
    )
    if broad_scheduler.returncode == 0 or 'parallel_denial_reason' not in broad_scheduler.stdout:
        raise SystemExit('Expected broad generated scheduler dry-run to retain denial reason')
    scheduler_dir = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'parallel-workers' / 'task-dispatch-fractal'
    if not (scheduler_dir / 'resource-locks.json').exists():
        raise SystemExit('Expected parallel resource locks')
    if not (scheduler_dir / 'branch-schedule.json').exists():
        raise SystemExit('Expected parallel branch schedule')

    manual_leaf_dir = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'fractal-workstreams' / 'parallel-smoke' / 'leaf-tasks'
    manual_leaf_dir.mkdir(parents=True, exist_ok=True)
    leaf_a = dict(first_leaf)
    leaf_a.update(
        {
            'parent_task_id': 'parallel-smoke',
            'task_id': 'parallel-smoke-leaf-a',
            'objective': 'Parallel smoke leaf A',
            'allowed_files': ['src/example.py'],
            'test_commands': [],
            'parallelizable': True,
            'conflict_keys': ['src/example.py'],
            'recommended_execution_path': 'optimistic_worker',
        }
    )
    leaf_b = dict(first_leaf)
    leaf_b.update(
        {
            'parent_task_id': 'parallel-smoke',
            'task_id': 'parallel-smoke-leaf-b',
            'objective': 'Parallel smoke leaf B',
            'allowed_files': ['tests/test_example.py'],
            'test_commands': [],
            'parallelizable': True,
            'conflict_keys': ['tests/test_example.py'],
            'recommended_execution_path': 'optimistic_worker',
        }
    )
    leaf_a_path = manual_leaf_dir / 'parallel-smoke-leaf-a.json'
    leaf_b_path = manual_leaf_dir / 'parallel-smoke-leaf-b.json'
    leaf_a_path.write_text(json.dumps(leaf_a, ensure_ascii=False, indent=2), encoding='utf-8')
    leaf_b_path.write_text(json.dumps(leaf_b, ensure_ascii=False, indent=2), encoding='utf-8')
    manual_index = manual_leaf_dir / 'leaf-tasks.json'
    manual_index.write_text(
        json.dumps(
            {
                'parent_task_id': 'parallel-smoke',
                'status': 'draft',
                'leaf_count': 2,
                'leaves': [
                    {
                        'task_id': leaf_a['task_id'],
                        'json': str(leaf_a_path),
                        'conflict_keys': leaf_a['conflict_keys'],
                        'parallelizable': True,
                    },
                    {
                        'task_id': leaf_b['task_id'],
                        'json': str(leaf_b_path),
                        'conflict_keys': leaf_b['conflict_keys'],
                        'parallelizable': True,
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_codex_parallel_workers.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-test',
            '--leaf-index',
            str(manual_index),
            '--max-workers',
            '2',
            '--worker-dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    parallel_report = json.loads(
        (
            tmp / '.zoo-agent' / 'runs' / 'run-test' / 'parallel-workers' / 'parallel-smoke' / 'parallel-run.json'
        ).read_text(encoding='utf-8')
    )
    if parallel_report.get('status') != 'completed':
        raise SystemExit('Expected completed parallel worker dry run')
    if len(parallel_report.get('completed_workers') or []) != 2:
        raise SystemExit('Expected two completed parallel worker dry-run entries')
    merge_queue = json.loads(
        (tmp / '.zoo-agent' / 'runs' / 'run-test' / 'merge-queue.json').read_text(encoding='utf-8')
    )
    if merge_queue.get('queue_status') != 'record_only_parallel_candidates_not_processable':
        raise SystemExit('Expected record-only parallel merge queue')
    active_locks = json.loads((tmp / '.zoo-agent' / 'locks' / 'resource-locks.json').read_text(encoding='utf-8'))
    if active_locks.get('locks'):
        raise SystemExit('Expected parallel worker locks to be released after worker dry run')
    conflict_leaf_b = dict(leaf_b)
    conflict_leaf_b['conflict_keys'] = ['src/example.py']
    conflict_leaf_b_path = manual_leaf_dir / 'parallel-smoke-leaf-b-conflict.json'
    conflict_leaf_b_path.write_text(json.dumps(conflict_leaf_b, ensure_ascii=False, indent=2), encoding='utf-8')
    conflict_index = manual_leaf_dir / 'leaf-tasks-conflict.json'
    conflict_index.write_text(
        json.dumps(
            {
                'parent_task_id': 'parallel-smoke-conflict',
                'status': 'draft',
                'leaf_count': 2,
                'leaves': [
                    {
                        'task_id': leaf_a['task_id'],
                        'json': str(leaf_a_path),
                        'conflict_keys': leaf_a['conflict_keys'],
                        'parallelizable': True,
                    },
                    {
                        'task_id': conflict_leaf_b['task_id'],
                        'json': str(conflict_leaf_b_path),
                        'conflict_keys': conflict_leaf_b['conflict_keys'],
                        'parallelizable': True,
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    conflict_check = run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_codex_worker_concurrency.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'run-test',
            '--leaf-index',
            str(conflict_index),
        ],
        cwd=tmp,
        check=False,
        env=env,
    )
    if conflict_check.returncode == 0 or 'conflict_key_overlap' not in conflict_check.stdout:
        raise SystemExit('Expected concurrency checker to block overlapping conflict keys')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'manage_resource_locks.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--owner',
            'owner-a',
            '--conflict-key',
            'src/example',
            '--acquire',
        ],
        cwd=tmp,
        env=env,
    )
    lock_conflict = run(
        [
            'python',
            str(ROOT / 'scripts' / 'manage_resource_locks.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--owner',
            'owner-b',
            '--conflict-key',
            'src/example',
            '--acquire',
        ],
        cwd=tmp,
        check=False,
        env=env,
    )
    if lock_conflict.returncode == 0 or 'resource_locked' not in lock_conflict.stdout:
        raise SystemExit('Expected active resource lock conflict')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'manage_resource_locks.py'),
            '--workspace',
            str(tmp),
            '--owner',
            'owner-a',
            '--conflict-key',
            'src/example',
            '--release',
        ],
        cwd=tmp,
        env=env,
    )

    closure_run = tmp / '.zoo-agent' / 'runs' / 'closure-run'
    (closure_run / 'optimistic-runs').mkdir(parents=True, exist_ok=True)
    (closure_run / 'optimistic-runs' / 'closure-task.json').write_text(
        json.dumps(
            {
                'route_decision': {'task_id': 'closure-task', 'route': 'optimistic_worker'},
                'status': 'merge_candidate',
                'attempts': [
                    {
                        'task_id': 'closure-task',
                        'worktree': str(tmp),
                        'branch': 'closure-branch',
                        'test_results': [
                            {'command': 'python -m pytest tests', 'returncode': 0, 'stdout': '', 'stderr': ''}
                        ],
                        'collected_result': {
                            'scope_guard': {'status': 'pass'},
                            'git_diff_name_only': ['src/example.py'],
                        },
                        'policy': {'status': 'merge_candidate'},
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (closure_run / 'merge-queue.json').write_text(
        json.dumps(
            {
                'schema_version': '1.0',
                'queue_status': 'record_only_parallel_candidates_not_processable',
                'readiness_flags': {
                    'approved_for_merge': False,
                    'approved_for_deploy': False,
                    'approved_for_release': False,
                    'merge_queue_processing_authorized': False,
                },
                'candidates': [
                    {
                        'task_id': 'closure-task',
                        'status': 'merge_candidate',
                        'worktree': str(tmp),
                        'branch': 'closure-branch',
                        'changed_files': ['src/example.py'],
                    }
                ],
                'blockers': ['quality gate pending'],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (closure_run / 'goal-alignment').mkdir(parents=True, exist_ok=True)
    (closure_run / 'goal-alignment' / 'closure-task.json').write_text(
        json.dumps(
            {
                'schema_version': '1.0',
                'generated_by': 'smoke_test.py',
                'run_id': 'closure-run',
                'task_id': 'closure-task',
                'goal_id': 'goal-main',
                'status': 'pass',
                'alignment_score': 1.0,
                'basis': ['Synthetic closure task is aligned with the smoke goal.'],
                'warnings': [],
                'blockers': [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (tmp / '.zoo-agent' / 'TASKS.md').write_text('- [x] closure-task\n', encoding='utf-8')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_task_board_consistency.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
        ],
        cwd=tmp,
        env=env,
    )
    task_board_warning = run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_task_board_consistency.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--expect-task',
            'missing-board-task',
        ],
        cwd=tmp,
        check=False,
        env=env,
    )
    if task_board_warning.returncode == 0 or 'observed_tasks_missing_from_board' not in task_board_warning.stdout:
        raise SystemExit('Expected task-board consistency warning for missing task id')
    (tmp / '.zoo-agent' / 'TASKS.md').write_text('- [x] closure-task\n- [x] missing-board-task\n', encoding='utf-8')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'check_task_board_consistency.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--expect-task',
            'missing-board-task',
        ],
        cwd=tmp,
        env=env,
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'update_risk_register.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--add',
            '--risk-id',
            'risk-001',
            '--title',
            'Closure smoke open risk',
            '--severity',
            'high',
            '--source',
            'smoke',
        ],
        cwd=tmp,
        env=env,
    )
    risk_gate = run(
        ['python', str(ROOT / 'scripts' / 'run_quality_gate.py'), '--workspace', str(tmp), '--run-id', 'closure-run'],
        cwd=tmp,
        check=False,
        env=env,
    )
    if risk_gate.returncode == 0 or 'open_run_risks' not in risk_gate.stdout:
        raise SystemExit('Expected quality gate to block open risks')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'update_risk_register.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--close',
            '--risk-id',
            'risk-001',
            '--resolution',
            'Closed by smoke test',
        ],
        cwd=tmp,
        env=env,
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_quality_gate.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--authorize-merge-queue',
        ],
        cwd=tmp,
        env=env,
    )
    quality_gate = json.loads((closure_run / 'quality-gate.json').read_text(encoding='utf-8'))
    if quality_gate.get('gate_status') != 'pass' or not quality_gate.get('readiness_flags', {}).get(
        'merge_queue_processing_authorized'
    ):
        raise SystemExit('Expected quality gate pass with merge queue authorization')
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'process_merge_queue.py'),
            '--workspace',
            str(tmp),
            '--run-id',
            'closure-run',
            '--authorize',
            '--authorization-note',
            'Smoke quality gate passed',
        ],
        cwd=tmp,
        env=env,
    )
    processed_queue = json.loads((closure_run / 'merge-queue.json').read_text(encoding='utf-8'))
    if processed_queue.get('queue_status') != 'processable_pending_serial_integrator':
        raise SystemExit('Expected processable merge queue after authorization')
    if not (closure_run / 'merge-queue-processing.json').exists():
        raise SystemExit('Expected merge queue processing artifact')
    run(
        ['python', str(ROOT / 'scripts' / 'agent.py'), 'review', '--workspace', str(tmp), '--run-id', 'closure-run'],
        cwd=tmp,
        env=env,
    )
    if not (closure_run / 'runtime-review.json').exists():
        raise SystemExit('Expected runtime review artifact')
    summary = tmp / '.zoo-agent' / 'runs' / 'run-test' / 'ai-native-summary.json'
    assert summary.exists(), 'missing ai-native summary'
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'summarize_ai_native_run.py'),
            '--run-id',
            'run-test',
            '--workspace',
            str(tmp),
        ],
        cwd=tmp,
        env=env,
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_optimistic_worker.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-optimistic',
            '--workspace',
            str(tmp),
            '--objective',
            'Optimistic dry run smoke test',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
            '--dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'run_optimistic_worker.py'),
            '--run-id',
            'run-test',
            '--task-id',
            'task-planned-dry',
            '--workspace',
            str(tmp),
            '--objective',
            'Planned isolated dry run smoke test',
            '--execution-path',
            'planned_worker',
            '--full-prompt',
            '--allow-hard-risk',
            '--allowed-file',
            'src/**',
            '--allowed-file',
            'tests/**',
            '--test-command',
            'python -m pytest',
            '--dry-run',
        ],
        cwd=tmp,
        env=env,
    )
    print('Smoke test passed.')
    print('Codex CLI available:', bool(shutil.which('codex')))
    if shutil.which('codex'):
        run(
            [
                'python',
                str(ROOT / 'scripts' / 'run_codex_worker.py'),
                '--task-dir',
                str(out),
                '--workspace',
                str(tmp),
                '--dry-run',
            ],
            env=env,
        )

    local_project = Path(tempfile.mkdtemp(prefix='zoo-local-roo-override-'))
    (local_project / '.roo' / 'commands').mkdir(parents=True)
    (local_project / '.roo' / 'commands' / 'agent-run.md').write_text(
        '# Local Agent Run\n\nKeep local instructions.\n', encoding='utf-8'
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'sync_zoo_entrypoints.py'),
            '--project-root',
            str(local_project),
            '--project-only',
            '--backup-root',
            str(local_project / '.roo-backups'),
        ],
        cwd=ROOT,
        env=env,
    )
    local_agent = (local_project / '.roo' / 'commands' / 'agent-run.md').read_text(encoding='utf-8')
    if 'Keep local instructions.' not in local_agent:
        raise SystemExit('Expected project local agent-run content to be preserved')
    if 'AI_NATIVE_DISPATCHER_OVERRIDE' not in local_agent:
        raise SystemExit('Expected project local agent-run override marker')
    if not (local_project / '.roo' / 'rules' / '00-ai-native-global-bridge.md').exists():
        raise SystemExit('Expected project local bridge shim rule')
    if not (local_project / '.roo' / 'commands' / 'codex-task.md').exists():
        raise SystemExit('Expected missing lower-level command to be copied')
    if not (local_project / '.roo' / 'commands' / 'agent-bootstrap.md').exists():
        raise SystemExit('Expected agent bootstrap command to be copied')
    second = run(
        [
            'python',
            str(ROOT / 'scripts' / 'sync_zoo_entrypoints.py'),
            '--project-root',
            str(local_project),
            '--project-only',
            '--backup-root',
            str(local_project / '.roo-backups'),
            '--dry-run',
        ],
        cwd=ROOT,
        env=env,
    )
    second_payload = json.loads(second.stdout)
    drift = [
        item for item in second_payload.get('actions', []) if item.get('action') in {'write', 'copy', 'copy_missing'}
    ]
    if drift:
        raise SystemExit(f'Expected project local sync to be idempotent, got {drift}')

    unified_project = Path(tempfile.mkdtemp(prefix='zoo-unified-bootstrap-'))
    run(['git', 'init'], unified_project, env=env)
    (unified_project / 'src').mkdir()
    (unified_project / 'tests').mkdir()
    (unified_project / '.steward').mkdir()
    (unified_project / 'data').mkdir()
    (unified_project / '.roo' / 'rules').mkdir(parents=True)
    (unified_project / '.zoo-agent').mkdir()
    (unified_project / '.zoo-agent' / 'bootstrap' / 'proposals' / 'zoo-agent').mkdir(parents=True)
    (unified_project / '.zoo-agent' / 'runs' / 'run-old').mkdir(parents=True)
    (unified_project / '.zoo-agent' / 'project-profile.json').write_text(
        json.dumps(
            {
                'schema_version': '1.0',
                'languages': ['TypeScript', 'Python'],
                'frameworks': ['Next.js', 'React'],
                'source_roots': ['frontend/src', 'src'],
                'test_roots': ['frontend/tests', 'tests'],
                'api_entrypoints': ['frontend/src/app/api/route.ts'],
                'repository_manifests': ['frontend/package.json', 'package.json'],
                'commands': {'test': 'npm test', 'python_test': 'python -m pytest'},
                'risk_paths': {'secrets': ['.env'], 'data': ['data/**']},
                'project_summary': 'High-confidence existing project profile',
                'architecture_boundaries_path': '.zoo-agent/architecture-boundaries.json',
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.zoo-agent' / 'bootstrap' / 'proposals' / 'zoo-agent' / 'project-profile.json').write_text(
        json.dumps(
            {
                'schema_version': '1.0',
                'languages': ['Python'],
                'source_roots': [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.zoo-agent' / 'project-readiness.json').write_text(
        json.dumps(
            {
                'codex_cli_ready': False,
                'safe_for_level_0_1_trial': False,
                'blocking_issues': ['codex_cli_missing'],
                'next_actions': ['Install or authenticate Codex CLI before fast trials'],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.zoo-agent' / 'project-map.md').write_text(
        '# Project Map\n\n- source: src\n- generated: data/generated.csv\n', encoding='utf-8'
    )
    (unified_project / '.zoo-agent' / 'project-map.json').write_text(
        json.dumps(
            {
                'source_roots': ['src', 'data/generated'],
                'api_entrypoints': [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.zoo-agent' / 'runs' / 'run-old' / 'task-board-consistency.json').write_text(
        json.dumps(
            {
                'status': 'warnings',
                'warnings': ['stale redirect plan requires review'],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.roo' / 'rules' / '10-project-architecture.md').write_text(
        '# Project Architecture\n\nsource roots: unknown\n', encoding='utf-8'
    )
    (unified_project / '.steward' / 'state.json').write_text('{}\n', encoding='utf-8')
    (unified_project / 'data' / 'generated.csv').write_text('value\n1\n', encoding='utf-8')
    (unified_project / '3)])').write_text('accidental shell output\n', encoding='utf-8')
    (unified_project / '.gitignore').write_text('# existing gitignore\n', encoding='utf-8')
    (unified_project / 'src' / 'example.py').write_text('def ok():\n    return True\n', encoding='utf-8')
    (unified_project / 'tests' / 'test_example.py').write_text(
        'from src.example import ok\n\n\ndef test_ok():\n    assert ok()\n', encoding='utf-8'
    )
    run(
        [
            'python',
            str(ROOT / 'scripts' / 'agent_bootstrap.py'),
            '--project',
            str(unified_project),
            '--mode',
            'auto',
            '--goal',
            'Unified bootstrap smoke test',
            '--codex-home',
            env['CODEX_HOME'],
        ],
        cwd=ROOT,
        env=env,
    )
    if not (unified_project / '.zoo-agent' / 'agent-bootstrap-report.md').exists():
        raise SystemExit('Expected unified bootstrap report')
    if not (unified_project / '.zoo-agent' / 'bootstrap-report.md').exists():
        raise SystemExit('Expected project bootstrap report')
    unified_agent = unified_project / '.roo' / 'commands' / 'agent-run.md'
    if not unified_agent.exists():
        raise SystemExit('Expected unified bootstrap to install local agent-run command')
    if 'AI_NATIVE_DISPATCHER_OVERRIDE' not in unified_agent.read_text(encoding='utf-8'):
        raise SystemExit('Expected unified bootstrap to inject dispatcher marker')
    if not (unified_project / '.roo' / 'rules' / '00-ai-native-global-bridge.md').exists():
        raise SystemExit('Expected unified bootstrap bridge rule')
    if (unified_project / '.zoo-agent' / 'project-profile.json.new').exists():
        raise SystemExit('Expected project profile proposal to be moved out of .zoo-agent root')
    if (unified_project / '.gitignore.agent.patch').exists():
        raise SystemExit('Expected gitignore proposal to be moved out of project root')
    if not (unified_project / '.zoo-agent' / 'bootstrap' / 'proposals' / 'zoo-agent' / 'project-profile.json').exists():
        raise SystemExit('Expected project profile proposal inbox entry')
    compatibility_report = unified_project / '.zoo-agent' / 'architecture-compatibility-report.json'
    if not compatibility_report.exists():
        raise SystemExit('Expected architecture compatibility report')
    compatibility_payload = json.loads(compatibility_report.read_text(encoding='utf-8'))
    if compatibility_payload.get('kit_version') != '0.3.11-architecture-feedback-hardening-windows-probes':
        raise SystemExit('Expected architecture hardening kit version')
    issue_ids = {item.get('id') for item in compatibility_payload.get('issues', [])}
    expected_issue_ids = {
        'retired_governance_dirty_paths',
        'runtime_data_dirty_paths',
        'suspicious_root_artifacts',
        'governance_runtime_dirty_paths',
        'task_board_consistency_warnings',
        'profile_downgrade_proposal',
        'frontend_stack_lost_in_profile_proposal',
        'local_architecture_rule_unknowns',
        'dual_governance_state_requires_resolver',
        'inactive_bootstrap_proposals_present',
    }
    missing_issue_ids = sorted(expected_issue_ids - issue_ids)
    if missing_issue_ids:
        raise SystemExit(f'Expected architecture compatibility issues: {missing_issue_ids}')
    if compatibility_payload.get('status') != 'blocked':
        raise SystemExit('Expected blocked architecture compatibility status for profile downgrade smoke')
    (unified_project / '.zoo-agent' / 'project-readiness.json').write_text(
        json.dumps(
            {
                'codex_cli_ready': False,
                'safe_for_level_0_1_trial': False,
                'blocking_issues': ['codex_cli_missing'],
                'next_actions': ['Install or authenticate Codex CLI before fast trials'],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    (unified_project / '.zoo-agent' / 'project-map.md').write_text(
        '# Project Map\n\n- source: src\n- generated: data/generated.csv\n', encoding='utf-8'
    )
    (unified_project / '.zoo-agent' / 'project-map.json').write_text(
        json.dumps(
            {
                'source_roots': ['src', 'data/generated'],
                'api_entrypoints': [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )
    agent_bootstrap_module = load_agent_bootstrap_module()
    compatibility_payload = agent_bootstrap_module.write_architecture_hardening_artifacts(
        unified_project,
        {'inbox': str(unified_project / '.zoo-agent' / 'bootstrap' / 'proposals'), 'moved_count': 1},
    )
    issue_ids = {item.get('id') for item in compatibility_payload.get('issues', [])}
    refreshed_expected_issue_ids = {
        'project_readiness_blocks_fast_trial',
        'project_map_generated_path_contamination',
    }
    missing_refreshed_issue_ids = sorted(refreshed_expected_issue_ids - issue_ids)
    if missing_refreshed_issue_ids:
        raise SystemExit(f'Expected refreshed architecture compatibility issues: {missing_refreshed_issue_ids}')
    for required_artifact in [
        '.zoo-agent/architecture-compatibility-report.md',
        '.zoo-agent/installed-kit-version.json',
        '.zoo-agent/bootstrap/scan-policy.json',
        '.zoo-agent/bootstrap/source-of-truth-resolver.json',
        '.zoo-agent/bootstrap/migration-report.md',
        '.zoo-agent/bootstrap/rollback-anchor.md',
    ]:
        if not (unified_project / required_artifact).exists():
            raise SystemExit(f'Expected architecture hardening artifact: {required_artifact}')
    scan_policy = json.loads(
        (unified_project / '.zoo-agent' / 'bootstrap' / 'scan-policy.json').read_text(encoding='utf-8')
    )
    if 'data/**' not in scan_policy.get('exclude_patterns', []):
        raise SystemExit('Expected generated data path exclusion in scan policy')
    resolver = json.loads(
        (unified_project / '.zoo-agent' / 'bootstrap' / 'source-of-truth-resolver.json').read_text(encoding='utf-8')
    )
    resolver_surfaces = {item.get('surface') for item in resolver.get('precedence', [])}
    if (
        '.steward/**' not in resolver_surfaces
        or '.zoo-agent/runs/<run-id>/*.json and .zoo-agent/current-run.json' not in resolver_surfaces
    ):
        raise SystemExit('Expected source-of-truth resolver to cover active and legacy governance surfaces')
    rollback_text = (unified_project / '.zoo-agent' / 'bootstrap' / 'rollback-anchor.md').read_text(encoding='utf-8')
    if 'Do not delete project source' not in rollback_text:
        raise SystemExit('Expected rollback anchor to protect project source and runtime evidence')


if __name__ == '__main__':
    main()
