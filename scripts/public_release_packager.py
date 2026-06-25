#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from public_alpha_packager import build_manifest
from runtime_common import project_root, utc_now, write_json

VERSION = '1.0.0-alpha.1'


def public_release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'public_release'


def build_release_manifest(project: Path) -> dict[str, Any]:
    alpha_manifest = build_manifest(project)
    included = list(alpha_manifest.get('included_files') or [])
    for rel in ['VERSION', 'GITHUB_RELEASE_DRAFT.md', 'PUBLIC_RELEASE_CHECKLIST.md']:
        if (project / rel).exists() and rel not in included:
            included.append(rel)
    included = sorted(included)
    excluded_runtime = ['.zoo-agent/', '.env', '.env.*', '*.log', '__pycache__/', '.venv/', 'node_modules/', 'dist/']
    docs = sorted([path for path in included if path.endswith('.md') and not path.startswith('examples/')])
    examples = sorted([path for path in included if path.startswith('examples/demo_project/')])
    tests = sorted(
        [
            path
            for path in included
            if path.startswith('scripts/test_') or '/tests/' in path or path.startswith('examples/demo_project/tests/')
        ]
    )
    unsafe = [
        path
        for path in included
        if path.startswith('.zoo-agent/') or path.endswith('.log') or Path(path).name.startswith('.env')
    ]
    manifest = {
        'generated_at': utc_now(),
        'version': VERSION,
        'included_files': included,
        'excluded_files': alpha_manifest.get('excluded_files') or [],
        'excluded_runtime_artifacts': excluded_runtime,
        'docs_included': docs,
        'examples_included': examples,
        'tests_included': tests,
        'safe_to_package': not unsafe and bool((project / 'VERSION').exists()),
        'unsafe_included_files': unsafe,
    }
    return manifest


def write_release_manifest(project: Path) -> dict[str, Any]:
    manifest = build_release_manifest(project)
    write_json(public_release_dir(project) / 'public_release_package_manifest.json', manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    manifest = write_release_manifest(project)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get('safe_to_package') else 1


if __name__ == '__main__':
    raise SystemExit(main())
