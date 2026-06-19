#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from big_task_common import load_leaf_contracts, project_root, render_leaf_md  # noqa: E402


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Render markdown for leaf task contracts.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    project = project_root(args.workspace)
    leaves = load_leaf_contracts(project, args.run_id)
    written = []
    for leaf in leaves:
        path = Path(str(leaf.get('_path'))).with_suffix('.md')
        path.write_text(render_leaf_md(leaf), encoding='utf-8')
        written.append(str(path))
    print(json.dumps({'status': 'ok', 'written': written}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
