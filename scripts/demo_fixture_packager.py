#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_alpha_packager import public_alpha_dir
from public_docs_leakage_scanner import scan_texts
from runtime_common import project_root, utc_now, write_json

DEMO_FILES = {
    'README.md': """# Demo Project

This is a synthetic demo project for the Agent Runtime public alpha.

It is intentionally small and safe:

- no secrets
- no `.env`
- no network setup
- no deployment scripts
- no real API keys

## Try The Operator Flow

```bash
agent cockpit
agent start "prepare this demo project for public release"
agent status
agent release
agent pr
```
""",
    'DEMO_STEPS.md': """# Demo Steps

Run these commands from this demo project:

```bash
agent cockpit
agent start "prepare this demo project for public release"
agent status
agent release
agent pr
```

No network, push, merge, remote PR, deployment, token, or secret is required.
""",
    'docs/overview.md': """# Demo Project Overview

This demo project shows the AI Project Operator public alpha path.
""",
    'src/sample_app.py': """def greeting(name: str) -> str:
    clean_name = name.strip() or 'there'
    return f'Hello, {clean_name}!'
""",
    'tests/test_sample_app.py': """from src.sample_app import greeting


def test_greeting_trims_name() -> None:
    assert greeting(' Demo ') == 'Hello, Demo!'
""",
    'demo_artifacts/project_map_snapshot.json': json.dumps(
        {
            'project_name': 'Demo Project',
            'project_type': 'python_cli_sample',
            'main_goal': 'prepare this demo project for public release',
            'modules': [
                {
                    'name': 'sample_app',
                    'status': 'mapped',
                    'confidence': 0.9,
                    'key_files': ['src/sample_app.py'],
                    'evidence_count': 1,
                },
                {
                    'name': 'tests',
                    'status': 'mapped',
                    'confidence': 0.9,
                    'key_files': ['tests/test_sample_app.py'],
                    'evidence_count': 1,
                },
            ],
            'next_actions': [
                {
                    'title': 'Refresh the local Cockpit',
                    'why_now': 'Show project state before release artifacts.',
                    'risk_level': 'low',
                    'target_files': [],
                },
                {
                    'title': 'Generate release and PR drafts',
                    'why_now': 'Show the public alpha release workflow pack.',
                    'risk_level': 'low',
                    'target_files': [],
                },
            ],
        },
        indent=2,
    )
    + '\n',
    'demo_artifacts/cockpit_summary.json': json.dumps(
        {
            'project': {'name': 'Demo Project', 'state': 'ready_for_demo'},
            'session': {'status': 'not_started', 'goal': 'prepare this demo project for public release'},
            'safety': {'network_required': False, 'push_or_merge': False, 'secrets_required': False},
        },
        indent=2,
    )
    + '\n',
}


def demo_root(project: Path) -> Path:
    return project / 'examples' / 'demo_project'


def ensure_demo_fixture(project: Path) -> dict[str, Any]:
    root = demo_root(project)
    generated: list[str] = []
    preserved: list[str] = []
    for rel, content in DEMO_FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding='utf-8-sig', errors='replace') == content:
            preserved.append(path.relative_to(project).as_posix())
            continue
        if not path.exists():
            path.write_text(content, encoding='utf-8')
            generated.append(path.relative_to(project).as_posix())
        else:
            preserved.append(path.relative_to(project).as_posix())

    texts = {}
    for path in root.rglob('*'):
        if path.is_file():
            texts[path.relative_to(project).as_posix()] = path.read_text(encoding='utf-8-sig', errors='replace')
    safety = scan_texts(texts)
    manifest = {
        'generated_at': utc_now(),
        'fixture_path': 'examples/demo_project',
        'scenarios': [
            'project_map_demo',
            'session_start_demo',
            'cockpit_demo',
            'release_pack_demo',
            'pr_draft_demo',
        ],
        'generated_artifacts': sorted(texts),
        'new_files_written': generated,
        'preserved_files': preserved,
        'safe_to_use': bool(safety.get('safe')),
    }
    write_json(public_alpha_dir(project) / 'demo_fixture_manifest.json', manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    manifest = ensure_demo_fixture(project)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get('safe_to_use') else 1


if __name__ == '__main__':
    raise SystemExit(main())
