#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


def run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if check and proc.returncode:
        raise AssertionError(f'command failed with {proc.returncode}: {cmd}')
    return proc


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')


def repo(name: str) -> Path:
    root = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Fixture\n', encoding='utf-8')
    return root


def test_fixture_builder() -> Path:
    root = repo('cockpit-dogfood-fixture')
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_demo_fixture_builder.py'), '--workspace', str(root)], root)
    summary_path = root / '.zoo-agent' / 'cockpit_dogfood' / 'demo_fixture_summary.json'
    summary = load(summary_path)
    assert summary['safe_to_use'] is True
    assert 'active_session' in summary['scenarios']
    assert 'needs_attention' in summary['scenarios']
    raw = summary_path.read_text(encoding='utf-8').lower()
    assert '.env' not in raw
    assert 'secret' not in raw
    fixture = root / summary['fixture_path']
    assert (fixture / '.zoo-agent' / 'map' / 'project_map.json').exists()
    assert not (fixture / '.env').exists()
    return root


def test_quality_gate_negative_cases() -> None:
    root = repo('cockpit-quality-negative')
    data = {
        'project': {'name': 'Bad Demo', 'state': 'unknown'},
        'session': {},
        'map': {'modules': [], 'capabilities': [], 'risks': [], 'next_actions': []},
        'attention': {'items': []},
        'safety': {},
    }
    data_path = root / '.zoo-agent' / 'cockpit' / 'cockpit_data.json'
    write_json(data_path, data)

    missing_html = root / '.zoo-agent' / 'cockpit' / 'missing.html'
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_quality_gate.py'), '--workspace', str(root), '--html', str(missing_html), '--data', str(data_path)], root)
    missing = load(root / '.zoo-agent' / 'cockpit_dogfood' / 'cockpit_quality_report.json')
    assert 'cockpit_html' in missing['missing_sections']
    assert missing['recommendation'] == 'fix_before_095'

    bad_html = root / '.zoo-agent' / 'cockpit' / 'bad.html'
    write(bad_html, '<html><head><script src="https://cdn.example/app.js"></script></head><body>planner backend internals</body></html>')
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_quality_gate.py'), '--workspace', str(root), '--html', str(bad_html), '--data', str(data_path)], root)
    bad = load(root / '.zoo-agent' / 'cockpit_dogfood' / 'cockpit_quality_report.json')
    assert bad['internal_leakage_detected'] is True
    assert bad['external_dependency_detected'] is True
    assert bad['recommendation'] == 'fail'


def test_dogfood_runner_ready() -> Path:
    root = repo('cockpit-dogfood-ready')
    run([sys.executable, str(ROOT / 'scripts' / 'cockpit_dogfood_runner.py'), '--workspace', str(root)], root)
    dogfood = root / '.zoo-agent' / 'cockpit_dogfood'
    quality = load(dogfood / 'cockpit_quality_report.json')
    readiness = load(dogfood / 'readiness_for_095.json')
    report = dogfood / 'cockpit_ux_report.md'
    assert quality['recommendation'] == 'pass'
    assert quality['cockpit_quality_score'] >= 0.85
    assert readiness['readiness'] == 'READY_FOR_095_SESSION_RUNTIME'
    assert report.exists()
    assert 'Does This Feel Like AI Project Operator?' in report.read_text(encoding='utf-8')
    return root


def test_agent_entrypoints(root: Path) -> None:
    help_result = run([sys.executable, str(AGENT), '--help'], root)
    lowered = help_result.stdout.lower()
    assert 'agent cockpit' in lowered
    assert '--dogfood' not in lowered
    assert 'debug' not in lowered
    assert 'planner' not in lowered
    assert 'verifier' not in lowered

    normal = run([sys.executable, str(AGENT), 'cockpit', '--workspace', str(root)], root)
    payload = json.loads(normal.stdout)
    assert payload['mode'] == 'ready'
    assert 'Open: .zoo-agent/cockpit/index.html' in payload['result']
    assert (root / '.zoo-agent' / 'cockpit' / 'index.html').exists()

    dogfood = run([sys.executable, str(AGENT), 'cockpit', '--dogfood', '--workspace', str(root)], root)
    dogfood_payload = json.loads(dogfood.stdout)
    assert dogfood_payload['task'] == 'project cockpit dogfood'
    assert 'READY_FOR_095_SESSION_RUNTIME' in dogfood_payload['result']


def main() -> int:
    test_fixture_builder()
    test_quality_gate_negative_cases()
    ready_root = test_dogfood_runner_ready()
    test_agent_entrypoints(ready_root)
    print('project cockpit dogfood tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
