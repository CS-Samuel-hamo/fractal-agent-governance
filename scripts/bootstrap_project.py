#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description='Compatibility wrapper for agent bootstrap.')
    parser.add_argument('--workspace', '--project', dest='workspace', default='.')
    parser.add_argument('--new', action='store_true')
    parser.add_argument('--force-new-project', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--refresh-instructions', action='store_true')
    args = parser.parse_args()

    command = [
        sys.executable,
        str(ROOT / 'scripts' / 'agent.py'),
        'bootstrap',
        '--workspace',
        str(Path(args.workspace).resolve()),
    ]
    if args.new:
        command.append('--new')
    if args.force_new_project:
        command.append('--force-new-project')
    if args.dry_run:
        command.append('--dry-run')
    if args.refresh_instructions:
        command.append('--refresh-instructions')
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == '__main__':
    raise SystemExit(main())
