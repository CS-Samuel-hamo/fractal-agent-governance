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


EXPECTED_RELEASE_BRANCH = 'release/v1.0.0-alpha.1'
POST_LAUNCH_DIR = Path('.zoo-agent') / 'post_launch'

DOCS_AND_RELEASE_SCRIPTS = [
    'README.md',
    'RELEASE_NOTES.md',
    'LAUNCH.md',
    'POST_RELEASE_SMOKE_TEST.md',
    'PUBLIC_RELEASE_CHECKLIST.md',
    'GITHUB_RELEASE_DRAFT.md',
    'PUBLISHING.md',
    'BRANCHING.md',
    'POST_LAUNCH_STATUS.md',
    'scripts/public_launch_packager.py',
    'scripts/release_tag_preflight.py',
    'scripts/public_release_report_generator.py',
]

FORCE_PUSH_RE = re.compile(r'\bgit\s+push\b[^\n`]*(?:--force|-f)\b')
MAIN_PUSH_RE = re.compile(r'\bgit\s+push\s+origin\s+main\b')
GH_WRITE_RE = re.compile(r'\bgh\s+(?:release\s+create|pr\s+create|api\b[^\n`]*(?:--method\s+(?:POST|PATCH|PUT|DELETE)|-X\s*(?:POST|PATCH|PUT|DELETE)))')


def _allowed_negative_example(line: str) -> bool:
    lowered = line.lower()
    return any(marker in lowered for marker in ['do not run', 'never run', 'wrong example', 'do not use', 'avoid running'])


def lint_texts(texts: dict[str, str]) -> dict[str, Any]:
    bad_commands: list[dict[str, Any]] = []
    rewrites: list[dict[str, str]] = []
    hardcoded_main = False
    force_push = False
    unsafe_github_write = False

    for rel, text in sorted(texts.items()):
        for lineno, line in enumerate(text.splitlines(), start=1):
            if MAIN_PUSH_RE.search(line) and not _allowed_negative_example(line):
                hardcoded_main = True
                bad_commands.append({'file': rel, 'line': lineno, 'command': 'git push origin main', 'reason': 'hardcoded main publish command'})
                rewrites.append({'file': rel, 'line': str(lineno), 'rewrite': f'git push origin HEAD:refs/heads/{EXPECTED_RELEASE_BRANCH}'})
            if FORCE_PUSH_RE.search(line) and not _allowed_negative_example(line):
                force_push = True
                bad_commands.append({'file': rel, 'line': lineno, 'command': line.strip(), 'reason': 'force push command'})
            if GH_WRITE_RE.search(line) and not _allowed_negative_example(line):
                unsafe_github_write = True
                bad_commands.append({'file': rel, 'line': lineno, 'command': line.strip(), 'reason': 'automated GitHub write command'})
    passed = not hardcoded_main and not force_push and not unsafe_github_write and not bad_commands
    return {
        'generated_at': utc_now(),
        'publishing_command_lint_passed': passed,
        'hardcoded_main_push_detected': hardcoded_main,
        'force_push_detected': force_push,
        'unsafe_github_write_detected': unsafe_github_write,
        'bad_commands': bad_commands,
        'recommended_rewrites': rewrites,
    }


def lint_project(project: Path) -> dict[str, Any]:
    texts: dict[str, str] = {}
    for rel in DOCS_AND_RELEASE_SCRIPTS:
        path = project / rel
        if path.exists():
            texts[rel] = path.read_text(encoding='utf-8-sig', errors='replace')
    payload = lint_texts(texts)
    write_json(project / POST_LAUNCH_DIR / 'publishing_command_lint_report.json', payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    payload = lint_project(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('publishing_command_lint_passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
