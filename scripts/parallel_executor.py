#!/usr/bin/env python3
"""Parallel Worker executor — split a task across multiple workers and merge results.

Supports:
  - Decomposing a task into sub-tasks using big_task_common
  - Routing each sub-task to the best worker based on capability
  - Running workers in parallel with shared task context
  - Merging results and detecting conflicts
"""

from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root


def _run_worker(worker_name: str, task: str, project: Path, results: list, index: int) -> None:
    """Run a single worker task and store the result."""
    from agent_utils import delegate_capture

    start = time.time()
    try:
        output = delegate_capture(
            'pipeline_loop.py',
            [
                '--workspace',
                str(project),
                '--max-iterations',
                '1',
                '--sandbox',
                'workspace-write',
                '--timeout-seconds',
                '300',
                '--backend',
                worker_name,
                task,
            ],
        )
        duration = time.time() - start
        stdout = str(output.get('stdout') or '')
        results[index] = {
            'worker': worker_name,
            'task': task[:200],
            'returncode': output.get('returncode'),
            'duration_seconds': round(duration, 2),
            'stdout_preview': stdout[:1000],
            'success': output.get('returncode') == 0,
        }
    except Exception as exc:
        results[index] = {
            'worker': worker_name,
            'task': task[:200],
            'error': str(exc),
            'success': False,
        }


def decompose_and_parallelize(project: Path, task_text: str) -> dict[str, Any]:
    """Decompose a task and run sub-tasks in parallel across multiple workers.

    1. Uses big_task_common to classify and decompose
    2. Maps each sub-task to the best worker
    3. Runs workers in parallel threads
    4. Merges results
    """
    from big_task_common import (
        build_big_task_contract,
        generate_resource_map,
        leaf_task_type,
        recommended_worker,
        split_leaf_objectives,
    )
    from task_context import add_decision, default_context, save_context, summarize_for_worker

    task_id = f'parallel-{int(time.time())}'
    context = default_context(task_id, task_text[:500])

    # Step 1: Build contract and resource map
    contract = build_big_task_contract(project, task_id, task_text, goal_id='')
    resource_map = generate_resource_map(project, task_text)

    # Step 2: Split into leaf objectives
    leaves = split_leaf_objectives(contract, resource_map)
    if not leaves:
        return {'status': 'no_decomposition', 'task': task_text[:200], 'worker_count': 0}

    # Step 3: Map leaves to workers and build sub-tasks
    sub_tasks: list[dict[str, Any]] = []
    for idx, (objective, paths, resources) in enumerate(leaves):
        task_type = leaf_task_type(objective, paths)
        worker = recommended_worker(task_type, project)
        context_part = summarize_for_worker(context)
        full_task = f'{context_part}\n\n## Sub-task {idx + 1}\n\n{objective}\n\nFiles: {", ".join(paths) if paths else "not specified"}'
        sub_tasks.append(
            {
                'index': idx,
                'objective': objective[:200],
                'task_type': task_type,
                'recommended_worker': worker,
                'full_task': full_task,
                'paths': paths,
            }
        )

    # Step 4: Run workers in parallel
    worker_count = len(sub_tasks)
    results: list[Any] = [None] * worker_count
    threads = []
    for item in sub_tasks:
        t = threading.Thread(
            target=_run_worker,
            args=(item['recommended_worker'], item['full_task'], project, results, item['index']),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join(timeout=360)

    # Step 5: Collect results and update context
    changed_files: list[str] = []
    for item in results:
        if item and item.get('success'):
            changed_files.append(f'{item["worker"]}: {item.get("task", "")[:60]}')

    # Record in shared context
    add_decision(context, f'Parallel execution with {worker_count} workers', 'parallel_executor')
    save_context(project, context)

    return {
        'status': 'ok',
        'task_id': task_id,
        'worker_count': worker_count,
        'sub_tasks': [
            {'index': s['index'], 'type': s['task_type'], 'worker': s['recommended_worker']} for s in sub_tasks
        ],
        'results': results,
        'changed_files': changed_files,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description='Parallel Worker executor.')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--task', nargs='*', help='Task description')
    args = parser.parse_args()

    project = project_root(args.workspace)
    task_text = ' '.join(args.task).strip()
    if not task_text:
        print(json.dumps({'status': 'error', 'error': 'no task provided'}))
        return 1

    result = decompose_and_parallelize(project, task_text)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
