#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from project_map_builder import build_project_map  # noqa: E402
from project_map_updater import update_project_map  # noqa: E402
from runtime_common import write_json  # noqa: E402


def run(cmd: list[str], cwd: Path) -> None:
    proc = subprocess.run(cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print('$', ' '.join(str(item) for item in cmd))
    print(proc.stdout)
    if proc.returncode:
        raise AssertionError(f'command failed: {cmd}')


def init_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix='project-map-kernel-', dir=tempfile.gettempdir())).resolve()
    (repo / 'README.md').write_text('# Project Map Kernel\n', encoding='utf-8')
    (repo / 'docs').mkdir()
    (repo / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (repo / 'src').mkdir()
    (repo / 'src' / 'app.py').write_text('print("ok")\n', encoding='utf-8')
    (repo / '.env').write_text('SHOULD_NOT_BE_READ=1\n', encoding='utf-8')
    run(['git', 'init'], repo)
    run(['git', 'config', 'user.email', 'map@example.local'], repo)
    run(['git', 'config', 'user.name', 'Project Map Test'], repo)
    run(['git', 'add', 'README.md', 'docs/guide.md', 'src/app.py'], repo)
    run(['git', 'commit', '-m', 'init'], repo)
    return repo


def main() -> int:
    repo = init_repo()
    project_map, state, evidence = build_project_map(repo, main_goal='Improve project readiness')
    assert project_map['project_name'] == repo.name
    assert project_map['modules'], 'expected mapped modules'
    assert project_map['capabilities'], 'expected capabilities'
    assert project_map['next_actions'], 'expected map-backed next actions'
    assert evidence['sensitive_content_read'] is False
    assert '.env' in evidence['skipped_sensitive_paths']
    assert all(item.get('evidence') for item in project_map['next_actions']), 'next actions must be evidence-backed'
    assert state['status'] in {'mapped', 'unknown'}

    map_dir = repo / '.zoo-agent' / 'map'
    write_json(map_dir / 'project_map.json', project_map)
    write_json(map_dir / 'project_state.json', state)
    write_json(map_dir / 'map_evidence.json', evidence)
    execution = {'leaf_results': [{'business_changed_files': ['README.md'], 'delivery_outcome': 'delivered'}]}
    final = {'final_verdict': 'COMPLETED'}
    updated = update_project_map(repo, run_id='map-update-test', action=project_map['next_actions'][0], execution_result=execution, final_result=final)
    assert updated['changed_files'] == ['README.md']
    assert (map_dir / 'project_map.json').exists()
    assert (map_dir / 'project_map.md').exists()
    assert (map_dir / 'project_state.json').exists()
    print('project map kernel tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
