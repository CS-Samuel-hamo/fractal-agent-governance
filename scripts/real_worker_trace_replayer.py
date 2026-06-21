#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root  # noqa: E402


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'real_worker_dogfood'


def row_line(row: dict[str, Any]) -> str:
    return (
        f"- {str(row.get('scenario') or 'scenario').replace('_', ' ')}: {row.get('outcome', 'unknown')}; "
        f"worker {row.get('worker_role') or row.get('selected_worker') or 'not selected'}; "
        f"mode {row.get('execution_mode', 'unknown')}"
    )


def build_replay(project: Path) -> str:
    trace = load_json(dogfood_dir(project) / 'real_worker_dogfood_trace.json')
    doctor = load_json(project / '.zoo-agent' / 'workers' / 'worker_doctor_report.json')
    scanner = load_json(project / '.zoo-agent' / 'workers' / 'local_scanner_report.json')
    codex = load_json(project / '.zoo-agent' / 'workers' / 'codex_adapter_health.json')
    claude = load_json(project / '.zoo-agent' / 'workers' / 'claude_code_detection.json')
    workers = doctor.get('workers') or []
    available = [f"{item.get('role')} ({item.get('health')})" for item in workers if item.get('available')]
    unavailable = [f"{item.get('role')}: {item.get('why_unavailable')}" for item in workers if not item.get('available')]
    runs = [item for item in trace.get('runs') or [] if isinstance(item, dict)]
    available_lines = [f'- {item}' for item in available] if available else ['- No available workers recorded.']
    unavailable_lines = [f'- {item}' for item in unavailable] if unavailable else ['- No unavailable workers recorded.']
    lines = [
        '# Real Worker Dogfood Replay',
        '',
        '## Available Workers',
        *available_lines,
        '',
        '## Unavailable Workers',
        *unavailable_lines,
        '',
        '## Local Scanner',
        f"- Scanned files: {scanner.get('files_scanned', 0)}",
        f"- Evidence rows: {len((scanner.get('map_support') or {}).get('evidence') or [])}",
        '- Secret-like files are recorded as skipped metadata only.',
        '',
        '## Graceful Degradation',
        f"- Code Worker health: {codex.get('health', 'unknown')} ({codex.get('reason', 'not available')})",
        f"- Claude Code detection: {claude.get('status', 'unknown')} ({claude.get('reason', 'not available')})",
        '- If an external worker is unavailable, the system keeps repo scan, preview, dry-run, or needs-attention flows available.',
        '',
        '## Session And Routing',
    ]
    lines.extend(row_line(row) for row in runs)
    lines.extend(
        [
            '',
            '## Cockpit',
            '- Cockpit shows Worker Readiness as product-level roles, not raw provider logs.',
            '',
            '## Next Commands',
            '- agent workers --doctor',
            '- agent start "prepare this project for public release"',
            '- agent status',
            '- agent continue',
            '- agent cockpit',
            '',
            '## Product Takeaway',
            'The worker layer supports AI Project Operator behavior by preserving project map, session, and cockpit flows even when external code workers are unavailable.',
            '',
        ]
    )
    return '\n'.join(lines)


def run_replay(project: Path) -> Path:
    path = dogfood_dir(project) / 'real_worker_replay.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_replay(project), encoding='utf-8')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description='Replay real worker adapter dogfood in human-readable form.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    path = run_replay(project)
    print(json.dumps({'status': 'ok', 'replay': str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
