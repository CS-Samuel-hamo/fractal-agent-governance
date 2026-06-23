#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from bounded_docs_writer import is_safe_docs_target, normalize_rel
from runtime_common import project_root
from seed_prompt_discovery import discover_seed_prompt


DOC_FILE_RE = re.compile(r'(?i)(README\.md|docs[/\\][^\s"\'<>:|?*]+?\.(?:md|txt))')
GENERIC_FILE_RE = re.compile(r'(?i)([A-Za-z0-9_.\-/\\]+\.(?:py|js|ts|tsx|jsx|json|toml|yaml|yml|md|txt))')
SEED_VERB_RE = re.compile(r'(?i)\b(read|execute|run|use|follow|load)\b|读取|执行|运行|根据|按照|使用')
EDIT_VERB_RE = re.compile(r'(?i)\b(fix|update|edit|extend|expand|write|add|revise|improve|change)\b|修复|修改|扩展|完善|加入|添加|补充|更新|改写')
PROJECT_GOAL_RE = re.compile(r'(?i)\b(project|release|prepare|build|bootstrap|roadmap|plan|operator)\b|项目|发布|准备|规划|启动|执行这个项目')
PREVIEW_ARTIFACT_RE = re.compile(r'(?i)\b(temp|temporary|preview|demo|show me|example|sample)\b|临时|预览|演示|示例|给我看|看一下|不保留|删掉')
PREVIEW_ARTIFACT_RE = re.compile(
    r'(?i)\b(temp|temporary|preview|demo|show me|example|sample|do not keep|one-off)\b'
    r'|\u4e34\u65f6|\u9884\u89c8|\u6f14\u793a|\u793a\u4f8b|\u7ed9\u6211\u770b|\u770b\u4e00\u4e0b|\u4e0d\u4fdd\u7559|\u5220\u6389'
    r'|涓存椂|棰勮|婕旂ず|绀轰緥|缁欐垜鐪媩鐪嬩竴涓媩涓嶄繚鐣檤鍒犳帀'
)
UNSAFE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r'(?i)(^|\s|[/\\])\.env(\s|$|[/\\])'), 'secret file access'),
    (re.compile(r'(?i)\b(secret|api[_-]?key|token|password|credential|private key|ssh key|cert)\b|密钥|令牌|密码|凭证'), 'credential or secret handling'),
    (re.compile(r'(?i)\b(delete|remove|wipe|destroy|rm\s+-rf|del\s+/s|erase)\b|删除|清空|销毁'), 'destructive file operation'),
    (re.compile(r'(?i)\b(git\s+push|push\b|git\s+merge|merge\b|remote branch)\b|推送|合并'), 'remote git operation'),
    (re.compile(r'(?i)\b(deploy|production|prod|release to production)\b|生产部署|上线'), 'production deployment'),
    (re.compile(r'(?i)\b(database migration|db migration|migrate database|schema migration)\b|数据库迁移'), 'database migration'),
    (re.compile(r'(?i)\b(auth|payment|billing|checkout)\b|支付|认证|授权'), 'auth or payment area'),
]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = normalize_rel(item)
        key = normalized.lower()
        if normalized and key not in seen:
            result.append(normalized)
            seen.add(key)
    return result


def unsafe_reason(prompt: str) -> str:
    for pattern, reason in UNSAFE_PATTERNS:
        if pattern.search(prompt or ''):
            return reason
    return ''


def extract_doc_targets(prompt: str) -> list[str]:
    matches = [match.group(1).replace('\\', '/') for match in DOC_FILE_RE.finditer(prompt or '')]
    return [item for item in _unique(matches) if is_safe_docs_target(item)]


def extract_file_targets(prompt: str) -> list[str]:
    matches = [match.group(1).replace('\\', '/') for match in GENERIC_FILE_RE.finditer(prompt or '')]
    return _unique(matches)


def _seed_mentioned(prompt: str, seed_path: str = '') -> bool:
    surface = prompt.lower()
    if seed_path and seed_path.lower() in surface:
        return True
    return any(name in surface for name in ['project_beginning_prompt.md', 'project_prompt.md', 'goal.md', 'brief.md', 'spec.md', 'requirements.md', 'prompt.md'])


def classify_prompt(project: Path, prompt: str, *, allowed_files: list[str] | None = None) -> dict[str, Any]:
    text = (prompt or '').strip()
    docs_from_allowed = [normalize_rel(item) for item in (allowed_files or []) if is_safe_docs_target(item)]
    doc_targets = _unique([*docs_from_allowed, *extract_doc_targets(text)])
    all_targets = _unique([*(allowed_files or []), *extract_file_targets(text)])
    danger = unsafe_reason(text)
    seed_payload = discover_seed_prompt(project, goal=text)
    seed = seed_payload.get('selected') if isinstance(seed_payload.get('selected'), dict) else {}
    seed_path = str(seed.get('path') or '')

    if danger:
        return {
            'intent': 'unsafe_or_needs_confirmation',
            'execution_mode': 'needs_attention',
            'status': 'Needs attention',
            'risk_level': 'high',
            'target_files': doc_targets or all_targets,
            'seed_file': seed_path,
            'reason': danger,
            'recommended_action': 'Review the request and remove the high-risk operation before running again.',
        }

    if doc_targets and EDIT_VERB_RE.search(text):
        return {
            'intent': 'single_step_edit',
            'execution_mode': 'direct_docs_apply',
            'status': 'Done',
            'risk_level': 'low',
            'target_files': doc_targets,
            'seed_file': seed_path,
            'reason': 'The prompt names a safe documentation target.',
            'recommended_action': 'Apply a bounded documentation update.',
        }

    if _seed_mentioned(text, seed_path) and (SEED_VERB_RE.search(text) or not doc_targets):
        targets = ['README.md', 'docs/project_plan.md']
        if seed.get('research_seed') or re.search(r'(?i)research|paper|literature|evidence|论文|文献|证据|验证', text):
            targets.append('docs/research_workflow.md')
        return {
            'intent': 'seed_prompt_execution',
            'execution_mode': 'project_safe_step',
            'status': 'Working',
            'risk_level': 'low',
            'target_files': targets,
            'seed_file': seed_path,
            'reason': 'The prompt asks to execute a project seed prompt.',
            'recommended_action': 'Build project context and execute the first safe step.',
        }

    if PREVIEW_ARTIFACT_RE.search(text):
        return {
            'intent': 'preview_artifact',
            'execution_mode': 'temporary_preview',
            'status': 'Done',
            'risk_level': 'low',
            'target_files': [],
            'seed_file': seed_path,
            'reason': 'The prompt asks for a temporary preview artifact.',
            'recommended_action': 'Generate a local preview artifact without modifying project docs.',
        }

    if doc_targets:
        return {
            'intent': 'single_step_edit',
            'execution_mode': 'direct_docs_apply',
            'status': 'Done',
            'risk_level': 'low',
            'target_files': doc_targets,
            'seed_file': seed_path,
            'reason': 'The prompt names a safe documentation target.',
            'recommended_action': 'Apply a bounded documentation update.',
        }

    if PROJECT_GOAL_RE.search(text) or seed_path:
        return {
            'intent': 'project_goal',
            'execution_mode': 'project_safe_step',
            'status': 'Working',
            'risk_level': 'low',
            'target_files': [],
            'seed_file': seed_path,
            'reason': 'The prompt describes a project goal.',
            'recommended_action': 'Start a project job and execute the first safe step.',
        }

    return {
        'intent': 'single_step_edit',
        'execution_mode': 'needs_target_or_preview',
        'status': 'Needs attention',
        'risk_level': 'unknown',
        'target_files': [],
        'seed_file': seed_path,
        'reason': 'No safe target file or project seed prompt was identified.',
        'recommended_action': 'Name the file to change, or add a project_beginning_prompt.md seed prompt.',
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Classify a user prompt for the unified agent entry.')
    parser.add_argument('prompt')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--allowed-file', action='append', default=[])
    args = parser.parse_args()
    payload = classify_prompt(project_root(args.workspace), args.prompt, allowed_files=args.allowed_file)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
