#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import load_json, project_root, utc_now


def release_dir(project: Path) -> Path:
    return project / '.zoo-agent' / 'release'


def build_changelog(project: Path) -> dict[str, str]:
    project_map = load_json(project / '.zoo-agent' / 'map' / 'project_map.json')
    readiness = load_json(release_dir(project) / 'release_readiness.json')
    git_context = load_json(release_dir(project) / 'git_context.json')
    changed = git_context.get('changed_files') or []
    capabilities = [
        str(item.get('name') or item.get('capability_id'))
        for item in project_map.get('capabilities') or []
        if isinstance(item, dict) and item.get('status') in {'implemented', 'verified'}
    ][:8]
    capability_rows = (
        [f'- {item}' for item in capabilities]
        if capabilities
        else ['- No completed capability claim found in Project Map.']
    )
    limitation_rows = (
        [f'- {item}' for item in readiness.get('must_fix') or []]
        if readiness.get('must_fix')
        else ['- No hard release blocker recorded.']
    )
    lines = [
        '# Changelog Draft',
        '',
        '## Unreleased',
        '',
        '### Added',
        *capability_rows,
        '',
        '### Changed',
        f'- Release readiness stage: {readiness.get("stage") or "unknown"}',
        '',
        '### Fixed',
        '- No fixes are claimed by this local workflow.',
        '',
        '### Known limitations',
        *limitation_rows,
        '',
        '### Not included',
        '- No version number is assigned by this workflow.',
        '- No remote release was created.',
        f'- Changed files currently detected: {len(changed)}',
        '',
        f'_Generated locally at {utc_now()}._',
        '',
    ]
    path = release_dir(project) / 'changelog_draft.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines), encoding='utf-8')
    return {'status': 'ok', 'changelog': '.zoo-agent/release/changelog_draft.md'}


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate local changelog draft.')
    parser.add_argument('--workspace', default='.')
    args = parser.parse_args()
    project = project_root(args.workspace)
    payload = build_changelog(project)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
