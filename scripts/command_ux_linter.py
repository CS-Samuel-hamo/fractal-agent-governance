#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from runtime_common import project_root, utc_now, write_json

DOCS = [
    'README.md',
    'QUICKSTART.md',
    'CLI_REFERENCE.md',
    'FAQ.md',
    'DEMO.md',
    'NEW_PROJECT_GUIDE.md',
    'FIRST_USER_TEST_PLAN.md',
]
HIDDEN_TERMS = ['workers --doctor', 'learning --build', 'feedback --report', 'postlaunch', 'publish --']
OVERCLAIMS = [
    'fully autonomous 24h',
    '24h fully autonomous',
    'full autonomous',
    'runs forever in the background',
    'always-on daemon',
]


def _read(project: Path, name: str) -> str:
    path = project / name
    return path.read_text(encoding='utf-8-sig') if path.exists() else ''


def lint(project: Path) -> dict[str, Any]:
    failed: list[str] = []
    texts = {name: _read(project, name) for name in DOCS}
    combined = '\n'.join(texts.values())
    help_proc = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts' / 'agent.py'), '--help'],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    help_text = help_proc.stdout
    if 'agent "<goal>"' not in texts.get('README.md', '') or '\nagent\n' not in texts.get('README.md', ''):
        failed.append('readme_missing_two_command_flow')
    if 'most usage is two commands' not in texts.get('QUICKSTART.md', '').lower():
        failed.append('quickstart_missing_two_command_flow')
    if 'daily path' not in texts.get('CLI_REFERENCE.md', '').lower():
        failed.append('cli_reference_not_layered')
    if 'why are there more commands' not in texts.get('FAQ.md', '').lower():
        failed.append('faq_missing_command_simplification')
    if 'agent "<goal>"' not in help_text or 'agent' not in help_text:
        failed.append('help_missing_two_command_flow')
    if any(term in help_text for term in HIDDEN_TERMS):
        failed.append('help_exposes_hidden_commands')
    if 'Codex wrapper' in combined and 'not a Codex wrapper' not in combined:
        failed.append('codex_wrapper_positioning_risk')
    if any(term.lower() in combined.lower() for term in OVERCLAIMS):
        failed.append('overclaims_background_daemon')
    score = round(max(0.0, 1.0 - (len(failed) * 0.12)), 3)
    two_command = (
        1.0 if not any(item.startswith(('readme', 'quickstart', 'cli_reference', 'help')) for item in failed) else 0.7
    )
    hidden = 0.0 if 'help_exposes_hidden_commands' in failed else 1.0
    overclaim = any(item == 'overclaims_background_daemon' for item in failed)
    recommendation = 'pass' if score >= 0.85 and not overclaim and hidden == 1.0 else 'fix_before_user_test'
    payload = {
        'generated_at': utc_now(),
        'command_ux_score': score,
        'two_command_flow_score': two_command,
        'hidden_complexity_score': hidden,
        'overclaim_detected': overclaim,
        'codex_wrapper_risk': 'low' if 'codex_wrapper_positioning_risk' not in failed else 'medium',
        'failed_checks': failed,
        'recommendation': recommendation,
    }
    write_json(project / '.zoo-agent' / 'command_ux' / 'command_ux_lint_report.json', payload)
    readiness = {
        'generated_at': utc_now(),
        'readiness': 'BACKGROUND_JOB_UX_104_READY' if recommendation == 'pass' else 'FIX_BEFORE_FIRST_USER_TEST',
        'command_ux_score': score,
        'two_command_flow_score': two_command,
        'hidden_complexity_score': hidden,
        'must_fix': failed,
    }
    write_json(project / '.zoo-agent' / 'command_ux' / 'readiness_for_first_user_test.json', readiness)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Lint product command UX and docs.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    payload = lint(project_root(args.workspace))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('recommendation') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
