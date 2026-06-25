#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from learning_signal_collector import build_learning_signal
from runtime_common import load_json, project_root, utc_now, write_json


def append_learning_signal(project: Path, signal: dict[str, Any], *, limit: int = 500) -> dict[str, Any]:
    path = project / '.zoo-agent' / 'learning' / 'signals.json'
    payload = load_json(path)
    signals = payload.get('signals') if isinstance(payload.get('signals'), list) else []
    signals = [item for item in signals if isinstance(item, dict)]
    signals.append(signal)
    output = {
        'schema_version': '1.0',
        'generated_by': 'learning_signal_engine.py',
        'updated_at': utc_now(),
        'signals': signals[-limit:],
    }
    write_json(path, output)
    return output


def collect_and_write_learning_signal(
    project: Path, eval_payload: dict[str, Any], governance_decision: dict[str, Any]
) -> dict[str, Any]:
    signal = build_learning_signal(eval_payload, governance_decision)
    return append_learning_signal(project, signal)


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect internal learning signals from invisible eval results.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--eval', required=True)
    parser.add_argument('--governance', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = collect_and_write_learning_signal(
        project,
        load_json(Path(args.eval).resolve()),
        load_json(Path(args.governance).resolve()),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
