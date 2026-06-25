from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from runtime_common import project_root, utc_now, write_json

DOC_SUFFIXES = ('.md', '.txt')
SENSITIVE_RE = re.compile(r'(?i)(^|/|\\|\.)(env|secret|key|token|password|credential|private|cert)(\.|/|\\|$)')
SOURCE_RE = re.compile(
    r'(?i)([\w.\-/\\]*project_beginning_prompt\.md|[\w.\-/\\]*project_prompt\.md|[\w.\-/\\]*prompt\.md|[\w.\-/\\]*brief\.md|[\w.\-/\\]*requirements\.md)'
)


def normalize_rel(path: str) -> str:
    return str(path or '').strip().replace('\\', '/').lstrip('./')


def is_safe_source_file(path: str) -> bool:
    normalized = normalize_rel(path)
    return bool(
        normalized
        and not Path(normalized).is_absolute()
        and '..' not in normalized.split('/')
        and not SENSITIVE_RE.search(normalized)
        and normalized.lower().endswith(DOC_SUFFIXES)
    )


def is_safe_docs_target(path: str) -> bool:
    normalized = normalize_rel(path)
    if not normalized or Path(normalized).is_absolute() or '..' in normalized.split('/'):
        return False
    if SENSITIVE_RE.search(normalized):
        return False
    if not normalized.lower().endswith(DOC_SUFFIXES):
        return False
    return normalized == 'README.md' or normalized.startswith('docs/')


def extract_source_files(objective: str) -> list[str]:
    found: list[str] = []
    for match in SOURCE_RE.findall(objective or ''):
        normalized = normalize_rel(match)
        if normalized and normalized not in found and is_safe_source_file(normalized):
            found.append(normalized)
    if not found:
        found.append('project_beginning_prompt.md')
    return found


def read_source_summary(project: Path, source_files: list[str]) -> tuple[list[str], str]:
    used: list[str] = []
    chunks: list[str] = []
    for item in source_files:
        if not is_safe_source_file(item):
            continue
        path = project / item
        if not path.exists() or not path.is_file() or path.stat().st_size > 128 * 1024:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        excerpt = ' '.join(lines[:24])
        if excerpt:
            used.append(item)
            chunks.append(excerpt[:1600])
    summary = '\n\n'.join(chunks).strip()
    if not summary:
        summary = 'No safe seed prompt summary was available; use the user task as the document update intent.'
    return used, summary[:2400]


def marker_for(objective: str, target: str) -> str:
    digest = hashlib.sha256(f'{target}\n{objective}'.encode('utf-8', errors='replace')).hexdigest()[:12]
    return f'<!-- agent-runtime:bounded-docs:{digest} -->'


def build_append_markdown(*, objective: str, target: str, source_files: list[str], source_summary: str) -> str:
    marker = marker_for(objective, target)
    source_line = ', '.join(f'`{item}`' for item in source_files) if source_files else 'user task'
    surface = f'{objective}\n{source_summary}'.lower()
    if any(
        signal in surface
        for signal in ['research', 'paper', 'literature', 'evidence', 'validation', '论文', '文献', '证据', '验证']
    ):
        body = (
            '## 文献、证据和验证流程\n\n'
            f'来源：{source_line}\n\n'
            '### 1. 文献流程\n\n'
            '- 先定义研究问题、关键词、领域边界和排除条件，再开始检索。\n'
            '- 建立文献矩阵，至少记录：作者、年份、问题、方法、数据、主要发现、局限、与本项目的关系。\n'
            '- 所有引用必须来自用户提供或后续人工确认的真实来源；不得生成占位式或虚构引用。\n\n'
            '### 2. 证据流程\n\n'
            '- 将事实、假设、推论和待验证问题分开记录。\n'
            '- 为每个核心论点标注所需证据类型：文献证据、数据证据、案例证据、实验结果或专家判断。\n'
            '- 缺少证据时只标记为待验证，不把假设写成结论。\n\n'
            '### 3. 验证流程\n\n'
            '- 优先做最小可行验证：小样本、可复现检查、反例搜索或专家审阅。\n'
            '- 每一轮验证都记录输入、方法、输出、失败原因和下一步。\n'
            '- 正式扩写前先完成红队审查：是否有伪引用、伪数据、过度结论或未披露不确定性。\n\n'
            '### 4. 下一步动作\n\n'
            '- 补充一张文献矩阵模板。\n'
            '- 列出当前最关键的 3-5 个待验证假设。\n'
            '- 为每个假设指定最小证据要求和验证方法。\n'
        )
    else:
        body = (
            '## Agent Update\n\n'
            f'Source: {source_line}\n\n'
            f'Task: {objective}\n\n'
            '### Proposed Workflow\n\n'
            '- Clarify the concrete outcome.\n'
            '- Separate confirmed facts from assumptions.\n'
            '- Define the smallest useful validation step.\n'
            '- Record risks, open questions, and next actions.\n'
        )
    return f'\n\n{marker}\n{body}'


def apply_docs_patch(project: Path, *, objective: str, target_files: list[str]) -> dict[str, Any]:
    changed: list[str] = []
    skipped: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    sources, summary = read_source_summary(project, extract_source_files(objective))

    for raw_target in target_files:
        target = normalize_rel(raw_target)
        if not is_safe_docs_target(target):
            blocked.append({'path': target, 'reason': 'unsafe_or_unsupported_docs_target'})
            continue
        path = project / target
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            before = ''
        else:
            before = path.read_text(encoding='utf-8', errors='replace')
        append_text = build_append_markdown(
            objective=objective, target=target, source_files=sources, source_summary=summary
        )
        marker = marker_for(objective, target)
        if marker in before:
            skipped.append({'path': target, 'reason': 'bounded_docs_patch_already_present'})
            continue
        path.write_text(before.rstrip() + append_text + '\n', encoding='utf-8')
        changed.append(target)

    status = 'success' if changed and not blocked else ('blocked' if blocked else 'skipped')
    payload = {
        'schema_version': '1.0',
        'generated_by': 'bounded_docs_writer.py',
        'generated_at': utc_now(),
        'status': status,
        'objective': objective,
        'changed_files': changed,
        'skipped': skipped,
        'blocked': blocked,
        'source_files': sources,
        'safe_for_user_output': True,
        'summary': 'Applied safe docs update.'
        if changed
        else ('Blocked unsafe docs target.' if blocked else 'No changes needed.'),
    }
    write_json(project / '.zoo-agent' / 'workers' / 'bounded_docs_writer_result.json', payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply a bounded, low-risk docs update.')
    parser.add_argument('objective')
    parser.add_argument('--workspace', default='.')
    parser.add_argument('--target-file', action='append', default=[])
    args = parser.parse_args()
    payload = apply_docs_patch(project_root(args.workspace), objective=args.objective, target_files=args.target_file)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get('status') in {'success', 'skipped'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
