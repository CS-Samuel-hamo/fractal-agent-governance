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

from runtime_common import project_root, utc_now, write_json  # noqa: E402


FEEDBACK_DIR = Path('.zoo-agent') / 'feedback'
ITEMS_FILE = FEEDBACK_DIR / 'feedback_items.jsonl'

ALLOWED = {
    'source': {'github_issue', 'manual', 'discord', 'email', 'self_dogfood', 'unknown'},
    'user_type': {'solo_dev', 'indie_hacker', 'oss_maintainer', 'small_team_lead', 'vibe_coding_user', 'unknown'},
    'project_type': {'python_cli', 'node_app', 'library', 'docs_site', 'agent_runtime', 'unknown'},
    'flow': {'install', 'first_run', 'project_map', 'session', 'cockpit', 'release', 'pr', 'worker', 'learning', 'docs', 'positioning'},
    'severity': {'low', 'medium', 'high', 'critical'},
    'product_signal': {'bug', 'friction', 'confusion', 'positioning', 'missing_capability', 'delight', 'unknown'},
    'status': {'new', 'triaged', 'planned', 'closed', 'wont_fix'},
}

SECRET_RE = re.compile(r'(gho_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|password\s*=|token\s*=)', re.I)
ABS_PATH_RE = re.compile(r'([A-Za-z]:\\[^\s]+|/Users/[^\s]+|/home/[^\s]+)')


def feedback_dir(project: Path) -> Path:
    return project / FEEDBACK_DIR


def sanitize_text(text: str) -> tuple[str, bool]:
    contains_secret = bool(SECRET_RE.search(text))
    text = SECRET_RE.sub('<redacted-secret>', text)
    text = ABS_PATH_RE.sub('<redacted-path>', text)
    return text.strip(), contains_secret


def sample_feedback() -> list[dict[str, Any]]:
    return [
        {
            'feedback_id': 'sample-first-run-001',
            'date': utc_now().split('T')[0],
            'source': 'self_dogfood',
            'user_type': 'solo_dev',
            'project_type': 'agent_runtime',
            'flow': 'first_run',
            'summary': 'First-run user needs clearer branch-aware publishing guidance.',
            'raw_feedback_sanitized': 'I am not sure whether to push main or the release branch.',
            'severity': 'high',
            'product_signal': 'friction',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
        {
            'feedback_id': 'sample-positioning-001',
            'date': utc_now().split('T')[0],
            'source': 'self_dogfood',
            'user_type': 'indie_hacker',
            'project_type': 'python_cli',
            'flow': 'positioning',
            'summary': 'User asks whether this is just a Codex wrapper.',
            'raw_feedback_sanitized': 'Why not just use Codex directly?',
            'severity': 'medium',
            'product_signal': 'positioning',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
        {
            'feedback_id': 'sample-cockpit-001',
            'date': utc_now().split('T')[0],
            'source': 'self_dogfood',
            'user_type': 'oss_maintainer',
            'project_type': 'library',
            'flow': 'cockpit',
            'summary': 'Cockpit value is promising but wording should more clearly explain next actions.',
            'raw_feedback_sanitized': 'Cockpit helps, but I want a clearer next step.',
            'severity': 'medium',
            'product_signal': 'confusion',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
        {
            'feedback_id': 'sample-release-001',
            'date': utc_now().split('T')[0],
            'source': 'self_dogfood',
            'user_type': 'small_team_lead',
            'project_type': 'docs_site',
            'flow': 'release',
            'summary': 'Local release and PR drafts feel useful before manual publishing.',
            'raw_feedback_sanitized': 'The release pack is useful because it stays local and reviewable.',
            'severity': 'low',
            'product_signal': 'delight',
            'privacy_checked': True,
            'contains_secret': False,
            'status': 'new',
        },
    ]


def schema() -> dict[str, Any]:
    return {
        'generated_at': utc_now(),
        'schema_version': '1.0',
        'path': '.zoo-agent/feedback/feedback_items.jsonl',
        'required_fields': [
            'feedback_id',
            'date',
            'source',
            'user_type',
            'project_type',
            'flow',
            'summary',
            'raw_feedback_sanitized',
            'severity',
            'product_signal',
            'privacy_checked',
            'contains_secret',
            'status',
        ],
        'allowed_values': {key: sorted(value) for key, value in ALLOWED.items()},
        'privacy_rules': [
            'do not store raw secrets',
            'do not store tokenized URLs',
            'do not store raw backend logs',
            'do not store full local absolute paths',
        ],
    }


def validate_item(item: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    cleaned = dict(item)
    for field in schema()['required_fields']:
        if field not in cleaned:
            errors.append(f'missing:{field}')
    for field, allowed in ALLOWED.items():
        value = str(cleaned.get(field) or 'unknown')
        if value not in allowed:
            errors.append(f'invalid:{field}:{value}')
            cleaned[field] = 'unknown' if 'unknown' in allowed else sorted(allowed)[0]
    for field in ['summary', 'raw_feedback_sanitized']:
        text, contains = sanitize_text(str(cleaned.get(field) or ''))
        cleaned[field] = text
        if contains:
            cleaned['contains_secret'] = True
    cleaned['privacy_checked'] = True
    return cleaned, errors


def load_items(project: Path, *, create_sample: bool = True) -> list[dict[str, Any]]:
    path = project / ITEMS_FILE
    if not path.exists() and create_sample:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as handle:
            for item in sample_feedback():
                handle.write(json.dumps(item, ensure_ascii=False) + '\n')
    items: list[dict[str, Any]] = []
    if not path.exists():
        return items
    for line in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        cleaned, _errors = validate_item(item)
        items.append(cleaned)
    return items


def write_schema(project: Path) -> dict[str, Any]:
    payload = schema()
    feedback_dir(project).mkdir(parents=True, exist_ok=True)
    write_json(feedback_dir(project) / 'feedback_intake_schema.json', payload)
    load_items(project, create_sample=True)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = write_schema(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
