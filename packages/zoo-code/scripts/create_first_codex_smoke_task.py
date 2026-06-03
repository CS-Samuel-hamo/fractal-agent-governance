#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a harmless first Codex smoke task pack.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--run-id", default="bootstrap-smoke")
    parser.add_argument("--task-id", default="task-001")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    example = project / "src" / "example.py"
    tests = project / "tests"
    if not example.exists() or not tests.exists():
        print("unknown: no harmless src/example.py plus tests/ target found")
        return 0
    cmd = [
        "python",
        str(ROOT / "scripts" / "generate-codex-task-pack.py"),
        "--run-id",
        args.run_id,
        "--task-id",
        args.task_id,
        "--objective",
        "Make a harmless, reviewable test/demo change and keep tests passing.",
        "--allowed-file",
        "src/**",
        "--allowed-file",
        "tests/**",
        "--denied-file",
        ".env",
        "--denied-file",
        "pyproject.toml",
        "--acceptance",
        "scope guard passes",
        "--acceptance",
        "relevant tests pass or blockers are documented",
        "--test-command",
        "python -m pytest",
    ]
    proc = subprocess.run(cmd, cwd=project, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(proc.stdout.strip())
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
