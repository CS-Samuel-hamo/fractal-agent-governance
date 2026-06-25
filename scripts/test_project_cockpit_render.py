#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = [
    'eval',
    'governance',
    'planner',
    'verifier',
    'scheduler',
    'backend',
    'execution_result',
    'pipeline_loop.py',
]


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def fixture_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='cockpit-render-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Render Fixture\n', encoding='utf-8')
    evidence = [{'kind': 'file', 'path': 'README.md', 'summary': 'README exists.', 'confidence': 0.8}]
    write_json(
        repo / '.zoo-agent' / 'map' / 'project_map.json',
        {
            'project_name': 'Render Fixture',
            'project_type': 'docs',
            'main_goal': 'make project understandable',
            'last_updated': '2026-06-20T00:00:00Z',
            'modules': [
                {
                    'name': 'Docs',
                    'status': 'mapped',
                    'confidence': 0.72,
                    'key_files': ['README.md'],
                    'evidence': evidence,
                }
            ],
            'capabilities': [
                {'name': 'Project onboarding', 'status': 'partial', 'related_modules': ['Docs'], 'evidence': evidence}
            ],
            'risks': [
                {
                    'description': 'Docs may be stale',
                    'severity': 'medium',
                    'affected_files': ['README.md'],
                    'evidence': evidence,
                }
            ],
            'next_actions': [
                {
                    'action_id': 'docs-action',
                    'title': 'Clarify README opening',
                    'why_now': 'Project entry point needs a concise summary.',
                    'expected_impact': 'New users understand the project faster.',
                    'risk_level': 'low',
                    'target_files': ['README.md'],
                    'autopilot_eligible': True,
                    'evidence': evidence,
                }
            ],
        },
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'session.json', {'goal': 'make project understandable', 'status': 'doing'}
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'attention_required.json',
        {'reason': 'Review needed', 'suggested_next_step': 'Run agent continue after review.'},
    )
    write_json(
        repo / '.zoo-agent' / 'autopilot' / 'checkpoints.json',
        {
            'checkpoints': [
                {'checkpoint_id': 'checkpoint-0001', 'created_at': '2026-06-20T00:01:00Z', 'undo_available': True}
            ]
        },
    )
    return repo


def main() -> int:
    repo = fixture_repo()
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_renderer.py'), '--workspace', str(repo)], repo)
    html_path = repo / '.zoo-agent' / 'cockpit' / 'index.html'
    data_path = repo / '.zoo-agent' / 'cockpit' / 'cockpit_data.json'
    html = html_path.read_text(encoding='utf-8')
    lowered = html.lower()
    assert html_path.exists()
    assert data_path.exists()
    assert 'Project Map' in html
    assert 'Autopilot Session' in html
    assert 'Next Actions' in html
    assert 'Attention Required' in html
    assert 'agent undo' in html
    assert 'http://' not in lowered
    assert 'https://' not in lowered
    assert '<script' not in lowered
    for term in FORBIDDEN:
        assert term not in lowered, f'internal term leaked into cockpit html: {term}'
    print('project cockpit render tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
