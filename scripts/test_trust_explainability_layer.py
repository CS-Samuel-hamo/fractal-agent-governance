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


def run(cmd: list[str], cwd: Path, *, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def init_repo(env: dict[str, str]) -> Path:
    repo = Path(tempfile.mkdtemp(prefix='trust-explain-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Trust Explainability\n', encoding='utf-8')
    run(['git', 'init'], repo, env=env)
    run(['git', 'config', 'user.email', 'trust@example.local'], repo, env=env)
    run(['git', 'config', 'user.name', 'Trust Explainability Test'], repo, env=env)
    run(['git', 'add', 'README.md'], repo, env=env)
    run(['git', 'commit', '-m', 'init'], repo, env=env)
    return repo


def assert_no_internal_terms(payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False).lower()
    for term in ['planner', 'executor', 'verifier', 'backend', 'governance', 'eval']:
        assert term not in text, f'human-readable trust artifact leaked internal term: {term}'


def main() -> int:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='trust-codex-home-')).resolve()))
    Path(env['CODEX_HOME']).mkdir(parents=True, exist_ok=True)
    repo = init_repo(env)
    run([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(repo)], repo, env=env)

    proc = run(
        [sys.executable, str(AGENT), 'fix README typo', '--workspace', str(repo), '-f', 'README.md'],
        repo,
        env=env,
    )
    public_payload = json.loads(proc.stdout)
    assert sorted(public_payload) == ['mode', 'result', 'task']
    assert 'trust' not in proc.stdout.lower()
    assert 'explain' not in proc.stdout.lower()
    assert 'impact' not in proc.stdout.lower()

    explanation = load(repo / '.zoo-agent' / 'explain' / 'execution_explanation.json')
    assert explanation['why_this_change']
    assert isinstance(explanation['what_changed'], list)
    assert explanation['risk_analysis']
    assert explanation['rollback_strategy']
    assert_no_internal_terms(explanation)

    impact = load(repo / '.zoo-agent' / 'impact' / 'impact_summary.json')
    for field in ['affected_files', 'affected_modules', 'cross_module_risk', 'backward_compatibility', 'rollback_cost']:
        assert field in impact

    trust = load(repo / '.zoo-agent' / 'trust' / 'trust_score.json')
    assert 0.0 <= float(trust['trust_score']) <= 1.0
    assert trust['confidence_level'] in {'low', 'medium', 'high'}
    assert trust['reasoning']
    assert trust['safe_to_apply'] == 'suggested_only'
    assert trust['requires_user_confirmation'] is True
    assert trust['recommendation'] in {'proceed', 'review', 'avoid'}

    safety = load(repo / '.zoo-agent' / 'explain' / 'safety_summary.json')
    for field in ['what_changed', 'recommendation', 'requires_user_confirmation', 'risk_level', 'impact_scope', 'safe_to_apply', 'rollback_available', 'reasoning', 'summary']:
        assert field in safety
    assert safety['safe_to_apply'] == 'suggested_only'
    assert safety['requires_user_confirmation'] is True
    assert safety['recommendation'] in {'proceed', 'review', 'avoid'}
    assert_no_internal_terms({'summary': safety['summary']})
    assert (repo / '.zoo-agent' / 'explain' / 'safety_summary.md').exists()

    run_eval = load(repo / '.zoo-agent' / 'runs' / load(repo / '.zoo-agent' / 'eval' / 'invisible_eval.json')['run_id'] / 'explain' / 'safety_summary.json')
    assert run_eval['summary'] == safety['summary']

    help_text = run([sys.executable, str(AGENT), '--help'], repo, env=env).stdout.lower()
    for hidden in ['trust', 'explain', 'impact', 'risk assessment']:
        assert hidden not in help_text

    print('trust explainability layer tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
