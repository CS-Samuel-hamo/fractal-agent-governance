#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [sys.executable, str(ROOT / 'scripts' / 'run_codex_parallel_workers.py'), *sys.argv[1:]]
    proc = subprocess.run(command, cwd=ROOT)
    return proc.returncode


if __name__ == '__main__':
    raise SystemExit(main())
