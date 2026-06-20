#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, datetime, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import ensure_goal, project_root  # noqa: E402

TEMPLATE_DIR = ROOT / 'templates' / 'codex'

def render(text: str, mapping: dict[str,str]) -> str:
    for k,v in mapping.items():
        text = text.replace('{{'+k+'}}', v)
    return text

def yaml_list(items, indent='      '):
    if not items:
        return indent + '- ""'
    return '\n'.join(indent + '- "' + str(x).replace('"','\\"') + '"' for x in items)


def yaml_scalar(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def copy_task_context(context_path: Path, out: Path) -> None:
    if context_path.suffix.lower() == '.md':
        shutil.copy2(context_path, out / 'TASK_CONTEXT.md')
        json_sibling = context_path.with_suffix('.json')
        if json_sibling.exists():
            shutil.copy2(json_sibling, out / 'TASK_CONTEXT.json')
        return

    shutil.copy2(context_path, out / 'TASK_CONTEXT.json')
    md_sibling = context_path.with_suffix('.md')
    if md_sibling.exists():
        shutil.copy2(md_sibling, out / 'TASK_CONTEXT.md')


def resolve_goal_binding(args) -> dict[str, str]:
    workspace = Path(args.worktree).resolve() if args.worktree else Path.cwd().resolve()
    try:
        project = project_root(workspace)
    except SystemExit:
        project = workspace
    goal = ensure_goal(project, goal_id=args.goal_id, fallback_goal=args.objective)
    return {
        'goal_id': str(goal.get('goal_id') or args.goal_id),
        'goal_path': str(goal.get('_path') or ''),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--task-id', required=True)
    ap.add_argument('--branch-id', default='')
    ap.add_argument('--objective', required=True)
    ap.add_argument('--goal-id', default='', help='Goal id to bind this task pack to; defaults to active goal or creates one from the objective')
    ap.add_argument('--allowed-file', action='append', default=[])
    ap.add_argument('--denied-file', action='append', default=[])
    ap.add_argument('--acceptance', action='append', default=[])
    ap.add_argument('--test-command', action='append', default=[])
    ap.add_argument('--worktree', default='')
    ap.add_argument('--output', default='')
    ap.add_argument('--prompt-template', default='CODEX_TASK_PROMPT.md', help='Prompt template file under templates/codex')
    ap.add_argument('--task-context', default='', help='Optional task context JSON or Markdown file to copy into the task pack')
    args = ap.parse_args()

    out = Path(args.output) if args.output else Path('.zoo-agent') / 'runs' / args.run_id / 'codex-tasks' / args.task_id
    out.mkdir(parents=True, exist_ok=True)
    goal_binding = resolve_goal_binding(args)

    mapping = {
        'RUN_ID': args.run_id,
        'TASK_ID': args.task_id,
        'GOAL_ID': goal_binding['goal_id'],
        'BRANCH_ID': args.branch_id or args.task_id,
        'OBJECTIVE': args.objective,
        'OBJECTIVE_YAML': yaml_scalar(args.objective),
        'ALLOWED_FILES': yaml_list(list(args.allowed_file) + [f'.zoo-agent/runs/{args.run_id}/codex-tasks/{args.task_id}/**']),
        'DENIED_FILES': yaml_list(args.denied_file or ['.env', '.env.*', '**/*.pem', '**/*.key', 'secrets/**', 'credentials/**']),
        'ACCEPTANCE': yaml_list(args.acceptance or ['Scope guard passes', 'Relevant tests pass or blockers are documented']),
        'TEST_COMMANDS': yaml_list(args.test_command),
    }

    prompt_template = TEMPLATE_DIR / args.prompt_template
    if not prompt_template.exists():
        raise SystemExit(f'Missing prompt template: {prompt_template}')

    for name in ['AGENTS.md','TASKS.yaml','ACCEPTANCE.md','CODEX_TASK_PROMPT.md','PROGRESS.md','BLOCKERS.md']:
        src = TEMPLATE_DIR / name
        if name == 'CODEX_TASK_PROMPT.md':
            src = prompt_template
        (out / name).write_text(render(src.read_text(encoding='utf-8'), mapping), encoding='utf-8')

    context_path = Path(args.task_context).resolve() if args.task_context else None
    if context_path and context_path.exists():
        copy_task_context(context_path, out)

    # Copy scope guard into task pack for Codex to run from pack/worktree.
    scope_src = ROOT / 'scripts' / 'check_codex_scope.py'
    if scope_src.exists():
        shutil.copy2(scope_src, out / 'check_codex_scope.py')

    meta = {
        'run_id': args.run_id,
        'task_id': args.task_id,
        'branch_id': args.branch_id or args.task_id,
        'executor': 'codex_cli',
        'goal_id': goal_binding['goal_id'],
        'goal_path': goal_binding['goal_path'],
        'objective': args.objective,
        'allowed_files': args.allowed_file,
        'denied_files': args.denied_file,
        'acceptance': args.acceptance,
        'test_commands': args.test_command,
        'worktree_path': args.worktree,
        'prompt_template': args.prompt_template,
        'task_context': str(context_path) if context_path else '',
        'scope_guard_command': f'python check_codex_scope.py {args.task_id}',
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    (out / 'task-metadata.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(out)

if __name__ == '__main__':
    main()
