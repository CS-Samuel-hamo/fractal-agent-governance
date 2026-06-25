#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json


def classify_step_result(
    final_result: dict[str, Any], execution: dict[str, Any], selected_action: dict[str, Any]
) -> dict[str, Any]:
    if selected_action.get('execution_mode') == 'needs_attention':
        return {
            'outcome': 'blocked',
            'status': 'needs_attention',
            'reason': selected_action.get('reason') or 'selected action needs attention',
            'pause': True,
        }
    verdict = str(final_result.get('final_verdict') or '')
    if verdict == 'COMPLETED':
        return {'outcome': 'delivered', 'status': 'active', 'reason': 'action completed', 'pause': False}
    if verdict == 'DRY_RUN_COMPLETE':
        return {
            'outcome': 'dry_run_only',
            'status': 'needs_attention',
            'reason': 'preview completed; apply requires user intent',
            'pause': True,
        }
    if verdict == 'NO_DELIVERY':
        return {
            'outcome': 'no_delivery',
            'status': 'needs_attention',
            'reason': 'action did not produce a usable change',
            'pause': True,
        }
    if verdict in {'BLOCKED', 'NEEDS_DELIVERY_VERIFICATION', 'PARTIAL'}:
        return {
            'outcome': 'blocked',
            'status': 'needs_attention',
            'reason': 'action needs review before continuing',
            'pause': True,
        }
    for leaf in execution.get('leaf_results') or []:
        status = str(leaf.get('execution_status') or '')
        delivery = str(leaf.get('delivery_outcome') or '')
        if status in {'timeout', 'failed', 'partial'}:
            return {
                'outcome': status or 'failed',
                'status': 'needs_attention',
                'reason': 'worker could not complete the action',
                'pause': True,
            }
        if delivery in {'blocked', 'unsafe', 'no_delivery'}:
            return {
                'outcome': delivery,
                'status': 'needs_attention',
                'reason': 'action needs review before continuing',
                'pause': True,
            }
    return {'outcome': 'unknown', 'status': 'needs_attention', 'reason': 'result was unclear', 'pause': True}


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a session step result.')
    parser.add_argument('--final-result', required=True)
    parser.add_argument('--execution-result', required=True)
    parser.add_argument('--selected-action', required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            classify_step_result(
                load_json(Path(args.final_result).resolve()),
                load_json(Path(args.execution_result).resolve()),
                load_json(Path(args.selected_action).resolve()),
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
