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

from public_alpha_packager import PUBLIC_DOCS, public_alpha_dir  # noqa: E402
from runtime_common import project_root, utc_now, write_json  # noqa: E402


WINDOWS_PATH_RE = re.compile(r'\b[A-Za-z]:\\[^\s)`"\']+')
UNIX_PRIVATE_PATH_RE = re.compile(r'(?<!`)(?:/Users/|/home/|/tmp/)[^\s)`"\']+')
TOKEN_RE = re.compile(r'\b(?:ghp|gho|github_pat|sk|xoxb|xoxp)_[A-Za-z0-9_]{12,}\b')
KEY_VALUE_SECRET_RE = re.compile(r'\b(?:API_KEY|SECRET|TOKEN|PASSWORD|PRIVATE_KEY)\s*=\s*[^ \n]+', re.IGNORECASE)
TOKENIZED_REMOTE_RE = re.compile(r'https?://[^/\s:@]+:[^@\s]+@|https?://(?:ghp|github_pat)_[^@\s]+@', re.IGNORECASE)
RAW_LOG_RE = re.compile(r'(?:Traceback \(most recent call last\)|DEBUG\s+\[|raw backend log|stdout=|stderr=)', re.IGNORECASE)
RAW_JSON_DUMP_RE = re.compile(r'"(?:session_state|routing_decision|execution_result)"\s*:\s*\{', re.IGNORECASE)
UNSUPPORTED_CLAIM_PATTERNS = [
    re.compile(r'\bcreates?\s+remote\s+(?:pull\s+requests?|prs?)\b', re.IGNORECASE),
    re.compile(r'\bcalls?\s+github\s+api\b', re.IGNORECASE),
    re.compile(r'\bpushes?\s+to\s+github\b', re.IGNORECASE),
    re.compile(r'\bmerges?\s+pull\s+requests?\b', re.IGNORECASE),
    re.compile(r'\bcloud\s+sync\s+enabled\b', re.IGNORECASE),
]
INTERNAL_MAIN_PATH_TERMS = re.compile(r'\b(eval|governance|planner|verifier|scheduler)\b', re.IGNORECASE)
MAIN_PATH_DOCS = {'README.md', 'QUICKSTART.md', 'EXAMPLES.md'}


def text_files_to_scan(project: Path) -> dict[str, str]:
    paths = [project / rel for rel in PUBLIC_DOCS]
    manifest = public_alpha_dir(project) / 'public_alpha_package_manifest.json'
    if manifest.exists():
        paths.append(manifest)
    demo_root = project / 'examples' / 'demo_project'
    if demo_root.exists():
        paths.extend([path for path in demo_root.rglob('*') if path.is_file()])
    texts: dict[str, str] = {}
    for path in paths:
        if not path.exists() or path.is_dir():
            continue
        try:
            rel = path.relative_to(project).as_posix()
        except ValueError:
            rel = path.name
        texts[rel] = path.read_text(encoding='utf-8-sig', errors='replace')
    return texts


def scan_texts(texts: dict[str, str]) -> dict[str, Any]:
    failed: list[str] = []
    secret = False
    abs_path = False
    raw_log = False
    internal = False
    unsupported = False

    for rel, text in texts.items():
        if TOKEN_RE.search(text) or KEY_VALUE_SECRET_RE.search(text) or TOKENIZED_REMOTE_RE.search(text):
            secret = True
            failed.append(f'{rel}: secret_or_token_marker')
        if WINDOWS_PATH_RE.search(text) or UNIX_PRIVATE_PATH_RE.search(text):
            abs_path = True
            failed.append(f'{rel}: absolute_path')
        if RAW_LOG_RE.search(text) or RAW_JSON_DUMP_RE.search(text):
            raw_log = True
            failed.append(f'{rel}: raw_log_or_debug_dump')
        if rel in MAIN_PATH_DOCS and INTERNAL_MAIN_PATH_TERMS.search(text):
            internal = True
            failed.append(f'{rel}: internal_term_in_main_path')
        for pattern in UNSUPPORTED_CLAIM_PATTERNS:
            for match in pattern.finditer(text):
                prefix = text[max(0, match.start() - 160) : match.start()].lower()
                if (
                    'not ' in prefix
                    or 'no ' in prefix
                    or 'does not ' in prefix
                    or 'do not ' in prefix
                    or 'never automatic' in prefix
                    or 'not automatic' in prefix
                ):
                    continue
                unsupported = True
                failed.append(f'{rel}: unsupported_claim:{match.group(0)}')

    safe = not (secret or abs_path or raw_log or internal or unsupported)
    return {
        'generated_at': utc_now(),
        'safe': safe,
        'secret_leak_detected': secret,
        'absolute_path_leak_detected': abs_path,
        'raw_log_leak_detected': raw_log,
        'internal_leakage_detected': internal,
        'unsupported_claim_detected': unsupported,
        'failed_checks': sorted(set(failed)),
    }


def scan_project(project: Path) -> dict[str, Any]:
    report = scan_texts(text_files_to_scan(project))
    write_json(public_alpha_dir(project) / 'public_docs_safety_report.json', report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    report = scan_project(project)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get('safe') else 1


if __name__ == '__main__':
    raise SystemExit(main())
