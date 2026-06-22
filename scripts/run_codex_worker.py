#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, subprocess, sys, datetime, time
from pathlib import Path


TASK_PACK_FILES = [
    'AGENTS.md',
    'TASKS.yaml',
    'ACCEPTANCE.md',
    'CODEX_TASK_PROMPT.md',
    'PROGRESS.md',
    'BLOCKERS.md',
    'check_codex_scope.py',
]


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def safe_name(value: str) -> str:
    return ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in value)


def runtime_name(task_dir: Path) -> str:
    run_id = task_dir.parent.parent.name if task_dir.parent.name in {'codex-tasks', 'codex_tasks'} else task_dir.parent.name
    return safe_name(f'{run_id}__{task_dir.name}')


def prepare_task_runtime_dir(task_dir: Path, workspace: Path) -> tuple[Path, bool]:
    if is_relative_to(task_dir, workspace):
        return task_dir, False

    runtime_dir = workspace / '.zoo-agent' / 'tmp' / 'codex-task-packs' / runtime_name(task_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    for name in TASK_PACK_FILES:
        src = task_dir / name
        if src.exists():
            shutil.copy2(src, runtime_dir / name)
    return runtime_dir.resolve(), True


def sync_runtime_task_files(runtime_dir: Path, task_dir: Path) -> None:
    if runtime_dir == task_dir:
        return
    for name in ['PROGRESS.md', 'BLOCKERS.md']:
        src = runtime_dir / name
        if src.exists():
            shutil.copy2(src, task_dir / name)


def kill_process_tree(pid: int) -> None:
    if os.name == 'nt':
        subprocess.run(
            ['taskkill', '/PID', str(pid), '/T', '/F'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )
    else:
        try:
            os.kill(pid, 9)
        except OSError:
            pass


def write_env_wrappers(codex_tmp: Path, pycache_tmp: Path) -> tuple[Path, Path]:
    cmd = codex_tmp / 'codex-env.cmd'
    sh = codex_tmp / 'codex-env.sh'
    cmd.write_text(
        '@echo off\r\n'
        f'set "TEMP={codex_tmp}"\r\n'
        f'set "TMP={codex_tmp}"\r\n'
        f'set "TMPDIR={codex_tmp}"\r\n'
        f'set "PYTHONPYCACHEPREFIX={pycache_tmp}"\r\n'
        '%*\r\n',
        encoding='utf-8',
    )
    sh.write_text(
        '#!/usr/bin/env sh\n'
        f'export TEMP="{codex_tmp.as_posix()}"\n'
        f'export TMP="{codex_tmp.as_posix()}"\n'
        f'export TMPDIR="{codex_tmp.as_posix()}"\n'
        f'export PYTHONPYCACHEPREFIX="{pycache_tmp.as_posix()}"\n'
        'exec "$@"\n',
        encoding='utf-8',
    )
    try:
        sh.chmod(0o755)
    except OSError:
        pass
    return cmd, sh


def run_adapter(command: list[str], cwd: Path, *, timeout: int | None = None) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': proc.returncode,
            'stdout': proc.stdout,
            'stderr': proc.stderr,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            'command': [str(item) for item in command],
            'cwd': str(cwd),
            'returncode': 124,
            'stdout': exc.stdout or '',
            'stderr': exc.stderr or '',
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'timed_out': True,
        }


def is_git_worktree(path: Path) -> bool:
    try:
        proc = subprocess.run(
            ['git', '-C', str(path), 'rev-parse', '--is-inside-work-tree'],
            text=True,
            encoding='utf-8',
            errors='replace',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
        return proc.returncode == 0 and proc.stdout.strip().lower() == 'true'
    except Exception:
        return False


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copy2(src, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task-dir', required=True, help='Directory containing CODEX_TASK_PROMPT.md')
    ap.add_argument('--workspace', required=True, help='Git worktree or repo root for codex exec --cd')
    ap.add_argument('--sandbox', default='workspace-write', choices=['read-only','workspace-write','danger-full-access'])
    ap.add_argument('--profile', default='')
    ap.add_argument('--ephemeral', action='store_true')
    ap.add_argument('--json-events', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--codex-home', default='', help='Optional CODEX_HOME directory for Codex CLI state')
    ap.add_argument('--timeout-seconds', type=int, default=0, help='Optional timeout for codex exec; 0 means no timeout')
    ap.add_argument('--no-output-timeout-seconds', type=int, default=600)
    ap.add_argument('--skip-git-repo-check', action='store_true')
    ap.add_argument('--leaf-resolution', default='', help='Optional leaf resolution JSON that must allow execution.')
    ap.add_argument('--require-leaf-resolution', action='store_true', help='Block actual Codex execution unless the leaf resolved to execute.')
    args = ap.parse_args()

    task_dir = Path(args.task_dir).resolve()
    workspace = Path(args.workspace).resolve()
    prompt_path = task_dir / 'CODEX_TASK_PROMPT.md'
    if not prompt_path.exists():
        print(f'Missing prompt: {prompt_path}', file=sys.stderr)
        return 2
    if not workspace.exists():
        print(f'Missing workspace: {workspace}', file=sys.stderr)
        return 2
    if args.require_leaf_resolution:
        resolution_path = Path(args.leaf_resolution).resolve() if args.leaf_resolution else task_dir / 'leaf-resolution.json'
        resolution = load_json(resolution_path)
        if resolution.get('final_resolution') != 'execute' or resolution.get('status') == 'stuck':
            report = {
                'status': 'blocked_missing_leaf_execute_resolution',
                'leaf_resolution_path': str(resolution_path),
                'message': 'Codex leaf execution requires final_resolution=execute from leaf convergence.',
            }
            (task_dir / 'codex-run.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=True, indent=2))
            return 20
    task_runtime_dir, task_dir_mirrored = prepare_task_runtime_dir(task_dir, workspace)

    if args.codex_home:
        codex_home = Path(args.codex_home).expanduser().resolve()
        codex_home.mkdir(parents=True, exist_ok=True)
        codex_home_display = str(codex_home)
    elif os.environ.get('CODEX_HOME'):
        codex_home = Path(os.environ['CODEX_HOME']).expanduser().resolve()
        codex_home_display = f"{os.environ['CODEX_HOME']} (inherited)"
    else:
        codex_home = None
        codex_home_display = 'inherited/unset'
    codex_tmp = workspace / '.zoo-agent' / 'tmp' / 'codex' / runtime_name(task_dir)
    pycache_tmp = codex_tmp / 'pycache'
    codex_tmp.mkdir(parents=True, exist_ok=True)
    pycache_tmp.mkdir(parents=True, exist_ok=True)
    codex_tmp_display = str(codex_tmp)
    pycache_tmp_display = str(pycache_tmp)
    env_cmd, env_sh = write_env_wrappers(codex_tmp, pycache_tmp)

    final_msg = task_dir / 'codex-final-message.md'
    events = task_dir / 'codex-events.jsonl'
    run_report = task_dir / 'codex-run.json'
    prompt_adapter = task_dir / 'codex-adapter-prompt.md'
    stdout_log = task_dir / 'codex-stdout.log'
    stderr_log = task_dir / 'codex-stderr.log'
    worker_status_path = task_dir / 'codex-worker-status.json'
    prompt = prompt_path.read_text(encoding='utf-8')
    prompt = (
        "Runtime environment note:\n"
        f"- CODEX_HOME is `{codex_home_display}`.\n"
        f"- Task pack directory visible to Codex is `{task_runtime_dir}`.\n"
        f"- Read `AGENTS.md`, `TASKS.yaml`, `ACCEPTANCE.md`, `PROGRESS.md`, and `BLOCKERS.md` from `{task_runtime_dir}`.\n"
        f"- Update `PROGRESS.md` or `BLOCKERS.md` in `{task_runtime_dir}`.\n"
        f"- Use this temporary directory for all shell, Python, and test commands: `{codex_tmp_display}`.\n"
        f"- On Windows, run every Python/pytest command through `{env_cmd}`. Example: `{env_cmd} python -m pytest ...`.\n"
        f"- On POSIX shells, run every Python/pytest command through `{env_sh}`. Example: `{env_sh} python -m pytest ...`.\n"
        f"- Run scope guard from the workspace as `{env_cmd} python {task_runtime_dir / 'check_codex_scope.py'} {task_dir.name} --tasks {task_runtime_dir / 'TASKS.yaml'}` on Windows.\n"
        "- Do not hand-write PowerShell `$env:TEMP` commands and do not run bare Python or pytest first.\n"
        "- Do not create temporary probe files in the workspace root.\n\n"
        + prompt
    )
    prompt_adapter.write_text(prompt, encoding='utf-8')

    adapter_cmd = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / 'scripts' / 'codex_exec_adapter.py'),
        '--workspace',
        str(workspace),
        '--task-dir',
        str(task_dir),
        '--prompt-file',
        str(prompt_adapter),
        '--output-last-message',
        str(final_msg),
        '--sandbox',
        args.sandbox,
        '--timeout-seconds',
        str(args.timeout_seconds if args.timeout_seconds and args.timeout_seconds > 0 else 1800),
        '--no-output-timeout-seconds',
        str(args.no_output_timeout_seconds),
        '--stdout-log',
        str(stdout_log),
        '--stderr-log',
        str(stderr_log),
        '--status-json',
        str(worker_status_path),
    ]
    if args.codex_home:
        adapter_cmd += ['--codex-home', str(codex_home)]
    if args.skip_git_repo_check or not is_git_worktree(workspace):
        adapter_cmd.append('--skip-git-repo-check')
    if args.profile:
        adapter_cmd += ['--extra-codex-arg=--profile', '--extra-codex-arg', args.profile]
    if args.ephemeral:
        adapter_cmd += ['--extra-codex-arg=--ephemeral']
    if args.json_events:
        adapter_cmd += ['--extra-codex-arg=--json']
    if args.dry_run:
        adapter_cmd.append('--dry-run')

    if args.dry_run:
        adapter = run_adapter(adapter_cmd, Path(__file__).resolve().parents[1])
        print(adapter.get('stdout', ''), end='')
        return int(adapter.get('returncode') or 0)

    adapter = run_adapter(
        adapter_cmd,
        Path(__file__).resolve().parents[1],
        timeout=(args.timeout_seconds + 120 if args.timeout_seconds and args.timeout_seconds > 0 else None),
    )
    sync_runtime_task_files(task_runtime_dir, task_dir)
    if args.json_events and stdout_log.exists():
        shutil.copy2(stdout_log, events)
    copy_if_exists(stdout_log, task_dir / 'codex-stdout.txt')
    copy_if_exists(stderr_log, task_dir / 'codex-stderr.txt')
    worker_status = load_json(worker_status_path)
    returncode = int(worker_status.get('returncode') if worker_status.get('returncode') is not None else adapter.get('returncode') or 0)
    timed_out = worker_status.get('status') in {'timeout', 'no_output_timeout'} or bool(adapter.get('timed_out'))
    report = {
        'started_at': worker_status.get('started_at', ''),
        'ended_at': worker_status.get('finished_at', ''),
        'elapsed_seconds': worker_status.get('duration_seconds', adapter.get('elapsed_seconds')),
        'timed_out': timed_out,
        'timeout_seconds': args.timeout_seconds if args.timeout_seconds and args.timeout_seconds > 0 else 1800,
        'no_output_timeout_seconds': args.no_output_timeout_seconds,
        'status': worker_status.get('status', 'unknown'),
        'workspace': str(workspace),
        'task_dir': str(task_dir),
        'task_runtime_dir': str(task_runtime_dir),
        'task_dir_mirrored': task_dir_mirrored,
        'command': worker_status.get('command', []),
        'codex_home': codex_home_display,
        'codex_tmpdir': codex_tmp_display,
        'codex_env_cmd': str(env_cmd),
        'codex_env_sh': str(env_sh),
        'returncode': returncode,
        'final_message': str(final_msg) if final_msg.exists() else None,
        'stdout': str(stdout_log),
        'stderr': str(stderr_log),
        'stdout_compat': str(task_dir / 'codex-stdout.txt'),
        'stderr_compat': str(task_dir / 'codex-stderr.txt'),
        'worker_status_path': str(worker_status_path),
        'worker_status': worker_status,
        'adapter_result': adapter,
    }
    run_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return returncode

if __name__ == '__main__':
    raise SystemExit(main())
