#!/usr/bin/env python3
"""Shared test utilities for the agent runtime test suite.

Import these helpers instead of redefining them in each test file.
All test files should remain runnable via `python test_*.py` directly
while also working with `pytest`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Re-export commonly used stdlib for convenience
__all__ = [
    'AGENT',
    'ROOT',
    'assert_eq',
    'assert_true',
    'load_json',
    'repo',
    'run_agent',
    'run_script',
    'write_file',
]

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'


# ── Test environment ──────────────────────────────────────────────────────


def repo(name: str) -> Path:
    """Create a temporary directory for a test project."""
    return Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()


def run_agent(project: Path, *args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    """Run the agent CLI against a test project directory."""
    env = os.environ.copy()
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('PYTHONUTF8', '1')
    return subprocess.run(
        [sys.executable, str(AGENT), *args, '--workspace', str(project)],
        cwd=project,
        env=env,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
        timeout=timeout,
    )


def run_script(script_name: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run one of the scripts/ modules as a subprocess."""
    cwd = cwd or ROOT
    return subprocess.run(
        [sys.executable, str(ROOT / 'scripts' / script_name), *args],
        cwd=cwd,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )


def load_json(path: Path) -> dict:
    """Read and parse a JSON file."""
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_file(project: Path, path: str, content: str) -> Path:
    """Write a file inside a test project directory."""
    target = project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    return target


# ── Assertions (usable without pytest) ────────────────────────────────────


def assert_true(value: object, message: str = '') -> None:
    if not value:
        raise AssertionError(message or f'Expected True, got {value!r}')


def assert_eq(left: object, right: object, message: str = '') -> None:
    if left != right:
        msg = message or f'Expected {left!r} == {right!r}'
        raise AssertionError(msg)


def assert_in(member: object, container: object, message: str = '') -> None:
    if member not in container:
        msg = message or f'Expected {member!r} to be in {container!r}'
        raise AssertionError(msg)
