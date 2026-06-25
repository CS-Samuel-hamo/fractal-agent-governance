#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def new_repo(name: str) -> Path:
    repo = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Cockpit Fixture\n', encoding='utf-8')
    return repo


def test_missing_artifacts_degrade() -> None:
    repo = new_repo('cockpit-empty')
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_data_builder.py'), '--workspace', str(repo)], repo)
    data = load(repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json')
    assert data['project']['state'] == 'unknown'
    assert data['session']['status'] == 'not_started'
    assert data['map']['modules'] == []
    assert data['readiness']['for_094'] == 'not available'


def test_data_projection_and_sanitization() -> None:
    repo = new_repo('cockpit-data')
    evidence = [{'kind': 'file', 'path': 'README.md', 'summary': 'README exists.', 'confidence': 0.8}]
    write_json(
        repo / '.zoo-agent' / 'map' / 'project_map.json',
        {
            'project_name': 'Cockpit Fixture',
            'project_type': 'docs',
            'main_goal': 'prepare project for release',
            'last_updated': '2026-06-20T00:00:00Z',
            'modules': [
                {
                    'name': 'Docs',
                    'status': 'mapped',
                    'confidence': 0.7,
                    'key_files': ['README.md'],
                    'evidence': evidence,
                }
            ],
            'capabilities': [
                {'name': 'Onboarding', 'status': 'partial', 'related_modules': ['Docs'], 'evidence': evidence}
            ],
            'risks': [
                {
                    'description': 'Release notes need review',
                    'severity': 'low',
                    'affected_files': ['README.md'],
                    'evidence': evidence,
                }
            ],
            'next_actions': [
                {
                    'action_id': 'readme-note',
                    'title': 'Add README release note',
                    'why_now': 'README exists and release readiness is partial.',
                    'expected_impact': 'Improves onboarding clarity.',
                    'risk_level': 'low',
                    'target_files': ['README.md'],
                    'autopilot_eligible': True,
                    'evidence': evidence,
                },
                {
                    'action_id': 'restricted-action',
                    'title': 'Review API key handling',
                    'why_now': 'Avoid .env leaks.',
                    'expected_impact': 'Protect token configuration.',
                    'risk_level': 'high',
                    'target_files': ['.env'],
                    'autopilot_eligible': False,
                    'evidence': evidence,
                },
            ],
        },
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'session.json', {'goal': 'prepare project for release', 'status': 'doing'}
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'progress.json', {'title': 'Add README release note', 'status': 'done'}
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'action_history.json',
        {
            'actions': [
                {
                    'title': 'Add README release note',
                    'status': 'done',
                    'result': 'COMPLETED',
                    'changed_files': ['README.md'],
                }
            ]
        },
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'attention_required.json',
        {'reason': 'Blocked area requires review', 'suggested_next_step': 'Review manually.'},
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json',
        {
            'checkpoints': [
                {'checkpoint_id': 'checkpoint-0001', 'created_at': '2026-06-20T00:01:00Z', 'undo_available': True}
            ]
        },
    )
    write_json(
        repo / '.zoo-agent' / 'dogfood' / 'readiness_for_094.json', {'final_recommendation': 'READY_FOR_094_COCKPIT'}
    )
    write_json(
        repo / '.zoo-agent' / 'dogfood' / 'map_quality_report.json',
        {'map_quality_score': 0.91, 'evidence_coverage': 0.88},
    )

    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_data_builder.py'), '--workspace', str(repo)], repo)
    data_path = repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json'
    data = load(data_path)
    raw = data_path.read_text(encoding='utf-8')
    assert data['project']['state'] == 'needs_attention'
    assert data['session']['status'] == 'needs_attention'
    assert data['map']['modules'][0]['evidence_count'] == 1
    assert data['attention']['requires_attention'] is True
    assert data['safety']['undo_available'] is True
    assert data['readiness']['for_094'] == 'READY_FOR_094_COCKPIT'
    for forbidden in ['.env', 'api key', 'token', 'secret']:
        assert forbidden not in raw.lower()


def main() -> int:
    test_missing_artifacts_degrade()
    test_data_projection_and_sanitization()
    print('project cockpit data tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
