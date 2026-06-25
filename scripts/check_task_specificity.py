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

from execution_policy import detect_hard_risk
from runtime_common import safe_name, utc_now, write_json

PATH_RE = re.compile(
    r'([A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.@-]+\.(py|ts|tsx|js|jsx|json|md|yml|yaml|toml|css|scss|html|go|rs|java|cs)\b',
    re.IGNORECASE,
)
AMBIGUOUS_PATTERNS = [
    r'^\s*fix\s+readme\s*$',
    r'^\s*improve\s+docs?\s*$',
    r'^\s*optimi[sz]e\s+code\s*$',
    r'^\s*clean\s+up\s+project\s*$',
    r'^\s*refactor\s+code\s*$',
]
INTENT_TERMS = [
    'fix',
    'add',
    'update',
    'change',
    'remove',
    'rename',
    'create',
    'validate',
    'test',
    'typo',
    '修复',
    '新增',
    '修改',
    '更新',
]
ACCEPTANCE_TERMS = ['only', 'pass', 'ensure', 'so that', 'must', 'test', '验收', '只', '必须']
ARCHITECTURE_TERMS = ['architecture', 'redesign', 'system-wide', 'framework', 'strategy', '架构', '重构']


def has_explicit_scope(text: str, allowed_files: list[str]) -> bool:
    if PATH_RE.search(text):
        return True
    if re.search(r'\b(readme|docs?/|docs?\b|tests?/|src/|app/|lib/)\b', text, re.IGNORECASE):
        return True
    return bool(allowed_files) and any('*' not in item for item in allowed_files)


def looks_broad_allowed(allowed_files: list[str]) -> bool:
    if not allowed_files:
        return False
    return any(item in {'**', 'src/**', 'docs/**'} or item.endswith('/**') for item in allowed_files)


def is_ambiguous(text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in AMBIGUOUS_PATTERNS)


def evaluate(text: str, allowed_files: list[str], *, route: str = 'fast') -> dict[str, Any]:
    lowered = text.lower()
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    questions: list[str] = []
    hard_risk_hits = detect_hard_risk(text, allowed_files)
    explicit_scope = has_explicit_scope(text, allowed_files)
    clear_intent = any(term in lowered for term in INTENT_TERMS)
    acceptance_hint = any(term in lowered for term in ACCEPTANCE_TERMS)
    architecture_needed = any(term in lowered for term in ARCHITECTURE_TERMS)

    if route == 'fast' and hard_risk_hits:
        blockers.append(
            {'id': 'hard_risk_terms', 'message': 'Fast path cannot execute high-risk terms.', 'hits': hard_risk_hits}
        )
    if route == 'fast' and architecture_needed:
        blockers.append(
            {'id': 'architecture_judgment_required', 'message': 'Task appears to need architecture judgment.'}
        )
    if route == 'fast' and (is_ambiguous(text) or not explicit_scope or looks_broad_allowed(allowed_files)):
        blockers.append(
            {'id': 'ambiguous_fast_task', 'message': 'Fast path task lacks a precise file/directory scope.'}
        )
        questions.append('Which exact file or directory should be changed?')
    if route == 'fast' and not clear_intent:
        blockers.append(
            {'id': 'missing_modification_intent', 'message': 'Fast path task lacks a clear modification intent.'}
        )
        questions.append('What should change in the target file?')
    if route == 'fast' and not acceptance_hint:
        warnings.append({'id': 'acceptance_not_explicit', 'message': 'No explicit acceptance cue was found.'})
        questions.append('What should count as done for this small task?')

    readme_typo_probe_allowed = bool(re.search(r'\bfix\s+(a\s+)?typo\s+in\s+readme\b', lowered))
    if readme_typo_probe_allowed:
        blockers = [item for item in blockers if item.get('id') != 'ambiguous_fast_task']
        warnings.append(
            {
                'id': 'readme_typo_probe',
                'message': 'README typo task may scan README; if no typo is found, no-op evidence is required.',
            }
        )

    status = 'pass' if not blockers else 'needs_clarification'
    return {
        'schema_version': '1.0',
        'generated_by': 'check_task_specificity.py',
        'generated_at': utc_now(),
        'route': route,
        'input': text,
        'allowed_files': allowed_files,
        'status': status,
        'verdict': 'SPECIFIC_ENOUGH' if status == 'pass' else 'NEEDS_CLARIFICATION',
        'blockers': blockers,
        'warnings': warnings,
        'clarifying_questions': questions[:3],
        'readme_typo_probe_allowed': readme_typo_probe_allowed,
        'requires_no_op_evidence_if_no_diff': readme_typo_probe_allowed or status == 'pass',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Check whether a fast path task is specific enough to execute.')
    parser.add_argument('input', nargs='*')
    parser.add_argument('--input-text', default='')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', default='')
    parser.add_argument('--task-id', default='')
    parser.add_argument('--route', default='fast')
    parser.add_argument('--allowed-file', action='append', default=[])
    parser.add_argument('--json-output', default='')
    args = parser.parse_args()

    text = args.input_text or ' '.join(args.input).strip()
    if not text:
        print('Missing task input.', file=sys.stderr)
        return 2
    payload = evaluate(text, [str(item) for item in args.allowed_file], route=args.route)
    if args.json_output:
        write_json(Path(args.json_output).resolve(), payload)
    elif args.run_id:
        workspace = Path(args.workspace).resolve()
        write_json(
            workspace
            / '.zoo-agent'
            / 'runs'
            / args.run_id
            / 'task-specificity'
            / f'{safe_name(args.task_id or "task")}.json',
            payload,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload['status'] == 'pass' else 10


if __name__ == '__main__':
    raise SystemExit(main())
