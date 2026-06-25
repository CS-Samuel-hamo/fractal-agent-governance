#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import (
    common_big_task_parser,
    generate_resource_map,
    project_root,
    write_resource_map,
)


def main() -> int:
    parser = common_big_task_parser('Generate a lightweight semantic resource map.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    text = args.input_text or ' '.join(args.input).strip()
    resource_map = generate_resource_map(project, text)
    paths = write_resource_map(project, resource_map)
    report = {'status': 'ok', 'resource_map': resource_map, 'paths': paths}
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if resource_map.get('confidence') != 'low' else 10


if __name__ == '__main__':
    raise SystemExit(main())
