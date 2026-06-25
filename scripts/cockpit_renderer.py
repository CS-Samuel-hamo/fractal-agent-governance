#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from cockpit_data_builder import build_cockpit_data
from cockpit_html_template import render_cockpit_html
from cockpit_schema import cockpit_dir
from runtime_common import load_json, project_root, write_json


def render_cockpit(project: Path) -> dict:
    out_dir = cockpit_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / 'cockpit_data.json'
    html_path = out_dir / 'index.html'
    data = build_cockpit_data(project)
    write_json(data_path, data)
    html_path.write_text(render_cockpit_html(data), encoding='utf-8')
    return {
        'status': 'ok',
        'cockpit': str(html_path),
        'cockpit_data': str(data_path),
        'project_state': data.get('project', {}).get('state', 'unknown'),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Render a local Project Cockpit.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--data', default='')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    out_dir = cockpit_dir(project)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = Path(args.data).resolve() if args.data else out_dir / 'cockpit_data.json'
    html_path = Path(args.output).resolve() if args.output else out_dir / 'index.html'
    if args.data:
        data = load_json(data_path)
    else:
        data = build_cockpit_data(project)
        write_json(data_path, data)
    html_path.write_text(render_cockpit_html(data), encoding='utf-8')
    print(
        json.dumps(
            {'status': 'ok', 'cockpit': str(html_path), 'cockpit_data': str(data_path)}, ensure_ascii=False, indent=2
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
