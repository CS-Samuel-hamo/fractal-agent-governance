#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cross_project_store import write_store  # noqa: E402
from runtime_common import load_json, project_root  # noqa: E402


DEFAULT_FAILURES = {
    'no_delivery': ('Worker completed without useful delivery.', 'Pause, inspect delivery outcome, and fallback to dry-run or needs attention.', 'medium'),
    'bad_next_action_without_evidence': ('Next action did not have enough map evidence.', 'Require evidence-backed next_action before autopilot.', 'medium'),
    'worker_unavailable': ('Selected worker was not available locally.', 'Fallback to local scanner, dry-run, or needs attention.', 'low'),
    'fallback_to_needs_attention': ('No safe fallback could execute automatically.', 'Pause session and ask user to review.', 'medium'),
    'blocked_zone_attempt': ('Task touched blocked or sensitive zone.', 'Do not execute; route to needs attention.', 'high'),
    'missing_checkpoint': ('Execution proceeded without checkpoint evidence.', 'Block actual execution until checkpoint is present.', 'high'),
    'map_hallucination_risk': ('Map element lacked supporting evidence.', 'Mark unknown or rebuild map from evidence.', 'medium'),
    'timeout': ('Worker timed out.', 'Retry within bounded policy, then fallback.', 'medium'),
    'scope_violation': ('Worker attempted outside allowed scope.', 'Stop execution and preserve scope guard.', 'high'),
    'test_failure': ('Tests failed after change.', 'Pause and summarize failing area.', 'medium'),
}


def build_failure_taxonomy(project: Path) -> dict[str, Any]:
    counts = {key: 0 for key in DEFAULT_FAILURES}
    evidence = {key: [] for key in DEFAULT_FAILURES}
    for relative in [
        '.zoo-agent/session_dogfood/session_dogfood_trace.json',
        '.zoo-agent/worker_dogfood/worker_router_dogfood_trace.json',
        '.zoo-agent/real_worker_dogfood/real_worker_dogfood_trace.json',
    ]:
        trace = load_json(project / relative)
        surface = json.dumps(trace, ensure_ascii=False).lower()
        for failure_type in DEFAULT_FAILURES:
            token = failure_type.replace('_', ' ')
            if failure_type in surface or token in surface:
                counts[failure_type] += surface.count(failure_type) + surface.count(token)
                evidence[failure_type].append({'source': relative})
    patterns = []
    for failure_type, (description, response, severity) in DEFAULT_FAILURES.items():
        patterns.append(
            {
                'failure_type': failure_type,
                'description': description,
                'common_causes': [description],
                'recommended_response': response,
                'evidence': evidence[failure_type] or [{'source': 'default_taxonomy', 'basis': 'required failure class'}],
                'frequency': counts[failure_type],
                'severity': severity,
            }
        )
    return write_store(project, 'failure_taxonomy', {'generated_by': 'failure_taxonomy_builder.py', 'failure_patterns': patterns})


def main() -> int:
    parser = argparse.ArgumentParser(description='Build cross-project failure taxonomy.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_failure_taxonomy(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
