#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json

TOKEN_RE = re.compile(r'(?i)(api[_-]?key|token|secret|password|credential)\s*[:=]\s*["\']?[^"\'\s,}]+')
EMAIL_RE = re.compile(r'[\w.\-+]+@[\w.\-]+\.\w+')
WINDOWS_PATH_RE = re.compile(r'[A-Za-z]:[\\/][^"\']+')
POSIX_ABS_RE = re.compile(r'(?<![\w])/(?:Users|home|tmp|var|etc)/[^"\']+')
PRIVATE_KEY_RE = re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----', re.DOTALL)
RAW_LOG_KEYS = {'stdout_tail', 'stderr_tail', 'raw_log', 'raw_logs', 'backend_log', 'command_result'}
SECRET_NAME_RE = re.compile(r'(?i)(^|/|\\)(\.env|.*secret.*|.*credential.*|.*token.*|.*\.pem|.*\.key)$')
CODE_BLOCK_RE = re.compile(r'```.*?```', re.DOTALL)


def redact_text(value: str, redactions: list[str]) -> str:
    text = value
    if TOKEN_RE.search(text):
        redactions.append('token_like_content')
        text = TOKEN_RE.sub('[REDACTED_SECRET]', text)
    if PRIVATE_KEY_RE.search(text):
        redactions.append('private_key_block')
        text = PRIVATE_KEY_RE.sub('[REDACTED_PRIVATE_KEY]', text)
    if EMAIL_RE.search(text):
        redactions.append('email')
        text = EMAIL_RE.sub('[REDACTED_EMAIL]', text)
    if WINDOWS_PATH_RE.search(text) or POSIX_ABS_RE.search(text):
        redactions.append('absolute_path')
        text = WINDOWS_PATH_RE.sub('<LOCAL_PATH>', text)
        text = POSIX_ABS_RE.sub('<LOCAL_PATH>', text)
    for block in CODE_BLOCK_RE.findall(text):
        if len(block) > 400:
            redactions.append('long_code_block')
            text = text.replace(block, '[REDACTED_LONG_CODE_BLOCK]')
    return text


def sanitize(value: Any, redactions: list[str], *, key: str = '') -> Any:
    lowered_key = key.lower()
    if lowered_key in RAW_LOG_KEYS:
        redactions.append(f'raw_log_field:{key}')
        return '[REDACTED_RAW_LOG]'
    if isinstance(value, dict):
        return {str(k): sanitize(v, redactions, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize(item, redactions, key=key) for item in value[:200]]
    if isinstance(value, str):
        normalized = value.replace('\\', '/')
        looks_like_path = '/' in normalized or normalized.startswith('.') or normalized.endswith(('.pem', '.key'))
        if looks_like_path and SECRET_NAME_RE.search(normalized):
            redactions.append('secret_like_path')
            return normalized.split('/')[-1] + ' [restricted metadata only]'
        return redact_text(value, redactions)
    return value


def filter_artifact(path: Path, payload: Any | None = None) -> dict[str, Any]:
    redactions: list[str] = []
    if SECRET_NAME_RE.search(path.name):
        return {
            'input_artifact': path.name,
            'privacy_status': 'rejected',
            'redactions': ['secret_like_filename'],
            'rejection_reason': 'secret-like artifact is not imported',
            'safe_to_store': False,
            'sanitized': {},
        }
    data = payload if payload is not None else load_json(path)
    sanitized = sanitize(data, redactions)
    status = 'sanitized' if redactions else 'passed'
    text = json.dumps(sanitized, ensure_ascii=False).lower()
    if 'should-not-be-read' in text:
        return {
            'input_artifact': path.name,
            'privacy_status': 'rejected',
            'redactions': sorted(set([*redactions, 'secret_marker_after_sanitize'])),
            'rejection_reason': 'secret-like marker remained after sanitize',
            'safe_to_store': False,
            'sanitized': {},
        }
    return {
        'input_artifact': path.name,
        'privacy_status': status,
        'redactions': sorted(set(redactions)),
        'rejection_reason': '',
        'safe_to_store': True,
        'sanitized': sanitized,
    }


def write_privacy_report(project: Path, report: dict[str, Any]) -> dict[str, Any]:
    public = {key: value for key, value in report.items() if key != 'sanitized'}
    write_json(project / '.zoo-agent' / 'learning' / 'cross_project' / 'privacy_filter_report.json', public)
    return public


def main() -> int:
    parser = argparse.ArgumentParser(description='Sanitize one artifact before cross-project learning import.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--artifact', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    report = filter_artifact(Path(args.artifact).resolve())
    public = write_privacy_report(project, report)
    print(json.dumps(public, ensure_ascii=False, indent=2))
    return 0 if public.get('safe_to_store') else 1


if __name__ == '__main__':
    raise SystemExit(main())
