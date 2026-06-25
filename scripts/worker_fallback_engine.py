#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, write_json


def fallback_trace(
    *,
    original_worker: str = '',
    fallback_chain: list[str] | None = None,
    final_worker: str = '',
    final_mode: str = 'preview',
    reason: str = '',
    safe: bool = True,
) -> dict[str, Any]:
    return {
        'schema_version': '1.0',
        'generated_by': 'worker_fallback_engine.py',
        'original_worker': original_worker,
        'fallback_chain': fallback_chain or [],
        'final_worker': final_worker,
        'final_mode': final_mode,
        'reason': reason,
        'safe': bool(safe),
    }


def write_fallback_trace(project: Path, payload: dict[str, Any]) -> dict[str, Any]:
    write_json(project / '.zoo-agent' / 'workers' / 'fallback_trace.json', payload)
    return payload


def fallback_for_result(
    project: Path, *, routing_decision: dict[str, Any], worker_result: dict[str, Any]
) -> dict[str, Any]:
    status = str(worker_result.get('status') or '')
    if status in {'success', 'skipped'}:
        payload = fallback_trace(
            original_worker=str(routing_decision.get('selected_worker') or ''),
            fallback_chain=[],
            final_worker=str(routing_decision.get('selected_worker') or ''),
            final_mode=str(routing_decision.get('execution_mode') or 'auto'),
            reason='no_fallback_needed',
            safe=True,
        )
    else:
        payload = fallback_trace(
            original_worker=str(routing_decision.get('selected_worker') or ''),
            fallback_chain=[str(item) for item in routing_decision.get('fallback_workers') or []],
            final_worker='dry_run_worker' if 'dry_run_worker' in routing_decision.get('fallback_workers', []) else '',
            final_mode='preview'
            if 'dry_run_worker' in routing_decision.get('fallback_workers', [])
            else 'needs_attention',
            reason=status or 'worker_failed',
            safe=True,
        )
    return write_fallback_trace(project, payload)


def main() -> int:
    parser = argparse.ArgumentParser(description='Write or inspect worker fallback trace.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--routing-decision', default='')
    parser.add_argument('--worker-result', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    if args.routing_decision and args.worker_result:
        payload = fallback_for_result(
            project,
            routing_decision=load_json(Path(args.routing_decision).resolve()),
            worker_result=load_json(Path(args.worker_result).resolve()),
        )
    else:
        payload = load_json(project / '.zoo-agent' / 'workers' / 'fallback_trace.json')
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
