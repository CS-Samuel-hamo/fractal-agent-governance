#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from pr_draft_quality_gate import evaluate_pr_draft  # noqa: E402
from release_artifact_quality_gate import evaluate_release_artifacts  # noqa: E402
from release_product_report_generator import generate_report  # noqa: E402
from release_workflow_trace_replayer import generate_replay  # noqa: E402
from runtime_common import load_json, project_root, write_json  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release_dogfood'


def run(command: list[str], cwd: Path, *, allow_fail: bool = False) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='release-dogfood-codex-home-')).resolve()))
    proc = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0 and not allow_fail:
        raise RuntimeError(f"command failed: {' '.join(command)}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    return proc


def init_git(root: Path, *, tokenized_remote: bool = False) -> None:
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'release-dogfood@example.local'], root)
    run(['git', 'config', 'user.name', 'Release Dogfood'], root)
    if tokenized_remote:
        fake_token = 'ghp_' + ('2' * 36)
        run(['git', 'remote', 'add', 'origin', f'https://user:{fake_token}@github.com/example/release-dogfood.git'], root)


def write_project_map(root: Path, *, high_risk: bool = False) -> None:
    map_dir = root / '.zoo-agent' / 'map'
    map_dir.mkdir(parents=True, exist_ok=True)
    risks = []
    if high_risk:
        risks.append({'risk_id': 'deploy', 'description': 'Production deploy risk', 'severity': 'high', 'affected_files': ['deploy/config.yml'], 'evidence': [{'source': 'fixture'}]})
    project_map = {
        'project_name': root.name,
        'project_type': 'agent_runtime',
        'main_goal': 'prepare this project for public release',
        'modules': [{'module_id': 'docs', 'name': 'Docs', 'purpose': 'User docs', 'key_files': ['README.md'], 'status': 'mapped', 'confidence': 0.75, 'evidence': [{'source': 'README.md'}]}],
        'capabilities': [{'capability_id': 'cli', 'name': 'CLI usage', 'status': 'verified', 'evidence': [{'source': 'README.md'}], 'related_modules': ['docs']}],
        'risks': risks,
        'next_actions': [
            {'action_id': 'docs', 'title': 'Refresh public release docs', 'why_now': 'Docs clarify release readiness.', 'expected_impact': 'Users can install and run locally.', 'risk_level': 'low', 'target_files': ['README.md'], 'autopilot_eligible': True, 'evidence': [{'source': 'README.md'}]},
            {'action_id': 'blocked', 'title': 'Review deployment configuration', 'why_now': 'Deployment is high risk.', 'expected_impact': 'Avoid unsafe release work.', 'risk_level': 'high', 'target_files': ['deploy/config.yml'], 'autopilot_eligible': False, 'evidence': [{'source': 'fixture'}]},
        ],
        'last_updated': '2026-01-01T00:00:00Z',
    }
    write_json(map_dir / 'project_map.json', project_map)
    write_json(map_dir / 'map_evidence.json', {'evidence': [{'source': 'fixture', 'summary': 'synthetic release dogfood'}]})


def write_session_history(root: Path) -> None:
    session_dir = root / '.zoo-agent' / 'session'
    session_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        session_dir / 'session_history.json',
        {'history': [{'step': 1, 'action': 'Refresh docs', 'outcome': 'delivered', 'evidence': ['README.md']}]},
    )


def write_learning(root: Path) -> None:
    store = root / '.zoo-agent' / 'learning' / 'cross_project'
    store.mkdir(parents=True, exist_ok=True)
    write_json(
        store / 'pattern_library.json',
        {'patterns': [{'pattern_id': 'docs_cleanup_before_release', 'success_count': 2, 'failure_count': 0, 'confidence': 0.7, 'evidence': [{'source': 'fixture'}]}]},
    )
    write_json(
        store / 'learning_insights.json',
        {'insights': [{'insight_id': 'release-docs', 'type': 'readiness_template', 'message': 'Docs and quickstart often unblock release readiness.', 'confidence': 0.7, 'recommended_effect': 'boost', 'evidence': [{'source': 'fixture'}]}]},
    )


def base_fixture(root: Path, *, docs: bool = True, tests: bool = True, changelog: bool = True, license_file: bool = True, git: bool = True, tokenized_remote: bool = False) -> None:
    if docs:
        (root / 'README.md').write_text('# Release Dogfood\n\nLocal release workflow fixture.\n', encoding='utf-8')
        (root / 'QUICKSTART.md').write_text('# Quickstart\n\nRun `agent release`.\n', encoding='utf-8')
        (root / 'INSTALL.md').write_text('# Install\n\nRun locally.\n', encoding='utf-8')
    else:
        (root / 'notes.txt').write_text('No public docs yet.\n', encoding='utf-8')
    if tests:
        (root / 'tests').mkdir(parents=True, exist_ok=True)
        (root / 'tests' / 'test_basic.py').write_text('def test_basic():\n    assert True\n', encoding='utf-8')
    if changelog:
        (root / 'CHANGELOG.md').write_text('# Changelog\n\n## Unreleased\n', encoding='utf-8')
    if license_file:
        (root / 'LICENSE').write_text('MIT\n', encoding='utf-8')
    (root / 'docs').mkdir(exist_ok=True)
    (root / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    write_project_map(root)
    write_session_history(root)
    write_learning(root)
    if git:
        init_git(root, tokenized_remote=tokenized_remote)
        run(['git', 'add', '.'], root)
        run(['git', 'commit', '-m', 'init'], root)


def run_release_flow(root: Path) -> list[str]:
    commands = []
    for command in [
        [sys.executable, str(AGENT), 'release', '--workspace', str(root)],
        [sys.executable, str(AGENT), 'pr', '--workspace', str(root)],
        [sys.executable, str(AGENT), 'cockpit', '--workspace', str(root)],
    ]:
        run(command, root, allow_fail=False)
        commands.append(' '.join(command[2:4]).strip())
    return commands


def artifact_flags(root: Path) -> dict[str, Any]:
    release = root / '.zoo-agent' / 'release'
    cockpit = root / '.zoo-agent' / 'cockpit' / 'index.html'
    git_context = load_json(release / 'git_context.json')
    github_ready = load_json(release / 'github_readiness.json')
    safety = load_json(release / 'github_workflow_safety_report.json')
    all_text = ''
    for path in list(release.glob('*')) + ([cockpit] if cockpit.exists() else []):
        if path.is_file():
            all_text += path.read_text(encoding='utf-8', errors='replace') + '\n'
    return {
        'git_context_generated': (release / 'git_context.json').exists(),
        'github_readiness_generated': (release / 'github_readiness.json').exists(),
        'release_readiness_generated': (release / 'release_readiness.json').exists(),
        'pr_plan_generated': (release / 'pr_plan.json').exists(),
        'pr_draft_generated': (release / 'pr_draft.md').exists(),
        'release_notes_generated': (release / 'release_notes_draft.md').exists(),
        'changelog_generated': (release / 'changelog_draft.md').exists(),
        'cockpit_synced': cockpit.exists(),
        'safety_gate_passed': bool(safety.get('safe')),
        'network_called': bool(safety.get('network_call_detected')),
        'push_detected': bool(safety.get('push_detected')),
        'merge_detected': bool(safety.get('merge_detected')),
        'secret_leak_detected': bool(safety.get('secret_leak_detected')) or 'ghp_' + ('2' * 36) in all_text,
        'blockers': github_ready.get('blockers') or [],
        'warnings': github_ready.get('warnings') or [],
        'git_status': git_context.get('working_tree_status'),
        'github_ready': github_ready.get('github_ready'),
        'pr_ready': github_ready.get('pr_ready'),
        'release_ready': github_ready.get('release_ready'),
    }


def scenario_result(name: str, root: Path, output_project: Path, assert_fn) -> dict[str, Any]:
    commands = run_release_flow(root)
    flags = artifact_flags(root)
    passed = bool(assert_fn(root, flags))
    return {'scenario': name, 'commands': commands, **flags, 'outcome': 'pass' if passed else 'fail'}


def run_scenarios(output_project: Path) -> tuple[list[dict[str, Any]], Path]:
    runs: list[dict[str, Any]] = []
    quality_fixture: Path | None = None
    with tempfile.TemporaryDirectory(prefix='release-workflow-dogfood-') as tmp:
        base = Path(tmp)

        clean = base / 'clean_release_candidate'
        clean.mkdir()
        base_fixture(clean)
        runs.append(scenario_result('clean_release_candidate', clean, output_project, lambda root, flags: flags['release_ready'] is True and flags['safety_gate_passed']))
        quality_fixture = clean

        missing_docs = base / 'missing_docs'
        missing_docs.mkdir()
        base_fixture(missing_docs, docs=False)
        runs.append(scenario_result('missing_docs', missing_docs, output_project, lambda root, flags: any('README' in item or 'quickstart' in item for item in flags['blockers'])))

        missing_tests = base / 'missing_tests'
        missing_tests.mkdir()
        base_fixture(missing_tests, tests=False)
        runs.append(scenario_result('missing_tests', missing_tests, output_project, lambda root, flags: any('tests' in item.lower() for item in flags['blockers']) and 'Not run in this workflow' in (root / '.zoo-agent' / 'release' / 'pr_draft.md').read_text(encoding='utf-8')))

        dirty = base / 'dirty_worktree'
        dirty.mkdir()
        base_fixture(dirty)
        (dirty / 'README.md').write_text('# Release Dogfood\n\nDirty change.\n', encoding='utf-8')
        runs.append(scenario_result('dirty_worktree', dirty, output_project, lambda root, flags: flags['git_status'] == 'dirty' and any('dirty' in item.lower() or 'working tree' in item.lower() for item in flags['warnings'])))

        no_git = base / 'no_git_repo'
        no_git.mkdir()
        base_fixture(no_git, git=False)
        runs.append(scenario_result('no_git_repo', no_git, output_project, lambda root, flags: flags['github_ready'] is False and (root / '.zoo-agent' / 'release' / 'release_workflow_report.md').exists()))

        token = base / 'tokenized_remote_safety'
        token.mkdir()
        base_fixture(token, tokenized_remote=True)
        runs.append(scenario_result('tokenized_remote_safety', token, output_project, lambda root, flags: not flags['secret_leak_detected'] and '<redacted>' in json.dumps(load_json(root / '.zoo-agent' / 'release' / 'git_context.json'))))

        no_diff = base / 'no_actual_diff_pr'
        no_diff.mkdir()
        base_fixture(no_diff)
        runs.append(scenario_result('no_actual_diff_pr', no_diff, output_project, lambda root, flags: 'Draft only; no code changes included yet.' in (root / '.zoo-agent' / 'release' / 'pr_draft.md').read_text(encoding='utf-8')))

        cockpit = base / 'cockpit_release_view'
        cockpit.mkdir()
        base_fixture(cockpit)
        runs.append(scenario_result('cockpit_release_view', cockpit, output_project, lambda root, flags: all(text in (root / '.zoo-agent' / 'cockpit' / 'index.html').read_text(encoding='utf-8') for text in ['Release / PR', 'PR draft', 'Release score', '.zoo-agent/release/release_notes_draft.md'])))

        assert quality_fixture is not None
        # Copy the best fixture release artifacts into a stable dogfood fixture folder for debugging.
        fixture_copy = dogfood_dir(output_project) / 'quality_fixture_release'
        shutil.copytree(quality_fixture / '.zoo-agent' / 'release', fixture_copy, dirs_exist_ok=True)
        evaluate_release_artifacts(quality_fixture, output_project=output_project)
        evaluate_pr_draft(quality_fixture, output_project=output_project)

    return runs, dogfood_dir(output_project) / 'quality_fixture_release'


def run_dogfood(project: Path) -> dict[str, Any]:
    dogfood_dir(project).mkdir(parents=True, exist_ok=True)
    runs, fixture_path = run_scenarios(project)
    trace = {'generated_by': 'release_workflow_dogfood_runner.py', 'runs': runs, 'quality_fixture': '.zoo-agent/release_dogfood/quality_fixture_release'}
    write_json(dogfood_dir(project) / 'release_workflow_dogfood_trace.json', trace)
    generate_replay(project)
    report = generate_report(project)
    return {
        'status': 'ok',
        'trace': '.zoo-agent/release_dogfood/release_workflow_dogfood_trace.json',
        'release_artifact_quality_report': '.zoo-agent/release_dogfood/release_artifact_quality_report.json',
        'pr_draft_quality_report': '.zoo-agent/release_dogfood/pr_draft_quality_report.json',
        'replay': '.zoo-agent/release_dogfood/release_workflow_replay.md',
        'product_report': '.zoo-agent/release_dogfood/release_product_report.md',
        'readiness': report.get('readiness'),
        'readiness_value': report.get('status'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run controlled local release workflow dogfood.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('readiness_value') == 'READY_FOR_099_PUBLIC_ALPHA_FREEZE' else 1


if __name__ == '__main__':
    raise SystemExit(main())
