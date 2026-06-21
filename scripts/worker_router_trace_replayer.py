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
    return project / '.zoo-agent' / 'worker_dogfood'


def _value(value: Any, fallback: str = 'not available') -> str:
    text = str(value or '').strip()
    return text or fallback


def build_replay(trace: dict[str, Any]) -> str:
    lines = [
        '# Worker Router Replay',
        '',
        'This replay explains how the project operator selected workers during controlled dogfood.',
        '',
    ]
    for run in trace.get('runs') or []:
        if not isinstance(run, dict):
            continue
        profile = run.get('task_profile') if isinstance(run.get('task_profile'), dict) else {}
        decision = run.get('routing_decision') if isinstance(run.get('routing_decision'), dict) else {}
        rejected = decision.get('rejected_workers') if isinstance(decision.get('rejected_workers'), list) else []
        lines.extend(
            [
                f"## {_value(run.get('scenario')).replace('_', ' ').title()}",
                '',
                f"- outcome: {_value(run.get('outcome'))}",
                f"- selected action: {_value(run.get('selected_action'))}",
                f"- source: {_value(run.get('selected_action_source'))}",
                f"- task type: {_value(profile.get('task_type'))}",
                f"- risk: {_value(profile.get('risk_level'))}",
                f"- trust zone: {_value(profile.get('trust_zone'))}",
                f"- selected worker role: {_value(decision.get('worker_role') or decision.get('selected_worker_type'))}",
                f"- routing mode: {_value(decision.get('execution_mode'))}",
                f"- reason: {_value(decision.get('routing_reason'))}",
            ]
        )
        if rejected:
            lines.append('- other workers not selected:')
            for item in rejected[:5]:
                if isinstance(item, dict):
                    lines.append(f"  - {_value(item.get('worker'))}: {_value(item.get('reason'))}")
        if run.get('fallback_used'):
            lines.extend(
                [
                    f"- fallback: used",
                    f"- fallback safe: {'yes' if run.get('fallback_safe') else 'no'}",
                ]
            )
        else:
            lines.append('- fallback: not needed')
        lines.extend(
            [
                f"- checkpoint: {'created' if run.get('checkpoint_created') else 'not needed'}",
                f"- session updated: {'yes' if run.get('session_updated') else 'no'}",
                f"- cockpit synced: {'yes' if run.get('cockpit_synced') else 'no'}",
                '- next command: `agent status`, `agent continue`, or `agent cockpit`.',
                '',
            ]
        )
    return '\n'.join(lines).strip() + '\n'


def run_replay(project: Path, *, trace_path: Path | None = None) -> Path:
    trace = load_json(trace_path or dogfood_dir(project) / 'worker_router_dogfood_trace.json')
    out = dogfood_dir(project) / 'worker_router_replay.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_replay(trace), encoding='utf-8')
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description='Render worker router dogfood replay.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--trace', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    path = run_replay(project, trace_path=Path(args.trace).resolve() if args.trace else None)
    print(json.dumps({'status': 'ok', 'replay': '.zoo-agent/worker_dogfood/worker_router_replay.md'}, ensure_ascii=False, indent=2))
    return 0 if path.exists() else 1


if __name__ == '__main__':
    raise SystemExit(main())
