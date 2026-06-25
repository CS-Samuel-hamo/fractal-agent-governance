#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root


def main() -> int:
    parser = argparse.ArgumentParser(description='Render Codex backend profile and health into a concise report.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--output', default='')
    args = parser.parse_args()
    project = project_root(args.workspace)
    backend = project / '.zoo-agent' / 'backend'
    profile = load_json(backend / 'codex-backend-profile.json')
    quick = load_json(backend / 'codex-health-quick.json')
    full = load_json(backend / 'codex-health-full.json')
    lines = [
        '# Codex Backend Report',
        '',
        f'- backend: {profile.get("backend", "codex_cli")}',
        f'- version: {profile.get("version", "")}',
        f'- platform: {profile.get("platform", "")}',
        f'- health_status: {profile.get("health_status", "unknown")}',
        f'- allow_fast_actual: {profile.get("recommended_usage", {}).get("allow_fast_actual")}',
        f'- allow_parallel_actual: {profile.get("recommended_usage", {}).get("allow_parallel_actual")}',
        f'- quick_health: {quick.get("verdict", "missing")}',
        f'- full_health: {full.get("verdict", "missing")}',
        '',
        '## Known Risks',
        '',
    ]
    lines.extend([f'- {item}' for item in profile.get('known_risks') or []] or ['- none'])
    lines.extend(['', '## Fallbacks', ''])
    lines.extend([f'- {item}' for item in profile.get('fallbacks') or []] or ['- none'])
    output = Path(args.output).resolve() if args.output else backend / 'codex-backend-report.md'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps({'status': 'ok', 'report': str(output)}, ensure_ascii=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
