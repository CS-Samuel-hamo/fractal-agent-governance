#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from local_scanner_worker import scan_repo


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True)
    if proc.returncode != 0:
        raise AssertionError(f'command failed: {command}\nstdout={proc.stdout}\nstderr={proc.stderr}')
    return proc


def fixture() -> Path:
    root = Path(tempfile.mkdtemp(prefix='local-scanner-', dir=tempfile.gettempdir())).resolve()
    (root / 'README.md').write_text('# Scanner Fixture\n', encoding='utf-8')
    (root / 'pyproject.toml').write_text('[project]\nname = "scanner-fixture"\n', encoding='utf-8')
    (root / 'src').mkdir()
    (root / 'src' / 'app.py').write_text('VALUE = 1\n', encoding='utf-8')
    (root / 'tests').mkdir()
    (root / 'tests' / 'test_app.py').write_text('def test_ok():\n    assert True\n', encoding='utf-8')
    (root / 'docs').mkdir()
    (root / 'docs' / 'guide.md').write_text('# Guide\n', encoding='utf-8')
    (root / '.env').write_text('API_KEY=should-not-be-read\n', encoding='utf-8')
    (root / 'secrets.txt').write_text('token=should-not-be-read\n', encoding='utf-8')
    run(['git', 'init'], root)
    run(['git', 'config', 'user.email', 'scanner@example.local'], root)
    run(['git', 'config', 'user.name', 'Scanner Test'], root)
    run(['git', 'add', 'README.md', 'pyproject.toml', 'src', 'tests', 'docs'], root)
    run(['git', 'commit', '-m', 'init'], root)
    return root


def main() -> int:
    root = fixture()
    tracked_before = {
        'README.md': (root / 'README.md').read_text(encoding='utf-8'),
        'pyproject.toml': (root / 'pyproject.toml').read_text(encoding='utf-8'),
        'src/app.py': (root / 'src' / 'app.py').read_text(encoding='utf-8'),
        'tests/test_app.py': (root / 'tests' / 'test_app.py').read_text(encoding='utf-8'),
        'docs/guide.md': (root / 'docs' / 'guide.md').read_text(encoding='utf-8'),
    }
    report = scan_repo(root)
    assert report['files_scanned'] >= 5
    assert report['detected_project_type'] == 'python'
    assert 'pyproject.toml' in report['detected_manifests']
    assert 'README.md' in report['detected_docs']
    assert 'tests/test_app.py' in report['detected_tests']
    skipped_paths = [item['path'] for item in report['files_skipped']]
    assert '.env' in skipped_paths
    assert 'secrets.txt' in skipped_paths
    text = json.dumps(report, ensure_ascii=False)
    assert 'should-not-be-read' not in text
    assert 'API_KEY=' not in text
    for relative, content in tracked_before.items():
        assert (root / relative).read_text(encoding='utf-8') == content
    assert not run(
        ['git', 'diff', '--', 'README.md', 'pyproject.toml', 'src/app.py', 'tests/test_app.py', 'docs/guide.md'], root
    ).stdout
    assert report['map_support']['evidence']
    assert (root / '.zoo-agent' / 'workers' / 'local_scanner_report.json').exists()
    print('local scanner worker tests passed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
