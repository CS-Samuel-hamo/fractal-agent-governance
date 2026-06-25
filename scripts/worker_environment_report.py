#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root


def status_text(value: Any) -> str:
    return str(value or 'unknown').replace('_', ' ')


def build_environment_report(
    project: Path, *, registry: dict[str, Any] | None = None, diagnostics: dict[str, Any] | None = None
) -> str:
    registry = registry or load_json(project / '.zoo-agent' / 'workers' / 'worker_registry.json')
    diagnostics = diagnostics or load_json(project / '.zoo-agent' / 'workers' / 'installation_diagnostics.json')
    workers = [item for item in registry.get('workers') or [] if isinstance(item, dict)]
    real_actual_available = any(
        item.get('supports_actual_execution') and item.get('available') and item.get('provider') != 'mock'
        for item in workers
    )
    lines = [
        '# Worker Environment Report',
        '',
        '## Workers',
    ]
    for worker in workers:
        role = status_text(worker.get('role') or worker.get('worker_type') or 'worker')
        availability = 'available' if worker.get('available') else 'unavailable'
        health = status_text(worker.get('health'))
        notes = status_text(worker.get('notes'))
        lines.append(f'- {role}: {availability}, {health}. {notes}')
    if not workers:
        lines.append('- No worker registry available yet.')
    lines.extend(
        [
            '',
            '## System Status',
            f'- Project map: {"supported" if any("repo_scan" in (item.get("capabilities") or []) for item in workers) else "limited"}',
            f'- Preview: {"supported" if any(item.get("supports_preview") for item in workers) else "unavailable"}',
            f'- Actual code execution: {"available" if real_actual_available else "unavailable"}',
            f'- Autopilot: {"available with safe fallback" if workers else "not ready"}',
            '',
            '## Local Environment',
            f'- OS: {status_text((diagnostics.get("os") or {}).get("system"))}',
            f'- Git: {status_text((diagnostics.get("git") or {}).get("summary"))}',
            f'- Codex CLI: {status_text((diagnostics.get("codex_cli") or {}).get("reason"))}',
            f'- Claude Code CLI: {status_text((diagnostics.get("claude_code_cli") or {}).get("reason"))}',
            '',
            '## Suggested Fixes',
        ]
    )
    if not any(item.get('available') and item.get('provider') == 'codex' for item in workers):
        lines.append(
            '- Code Worker is unavailable. You can still use local scan, preview, dry-run, and needs-attention flows.'
        )
    if not any(item.get('available') and item.get('name') == 'local_scanner_worker' for item in workers):
        lines.append('- Local Scanner is unavailable; check write permissions and rerun worker doctor.')
    if not lines[-1].startswith('- '):
        lines.append('- No required fix detected.')
    lines.append('')
    return '\n'.join(lines)


def write_environment_report(
    project: Path, *, registry: dict[str, Any] | None = None, diagnostics: dict[str, Any] | None = None
) -> Path:
    path = project / '.zoo-agent' / 'workers' / 'worker_environment_report.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_environment_report(project, registry=registry, diagnostics=diagnostics), encoding='utf-8')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description='Render a human-readable worker environment report.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    path = write_environment_report(project)
    print(json.dumps({'status': 'ok', 'report': str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
