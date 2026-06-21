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

from claude_code_worker_detector import claude_health  # noqa: E402
from codex_worker_adapter_hardened import codex_health  # noqa: E402
from local_scanner_worker import scan_repo  # noqa: E402
from project_map_builder import build_project_map, render_markdown  # noqa: E402
from project_operator_value_report_generator import generate_report  # noqa: E402
from real_worker_trace_replayer import run_replay  # noqa: E402
from real_worker_value_gate import run_value_gate  # noqa: E402
from runtime_common import load_json, project_root, utc_now, write_json  # noqa: E402
from task_profile_classifier import classify_task_profile  # noqa: E402
from worker_doctor import doctor_payload  # noqa: E402
from worker_registry import write_worker_registry  # noqa: E402
from worker_router import route_worker  # noqa: E402


AGENT = ROOT / 'scripts' / 'agent.py'


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'real_worker_dogfood'


def run_proc(command: list[str], cwd: Path, *, allow_fail: bool = False) -> dict[str, Any]:
    env = os.environ.copy()
    env.setdefault('CODEX_HOME', str(Path(tempfile.mkdtemp(prefix='real-worker-dogfood-codex-home-')).resolve()))
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0 and not allow_fail:
        raise RuntimeError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}


def init_fixture() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='real-worker-dogfood-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Real Worker Fixture\n', encoding='utf-8')
    (repo / 'pyproject.toml').write_text('[project]\nname = "real-worker-fixture"\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    (repo / 'tests').mkdir()
    (repo / 'tests' / 'test_app.py').write_text('def test_ok():\n    assert True\n', encoding='utf-8')
    (repo / '.env').write_text('API_KEY=should-not-be-read\n', encoding='utf-8')
    (repo / 'secrets.txt').write_text('token=should-not-be-read\n', encoding='utf-8')
    run_proc(['git', 'init'], repo)
    run_proc(['git', 'config', 'user.email', 'real-worker@example.local'], repo)
    run_proc(['git', 'config', 'user.name', 'Real Worker Dogfood'], repo)
    run_proc(['git', 'add', 'README.md', 'pyproject.toml', 'docs', 'src', 'tests'], repo)
    run_proc(['git', 'commit', '-m', 'init fixture'], repo)
    return repo


def copy_artifact(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)


def worker_environment(project: Path) -> dict[str, str]:
    registry = load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    by_name = {item.get('name'): item for item in registry.get('workers') or [] if isinstance(item, dict)}
    return {
        'codex': str((by_name.get('codex_worker_existing_adapter') or {}).get('health') or 'unavailable'),
        'claude_code': str((by_name.get('claude_worker_stub') or {}).get('health') or 'unavailable'),
        'local_scanner': str((by_name.get('local_scanner_worker') or {}).get('health') or 'unavailable'),
        'dry_run': str((by_name.get('dry_run_worker') or {}).get('health') or 'healthy'),
        'mock': str((by_name.get('mock_worker') or {}).get('health') or 'healthy'),
    }


def row(
    project: Path,
    scenario: str,
    *,
    selected_worker: str = '',
    worker_role: str = '',
    execution_mode: str = 'preview',
    fallback_used: bool = False,
    fallback_reason: str = '',
    project_map_supported: bool = False,
    session_updated: bool = False,
    cockpit_synced: bool = False,
    unsafe_behavior_detected: bool = False,
    fake_capability_detected: bool = False,
    outcome: str = 'pass',
) -> dict[str, Any]:
    return {
        'scenario': scenario,
        'worker_environment': worker_environment(project),
        'selected_worker': selected_worker,
        'worker_role': worker_role,
        'execution_mode': execution_mode,
        'fallback_used': bool(fallback_used),
        'fallback_reason': fallback_reason,
        'project_map_supported': bool(project_map_supported),
        'session_updated': bool(session_updated),
        'cockpit_synced': bool(cockpit_synced),
        'unsafe_behavior_detected': bool(unsafe_behavior_detected),
        'fake_capability_detected': bool(fake_capability_detected),
        'outcome': outcome,
    }


def sync_worker_artifacts(source: Path, target: Path) -> None:
    for name in [
        'worker_registry.json',
        'worker_doctor_report.json',
        'worker_environment_report.md',
        'installation_diagnostics.json',
        'local_scanner_report.json',
        'codex_adapter_health.json',
        'claude_code_detection.json',
        'routing_decision.json',
        'fallback_trace.json',
    ]:
        copy_artifact(source / '.zoo-agent' / 'workers' / name, target / '.zoo-agent' / 'workers' / name)


def sync_map_artifacts(source: Path, target: Path) -> None:
    for name in ['project_map.json', 'map_evidence.json', 'project_state.json', 'project_map.md']:
        copy_artifact(source / '.zoo-agent' / 'map' / name, target / '.zoo-agent' / 'map' / name)


def scenario_worker_doctor(fixture: Path) -> dict[str, Any]:
    doctor_payload(fixture)
    report = load_json(fixture / '.zoo-agent' / 'workers' / 'worker_doctor_report.json')
    env_report = fixture / '.zoo-agent' / 'workers' / 'worker_environment_report.md'
    ok = bool(report.get('workers')) and env_report.exists()
    return row(fixture, 'worker_doctor', project_map_supported=True, outcome='pass' if ok else 'fail')


def scenario_local_scanner(fixture: Path) -> dict[str, Any]:
    report = scan_repo(fixture)
    skipped = json.dumps(report.get('files_skipped') or [], ensure_ascii=False).lower()
    ok = bool(report.get('files_scanned')) and bool((report.get('map_support') or {}).get('evidence')) and '.env' in skipped and 'should-not-be-read' not in json.dumps(report, ensure_ascii=False)
    return row(fixture, 'local_scanner_repo_scan', selected_worker='local_scanner_worker', worker_role='Analysis Worker', execution_mode='preview', project_map_supported=bool((report.get('map_support') or {}).get('evidence')), outcome='pass' if ok else 'fail')


def scenario_project_map_support(fixture: Path) -> dict[str, Any]:
    project_map, state, evidence = build_project_map(fixture, main_goal='prepare this project for public release')
    scanner = load_json(fixture / '.zoo-agent' / 'workers' / 'local_scanner_report.json')
    scanner_evidence = (scanner.get('map_support') or {}).get('evidence') or []
    evidence.setdefault('evidence', [])
    evidence['evidence'].extend(scanner_evidence[:10])
    if scanner.get('candidate_modules'):
        known = {item.get('name') for item in project_map.get('modules') or []}
        for module in scanner.get('candidate_modules') or []:
            name = str(module.get('name') or '')
            if name and name not in known:
                project_map.setdefault('modules', []).append({'module_id': name, 'name': name, 'purpose': 'Detected by local scanner metadata.', 'key_files': module.get('evidence') or [], 'status': 'mapped', 'confidence': 0.65, 'evidence': [{'source': 'local_scanner_worker', 'summary': 'metadata-backed candidate module'}]})
    write_json(fixture / '.zoo-agent' / 'map' / 'project_map.json', project_map)
    write_json(fixture / '.zoo-agent' / 'map' / 'project_state.json', state)
    write_json(fixture / '.zoo-agent' / 'map' / 'map_evidence.json', evidence)
    (fixture / '.zoo-agent' / 'map' / 'project_map.md').write_text(render_markdown(project_map), encoding='utf-8')
    ok = bool(project_map.get('modules')) and bool(evidence.get('evidence'))
    return row(fixture, 'project_map_support', selected_worker='local_scanner_worker', worker_role='Analysis Worker', execution_mode='preview', project_map_supported=ok, outcome='pass' if ok else 'fail')


def scenario_session(fixture: Path) -> dict[str, Any]:
    run_proc([sys.executable, str(AGENT), 'config', 'backend', 'mock', '--workspace', str(fixture)], fixture)
    proc = run_proc([sys.executable, str(AGENT), 'start', 'prepare this project for public release', '--workspace', str(fixture)], fixture, allow_fail=True)
    routing = load_json(fixture / '.zoo-agent' / 'workers' / 'routing_decision.json')
    state = load_json(fixture / '.zoo-agent' / 'session' / 'session_state.json')
    checkpoints = load_json(fixture / '.zoo-agent' / 'autopilot' / 'checkpoints.json')
    cockpit = fixture / '.zoo-agent' / 'cockpit' / 'index.html'
    selected_worker = str(routing.get('selected_worker') or '')
    ok = proc['returncode'] == 0 and bool(state) and bool(checkpoints.get('checkpoints')) and bool(selected_worker) and cockpit.exists()
    return row(
        fixture,
        'session_with_real_worker_availability',
        selected_worker=selected_worker,
        worker_role=str(routing.get('worker_role') or ''),
        execution_mode=str(routing.get('execution_mode') or ''),
        project_map_supported=True,
        session_updated=bool(state),
        cockpit_synced=cockpit.exists(),
        outcome='pass' if ok else 'fail',
    )


def scenario_codex_degrade(fixture: Path) -> dict[str, Any]:
    health = codex_health(fixture)
    profile = classify_task_profile({'title': 'Adjust small source constant', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'auto', 'target_files': ['src/app.py']})
    decision = route_worker(fixture, task_profile=profile, requested_worker='codex', execution_mode='auto')
    selected = str(decision.get('selected_worker') or '')
    codex_unavailable = health.get('available') is False or health.get('health') in {'unavailable', 'degraded'}
    ok = True
    fallback_used = False
    reason = str(decision.get('routing_reason') or '')
    if codex_unavailable:
        fallback_used = selected != 'codex_worker_existing_adapter'
        ok = fallback_used or decision.get('execution_mode') in {'preview', 'needs_attention'}
    return row(
        fixture,
        'codex_unavailable_graceful_degrade',
        selected_worker=selected,
        worker_role=str(decision.get('worker_role') or ''),
        execution_mode=str(decision.get('execution_mode') or ''),
        fallback_used=fallback_used,
        fallback_reason=reason,
        project_map_supported=True,
        session_updated=False,
        cockpit_synced=(fixture / '.zoo-agent' / 'cockpit' / 'index.html').exists(),
        outcome='pass' if ok else 'fail',
    )


def scenario_claude_no_fake(fixture: Path) -> dict[str, Any]:
    detection = claude_health(fixture)
    profile = classify_task_profile({'title': 'Adjust small source constant', 'risk_level': 'low', 'trust_zone': 'trusted', 'execution_mode': 'auto', 'target_files': ['src/app.py']})
    decision = route_worker(fixture, task_profile=profile, requested_worker='claude', execution_mode='auto')
    selected = str(decision.get('selected_worker') or '')
    ok = detection.get('supports_actual_execution') is False and selected != 'claude_worker_stub'
    return row(
        fixture,
        'claude_detection_no_fake_actual',
        selected_worker=selected,
        worker_role=str(decision.get('worker_role') or ''),
        execution_mode=str(decision.get('execution_mode') or ''),
        fallback_used=True,
        fallback_reason=str(decision.get('routing_reason') or ''),
        project_map_supported=True,
        outcome='pass' if ok else 'fail',
        fake_capability_detected=not ok,
    )


def scenario_cockpit(fixture: Path) -> dict[str, Any]:
    run_proc([sys.executable, str(AGENT), 'cockpit', '--workspace', str(fixture)], fixture)
    cockpit = fixture / '.zoo-agent' / 'cockpit' / 'index.html'
    html = cockpit.read_text(encoding='utf-8', errors='replace') if cockpit.exists() else ''
    ok = 'Worker Readiness' in html and 'raw backend' not in html.lower()
    return row(fixture, 'cockpit_worker_readiness', selected_worker='local_scanner_worker', worker_role='Analysis Worker', execution_mode='preview', project_map_supported=True, session_updated=True, cockpit_synced=cockpit.exists(), outcome='pass' if ok else 'fail')


def run_dogfood(project: Path) -> dict[str, Any]:
    base = dogfood_dir(project)
    base.mkdir(parents=True, exist_ok=True)
    fixture = init_fixture()
    rows = [
        scenario_worker_doctor(fixture),
        scenario_local_scanner(fixture),
        scenario_project_map_support(fixture),
        scenario_session(fixture),
        scenario_codex_degrade(fixture),
        scenario_claude_no_fake(fixture),
        scenario_cockpit(fixture),
    ]
    sync_worker_artifacts(fixture, project)
    sync_map_artifacts(fixture, project)
    copy_artifact(fixture / '.zoo-agent' / 'cockpit' / 'index.html', project / '.zoo-agent' / 'cockpit' / 'index.html')
    copy_artifact(fixture / '.zoo-agent' / 'cockpit' / 'cockpit_data.json', project / '.zoo-agent' / 'cockpit' / 'cockpit_data.json')
    trace = {
        'schema_version': '1.0',
        'generated_by': 'real_worker_dogfood_runner.py',
        'generated_at': utc_now(),
        'product_positioning': 'AI Project Operator',
        'fixture': '<SAFE_TEMP_REPO>',
        'runs': rows,
    }
    write_json(base / 'real_worker_dogfood_trace.json', trace)
    value = run_value_gate(project)
    run_replay(project)
    product = generate_report(project)
    readiness = product.get('readiness') or {}
    return {
        'status': 'ok' if readiness.get('readiness') == 'READY_FOR_097_CROSS_PROJECT_LEARNING' else 'needs_fix',
        'trace': '.zoo-agent/real_worker_dogfood/real_worker_dogfood_trace.json',
        'value_report': '.zoo-agent/real_worker_dogfood/real_worker_value_report.json',
        'replay': '.zoo-agent/real_worker_dogfood/real_worker_replay.md',
        'product_report': '.zoo-agent/real_worker_dogfood/project_operator_value_report.md',
        'readiness': readiness,
        'value_gate': value,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Run real local worker adapter dogfood.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_dogfood(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
