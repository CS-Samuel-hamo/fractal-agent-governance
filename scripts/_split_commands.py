#!/usr/bin/env python3
"""Properly extract session and goal modules from agent_commands.py."""

from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SRC = SCRIPTS / 'agent_commands.py'

content = SRC.read_text(encoding='utf-8').split('\n')

# Identify function ranges
session_funcs = {
    'bootstrap',
    'legacy_run',
    'run',
    'pipeline',
    'plan_big',
    'decompose_big',
    'aggregate_big',
    'goal_loop',
    'global_loop',
    'integration_check',
}
goal_funcs = {'goal_command', 'loop_command', 'review', 'codex_health'}
all_to_extract = session_funcs | goal_funcs

# Find start line of each function
func_starts = {}
for i, line in enumerate(content):
    for name in all_to_extract:
        if line.startswith('def ' + name + '('):
            func_starts[name] = i
            break

# Find end line of each function (next top-level def, or end of file)
func_ranges = {}
sorted_names = sorted(func_starts, key=lambda n: func_starts[n])
for idx, name in enumerate(sorted_names):
    start = func_starts[name]
    if idx + 1 < len(sorted_names):
        end = func_starts[sorted_names[idx + 1]]
    else:
        end = len(content)
    func_ranges[name] = (start, end)

# Extract function text
session_code = []
goal_code = []
lines_to_delete = set()

for name, (start, end) in func_ranges.items():
    chunk = content[start:end]
    # Ensure last line has newline
    text = '\n'.join(chunk)
    if not text.endswith('\n'):
        text += '\n'
    if name in session_funcs:
        session_code.append(text)
    else:
        goal_code.append(text)
    lines_to_delete.update(range(start, end))

# Remove extracted lines from original (from bottom to top)
new_content = [line for i, line in enumerate(content) if i not in lines_to_delete]

# Write agent_commands.py (remaining)
SRC.write_text('\n'.join(new_content), encoding='utf-8')
print(f'agent_commands.py: {len(new_content)} lines remaining ({len(content) - len(new_content)} removed)')

# Write session module
session_preamble = '''#!/usr/bin/env python3
"""Session runtime and pipeline command handlers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    clean_progress,
    delegate,
    delegate_capture,
    ensure_bootstrap_before_run,
    parse_json_output,
    prepare_bootstrap_workspace,
    print_bootstrap_output,
    print_json,
    run_command,
    run_command_capture,
    workspace_arg,
    write_onboarding_artifacts,
)
from backend_registry import read_backend_selection
from check_project_readiness import analyze_project_readiness
from runtime_common import initialize_loop, load_json, project_root, set_active_goal, utc_now, write_json
from update_runtime_metrics import update_metrics


'''
with open(SCRIPTS / 'agent_commands_session.py', 'w') as f:
    f.write(session_preamble)
    for code in session_code:
        f.write(code)
        if not code.endswith('\n'):
            f.write('\n')
print(f'agent_commands_session.py: {sum(len(c.split(chr(10))) for c in session_code)} lines')

# Write goal module
goal_preamble = '''#!/usr/bin/env python3
"""Goal, loop, and review command handlers."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from agent_utils import (
    clean_progress,
    delegate,
    delegate_capture,
    latest_run_id,
    parse_json_output,
    print_json,
    workspace_arg,
)
from runtime_common import project_root


'''
with open(SCRIPTS / 'agent_commands_goal.py', 'w') as f:
    f.write(goal_preamble)
    for code in goal_code:
        f.write(code)
        if not code.endswith('\n'):
            f.write('\n')
print(f'agent_commands_goal.py: {sum(len(c.split(chr(10))) for c in goal_code)} lines')

print('Done. Run: ruff format scripts/agent_commands_*.py && ruff check scripts/agent_commands_*.py')
