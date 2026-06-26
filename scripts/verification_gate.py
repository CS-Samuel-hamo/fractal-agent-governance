#!/usr/bin/env python3
"""Verification gate — automatically validates worker output before presenting to user.

Runs lint, type check, and tests on changed files. If checks fail, feeds failure
info back to the worker for repair. Loops until all checks pass or retry limit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root

MAX_RETRIES = 3


def detect_tools(project: Path) -> dict[str, bool]:
    """Detect which verification tools are available in the project."""
    has_ruff = (
        (project / '.ruff.toml').exists() or (project / 'pyproject.toml').exists() or (project / 'ruff.toml').exists()
    )
    has_mypy = (project / 'mypy.ini').exists() or (project / 'pyproject.toml').exists()
    has_pytest = (
        (project / 'pytest.ini').exists() or (project / 'pyproject.toml').exists() or (project / 'setup.cfg').exists()
    )
    return {
        'ruff': has_ruff,
        'mypy': has_mypy,
        'pytest': has_pytest,
    }


def _run(cmd: list[str], cwd: Path, timeout: int = 60) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=timeout
        )
        return {
            'returncode': proc.returncode,
            'stdout': (proc.stdout or '')[-2000:],
            'stderr': (proc.stderr or '')[-2000:],
            'passed': proc.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {'returncode': -1, 'stdout': '', 'stderr': 'timed out', 'passed': False}
    except FileNotFoundError:
        return {'returncode': -2, 'stdout': '', 'stderr': 'tool not found', 'passed': False}


def run_lint(project: Path, files: list[str] | None = None) -> dict[str, Any]:
    """Run ruff check on changed files."""
    cmd = ['ruff', 'check']
    if files:
        for f in files:
            if (project / f).exists():
                cmd.append(f)
    if len(cmd) == 2:  # no files added
        cmd.append(str(project / 'scripts'))
    result = _run(cmd, project, timeout=30)
    return {
        'tool': 'ruff',
        'passed': result['passed'],
        'summary': result['stdout'][:500] or result['stderr'][:500],
        'raw': result,
    }


def run_type_check(project: Path, files: list[str] | None = None) -> dict[str, Any]:
    """Run mypy on changed files if available."""
    if not shutil_which('mypy'):
        return {'tool': 'mypy', 'passed': True, 'summary': 'mypy not installed, skipping'}
    cmd = ['mypy', '--no-error-summary']
    if files:
        for f in files[:10]:
            if (project / f).exists():
                cmd.append(f)
    if len(cmd) == 2:
        return {'tool': 'mypy', 'passed': True, 'summary': 'no files to check'}
    result = _run(cmd, project, timeout=60)
    return {
        'tool': 'mypy',
        'passed': result['passed'],
        'summary': result['stderr'][:500] or result['stdout'][:500],
        'raw': result,
    }


def run_tests(project: Path, files: list[str] | None = None) -> dict[str, Any]:
    """Run pytest on files related to changed files."""
    test_files = []
    if files:
        for f in files:
            p = Path(f)
            test_candidates = [
                project / 'tests' / f'test_{p.stem}.py',
                project / 'test' / f'test_{p.stem}.py',
                project / 'scripts' / f'test_{p.stem}.py',
            ]
            for tc in test_candidates:
                if tc.exists():
                    test_files.append(str(tc))
    if not test_files:
        return {'tool': 'pytest', 'passed': True, 'summary': 'no related tests found, skipping'}
    cmd = ['python', '-m', 'pytest', *test_files, '-x', '--tb=short', '-q']
    result = _run(cmd, project, timeout=120)
    return {
        'tool': 'pytest',
        'passed': result['passed'],
        'summary': result['stdout'][:500] or result['stderr'][:500],
        'raw': result,
    }


def verify_changes(project: Path, changed_files: list[str] | None = None) -> dict[str, Any]:
    """Run all verification checks on changed files.

    Returns a dict with per-tool results and overall verdict.
    """
    changed_files = changed_files or []
    tools = detect_tools(project)
    results: dict[str, Any] = {
        'checks': [],
        'overall_passed': True,
        'summary': '',
    }

    if tools['ruff']:
        check = run_lint(project, changed_files)
        results['checks'].append(check)
        if not check['passed']:
            results['overall_passed'] = False

    if tools['mypy']:
        check = run_type_check(project, changed_files)
        results['checks'].append(check)
        if not check['passed']:
            results['overall_passed'] = False

    if tools['pytest']:
        check = run_tests(project, changed_files)
        results['checks'].append(check)
        if not check['passed']:
            results['overall_passed'] = False

    fails = [c for c in results['checks'] if not c['passed']]
    if fails:
        results['summary'] = '; '.join(f'{c["tool"]}: {c["summary"][:200]}' for c in fails)
    else:
        results['summary'] = 'all checks passed'

    return results


def verify_and_repair(
    project: Path,
    worker_call: callable,
    task: str,
    changed_files: list[str] | None = None,
    *,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """Run verification gate with auto-repair loop.

    Calls the worker, verifies output, and if checks fail, feeds failure
    info back to the worker for repair. Repeats until checks pass or
    retry limit reached.

    Args:
        project: Project root
        worker_call: Function that takes a task string and returns {'stdout': ..., 'changed_files': [...]}
        task: The original task description
        changed_files: Files changed by the worker (for targeted verification)
        max_retries: Max repair attempts

    Returns:
        dict with final_verdict, verification_results, repair_attempts
    """
    attempt = 0
    last_results = None

    while attempt <= max_retries:
        if attempt == 0:
            result = worker_call(task)
        else:
            repair_prompt = (
                f'The previous attempt had verification failures:\n\n'
                f'{last_results["summary"] if last_results else "unknown"}\n\n'
                f"Please fix the issues above. Only change what's needed to pass the checks."
            )
            result = worker_call(repair_prompt)

        raw_output = str(result.get('stdout', '') or '')
        changed = result.get('changed_files', changed_files or [])
        last_results = verify_changes(project, changed)

        if last_results['overall_passed']:
            return {
                'final_verdict': 'VERIFIED',
                'verification': last_results,
                'repair_attempts': attempt,
                'worker_output': raw_output[:2000],
            }

        attempt += 1

    return {
        'final_verdict': 'UNVERIFIED',
        'verification': last_results,
        'repair_attempts': attempt,
        'worker_output': raw_output[:2000],
        'error': f'Failed verification after {attempt} attempts',
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Verification gate for worker output.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--check', action='store_true', help='Run checks on the workspace')
    parser.add_argument('--files', nargs='*', default=[], help='Specific files to check')
    args = parser.parse_args()

    project = project_root(args.workspace)
    if args.check:
        result = verify_changes(project, args.files if args.files else None)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result['overall_passed'] else 1

    # Detect tools and show status
    tools = detect_tools(project)
    print(json.dumps({'tools': tools}, ensure_ascii=False, indent=2))
    return 0


# Need shutil_which for mypy check
def shutil_which(binary: str) -> str:
    from shutil import which

    return which(binary) or ''


if __name__ == '__main__':
    raise SystemExit(main())
