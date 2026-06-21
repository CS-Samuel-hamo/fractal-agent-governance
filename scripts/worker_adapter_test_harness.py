#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, write_json  # noqa: E402
from worker_adapter_contract import validate_contract  # noqa: E402
from worker_registry import write_worker_registry  # noqa: E402


def run_contract_checks(project: Path) -> dict[str, Any]:
    registry = write_worker_registry(project)
    failures = []
    for worker in registry.get('workers') or []:
        if not isinstance(worker, dict):
            continue
        contract = worker.get('contract') if isinstance(worker.get('contract'), dict) else {}
        if not contract:
            failures.append(f"missing_contract:{worker.get('name')}")
            continue
        errors = validate_contract(
            contract,
            {
                'supports_actual_execution': worker.get('supports_actual_execution'),
                'supports_preview': worker.get('supports_preview'),
                'capabilities': worker.get('capabilities') or [],
            },
        )
        failures.extend([f"{worker.get('name')}:{item}" for item in errors])
        if contract.get('supports_actual_execution') is False and worker.get('supports_actual_execution'):
            failures.append(f"{worker.get('name')}:actual_not_allowed_by_contract")
        if contract.get('reads_secrets') is not False:
            failures.append(f"{worker.get('name')}:reads_secrets_not_allowed")
    payload = {'schema_version': '1.0', 'generated_by': 'worker_adapter_test_harness.py', 'passed': not failures, 'failures': failures}
    write_json(project / '.zoo-agent' / 'workers' / 'worker_adapter_contract_check.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Run worker adapter contract boundary checks.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = run_contract_checks(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('passed') else 1


if __name__ == '__main__':
    raise SystemExit(main())
