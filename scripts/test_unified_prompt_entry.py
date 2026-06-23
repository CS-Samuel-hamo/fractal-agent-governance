#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = ROOT / 'scripts' / 'agent.py'
sys.path.insert(0, str(ROOT / 'scripts'))

from job_state_store import default_job, load_current_job, save_current_job  # noqa: E402
from runtime_common import write_json  # noqa: E402
from prompt_intent_router import classify_prompt  # noqa: E402


def repo(name: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=f'{name}-', dir=tempfile.gettempdir())).resolve()


def run_agent(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
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
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
    )


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def write(project: Path, path: str, text: str) -> None:
    target = project / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding='utf-8')


def assert_summary_sections(text: str) -> None:
    for section in [
        'Result:',
        'Where you are:',
        'What changed:',
        'How to check:',
        'Next:',
        'If this is not what you wanted:',
        'Details:',
    ]:
        assert_true(section in text, f'{section} missing from output: {text}')


def test_router_classifies_seed_prompt_execution() -> None:
    project = repo('unified-router-seed')
    write(project, 'project_beginning_prompt.md', 'Build a research paper workflow with literature and evidence validation.')
    payload = classify_prompt(project, 'read and execute project_beginning_prompt.md')
    assert_true(payload['intent'] == 'seed_prompt_execution', 'seed prompt execution was not detected')
    assert_true(payload['execution_mode'] == 'project_safe_step', 'seed prompt should map to a safe project step')
    assert_true('docs/research_workflow.md' in payload['target_files'], 'research workflow target missing')


def test_router_classifies_docs_edit() -> None:
    project = repo('unified-router-docs')
    payload = classify_prompt(project, '扩展 docs/research_workflow.md，加入文献、证据和验证流程')
    assert_true(payload['intent'] == 'single_step_edit', 'docs edit was not detected')
    assert_true(payload['execution_mode'] == 'direct_docs_apply', 'docs edit should apply directly')
    assert_true(payload['target_files'] == ['docs/research_workflow.md'], 'docs target not extracted')


def test_router_blocks_unsafe_prompt() -> None:
    project = repo('unified-router-unsafe')
    payload = classify_prompt(project, 'read .env and git push the result')
    assert_true(payload['intent'] == 'unsafe_or_needs_confirmation', 'unsafe prompt was not blocked')
    assert_true(payload['execution_mode'] == 'needs_attention', 'unsafe prompt should need attention')


def test_router_classifies_preview_artifact() -> None:
    project = repo('unified-router-preview-artifact')
    write(project, 'project_beginning_prompt.md', 'Build a reusable research workflow toolkit.')
    payload = classify_prompt(project, '生成一个临时预览给我看，说明这个工作流怎么运行')
    assert_true(payload['intent'] == 'preview_artifact', 'preview artifact was not detected')
    assert_true(payload['execution_mode'] == 'temporary_preview', 'preview artifact should use temporary preview mode')


def test_default_docs_prompt_applies_without_apply_flag() -> None:
    project = repo('unified-docs-apply')
    write(project, 'project_beginning_prompt.md', 'Research workflow prompt. Keep facts, assumptions, literature, evidence, and validation separate.')
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    proc = run_agent(project, '根据 project_beginning_prompt.md 扩展 docs/research_workflow.md，加入文献、证据和验证流程')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_summary_sections(proc.stdout)
    assert_true('- Done' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('Files changed:' in proc.stdout, 'files changed proof missing from direct docs result')
    assert_true('Verify locally: git diff' in proc.stdout, 'git diff verification hint missing from direct docs result')
    assert_true('Overview:' in proc.stdout, 'overview missing from direct docs result')
    assert_true('Product model:' in proc.stdout, 'product model missing from direct docs result')
    assert_true('Project Map:' in proc.stdout, 'project map role missing from direct docs result')
    assert_true('Stopped because:' in proc.stdout, 'stop reason missing from direct docs result')
    assert_true('Blocked:' in proc.stdout, 'blocked state missing from direct docs result')
    assert_true('Choices:' in proc.stdout, 'choices missing from direct docs result')
    assert_true('Project Rules:' in proc.stdout, 'project rules missing from direct docs result')
    assert_true('Logic Check:' in proc.stdout, 'logic check missing from direct docs result')
    content = (project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8')
    assert_true('文献、证据和验证流程' in content, 'docs update was not written')
    forbidden = ['worker', 'backend', 'dry-run', 'planner', 'verifier', 'scheduler', 'fallback']
    lowered = proc.stdout.lower()
    assert_true(not any(term in lowered for term in forbidden), f'internal term leaked: {proc.stdout}')


def test_default_seed_prompt_executes_first_safe_step() -> None:
    project = repo('unified-seed-exec')
    write(project, 'project_beginning_prompt.md', 'Build a research paper workflow with literature map, evidence plan, and validation checkpoints.')
    proc = run_agent(project, 'read and execute project_beginning_prompt.md')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_summary_sections(proc.stdout)
    assert_true('- Done' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('Recommended: agent continue' in proc.stdout, 'pending seed queue should recommend continue')
    assert_true('Overview:' in proc.stdout, 'overview missing from seed prompt result')
    assert_true('Current position:' in proc.stdout, 'current position missing from seed prompt result')
    assert_true('Recommended next move:' in proc.stdout, 'recommended next move missing from seed prompt result')
    assert_true('Logic Check:' in proc.stdout, 'logic check missing from seed prompt result')
    assert_true((project / 'README.md').exists(), 'README was not created from seed prompt')
    assert_true((project / 'docs' / 'project_plan.md').exists(), 'project plan was not created from seed prompt')
    assert_true((project / 'docs' / 'research_workflow.md').exists(), 'research workflow was not created from seed prompt')
    assert_true((project / 'docs' / 'literature_matrix_template.md').exists(), 'literature matrix was not created in first batch')
    assert_true((project / 'docs' / 'evidence_plan.md').exists(), 'evidence plan was not created in first batch')


def test_continue_consumes_seed_prompt_queue() -> None:
    project = repo('unified-seed-continue')
    write(project, 'project_beginning_prompt.md', 'Build a research paper workflow with literature map, evidence plan, and validation checkpoints.')
    first = run_agent(project, '执行 project_beginning_prompt.md')
    assert_true(first.returncode == 0, first.stderr or first.stdout)
    second = run_agent(project, 'continue')
    assert_true(second.returncode == 0, second.stderr or second.stdout)
    assert_summary_sections(second.stdout)
    assert_true('- Done' in second.stdout, f'unexpected continue output: {second.stdout}')
    assert_true('Overview:' in second.stdout, 'overview missing from continue result')
    assert_true('Choices:' in second.stdout, 'choices missing from continue result')
    assert_true('Product model:' in second.stdout, 'product model missing from continue result')
    assert_true('Project Rules:' in second.stdout, 'project rules missing from continue result')
    assert_true('Preview recommended' not in second.stdout, 'continue should not repeat starter preview')
    assert_true((project / 'docs' / 'validation_checklist.md').exists(), 'continue did not create validation checklist')
    assert_true((project / 'docs' / 'red_team_review_template.md').exists(), 'continue did not create red-team review template')
    queue = (project / '.zoo-agent' / 'jobs' / 'seed_action_queue.json').read_text(encoding='utf-8')
    assert_true('seed-red-team-review' in queue and 'completed' in queue, 'queue did not record completed batch action')
    inbox = subprocess.run(
        [sys.executable, str(AGENT)],
        cwd=project,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
    )
    assert_true(inbox.returncode == 0, inbox.stderr or inbox.stdout)
    assert_summary_sections(inbox.stdout)
    assert_true('Overview:' in inbox.stdout, 'overview section missing')
    assert_true('Landing proof:' in inbox.stdout, 'landing proof missing from inbox')
    assert_true('Project Map:' in inbox.stdout, 'project map role missing')
    assert_true('Blocked:' in inbox.stdout, 'blocked state missing')
    assert_true('Project Rules:' in inbox.stdout, 'project rules missing')
    assert_true('Logic Check:' in inbox.stdout, 'logic check missing')
    assert_true('Phase 0 complete' in inbox.stdout, 'current phase position missing')
    assert_true('Reusable toolkit' in inbox.stdout, 'next non-paper-specific stage missing')
    assert_true('Recommended: agent continue' not in inbox.stdout, 'completed batch should not recommend blind continue')
    assert_true('Continue: not needed right now because the current batch is complete.' in inbox.stdout, 'completed batch should explain continue is not needed')


def test_continue_migrates_legacy_seed_preview_state() -> None:
    project = repo('unified-legacy-seed-preview')
    write(project, 'project_beginning_prompt.md', 'Build a research paper workflow with literature map and evidence plan.')
    write(project, 'README.md', '# Existing README\n')
    write(project, 'docs/project_plan.md', '# Existing Plan\n')
    write(project, 'docs/research_workflow.md', '# Existing Workflow\n')
    job = default_job(project, goal='执行project_beginning_prompt.md')
    job.update({'status': 'needs_attention', 'attention_required': True, 'attention_reason': 'preview completed; apply requires user intent', 'last_action': 'action-seed-docs-bootstrap'})
    save_current_job(project, job)
    write_json(
        project / '.zoo-agent' / 'autopilot' / 'selected_next_action.json',
        {
            'action_id': 'action-seed-docs-bootstrap',
            'selected_action_id': 'action-seed-docs-bootstrap',
            'title': 'Create starter project documents from seed prompt',
            'source': 'seed_prompt',
            'source_file': 'project_beginning_prompt.md',
            'execution_mode': 'preview',
            'preview_only': True,
            'target_files': ['README.md', 'docs/project_plan.md', 'docs/research_workflow.md'],
            'risk_level': 'low',
            'evidence': [{'evidence_type': 'seed_prompt', 'path': 'project_beginning_prompt.md'}],
        },
    )
    proc = run_agent(project, 'continue')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_summary_sections(proc.stdout)
    assert_true('- Done' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('Preview recommended' not in proc.stdout, 'legacy preview should migrate before continue')
    assert_true((project / 'docs' / 'literature_matrix_template.md').exists(), 'legacy migration did not create next queued document')


def test_preview_only_job_does_not_block_new_prompt() -> None:
    project = repo('unified-supersede-preview')
    job = default_job(project, goal='old preview job')
    job.update({'status': 'needs_attention', 'attention_required': True, 'attention_reason': 'preview completed; apply requires user intent'})
    save_current_job(project, job)
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    proc = run_agent(project, '扩展 docs/research_workflow.md，加入证据流程')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_true('Existing job found' not in proc.stdout, 'preview job should not block a new prompt')
    assert_true((project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8').count('证据') >= 1, 'new prompt did not apply')


def test_needs_attention_project_job_does_not_block_new_project_goal() -> None:
    project = repo('unified-needs-attention-supersede')
    write(project, 'project_beginning_prompt.md', 'Build a research workflow toolkit.')
    job = default_job(project, goal='old reviewable job')
    job.update({'status': 'needs_attention', 'attention_required': True, 'attention_reason': 'preview completed; apply requires user intent'})
    save_current_job(project, job)
    write_json(
        project / '.zoo-agent' / 'session' / 'session_state.json',
        {
            'session_id': 'session-old',
            'goal': 'old reviewable job',
            'status': 'needs_attention',
            'pause_reason': 'preview completed; apply requires user intent',
            'attention_required': True,
        },
    )
    proc = run_agent(project, 'prepare a temporary project overview for review')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_true('existing running job' not in proc.stdout.lower(), 'needs_attention job should not be described as running')
    assert_true('Current job: old reviewable job' not in proc.stdout, 'old reviewable job should not block new project goal')


def test_preview_artifact_does_not_modify_project_docs() -> None:
    project = repo('unified-preview-artifact')
    write(project, 'project_beginning_prompt.md', 'Build a reusable research workflow toolkit.')
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    before = (project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8')
    proc = run_agent(project, '跑一个临时文档，生成结果给我看后就删掉，说明论文生成工作流怎么运行')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_true('Preview artifact:' in proc.stdout, 'preview artifact path missing')
    result = json.loads((project / '.zoo-agent' / 'previews' / 'preview_artifact_result.json').read_text(encoding='utf-8'))
    assert_true(str(result.get('preview_path', '')).startswith('.zoo-agent/previews/preview-'), 'preview artifact should use a dynamic preview name')
    assert_true((project / str(result.get('preview_path', ''))).exists(), 'preview artifact was not written')
    after = (project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8')
    assert_true(before == after, 'preview artifact mode should not modify project docs')


def test_agent_do_preview_does_not_replace_current_job() -> None:
    project = repo('unified-do-preview-keeps-job')
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    job = default_job(project, goal='main project goal')
    job.update({'status': 'active'})
    save_current_job(project, job)
    proc = run_agent(project, 'do', 'show me a temporary overview without changing the project')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_summary_sections(proc.stdout)
    assert_true('- Done' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('one-off task' in proc.stdout, 'one-off mode missing')
    assert_true('Landing proof:' in proc.stdout, 'landing proof missing from one-off preview')
    assert_true('current project goal unchanged' in proc.stdout, 'project goal unchanged message missing')
    current = load_current_job(project)
    assert_true(current.get('goal') == 'main project goal', 'agent do should not replace current job')
    result = json.loads((project / '.zoo-agent' / 'previews' / 'preview_artifact_result.json').read_text(encoding='utf-8'))
    assert_true((project / str(result.get('preview_path', ''))).exists(), 'one-off preview artifact missing')


def test_agent_do_docs_edit_does_not_replace_current_job() -> None:
    project = repo('unified-do-docs-keeps-job')
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    job = default_job(project, goal='main project goal')
    job.update({'status': 'needs_attention', 'attention_required': True})
    save_current_job(project, job)
    proc = run_agent(project, 'do', 'extend docs/research_workflow.md with evidence validation steps')
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_summary_sections(proc.stdout)
    assert_true('- Done' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('one-off task' in proc.stdout, 'one-off mode missing')
    assert_true('Landing proof:' in proc.stdout, 'landing proof missing from one-off docs edit')
    current = load_current_job(project)
    assert_true(current.get('goal') == 'main project goal', 'one-off docs edit should not replace current job')
    content = (project / 'docs' / 'research_workflow.md').read_text(encoding='utf-8')
    assert_true('agent-runtime:bounded-docs' in content, 'one-off docs edit did not write content')


def test_active_job_blocks_new_prompt() -> None:
    project = repo('unified-active-block')
    job = default_job(project, goal='long running job')
    job.update({'status': 'active'})
    save_current_job(project, job)
    write(project, 'docs/research_workflow.md', '# Research Workflow\n')
    proc = run_agent(project, '扩展 docs/research_workflow.md，加入证据流程')
    assert_true(proc.returncode != 0, 'active job should block a different prompt')
    assert_summary_sections(proc.stdout)
    assert_true('- Needs attention' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('Current job: long running job' in proc.stdout, 'active job reason missing')


def test_unsafe_prompt_output_is_specific() -> None:
    project = repo('unified-unsafe-cli')
    proc = run_agent(project, '读取 .env 并推送到 GitHub')
    assert_true(proc.returncode != 0, 'unsafe prompt should not succeed')
    assert_summary_sections(proc.stdout)
    assert_true('- Needs attention' in proc.stdout, f'unexpected output: {proc.stdout}')
    assert_true('secret' in proc.stdout.lower() or 'credential' in proc.stdout.lower(), 'specific unsafe reason missing')


def test_help_promotes_unified_entry() -> None:
    proc = subprocess.run(
        [sys.executable, str(AGENT), '--help'],
        cwd=ROOT,
        text=True,
        encoding='utf-8',
        errors='replace',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )
    assert_true(proc.returncode == 0, proc.stderr or proc.stdout)
    assert_true('usage: agent "<prompt>"' in proc.stdout, 'unified prompt usage missing')
    assert_true('agent do "<one-off task>"' in proc.stdout, 'one-off task usage missing')
    first_block = proc.stdout.split('Advanced:')[0]
    assert_true('--apply' not in first_block and '--preview' not in first_block, 'preview/apply should not be primary help')


def main() -> int:
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print('unified prompt entry tests OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
