#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from autopilot_dogfood_runner import run_dogfood  # noqa: E402
from autopilot_trace_replayer import render_replay  # noqa: E402
from dogfood_report_generator import generate_report  # noqa: E402
from map_quality_evaluator import evaluate_map  # noqa: E402
from map_task_selector import select_next_action  # noqa: E402
from project_map_builder import build_project_map, render_markdown  # noqa: E402
from project_map_schema import map_dir  # noqa: E402
from runtime_common import load_json, write_json  # noqa: E402


def run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=os.environ.copy())
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if proc.returncode:
        raise AssertionError(f'command failed: {cmd}')


def init_repo(prefix: str) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=prefix, dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Dogfood Gate\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'dogfood@example.local'], repo)
    run(['git', 'config', 'user.name', 'Dogfood Gate Test'], repo)
    run(['git', 'add', 'README.md', 'docs/guide.md'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def install_map(repo: Path, project_map: dict, evidence: dict | None = None) -> None:
    out = map_dir(repo)
    write_json(out / 'project_map.json', project_map)
    write_json(out / 'map_evidence.json', evidence or {'evidence': []})
    write_json(out / 'project_state.json', {'status': 'mapped', 'main_goal': project_map.get('main_goal', '')})
    (out / 'project_map.md').write_text(render_markdown(project_map), encoding='utf-8')


def test_bad_map_detected() -> None:
    report = evaluate_map(
        {
            'modules': [{'module_id': 'fake-module', 'name': 'Fake', 'status': 'mapped', 'confidence': 0.95, 'evidence': [], 'key_files': ['missing.py']}],
            'capabilities': [{'capability_id': 'fake-cap', 'name': 'Fake capability', 'status': 'implemented', 'evidence': []}],
            'risks': [],
            'next_actions': [{'action_id': 'vague', 'title': 'Improve stuff', 'why_now': '', 'expected_impact': '', 'target_files': []}],
        },
        {'evidence': []},
    )
    assert report['unsupported_module_count'] >= 1
    assert report['unsupported_capability_count'] >= 1
    assert report['vague_action_count'] >= 1
    assert report['recommendation'] in {'fix_before_094', 'fail'}


def test_vague_action_not_selected() -> None:
    repo = init_repo('dogfood-vague-')
    install_map(
        repo,
        {
            'project_name': repo.name,
            'main_goal': 'prepare release',
            'modules': [],
            'capabilities': [],
            'risks': [],
            'next_actions': [{'action_id': 'vague', 'title': 'Improve stuff', 'why_now': '', 'expected_impact': '', 'target_files': [], 'autopilot_eligible': True}],
        },
    )
    selected = select_next_action(repo, mode='standard')
    assert selected['execution_mode'] == 'needs_attention'
    assert selected['selected_action_id'] == ''


def test_selected_action_from_map() -> None:
    repo = init_repo('dogfood-select-')
    project_map, state, evidence = build_project_map(repo, main_goal='prepare release')
    install_map(repo, project_map, evidence)
    selected = select_next_action(repo, mode='standard')
    action_ids = {item['action_id'] for item in project_map['next_actions']}
    assert selected['selected_action_id'] in action_ids
    assert selected['source'] == 'project_map.next_actions'


def test_dogfood_trace_and_report() -> None:
    repo = init_repo('dogfood-run-')
    trace = run_dogfood(repo, goal='prepare this project for GitHub release', mode='standard', backend='mock', max_steps=1, include_continue=False)
    assert trace['runs'], 'expected at least one dogfood run'
    step = trace['runs'][0]
    assert step['source'] == 'project_map.next_actions'
    assert step['checkpoint_created'] is True
    assert step['map_updated'] is True
    assert step['progress_summary_created'] is True
    assert step['outcome'] == 'delivered'
    assert (repo / '.zoo-agent' / 'dogfood' / 'autopilot_trace.json').exists()

    replay = render_replay(trace, load_json(repo / '.zoo-agent' / 'map' / 'project_map.json'), load_json(repo / '.zoo-agent' / 'map' / 'project_state.json'))
    assert 'why selected' in replay
    (repo / '.zoo-agent' / 'dogfood' / 'autopilot_replay.md').write_text(replay, encoding='utf-8')

    readiness, report = generate_report(repo)
    assert readiness['final_recommendation'] in {'READY_FOR_094_COCKPIT', 'FIX_BEFORE_094', 'NOT_READY_FOR_PRODUCT_UI'}
    write_json(repo / '.zoo-agent' / 'dogfood' / 'readiness_for_094.json', readiness)
    (repo / '.zoo-agent' / 'dogfood' / 'dogfood_report.md').write_text(report, encoding='utf-8')
    assert (repo / '.zoo-agent' / 'dogfood' / 'dogfood_report.md').exists()
    assert (repo / '.zoo-agent' / 'dogfood' / 'readiness_for_094.json').exists()


def test_no_delivery_pauses() -> None:
    repo = init_repo('dogfood-nodelivery-')
    trace = run_dogfood(repo, goal='prepare this project for GitHub release', mode='standard', backend='dry_run', max_steps=1, include_continue=False)
    assert trace['runs']
    assert trace['runs'][0]['outcome'] == 'no_delivery'
    attention = load_json(repo / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    assert attention['status'] == 'needs_attention'


def test_blocked_zone_attention() -> None:
    repo = init_repo('dogfood-blocked-')
    install_map(
        repo,
        {
            'project_name': repo.name,
            'main_goal': 'prepare release',
            'modules': [],
            'capabilities': [],
            'risks': [],
            'next_actions': [
                {
                    'action_id': 'blocked-env',
                    'title': 'Edit secret file',
                    'why_now': 'Unsafe fixture.',
                    'expected_impact': 'none',
                    'risk_level': 'low',
                    'target_files': ['.env'],
                    'autopilot_eligible': True,
                    'evidence': [{'kind': 'fixture', 'path': '<hidden>', 'summary': 'blocked test fixture', 'confidence': 1.0}],
                }
            ],
        },
        {'evidence': [{'kind': 'fixture', 'path': '<hidden>', 'summary': 'blocked test fixture', 'confidence': 1.0}]},
    )
    trace = run_dogfood(repo, goal='prepare release', mode='standard', backend='mock', max_steps=1, include_continue=False)
    assert trace['runs'] == []
    attention = load_json(repo / '.zoo-agent' / 'autopilot' / 'attention_required.json')
    assert attention['status'] == 'needs_attention'


def main() -> int:
    os.environ.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='dogfood-codex-home-')).resolve()))
    test_bad_map_detected()
    test_vague_action_not_selected()
    test_selected_action_from_map()
    test_dogfood_trace_and_report()
    test_no_delivery_pauses()
    test_blocked_zone_attention()
    print('real project dogfood gate tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
