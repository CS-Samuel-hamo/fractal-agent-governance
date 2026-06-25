#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from runtime_common import load_json, project_root, utc_now, write_json


def mark_attention(
    project: Path, *, reason: str, suggested_next_step: str, action: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload = {
        'schema_version': '1.0',
        'generated_by': 'attention_router.py',
        'generated_at': utc_now(),
        'status': 'needs_attention',
        'reason': reason,
        'suggested_next_step': suggested_next_step,
        'action': action or {},
    }
    write_json(project / '.zoo-agent' / 'autopilot' / 'attention_required.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Record an autopilot attention requirement.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--reason', required=True)
    parser.add_argument('--suggested-next-step', default='Review and rerun when ready.')
    parser.add_argument('--action', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = mark_attention(
        project,
        reason=args.reason,
        suggested_next_step=args.suggested_next_step,
        action=load_json(Path(args.action).resolve()) if args.action else {},
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
