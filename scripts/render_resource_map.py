#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import generate_resource_map, project_root, render_resource_map_md, write_resource_map  # noqa: E402
from runtime_common import load_json  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Render the semantic resource map markdown.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--input-text', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    resource_map = load_json(project / '.zoo-agent' / 'project-resource-map.json') or generate_resource_map(project, args.input_text)
    paths = write_resource_map(project, resource_map)
    print(json.dumps({'status': 'ok', 'paths': paths, 'markdown_preview': render_resource_map_md(resource_map)[:200]}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
