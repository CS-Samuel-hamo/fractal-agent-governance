#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, subprocess, datetime, shutil, sys
from pathlib import Path


def run(cmd, cwd):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0 and proc.stderr:
            return proc.stdout + proc.stderr
        return proc.stdout
    except Exception as e:
        return f'ERROR: {e}'


def windows_command_variants(cmd):
    if not cmd or sys.platform != 'win32' or Path(cmd[0]).suffix:
        return [cmd]
    variants = [cmd]
    for suffix in ['.cmd', '.exe', '.bat']:
        variants.append([f'{cmd[0]}{suffix}', *cmd[1:]])
    return variants


def command_available(name):
    return any(shutil.which(variant[0]) is not None for variant in windows_command_variants([name]))


def probe_once(cmd, cwd):
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
        )
        return {
            'command': cmd,
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout.strip(),
        }
    except FileNotFoundError:
        return {
            'command': cmd,
            'cwd': str(cwd),
            'returncode': 127,
            'stdout': f'{cmd[0]} not found',
        }
    except OSError as exc:
        return {
            'command': cmd,
            'cwd': str(cwd),
            'returncode': getattr(exc, 'winerror', 1) or 1,
            'stdout': f'{type(exc).__name__}: {exc}',
        }
    except subprocess.TimeoutExpired:
        return {
            'command': cmd,
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': 'probe timed out',
        }


def should_try_probe_fallback(result):
    stdout = str(result.get('stdout', ''))
    return result.get('returncode') in {5, 127} or 'PermissionError' in stdout or 'not found' in stdout


def probe(cmd, cwd):
    attempts = []
    for variant in windows_command_variants(cmd):
        result = probe_once(variant, cwd)
        attempts.append(result)
        if result['returncode'] == 0 or not should_try_probe_fallback(result):
            if len(attempts) > 1:
                result['fallback_attempts'] = attempts[:-1]
            return result
    result = attempts[-1]
    if len(attempts) > 1:
        result['fallback_attempts'] = attempts[:-1]
    return result


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def package_declares_or_installs(frontend: Path, package_name: str) -> bool:
    try:
        package_json = json.loads((frontend / 'package.json').read_text(encoding='utf-8'))
    except Exception:
        package_json = {}
    if isinstance(package_json, dict):
        for key in ['dependencies', 'devDependencies', 'optionalDependencies', 'peerDependencies']:
            deps = package_json.get(key)
            if isinstance(deps, dict) and package_name in deps:
                return True
    return (frontend / 'node_modules' / package_name / 'package.json').exists()


def environment_fingerprint(workspace: Path) -> dict:
    frontend = workspace / 'frontend'
    probe_cwd = frontend if frontend.exists() else workspace
    node_available = command_available('node')
    npm_available = command_available('npm')
    codex_available = command_available('codex')
    payload = {
        'python': {
            'executable': sys.executable,
            'version': sys.version.split()[0],
        },
        'codex_cli': {
            'available': codex_available,
            'version_probe': probe(['codex', '--version'], workspace) if codex_available else None,
        },
        'node': {
            'available': node_available,
            'version_probe': probe(['node', '-v'], probe_cwd) if node_available else None,
            'abi_probe': probe(['node', '-p', 'process.versions.modules'], probe_cwd) if node_available else None,
        },
        'npm': {
            'available': npm_available,
            'version_probe': probe(['npm', '-v'], probe_cwd) if npm_available else None,
        },
        'native_dependencies': {},
    }
    if frontend.exists() and (frontend / 'package.json').exists() and node_available and package_declares_or_installs(frontend, 'better-sqlite3'):
        payload['native_dependencies']['better-sqlite3'] = {
            'package_version_probe': probe(
                ['node', '-p', "require('./node_modules/better-sqlite3/package.json').version"],
                frontend,
            ),
            'load_probe': probe(
                ['node', '-e', "try { const Database = require('better-sqlite3'); const db = new Database(':memory:'); db.close(); console.log('load_ok') } catch (error) { console.error(error && error.message ? error.message : error); process.exit(1) }"],
                frontend,
            ),
        }
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--task-dir', required=True)
    ap.add_argument('--workspace', required=True)
    args = ap.parse_args()

    task_dir = Path(args.task_dir).resolve()
    workspace = Path(args.workspace).resolve()
    out_dir = workspace / '.zoo-agent' / 'runs' / args.run_id / 'codex-results' / args.task_id
    out_dir.mkdir(parents=True, exist_ok=True)

    status = run(['git','status','--short'], workspace)
    diff_names = run(['git','diff','--name-only'], workspace)
    diff_stat = run(['git','diff','--stat'], workspace)
    final_msg = (task_dir / 'codex-final-message.md').read_text(encoding='utf-8') if (task_dir/'codex-final-message.md').exists() else ''
    progress = (task_dir / 'PROGRESS.md').read_text(encoding='utf-8') if (task_dir/'PROGRESS.md').exists() else ''
    blockers = (task_dir / 'BLOCKERS.md').read_text(encoding='utf-8') if (task_dir/'BLOCKERS.md').exists() else ''
    task_evidence_dir = workspace / '.zoo-agent' / 'runs' / args.run_id / 'tasks' / args.task_id
    task_baseline_path = task_evidence_dir / 'task-baseline.json'
    task_delta_path = task_evidence_dir / 'task-delta.json'
    delivery_outcome_path = workspace / '.zoo-agent' / 'runs' / args.run_id / 'delivery-outcome.json'

    # Run scope guard from task dir with workspace as cwd so no helper files pollute git status.
    scope = {'status': 'not_run'}
    guard = task_dir / 'check_codex_scope.py'
    tasks = task_dir / 'TASKS.yaml'
    if guard.exists() and tasks.exists():
        ignore_result = (Path('.zoo-agent') / 'runs' / args.run_id / 'codex-results' / args.task_id / '**').as_posix()
        ignore_runtime = (Path('.zoo-agent') / '**').as_posix()
        proc = subprocess.run(
            [
                'python',
                str(guard),
                args.task_id,
                '--tasks',
                str(tasks),
                '--json-output',
                str(out_dir/'scope-guard.json'),
                '--ignore-file',
                ignore_result,
                '--ignore-file',
                ignore_runtime,
            ],
            cwd=workspace,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        output = proc.stdout if proc.returncode == 0 else proc.stdout + proc.stderr
        scope = {'status': 'pass' if proc.returncode == 0 else 'fail', 'returncode': proc.returncode, 'output': output}

    result = {
        'run_id': args.run_id,
        'task_id': args.task_id,
        'workspace': str(workspace),
        'task_dir': str(task_dir),
        'environment_fingerprint': environment_fingerprint(workspace),
        'git_status_short': status,
        'git_diff_name_only': diff_names.splitlines(),
        'git_diff_stat': diff_stat,
        'scope_guard': scope,
        'task_baseline_path': str(task_baseline_path) if task_baseline_path.exists() else '',
        'task_baseline': load_json(task_baseline_path),
        'task_delta_path': str(task_delta_path) if task_delta_path.exists() else '',
        'task_delta': load_json(task_delta_path),
        'delivery_outcome_path': str(delivery_outcome_path) if delivery_outcome_path.exists() else '',
        'delivery_outcome': load_json(delivery_outcome_path),
        'final_message': final_msg,
        'progress_md': progress,
        'blockers_md': blockers,
        'collected_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    (out_dir / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    md = f"""# Codex Result: {args.task_id}

## Scope Guard

{scope.get('status')}

```
{scope.get('output','')}
```

## Environment Fingerprint

```json
{json.dumps(result['environment_fingerprint'], ensure_ascii=False, indent=2)}
```

## Git Status

```
{status}
```

## Changed Files

```
{diff_names}
```

## Diff Stat

```
{diff_stat}
```

## Codex Final Message

{final_msg}

## Progress

{progress}

## Blockers

{blockers}
"""
    (out_dir / 'result.md').write_text(md, encoding='utf-8')
    print(out_dir)

if __name__ == '__main__':
    main()
