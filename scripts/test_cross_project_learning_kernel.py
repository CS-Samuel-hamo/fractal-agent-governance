#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
PYTHON = sys.executable


def run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f"command failed: {' '.join(command)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def make_fixture(project: Path) -> None:
    (project / 'README.md').write_text('# Fixture\n\nQuickstart coming soon.\n', encoding='utf-8')
    (project / 'pyproject.toml').write_text('[project]\nname = "fixture"\nversion = "0.1.0"\n', encoding='utf-8')
    (project / 'docs').mkdir()
    (project / 'docs' / 'guide.md').write_text('# Guide\n\nRelease notes and usage.\n', encoding='utf-8')
    (project / 'tests').mkdir()
    (project / 'tests' / 'test_sample.py').write_text('def test_sample():\n    assert True\n', encoding='utf-8')
    (project / 'scripts').mkdir()
    (project / 'scripts' / 'tool.py').write_text('print("fixture")\n', encoding='utf-8')
    (project / '.env').write_text('SHOULD-NOT-BE-READ=1\n', encoding='utf-8')
    run(['git', 'init'], project)


def write_worker_trace(project: Path) -> None:
    trace_dir = project / '.zoo-agent' / 'worker_dogfood'
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace = {
        'runs': [
            {
                'scenario': 'repo_scan_1',
                'task_profile': {'task_type': 'repo_scan'},
                'selected_worker': 'local_scanner_worker',
                'routing_decision': {'selected_provider': 'local_scanner'},
                'fallback_used': False,
                'outcome': 'pass',
            },
            {
                'scenario': 'repo_scan_2',
                'task_profile': {'task_type': 'repo_scan'},
                'selected_worker': 'local_scanner_worker',
                'routing_decision': {'selected_provider': 'local_scanner'},
                'fallback_used': False,
                'outcome': 'pass',
            },
        ]
    }
    (trace_dir / 'worker_router_dogfood_trace.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')


def main() -> int:
    with tempfile.TemporaryDirectory(prefix='agent-learning-kernel-') as tmp:
        project = Path(tmp)
        make_fixture(project)
        run([PYTHON, str(SCRIPTS / 'project_map_builder.py'), '--workspace', str(project)])
        run([PYTHON, str(SCRIPTS / 'local_scanner_worker.py'), '--workspace', str(project)])
        run([PYTHON, str(SCRIPTS / 'worker_registry.py'), '--workspace', str(project)])
        write_worker_trace(project)

        build = run([PYTHON, str(SCRIPTS / 'agent.py'), 'learning', '--build', '--workspace', str(project)])
        assert_true('CROSS_PROJECT_LEARNING_097_READY' in build.stdout, 'learning build did not report ready')

        store = project / '.zoo-agent' / 'learning' / 'cross_project'
        pattern_library = load_json(store / 'pattern_library.json')
        release_templates = load_json(store / 'release_templates.json')
        worker_memory = load_json(store / 'worker_memory.json')
        failure_taxonomy = load_json(store / 'failure_taxonomy.json')
        insights = load_json(store / 'learning_insights.json')
        report = store / 'cross_project_learning_report.md'

        assert_true(bool(load_json(store / 'project_index.json').get('projects')), 'project index missing imported project')
        assert_true(all(item.get('evidence') for item in pattern_library.get('patterns') or []), 'pattern without evidence')
        low_count_patterns = [item for item in pattern_library.get('patterns') or [] if int(item.get('success_count') or 0) + int(item.get('failure_count') or 0) <= 1]
        assert_true(all(float(item.get('confidence') or 0) <= 0.45 for item in low_count_patterns), 'low evidence pattern was overconfident')
        template_ids = {item.get('template_id') for item in release_templates.get('templates') or []}
        assert_true({'cli_tool_release', 'python_library_release', 'docs_first_release', 'agent_runtime_release'} <= template_ids, 'release templates missing')
        unavailable_prefer = [item for item in worker_memory.get('worker_performance') or [] if item.get('recommended_use') == 'prefer' and item.get('worker_role') in {'claude', 'local'}]
        assert_true(not unavailable_prefer, 'unavailable worker was marked prefer')
        failure_types = {item.get('failure_type') for item in failure_taxonomy.get('failure_patterns') or []}
        assert_true({'no_delivery', 'worker_unavailable', 'blocked_zone_attempt', 'map_hallucination_risk'} <= failure_types, 'failure taxonomy incomplete')
        assert_true(bool(insights.get('insights')), 'learning insights missing')
        assert_true(report.exists(), 'learning report missing')

        store_text = '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in store.rglob('*') if path.is_file())
        assert_true('SHOULD-NOT-BE-READ' not in store_text, 'secret sentinel leaked into learning store')
        assert_true(str(project) not in store_text, 'absolute project path leaked into learning store')
        assert_true('raw backend log that should not be stored' not in store_text.lower(), 'raw backend log content leaked into learning store')

        run([PYTHON, str(SCRIPTS / 'agent.py'), 'cockpit', '--workspace', str(project)])
        cockpit = (project / '.zoo-agent' / 'cockpit' / 'index.html').read_text(encoding='utf-8')
        assert_true('Cross-project Learning' in cockpit, 'cockpit did not show learning section')
        assert_true('raw learning artifacts' not in cockpit.lower(), 'cockpit leaked raw learning wording')

        help_text = run([PYTHON, str(SCRIPTS / 'agent.py'), '--help']).stdout
        assert_true('learning --build' not in help_text and 'learning --import' not in help_text, 'ordinary help exposed learning commands')

    print('cross project learning kernel tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
