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

AGENT = ROOT / 'scripts' / 'agent.py'


def run(command: list[str], cwd: Path, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=cwd, env=env, text=True, encoding='utf-8', errors='replace', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def workspace() -> Path:
    root = Path(tempfile.mkdtemp(prefix='worker-doctor-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Worker Doctor\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'doctor@example.local'], root)
    run(['git', 'config', 'user.name', 'Worker Doctor'], root)
    run(['git', 'add', 'README.md'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def main() -> int:
    root = workspace()
    proc = run([sys.executable, str(AGENT), 'workers', '--doctor', '--workspace', str(root)], root)
    assert 'Workers:' in proc.stdout
    assert 'System status:' in proc.stdout
    assert 'Local Scanner' in proc.stdout or 'Analysis Worker' in proc.stdout
    assert 'raw log' not in proc.stdout.lower()
    assert 'api key' not in proc.stdout.lower()
    report_path = root / '.zoo-agent' / 'workers' / 'worker_doctor_report.json'
    env_path = root / '.zoo-agent' / 'workers' / 'worker_environment_report.md'
    diagnostics_path = root / '.zoo-agent' / 'workers' / 'installation_diagnostics.json'
    assert report_path.exists()
    assert env_path.exists()
    assert diagnostics_path.exists()
    report = json.loads(report_path.read_text(encoding='utf-8-sig'))
    assert report['system_status']['project_map'] == 'supported'
    diagnostics = json.loads(diagnostics_path.read_text(encoding='utf-8-sig'))
    assert 'diagnostic only; no installation performed' in diagnostics['actions_taken']
    help_text = run([sys.executable, str(AGENT), '--help'], root).stdout.lower()
    assert 'workers --doctor' not in help_text
    assert 'agent workers' not in help_text
    print('worker doctor tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
