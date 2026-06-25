#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json

SECRET_PATTERNS = [
    re.compile(r'ghp_[A-Za-z0-9_]{20,}'),
    re.compile(r'github_pat_[A-Za-z0-9_]{20,}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
    re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
    re.compile(r'://[^/<>\s:]+:[^/@\s]+@'),
    re.compile(r'\b(API_KEY|SECRET|PASSWORD|TOKEN)\s*='),
]
ABS_PATH_RE = re.compile(r'([A-Za-z]:\\|/Users/|/home/|/tmp/)')
NETWORK_MARKERS = ['NETWORK_CALL', 'GH_API_CALLED', 'gh api ', 'curl https://api.github.com']
PUSH_MARKERS = ['PUSH_EXECUTED', 'git push ']
MERGE_MARKERS = ['MERGE_EXECUTED', 'git merge ']
RAW_LOG_MARKERS = ['RAW_BACKEND_LOG', 'raw backend log dump']


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def artifact_texts(project: Path) -> list[tuple[str, str]]:
    rows = []
    root = release_dir(project)
    if not root.exists():
        return rows
    for path in sorted(root.glob('*')):
        if path.name == 'github_workflow_safety_report.json':
            continue
        if path.is_file() and path.suffix.lower() in {'.json', '.md', '.txt'}:
            try:
                rows.append((path.name, path.read_text(encoding='utf-8-sig', errors='replace')))
            except Exception:
                continue
    return rows


def run_safety_gate(project: Path) -> dict:
    network = False
    push = False
    merge = False
    token = False
    secret = False
    abs_path = False
    raw_log = False
    failed: list[str] = []
    for name, text in artifact_texts(project):
        if any(marker in text for marker in NETWORK_MARKERS):
            network = True
            failed.append(f'network marker in {name}')
        if any(marker in text for marker in PUSH_MARKERS):
            push = True
            failed.append(f'remote write marker in {name}')
        if any(marker in text for marker in MERGE_MARKERS):
            merge = True
            failed.append(f'merge marker in {name}')
        if any(pattern.search(text) for pattern in SECRET_PATTERNS):
            token = True
            secret = True
            failed.append(f'sensitive marker in {name}')
        if ABS_PATH_RE.search(text):
            abs_path = True
            failed.append(f'absolute path marker in {name}')
        if any(marker in text for marker in RAW_LOG_MARKERS):
            raw_log = True
            failed.append(f'raw log marker in {name}')
    safe = not any([network, push, merge, token, secret, abs_path, raw_log])
    payload = {
        'generated_by': 'github_workflow_safety_gate.py',
        'generated_at': utc_now(),
        'safe': safe,
        'network_call_detected': network,
        'push_detected': push,
        'merge_detected': merge,
        'token_read_detected': token,
        'secret_leak_detected': secret,
        'absolute_path_leak_detected': abs_path,
        'raw_backend_log_leak_detected': raw_log,
        'failed_checks': failed,
    }
    write_json(release_dir(project) / 'github_workflow_safety_report.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Validate local GitHub workflow safety.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_safety_gate(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('safe') else 1


if __name__ == '__main__':
    raise SystemExit(main())
