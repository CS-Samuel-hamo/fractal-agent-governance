#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json  # noqa: E402


PUBLIC_DOCS = [
    'README.md',
    'INSTALL.md',
    'QUICKSTART.md',
    'CLI_REFERENCE.md',
    'PRODUCT_POSITIONING.md',
    'ARCHITECTURE.md',
    'ROADMAP.md',
    'PRIVACY.md',
    'SAFETY_MODEL.md',
    'DEMO.md',
    'EXAMPLES.md',
    'RELEASE_NOTES.md',
    'ALPHA_RELEASE_CHECKLIST.md',
    'PUBLIC_ALPHA_REPORT.md',
]

CORE_SCRIPTS = [
    'scripts/agent.py',
    'scripts/public_alpha_packager.py',
    'scripts/public_alpha_audit.py',
    'scripts/public_positioning_linter.py',
    'scripts/public_docs_leakage_scanner.py',
    'scripts/demo_fixture_packager.py',
    'scripts/public_alpha_report_generator.py',
]

CORE_TESTS = [
    'scripts/test_public_alpha_packaging.py',
    'scripts/test_public_positioning.py',
    'scripts/test_public_docs_safety.py',
]

DEMO_ROOT = 'examples/demo_project'

EXCLUDE_PREFIXES = (
    '.zoo-agent/',
    '.git/',
    '.tmp/',
    'logs/',
    'worktrees/',
    'node_modules/',
    '.venv/',
    'venv/',
    '__pycache__/',
    '.pytest_cache/',
)

EXCLUDE_SUFFIXES = (
    '.log',
    '.tmp',
    '.pyc',
    '.pyo',
    '.coverage',
)

EXCLUDE_NAMES = {
    '.env',
    '.env.local',
    '.env.production',
    '.DS_Store',
}


def public_alpha_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'public_alpha'


def is_excluded(path: str) -> bool:
    normalized = path.replace('\\', '/')
    if normalized in EXCLUDE_NAMES or Path(normalized).name in EXCLUDE_NAMES:
        return True
    return normalized.startswith(EXCLUDE_PREFIXES) or normalized.endswith(EXCLUDE_SUFFIXES)


def iter_repo_files(project: Path) -> list[str]:
    files: list[str] = []
    for path in project.rglob('*'):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(project).as_posix()
        except ValueError:
            continue
        if is_excluded(rel):
            continue
        files.append(rel)
    return sorted(files)


def build_manifest(project: Path) -> dict[str, Any]:
    included_files = iter_repo_files(project)
    excluded_files = [
        '.zoo-agent/',
        '.env',
        '.tmp/',
        'logs/',
        'worktrees/',
        'node_modules/',
        '.venv/',
        '__pycache__/',
        '.pytest_cache/',
    ]
    docs = [path for path in PUBLIC_DOCS if (project / path).exists()]
    examples = [path for path in included_files if path.startswith(f'{DEMO_ROOT}/')]
    scripts = [path for path in CORE_SCRIPTS if (project / path).exists()]
    tests = [path for path in CORE_TESTS if (project / path).exists()]
    missing_required = [
        *[path for path in PUBLIC_DOCS if not (project / path).exists()],
        *[path for path in CORE_SCRIPTS if not (project / path).exists()],
        *[path for path in CORE_TESTS if not (project / path).exists()],
    ]
    ignored_runtime_artifacts = ['.zoo-agent/']
    safe_to_publish = not missing_required and not any(path.startswith('.zoo-agent/') for path in included_files)
    return {
        'generated_at': utc_now(),
        'included_files': included_files,
        'excluded_files': excluded_files,
        'docs': docs,
        'examples': examples,
        'scripts': scripts,
        'tests': tests,
        'ignored_runtime_artifacts': ignored_runtime_artifacts,
        'missing_required': missing_required,
        'safe_to_publish': safe_to_publish,
    }


def write_manifest(project: Path) -> dict[str, Any]:
    manifest = build_manifest(project)
    write_json(public_alpha_dir(project) / 'public_alpha_package_manifest.json', manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args(argv)
    project = project_root(args.workspace)
    manifest = write_manifest(project)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest.get('safe_to_publish') else 1


if __name__ == '__main__':
    raise SystemExit(main())
