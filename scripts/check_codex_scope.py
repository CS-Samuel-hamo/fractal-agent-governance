#!/usr/bin/env python3
"""Check that Codex modified only allowed files for a task.

Usage:
  python check_codex_scope.py <task_id> [--tasks TASKS.yaml] [--json-output scope.json]
"""
from __future__ import annotations
import argparse, fnmatch, json, subprocess, sys, re
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def _simple_yaml_tasks(text: str):
    """Very small fallback parser for the generated TASKS.yaml shape."""
    tasks = []
    current = None
    current_key = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith('#'):
            continue
        if re.match(r"\s*-\s+id:\s*", line):
            if current:
                tasks.append(current)
            current = {}
            current_key = None
            val = line.split('id:',1)[1].strip().strip('"\'')
            current['id'] = val
            continue
        if current is None:
            continue
        m = re.match(r"\s{4}([A-Za-z0-9_]+):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            current_key = key
            if val == '':
                current[key] = []
            else:
                current[key] = val.strip('"\'')
            continue
        m = re.match(r"\s{6}-\s*(.*)$", line)
        if m and current_key:
            current.setdefault(current_key, [])
            if not isinstance(current[current_key], list):
                current[current_key] = [current[current_key]]
            current[current_key].append(m.group(1).strip().strip('"\''))
    if current:
        tasks.append(current)
    return {'tasks': tasks}


def load_tasks(path: Path):
    text = path.read_text(encoding='utf-8')
    if yaml:
        return yaml.safe_load(text)
    return _simple_yaml_tasks(text)


def git_changed_files():
    out = subprocess.check_output(['git','diff','--name-only'], text=True, encoding='utf-8', errors='replace')
    staged = subprocess.check_output(['git','diff','--cached','--name-only'], text=True, encoding='utf-8', errors='replace')
    status = subprocess.check_output(['git','status','--porcelain','--untracked-files=all'], text=True, encoding='utf-8', errors='replace')
    files = set([x.strip().replace('\\','/') for x in (out + '\n' + staged).splitlines() if x.strip()])
    for line in status.splitlines():
        if not line.strip():
            continue
        # Porcelain format: XY PATH or XY OLD -> NEW
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if ' -> ' in path:
            path = path.split(' -> ', 1)[1]
        if path:
            files.add(path.replace('\\','/'))
    return sorted(files)


def matches_any(path: str, patterns):
    p = path.replace('\\','/')
    for pat in patterns or []:
        pat = str(pat).replace('\\','/')
        if fnmatch.fnmatch(p, pat) or fnmatch.fnmatch('/'+p, pat):
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('task_id')
    ap.add_argument('--tasks', default='TASKS.yaml')
    ap.add_argument('--json-output')
    ap.add_argument('--ignore-file', action='append', default=[], help='Changed-file glob to ignore')
    args = ap.parse_args()

    tasks_doc = load_tasks(Path(args.tasks))
    tasks = tasks_doc.get('tasks', []) if isinstance(tasks_doc, dict) else []
    task = next((t for t in tasks if str(t.get('id')) == args.task_id), None)
    if not task:
        print(f'Task not found: {args.task_id}', file=sys.stderr)
        return 2

    allowed = task.get('allowed_files') or []
    denied = task.get('denied_files') or []
    default_ignore = [
        '.zoo-agent/runs/**',
        '.zoo-agent/evals/**',
        '.zoo-agent/metrics/**',
        '.zoo-agent/tmp/**',
        '.zoo-agent/**/codex-final-message.md',
        '.zoo-agent/**/codex-results/**',
        '.zoo-agent/**/codex-tasks/**',
        '__pycache__/**',
        '**/__pycache__/**',
        '.pytest_cache/**',
        '**/.pytest_cache/**',
        '.codex-tmp/**',
        '**/.codex-tmp/**',
        '*.pyc',
        '**/*.pyc',
    ]
    ignore = default_ignore + (args.ignore_file or [])
    changed = [f for f in git_changed_files() if not matches_any(f, ignore)]
    violations = []
    denied_hits = []
    outside_hits = []

    for f in changed:
        denied_hit = matches_any(f, denied)
        allowed_hit = matches_any(f, allowed) if allowed else True
        if denied_hit:
            denied_hits.append(f)
            violations.append({'file': f, 'reason': 'denied_files'})
        elif not allowed_hit:
            outside_hits.append(f)
            violations.append({'file': f, 'reason': 'outside_allowed_files'})

    report = {
        'task_id': args.task_id,
        'changed_files': changed,
        'allowed_files': allowed,
        'denied_files': denied,
        'violations': violations,
        'pass': not violations,
    }
    if args.json_output:
        Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    if violations:
        print('Scope check FAILED.')
        for v in violations:
            print(f" - {v['file']}: {v['reason']}")
        return 1
    print('Scope check passed.')
    if changed:
        print('Changed files:')
        for f in changed:
            print(f' - {f}')
    else:
        print('No changed files detected.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
