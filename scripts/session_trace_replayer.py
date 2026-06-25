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


def dogfood_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'session_dogfood'


def _line(value: Any, fallback: str = 'not available') -> str:
    text = str(value or '').strip()
    return text or fallback


def build_replay(trace: dict[str, Any]) -> str:
    lines = [
        '# Session Replay',
        '',
        'This replay summarizes how the project session behaved during controlled dogfood.',
        '',
    ]
    for run in trace.get('runs') or []:
        if not isinstance(run, dict):
            continue
        lines.extend(
            [
                f'## {_line(run.get("scenario")).replace("_", " ").title()}',
                '',
                f'- result: {_line(run.get("scenario_result"))}',
            ]
        )
        for step in run.get('steps') or []:
            if not isinstance(step, dict):
                continue
            lines.extend(
                [
                    '',
                    f'### Step {step.get("step", 0)}',
                    f'- command: `{_line(step.get("command"))}`',
                    f'- before: {_line(step.get("session_status_before"))}',
                    f'- selected action: {_line(step.get("selected_action"))}',
                    f'- source: {_line(step.get("selected_action_source"))}',
                    f'- checkpoint: {"created" if step.get("checkpoint_created") else "not needed"}',
                    f'- outcome: {_line(step.get("execution_outcome"))}',
                    f'- after: {_line(step.get("session_status_after"))}',
                    f'- project map updated: {"yes" if step.get("project_map_updated") else "no"}',
                    f'- digest updated: {"yes" if step.get("digest_updated") else "no"}',
                    f'- cockpit synced: {"yes" if step.get("cockpit_synced") else "no"}',
                    f'- attention required: {"yes" if step.get("attention_required") else "no"}',
                    f'- resume available: {"yes" if step.get("resume_available") else "no"}',
                ]
            )
            if step.get('attention_required'):
                lines.append('- next command: review the digest, then run `agent continue` or `agent stop`.')
            elif step.get('session_status_after') == 'stopped':
                lines.append('- next command: run `agent start "<project goal>"` to begin a new session.')
            else:
                lines.append('- next command: run `agent status`, `agent continue`, `agent stop`, or `agent cockpit`.')
        lines.append('')
    return '\n'.join(lines).strip() + '\n'


def run_replay(project: Path, *, trace_path: Path | None = None) -> Path:
    trace = load_json(trace_path or dogfood_dir(project) / 'session_dogfood_trace.json')
    out = dogfood_dir(project) / 'session_replay.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_replay(trace), encoding='utf-8')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Render a readable replay for session dogfood.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    path = run_replay(project, trace_path=Path(args.trace).resolve() if args.trace else None)
    print(
        json.dumps(
            {'status': 'ok', 'replay': '.zoo-agent/session_dogfood/session_replay.md'}, ensure_ascii=False, indent=2
        )
    )
    return 0 if path.exists() else 1


if __name__ == '__main__':
    raise SystemExit(main())
