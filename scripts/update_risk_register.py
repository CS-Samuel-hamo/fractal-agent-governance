#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
from pathlib import Path

OPEN_STATUSES = {'open', 'blocked', 'needs_review', 'carried'}


def utc_now() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def git_root(workspace: Path) -> Path:
    proc = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        cwd=workspace,
        text=True,
        encoding='utf-8',
        errors='replace',
        capture_output=True,
    )
    if proc.returncode:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or 'workspace is not a git repository')
    return Path(proc.stdout.strip()).resolve()


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def next_risk_id(risks: list[dict]) -> str:
    used = set()
    for risk in risks:
        raw = str(risk.get('risk_id') or risk.get('id') or '')
        if raw.startswith('risk-'):
            try:
                used.add(int(raw.split('-', 1)[1]))
            except ValueError:
                pass
    index = 1
    while index in used:
        index += 1
    return f'risk-{index:03d}'


def normalize_register(payload: dict, run_id: str) -> dict:
    risks = payload.get('risks') if isinstance(payload.get('risks'), list) else []
    normalized = []
    for risk in risks:
        if isinstance(risk, dict):
            normalized.append(risk)
    return {
        'schema_version': payload.get('schema_version') or '1.0',
        'generated_by': payload.get('generated_by') or 'update_risk_register.py',
        'run_id': payload.get('run_id') or run_id,
        'updated_at': utc_now(),
        'risks': normalized,
    }


def apply_add(register: dict, args) -> dict:
    risks = register['risks']
    risk_id = args.risk_id or next_risk_id(risks)
    existing = next((item for item in risks if (item.get('risk_id') or item.get('id')) == risk_id), None)
    payload = {
        'risk_id': risk_id,
        'title': args.title,
        'severity': args.severity,
        'status': args.status,
        'source': args.source,
        'evidence': args.evidence,
        'owner': args.owner,
        'carry_to_next_phase': bool(args.carry_to_next_phase),
        'created_at': utc_now(),
        'updated_at': utc_now(),
    }
    if existing:
        existing.update({key: value for key, value in payload.items() if value not in {'', None}})
        existing['updated_at'] = utc_now()
    else:
        risks.append(payload)
    return {'status': 'added_or_updated', 'risk_id': risk_id}


def apply_close(register: dict, args) -> dict:
    for risk in register['risks']:
        if (risk.get('risk_id') or risk.get('id')) == args.risk_id:
            risk['status'] = 'closed' if args.status == 'open' else args.status
            risk['resolution'] = args.resolution
            risk['updated_at'] = utc_now()
            return {'status': 'closed', 'risk_id': args.risk_id}
    return {'status': 'missing_risk', 'risk_id': args.risk_id}


def seed_from_quality_gate(register: dict, run_dir: Path) -> dict:
    gate = load_json(run_dir / 'quality-gate.json')
    blockers = gate.get('blockers') if isinstance(gate.get('blockers'), list) else []
    created = []
    for blocker in blockers:
        if not isinstance(blocker, dict):
            continue
        blocker_id = str(blocker.get('id') or '')
        if not blocker_id:
            continue
        existing = [
            item
            for item in register['risks']
            if item.get('source') == 'quality_gate' and item.get('source_blocker_id') == blocker_id
        ]
        if existing:
            continue
        risk_id = next_risk_id(register['risks'])
        register['risks'].append(
            {
                'risk_id': risk_id,
                'title': blocker.get('message') or blocker_id,
                'severity': blocker.get('severity') or 'medium',
                'status': 'open',
                'source': 'quality_gate',
                'source_blocker_id': blocker_id,
                'evidence': blocker.get('evidence') or '',
                'owner': '',
                'carry_to_next_phase': True,
                'created_at': utc_now(),
                'updated_at': utc_now(),
            }
        )
        created.append(risk_id)
    return {'status': 'seeded_from_quality_gate', 'created_risk_ids': created}


def summarize(register: dict) -> dict:
    open_risks = [risk for risk in register['risks'] if str(risk.get('status') or 'open').lower() in OPEN_STATUSES]
    register['open_risk_count'] = len(open_risks)
    register['risk_count'] = len(register['risks'])
    return register


def write_markdown(path: Path, register: dict, action_result: dict) -> None:
    lines = [
        f'# Risk Register: {register["run_id"]}',
        '',
        f'- updated_at: {register["updated_at"]}',
        f'- risk_count: {register.get("risk_count", 0)}',
        f'- open_risk_count: {register.get("open_risk_count", 0)}',
        f'- last_action: {action_result.get("status", "unknown")}',
        '',
        '## Risks',
        '',
    ]
    if not register['risks']:
        lines.append('- none')
    for risk in register['risks']:
        lines.append(
            f'- {risk.get("risk_id")}: {risk.get("severity", "")} / {risk.get("status", "")} / {risk.get("title", "")}'
        )
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser(description='Create, update, close, or seed a Zoo run risk register.')
    ap.add_argument('--workspace', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--risk-id', default='')
    ap.add_argument('--title', default='')
    ap.add_argument('--severity', default='medium', choices=['low', 'medium', 'high', 'critical'])
    ap.add_argument('--status', default='open')
    ap.add_argument('--source', default='')
    ap.add_argument('--evidence', default='')
    ap.add_argument('--owner', default='')
    ap.add_argument('--resolution', default='')
    ap.add_argument('--carry-to-next-phase', action='store_true')
    ap.add_argument('--add', action='store_true')
    ap.add_argument('--close', action='store_true')
    ap.add_argument('--seed-from-quality-gate', action='store_true')
    args = ap.parse_args()

    actions = [args.add, args.close, args.seed_from_quality_gate]
    if sum(1 for item in actions if item) != 1:
        raise SystemExit('Choose exactly one of --add, --close, or --seed-from-quality-gate.')
    if args.add and not args.title:
        raise SystemExit('--title is required with --add.')
    if args.close and not args.risk_id:
        raise SystemExit('--risk-id is required with --close.')

    repo_root = git_root(Path(args.workspace).resolve())
    run_dir = repo_root / '.zoo-agent' / 'runs' / args.run_id
    path = run_dir / 'risk-register.json'
    register = normalize_register(load_json(path), args.run_id)

    if args.add:
        result = apply_add(register, args)
    elif args.close:
        result = apply_close(register, args)
    else:
        result = seed_from_quality_gate(register, run_dir)

    summarize(register)
    write_json(path, register)
    write_markdown(path.with_suffix('.md'), register, result)
    output = {'result': result, 'risk_register': register}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if result.get('status') != 'missing_risk' else 20


if __name__ == '__main__':
    raise SystemExit(main())
