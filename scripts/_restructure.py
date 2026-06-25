#!/usr/bin/env python3
"""Script to restructure scripts/ into sub-packages.

Run from project root: python scripts/_restructure.py

This moves files into logical sub-packages and updates imports.
Safe to re-run — it checks for existing targets before moving.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'

# Sub-package definitions: (directory_name, [file_patterns])
SUBPACKAGES = {
    'runtime': [
        'runtime_*.py',
        'pipeline_*.py',
        'execution_*.py',
    ],
    'session': [
        'session_*.py',
        'goal_*.py',
        'checkpoint_*.py',
        'loop_*.py',
        'step_*.py',
    ],
    'worker': [
        'worker_*.py',
        'codex_*.py',
        'run_*.py',
        'remote_*.py',
        'mock_*.py',
    ],
    'project': [
        'project_*.py',
        'map_*.py',
        'bootstrap*.py',
        'seed_*.py',
    ],
    'release': [
        'release_*.py',
        'changelog_*.py',
        'pr_*.py',
        'github_*.py',
        'publishing*.py',
        'public_*.py',
        'launch_*.py',
        'feedback_*.py',
    ],
    'cockpit': [
        'cockpit_*.py',
    ],
    'learning': [
        'learning_*.py',
        'cross_project_*.py',
    ],
}


def glob_patterns(base: Path, patterns: list[str]) -> list[Path]:
    files = []
    for pat in patterns:
        files.extend(sorted(base.glob(pat)))
    # Only match files that are not already in a sub-package
    return [f for f in files if f.parent == base and f.is_file()]


def update_import(filepath: Path, old_module: str, new_module: str) -> bool:
    """Update imports referencing old_module to new_module in file."""
    content = filepath.read_text(encoding='utf-8')
    # Common import patterns to update
    # from old_module import ...  →  from new_module import ...
    # import old_module  →  import new_module
    updated = content.replace(f'from {old_module} import ', f'from {new_module} import ')
    updated = updated.replace(f'import {old_module}', f'import {new_module}')
    if updated != content:
        filepath.write_text(updated, encoding='utf-8')
        return True
    return False


def main() -> int:
    print(f'Restructuring {SCRIPTS}...')
    all_moves: list[tuple[Path, Path]] = []
    all_imports: list[tuple[str, str]] = []

    for pkg_name, patterns in SUBPACKAGES.items():
        target_dir = SCRIPTS / pkg_name
        target_dir.mkdir(parents=True, exist_ok=True)
        init = target_dir / '__init__.py'
        if not init.exists():
            init.write_text(f'"""zoo-agent-runtime.{pkg_name} sub-package."""\n')
            print(f'  Created {target_dir.name}/')

        files = glob_patterns(SCRIPTS, patterns)
        for src in files:
            dst = target_dir / src.name
            if dst.exists():
                print(f'  SKIP {src.name} (already at {pkg_name}/)')
                continue
            # Move file
            shutil.move(str(src), str(dst))
            all_moves.append((src, dst))
            all_imports.append((src.stem, f'scripts.{pkg_name}.{src.stem}'))
            print(f'  Moved {src.name} → {pkg_name}/')

    # Update imports in all .py files that reference moved modules
    if all_imports:
        print('\nUpdating imports...')
        py_files = list(SCRIPTS.rglob('*.py'))
        update_count = 0
        for old_name, new_name in all_imports:
            for pyfile in py_files:
                # Don't update the moved file itself (it imports from scripts/ root)
                if update_import(pyfile, old_name, new_name):
                    update_count += 1
        print(f'  Updated {update_count} import references')

    print(f'\nDone. {len(all_moves)} files moved, {len(all_imports)} import paths updated.')
    print('Run ruff format scripts/ && ruff check scripts/ to verify.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
