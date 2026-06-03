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
    codex = shutil.which('codex')
    if not codex:
        print('Codex CLI not found. Install/login Codex CLI first.', file=sys.stderr)
        return 3

    task_runtime_dir, task_dir_mirrored = prepare_task_runtime_dir(task_dir, workspace)

    env = os.environ.copy()
    if args.codex_home:
        codex_home = Path(args.codex_home).expanduser().resolve()
        codex_home.mkdir(parents=True, exist_ok=True)
        env['CODEX_HOME'] = str(codex_home)
        codex_home_display = str(codex_home)
    elif env.get('CODEX_HOME'):
        codex_home = Path(env['CODEX_HOME']).expanduser().resolve()
        codex_home_display = f"{env['CODEX_HOME']} (inherited)"
    else:
        codex_home = None
        codex_home_display = 'inherited/unset'
    codex_tmp = workspace / '.zoo-agent' / 'tmp' / 'codex' / runtime_name(task_dir)
    pycache_tmp = codex_tmp / 'pycache'
    codex_tmp.mkdir(parents=True, exist_ok=True)
    pycache_tmp.mkdir(parents=True, exist_ok=True)
    env['TMPDIR'] = str(codex_tmp)
    env['TMP'] = str(codex_tmp)
    env['TEMP'] = str(codex_tmp)
    env['PYTHONPYCACHEPREFIX'] = str(pycache_tmp)
    codex_tmp_display = str(codex_tmp)
    pycache_tmp_display = str(pycache_tmp)
    env_cmd, env_sh = write_env_wrappers(codex_tmp, pycache_tmp)

    final_msg = task_dir / 'codex-final-message.md'
    events = task_dir / 'codex-events.jsonl'
    run_report = task_dir / 'codex-run.json'
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

    cmd = [codex, 'exec', '--cd', str(workspace), '--sandbox', args.sandbox, '--output-last-message', str(final_msg)]
    if args.profile:
        cmd += ['--profile', args.profile]
    if args.ephemeral:
        cmd += ['--ephemeral']
    if args.json_events:
        cmd += ['--json']
    cmd += ['-']

    if args.dry_run:
        print('DRY RUN command:')
        print(' '.join(cmd))
        print(f'CODEX_HOME={codex_home_display}')
        print(f'CODEX_TMPDIR={codex_tmp_display}')
        print(f'CODEX_ENV_CMD={env_cmd}')
        print(f'CODEX_ENV_SH={env_sh}')
        print(f'CODEX_TASK_RUNTIME_DIR={task_runtime_dir}')
        print(f'CODEX_TASK_DIR_MIRRORED={task_dir_mirrored}')
        return 0

    started = datetime.datetime.utcnow().isoformat() + 'Z'
    started_clock = time.monotonic()
    timeout = args.timeout_seconds if args.timeout_seconds and args.timeout_seconds > 0 else None
    timed_out = False
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env,
    )
    stdout = ''
    stderr = ''
    try:
        stdout, stderr = proc.communicate(input=prompt, timeout=timeout)
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or ''
        stderr = exc.stderr or ''
        kill_process_tree(proc.pid)
        try:
            proc.kill()
        except OSError:
            pass
        try:
            tail_stdout, tail_stderr = proc.communicate(timeout=15)
            stdout = (stdout or '') + (tail_stdout or '')
            stderr = (stderr or '') + (tail_stderr or '')
        except subprocess.TimeoutExpired as tail_exc:
            stdout = (stdout or '') + (tail_exc.stdout or '')
            stderr = (stderr or '') + (tail_exc.stderr or '')
            stderr += '\nTIMEOUT: codex exec did not close stdout/stderr after process-tree kill.\n'
        returncode = 124
    ended = datetime.datetime.utcnow().isoformat() + 'Z'
    elapsed_seconds = round(time.monotonic() - started_clock, 3)
    sync_runtime_task_files(task_runtime_dir, task_dir)
    if args.json_events:
        events.write_text(stdout, encoding='utf-8')
    else:
        (task_dir / 'codex-stdout.txt').write_text(stdout, encoding='utf-8')
    (task_dir / 'codex-stderr.txt').write_text(stderr, encoding='utf-8')
    report = {
        'started_at': started,
        'ended_at': ended,
        'elapsed_seconds': elapsed_seconds,
        'timed_out': timed_out,
        'timeout_seconds': timeout,
        'workspace': str(workspace),
        'task_dir': str(task_dir),
        'task_runtime_dir': str(task_runtime_dir),
        'task_dir_mirrored': task_dir_mirrored,
        'command': cmd,
        'codex_home': codex_home_display,
        'codex_tmpdir': codex_tmp_display,
        'codex_env_cmd': str(env_cmd),
        'codex_env_sh': str(env_sh),
        'returncode': returncode,
        'final_message': str(final_msg) if final_msg.exists() else None,
        'stdout': str(task_dir / 'codex-stdout.txt'),
        'stderr': str(task_dir / 'codex-stderr.txt'),
    }
    run_report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return returncode

if __name__ == '__main__':
    raise SystemExit(main())
