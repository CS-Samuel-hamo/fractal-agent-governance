#!/usr/bin/env python3
from __future__ import annotations

import html
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ''), quote=True)


def badge(value: Any) -> str:
    text = esc(value or 'unknown')
    tone = text.lower().replace('_', '-')
    if any(item in tone for item in ['ready', 'verified', 'complete', 'done', 'low', 'auto']):
        cls = 'good'
    elif any(item in tone for item in ['attention', 'blocked', 'high', 'missing', 'failed']):
        cls = 'bad'
    elif any(item in tone for item in ['partial', 'paused', 'preview', 'medium']):
        cls = 'warn'
    else:
        cls = 'neutral'
    return f'<span class="badge {cls}">{text}</span>'


def list_items(values: list[Any], *, empty: str = 'not available') -> str:
    rows = [f'<li>{esc(item)}</li>' for item in values if str(item or '').strip()]
    if not rows:
        rows = [f'<li class="muted">{esc(empty)}</li>']
    return '<ul>' + ''.join(rows) + '</ul>'


def module_cards(modules: list[dict[str, Any]]) -> str:
    if not modules:
        return '<div class="empty">No project map yet.</div>'
    rows = []
    for item in modules:
        files = ', '.join(esc(path) for path in item.get('key_files') or []) or 'not available'
        rows.append(
            f"""<article class="item">
  <div class="item-head"><strong>{esc(item.get('name'))}</strong>{badge(item.get('status'))}</div>
  <div class="meta">confidence {esc(item.get('confidence'))} | evidence {esc(item.get('evidence_count'))}</div>
  <div class="files">{files}</div>
</article>"""
        )
    return ''.join(rows)


def capability_rows(capabilities: list[dict[str, Any]]) -> str:
    if not capabilities:
        return '<div class="empty">No capabilities mapped yet.</div>'
    rows = []
    for item in capabilities:
        related = ', '.join(esc(path) for path in item.get('related_modules') or []) or 'not available'
        rows.append(
            f"""<tr>
  <td>{esc(item.get('name'))}</td>
  <td>{badge(item.get('status'))}</td>
  <td>{related}</td>
  <td>{esc(item.get('evidence_count'))}</td>
</tr>"""
        )
    return (
        '<table><thead><tr><th>Capability</th><th>Status</th><th>Related</th><th>Evidence</th></tr></thead><tbody>'
        + ''.join(rows)
        + '</tbody></table>'
    )


def risk_rows(risks: list[dict[str, Any]]) -> str:
    if not risks:
        return '<div class="empty">No project risks mapped yet.</div>'
    rows = []
    for item in risks:
        files = ', '.join(esc(path) for path in item.get('affected_files') or []) or 'not available'
        reason = esc(item.get('reason') or 'Mapped from project evidence.')
        rows.append(
            f"""<article class="item">
  <div class="item-head"><strong>{esc(item.get('description'))}</strong>{badge(item.get('severity'))}</div>
  <div class="meta">{files}</div>
  <p>{reason}</p>
</article>"""
        )
    return ''.join(rows)


def action_cards(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return '<div class="empty">No next actions available.</div>'
    rows = []
    for item in actions[:8]:
        files = ', '.join(esc(path) for path in item.get('target_files') or []) or 'not available'
        rows.append(
            f"""<article class="item action">
  <div class="item-head"><strong>{esc(item.get('title'))}</strong>{badge(item.get('risk_level'))}</div>
  <p><b>Why now:</b> {esc(item.get('why_now'))}</p>
  <p><b>Impact:</b> {esc(item.get('expected_impact'))}</p>
  <div class="meta">mode {esc(item.get('execution_mode'))} | evidence {esc(item.get('evidence_count'))} | {files}</div>
</article>"""
        )
    return ''.join(rows)


def timeline(progress: dict[str, Any]) -> str:
    completed = progress.get('completed_actions') or []
    blocked = progress.get('blocked_actions') or []
    # Merge and sort by timestamp descending (completed first, then blocked by latest)
    merged: list[dict[str, Any]] = []
    for item in completed:
        tagged = dict(item)
        tagged['_kind'] = 'completed'
        merged.append(tagged)
    for item in blocked:
        tagged = dict(item)
        tagged['_kind'] = 'blocked'
        merged.append(tagged)
    # Sort by updated_at descending, fall back to created_at
    merged.sort(
        key=lambda i: str(i.get('updated_at') or i.get('created_at') or ''),
        reverse=True,
    )
    # Show up to 20 entries (expanded from 6+4)
    merged = merged[:20]
    rows = []
    for idx, item in enumerate(merged):
        kind = item.get('_kind', 'completed')
        dot_class = 'good-dot' if kind == 'completed' else 'bad-dot'
        title = esc(item.get('title') or 'Action')
        status = esc(item.get('status') or kind)
        changed = item.get('changed_files') or []
        file_count = len(changed)
        file_info = f' | {file_count} file(s)' if file_count else ''
        # Compute duration from checkpoint timing if available
        duration = ''
        created = item.get('created_at') or ''
        updated = item.get('updated_at') or ''
        if created and updated and created < updated:
            try:
                from datetime import datetime

                c = datetime.fromisoformat(created.replace('Z', '+00:00'))
                u = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                delta = u - c
                total_secs = int(delta.total_seconds())
                if total_secs < 120:
                    duration = f' | {total_secs}s'
                elif total_secs < 7200:
                    duration = f' | {total_secs // 60}m'
                else:
                    duration = f' | {total_secs // 3600}h'
            except (ValueError, TypeError):
                pass
        dot_style = f'animation: pulse {1.5 + idx * 0.1}s ease-in-out infinite;' if kind == 'active' else ''
        rows.append(
            f'<li><span class="dot {dot_class}" style="{dot_style}"></span>'
            f'<b>{title}</b><small>{status}{duration}{file_info}</small></li>'
        )
    if not rows:
        rows.append(
            '<li><span class="dot"></span><b>No actions recorded yet.</b><small>Start a session to build progress.</small></li>'
        )
    return (
        '<style>'
        '@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:.5; } }'
        '</style>'
        '<ol class="timeline">' + ''.join(rows) + '</ol>'
    )


def attention_panel(attention: dict[str, Any]) -> str:
    items = attention.get('items') or []
    if not attention.get('requires_attention') or not items:
        return '<div class="empty">No attention needed right now.</div>'
    rows = []
    for item in items:
        severity = str(item.get('severity') or 'warning')
        sev_badge = {'blocking': 'bad', 'warning': 'warn', 'info': 'good'}.get(severity, 'warn')
        sev_html = f'<span class="badge {sev_badge}">{esc(severity)}</span>'
        related = item.get('related_modules') or []
        related_html = (
            '<div class="meta">Related: ' + ', '.join(esc(m) for m in related[:5]) + '</div>' if related else ''
        )
        changed = item.get('changed_files') or []
        file_html = '<div class="meta">Files: ' + ', '.join(esc(f) for f in changed[:8]) + '</div>' if changed else ''
        rows.append(
            f"""<article class="item">
  <div class="item-head"><strong>{esc(item.get('reason'))}</strong>{sev_html}</div>
  <p>{esc(item.get('suggested_next_step'))}</p>
  <div class="meta">{esc(item.get('action'))}</div>
  {related_html}
  {file_html}
</article>"""
        )
    return ''.join(rows)


def worker_panel(worker: dict[str, Any]) -> str:
    details = worker.get('developer_details') if isinstance(worker.get('developer_details'), dict) else {}
    provider = details.get('provider') or ''
    worker_name = details.get('worker_name') or ''
    developer = ''
    if provider or worker_name:
        developer = (
            '<details class="dev-details"><summary>Developer details</summary>'
            f'<p>Provider: {esc(provider or "not available")} | Worker: {esc(worker_name or "not available")}</p>'
            '</details>'
        )
    return f"""<p>{badge(worker.get('role') or 'Worker')}</p>
<p><b>Status:</b> {esc(worker.get('status') or 'not available')}</p>
<p><b>Routing mode:</b> {esc(worker.get('routing_mode') or 'not available')}</p>
<p><b>Why this worker:</b> {esc(worker.get('reason') or 'not available')}</p>
{developer}"""


def worker_readiness_panel(readiness: dict[str, Any]) -> str:
    rows = []
    for item in readiness.get('workers') or []:
        details = item.get('developer_details') if isinstance(item.get('developer_details'), dict) else {}
        developer = (
            '<details class="dev-details"><summary>Developer details</summary>'
            f'<p>Provider: {esc(details.get("provider") or "not available")} | Adapter: {esc(details.get("worker_name") or "not available")}</p>'
            f'<p>{esc(details.get("reason") or "")}</p>'
            '</details>'
        )
        rows.append(
            f"""<article class="item">
  <div class="item-head"><strong>{esc(item.get('role'))}</strong>{badge(item.get('status'))}</div>
  <div class="meta">{esc(item.get('safe_capability') or 'not available')}</div>
  {developer}
</article>"""
        )
    if not rows:
        rows.append('<div class="empty">Worker readiness is not available yet.</div>')
    return f"""<p>{badge('actual execution ' + str(readiness.get('actual_execution') or 'unknown'))}</p>
{''.join(rows)}"""


def learning_panel(learning: dict[str, Any]) -> str:
    items = learning.get('items') or []
    if not learning.get('available') or not items:
        return '<div class="empty">No cross-project learning yet. Run more sessions to build local patterns.</div>'
    rows = []
    for item in items:
        rows.append(
            f"""<article class="item">
  <div class="item-head"><strong>{esc(item.get('label') or 'Learning insight')}</strong>{badge(item.get('effect') or 'suggestion')}</div>
  <p>{esc(item.get('message') or 'Similar project signal is available.')}</p>
  <div class="meta">confidence {esc(item.get('confidence'))} | evidence {esc(item.get('evidence_count'))}</div>
</article>"""
        )
    return ''.join(rows)


def release_panel(release: dict[str, Any]) -> str:
    if not release.get('available'):
        return '<div class="empty">Run <code>agent release</code> to generate a local release workflow pack.</div>'
    blockers = release.get('blockers') or []
    path_items = [
        release.get('pr_draft_path') and f'PR draft: {release.get("pr_draft_path")}',
        release.get('release_notes_path') and f'Release notes: {release.get("release_notes_path")}',
        release.get('changelog_path') and f'Changelog: {release.get("changelog_path")}',
        release.get('report_path') and f'Workflow report: {release.get("report_path")}',
    ]
    learning_path = release.get('learning_informed_path') or []
    return f"""<div class="stats">
  <div class="stat"><span class="muted">Git status</span><b>{esc(release.get('git_status') or 'n/a')}</b></div>
  <div class="stat"><span class="muted">GitHub ready</span><b>{esc(str(bool(release.get('github_ready'))).lower())}</b></div>
  <div class="stat"><span class="muted">PR ready</span><b>{esc(str(bool(release.get('pr_ready'))).lower())}</b></div>
  <div class="stat"><span class="muted">Release score</span><b>{esc(release.get('release_score') if release.get('release_score') is not None else 'n/a')}</b></div>
</div>
<p>{badge(release.get('release_stage') or 'not available')} {badge('safety ' + str(release.get('safety') or 'unknown'))}</p>
<p><b>PR draft:</b> {esc(release.get('pr_title') or 'not available')}</p>
<p><b>Suggested command:</b> <code>{esc(release.get('suggested_next_command') or 'agent release')}</code></p>
<h3>Local artifacts</h3>
{list_items([item for item in path_items if item], empty='No release artifacts available yet.')}
<h3>Main blockers</h3>
{list_items(blockers, empty='No release blocker recorded.')}
<h3>Learning-informed release path</h3>
{list_items(learning_path, empty='No local learning path available yet.')}"""


def logic_rules_panel(logic_rules: dict[str, Any]) -> str:
    if not logic_rules:
        return '<div class="empty">Project logic and rules check is not available yet.</div>'
    coverage = logic_rules.get('coverage') if isinstance(logic_rules.get('coverage'), dict) else {}
    coverage_rows = [
        f'No fake citations: {str(bool(coverage.get("no_fake_citations"))).lower()}',
        f'No fake results: {str(bool(coverage.get("no_fake_results"))).lower()}',
        f'Evidence separation: {str(bool(coverage.get("evidence_separation"))).lower()}',
        f'Restricted access policy: {str(bool(coverage.get("restricted_access"))).lower()}',
    ]
    links = (logic_rules.get('missing_links') or []) + (logic_rules.get('weak_links') or [])
    return f"""<div class="stats">
  <div class="stat"><span class="muted">Rules</span><b>{esc(logic_rules.get('rules_status') or 'unknown')}</b></div>
  <div class="stat"><span class="muted">Workflow</span><b>{esc(logic_rules.get('workflow_chain') or 'unknown')}</b></div>
  <div class="stat"><span class="muted">Risk coverage</span><b>{esc(logic_rules.get('risk_coverage') or 'unknown')}</b></div>
  <div class="stat"><span class="muted">Overall</span><b>{esc(logic_rules.get('overall_status') or 'unknown')}</b></div>
</div>
<h3>Rule coverage</h3>
{list_items(coverage_rows)}
<h3>Missing or weak links</h3>
{list_items(links, empty='No missing or weak module link recorded.')}
<h3>Recommended fixes</h3>
{list_items(logic_rules.get('recommendations') or [], empty='No logic fix recommended right now.')}"""


def render_cockpit_html(data: dict[str, Any]) -> str:
    project = data.get('project') or {}
    session = data.get('session') or {}
    project_map = data.get('map') or {}
    progress = data.get('progress') or {}
    attention = data.get('attention') or {}
    safety = data.get('safety') or {}
    readiness = data.get('readiness') or {}
    worker = data.get('worker') or {}
    worker_readiness = data.get('worker_readiness') or {}
    learning = data.get('learning') or {}
    release = data.get('release') or {}
    logic_rules = data.get('logic_rules') or {}
    commands = ['agent status', 'agent continue', 'agent stop', 'agent undo']
    recent_changes = progress.get('recent_changes') or []
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(project.get('name') or 'Project')} Cockpit</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f7f9;
  --panel: #ffffff;
  --text: #16181d;
  --muted: #687083;
  --line: #e7e9ee;
  --good: #0a7f45;
  --good-bg: #eaf8f0;
  --warn: #a15c00;
  --warn-bg: #fff4de;
  --bad: #b42318;
  --bad-bg: #fff0ee;
  --neutral: #465166;
  --neutral-bg: #eef1f6;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; background: var(--bg); color: var(--text); }}
.shell {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
header {{ display: grid; gap: 14px; margin-bottom: 24px; }}
.eyebrow {{ color: var(--muted); font-size: 13px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }}
h1 {{ margin: 0; font-size: 38px; line-height: 1.05; letter-spacing: 0; }}
h2 {{ margin: 0 0 14px; font-size: 18px; letter-spacing: 0; }}
h3 {{ margin: 0; font-size: 15px; }}
p {{ color: var(--muted); line-height: 1.5; margin: 8px 0 0; }}
.goal {{ font-size: 17px; color: var(--muted); max-width: 860px; }}
.grid {{ display: grid; grid-template-columns: repeat(12, 1fr); gap: 16px; }}
.card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 18px; box-shadow: 0 1px 2px rgba(16,24,40,.04); }}
.span-4 {{ grid-column: span 4; }}
.span-6 {{ grid-column: span 6; }}
.span-8 {{ grid-column: span 8; }}
.span-12 {{ grid-column: span 12; }}
.stats {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fbfcfe; }}
.stat b {{ display: block; font-size: 22px; margin-top: 6px; }}
.badge {{ display: inline-flex; align-items: center; border-radius: 999px; padding: 4px 9px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
.badge.good {{ color: var(--good); background: var(--good-bg); }}
.badge.warn {{ color: var(--warn); background: var(--warn-bg); }}
.badge.bad {{ color: var(--bad); background: var(--bad-bg); }}
.badge.neutral {{ color: var(--neutral); background: var(--neutral-bg); }}
.item {{ border-top: 1px solid var(--line); padding: 14px 0; }}
.item:first-child {{ border-top: 0; padding-top: 0; }}
.item:last-child {{ padding-bottom: 0; }}
.item-head {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
.meta, .files, small {{ color: var(--muted); font-size: 13px; line-height: 1.45; }}
table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
th, td {{ border-top: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
ul {{ margin: 8px 0 0; padding-left: 18px; color: var(--muted); }}
.command-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }}
code {{ border: 1px solid var(--line); background: #f8fafc; border-radius: 6px; padding: 5px 8px; color: #20242c; }}
.timeline {{ list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }}
.timeline li {{ display: grid; grid-template-columns: 16px 1fr; column-gap: 10px; align-items: start; }}
.timeline small {{ display: block; margin-top: 3px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; background: #c8ceda; margin-top: 4px; }}
.good-dot {{ background: var(--good); }}
.bad-dot {{ background: var(--bad); }}
.empty {{ color: var(--muted); border: 1px dashed var(--line); border-radius: 8px; padding: 16px; background: #fbfcfe; }}
.muted {{ color: var(--muted); }}
.dev-details {{ margin-top: 10px; color: var(--muted); }}
.dev-details summary {{ cursor: pointer; font-size: 13px; }}
@media (max-width: 900px) {{ .span-4, .span-6, .span-8, .span-12 {{ grid-column: span 12; }} .stats {{ grid-template-columns: 1fr 1fr; }} }}
</style>
</head>
<body>
<main class="shell">
  <header>
    <div class="eyebrow">AI Project Operator</div>
    <h1>{esc(project.get('name') or 'Project Cockpit')}</h1>
    <div>{badge(project.get('state'))}</div>
    <p class="goal">{esc(project.get('main_goal') or 'No project goal available yet.')}</p>
    <p>Type: {esc(project.get('type') or 'not available')} | Last updated: {esc(project.get('last_updated') or data.get('generated_at') or 'not available')}</p>
  </header>

  <section class="grid">
    <div class="card span-12">
      <div class="stats">
        <div class="stat"><span class="muted">Modules</span><b>{len(project_map.get('modules') or [])}</b></div>
        <div class="stat"><span class="muted">Capabilities</span><b>{len(project_map.get('capabilities') or [])}</b></div>
        <div class="stat"><span class="muted">Next actions</span><b>{len(project_map.get('next_actions') or [])}</b></div>
        <div class="stat"><span class="muted">Readiness</span><b>{esc(readiness.get('for_094') or 'n/a')}</b></div>
      </div>
    </div>

    <section class="card span-6">
      <h2>Autopilot Session</h2>
      <p>Status {badge(session.get('status'))}</p>
      <p><b>Goal:</b> {esc(session.get('goal') or 'No session yet.')}</p>
      <p><b>Current action:</b> {esc(session.get('current_action') or 'not available')}</p>
      <p><b>Next action:</b> {esc(session.get('next_action') or 'not available')}</p>
      <div class="command-list">{''.join(f'<code>{esc(command)}</code>' for command in commands)}</div>
    </section>

    <section class="card span-6">
      <h2>Safety / Recovery</h2>
      <p>{badge('undo available' if safety.get('undo_available') else 'undo not available')}</p>
      <p><b>Checkpoints:</b> {esc('available' if safety.get('checkpoints_available') else 'not available')}</p>
      <p><b>Last checkpoint:</b> {esc(safety.get('last_checkpoint') or 'not available')}</p>
      <p><b>Recent changes:</b></p>
      {list_items(recent_changes, empty='No file changes recorded yet.')}
    </section>

    <section class="card span-4">
      <h2>Worker</h2>
      {worker_panel(worker)}
    </section>

    <section class="card span-8">
      <h2>Worker Readiness</h2>
      {worker_readiness_panel(worker_readiness)}
    </section>

    <section class="card span-12">
      <h2>Cross-project Learning</h2>
      <p>Learned from similar local project sessions.</p>
      {learning_panel(learning)}
    </section>

    <section class="card span-12">
      <h2>Release / PR</h2>
      <p>Local release workflow pack for review-ready handoff.</p>
      {release_panel(release)}
    </section>

    <section class="card span-12">
      <h2>Project Logic / Rules</h2>
      <p>Checks whether project rules are available and whether mapped modules form a usable workflow.</p>
      {logic_rules_panel(logic_rules)}
    </section>

    <section class="card span-8">
      <h2>Project Map</h2>
      {module_cards(project_map.get('modules') or [])}
    </section>

    <section class="card span-4">
      <h2>Attention Required</h2>
      {attention_panel(attention)}
    </section>

    <section class="card span-12">
      <h2>Capabilities</h2>
      {capability_rows(project_map.get('capabilities') or [])}
    </section>

    <section class="card span-6">
      <h2>Risks</h2>
      {risk_rows(project_map.get('risks') or [])}
    </section>

    <section class="card span-6">
      <h2>Progress Timeline</h2>
      {timeline(progress)}
    </section>

    <section class="card span-12">
      <h2>Next Actions</h2>
      {action_cards(project_map.get('next_actions') or [])}
    </section>
  </section>
</main>
</body>
</html>
"""
