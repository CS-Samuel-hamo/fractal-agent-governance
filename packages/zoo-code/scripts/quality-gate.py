#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path


def load_json(path: Path) -> dict:
    try: return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception: return {}


def has_section(text: str, title: str) -> bool:
    wanted = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return any(re.sub(r"[^a-z0-9]+", " ", line.strip().strip("#:*` ").lower()).strip() == wanted for line in text.splitlines())


def present(value: object) -> bool:
    if value is None: return False
    if isinstance(value, str): return value.strip().lower() not in {"", "unknown", "tbd", "todo", "none"}
    if isinstance(value, list): return bool(value)
    return True


def find_ledger(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.exists() else p
    ledgers = sorted(Path(".zoo-agent/runs").glob("*/obligation-ledger.json")) if Path(".zoo-agent/runs").exists() else []
    return ledgers[-1] if ledgers else None


def obligation_checks(path: Path | None) -> list[dict]:
    checks = [{"name": "obligation_ledger_exists", "status": "pass" if path and path.exists() else "fail", "path": str(path) if path else "unknown"}]
    if not path or not path.exists():
        return checks
    data = load_json(path)
    required_open = []
    deferred_bad = []
    escalated_bad = []
    na_bad = []
    security_triggered = False
    operational_triggered = False
    for item in data.get("implicit_obligations", []):
        status = item.get("status", "required")
        text = json.dumps(item).lower()
        security_triggered = security_triggered or any(k in text for k in ["security", "auth", "payment", "pii", "credential"])
        operational_triggered = operational_triggered or any(k in text for k in ["operational", "logging", "metrics", "tracing", "runbook", "rollback"])
        if status == "required" and not (present(item.get("verification")) and present(item.get("evidence"))):
            required_open.append(item.get("obligation_id", "unknown"))
        if status == "deferred" and not (present(item.get("owner_mode")) and present(item.get("why_required"))):
            deferred_bad.append(item.get("obligation_id", "unknown"))
        if status == "escalated" and not (present(item.get("escalation_id")) or item.get("escalation_required") is True):
            escalated_bad.append(item.get("obligation_id", "unknown"))
        if status == "not_applicable" and not present(item.get("evidence")):
            na_bad.append(item.get("obligation_id", "unknown"))
    checks.append({"name": "required_obligations_closed", "status": "pass" if not required_open else "fail", "open": required_open})
    checks.append({"name": "deferred_obligations_owned", "status": "pass" if not deferred_bad else "fail", "bad": deferred_bad})
    checks.append({"name": "escalated_obligations_have_id", "status": "pass" if not escalated_bad else "fail", "bad": escalated_bad})
    checks.append({"name": "not_applicable_have_evidence", "status": "pass" if not na_bad else "fail", "bad": na_bad})
    run_dir = path.parent
    checks.append({"name": "security_gate_when_triggered", "status": "pass" if not security_triggered or (run_dir / "security-gate.json").exists() else "fail"})
    checks.append({"name": "operational_readiness_when_triggered", "status": "pass" if not operational_triggered or (run_dir / "operational-readiness.json").exists() else "fail"})
    return checks


def diagnostics_checks(path: Path | None) -> list[dict]:
    if not path or not path.exists():
        return [{"name": "diagnostics_report", "status": "unknown", "path": str(path) if path else "unknown"}]
    data = load_json(path)
    new_errors = data.get("new_errors", [])
    status = data.get("status", "unknown")
    checks = [{"name": "diagnostics_report_present", "status": "pass", "diagnostics_status": status}]
    checks.append({"name": "no_new_error_diagnostics", "status": "pass" if not new_errors and status != "fail" else "fail", "new_errors": new_errors})
    return checks


def evaluate(profile_path: Path, evidence_path: Path | None, ledger_path: Path | None, diagnostics_path: Path | None = None) -> dict:
    profile = load_json(profile_path) if profile_path.exists() else {}
    commands = profile.get("commands", {}) if isinstance(profile, dict) else {}
    text = evidence_path.read_text(encoding="utf-8", errors="replace") if evidence_path and evidence_path.exists() else ""
    checks = [
        {"name": "project_profile_exists", "status": "pass" if profile else "fail", "path": str(profile_path)},
        {"name": "test_command_recorded", "status": "pass" if isinstance(commands, dict) and commands.get("test") not in (None, "", "unknown") else "fail", "value": commands.get("test", "unknown") if isinstance(commands, dict) else "unknown"},
    ]
    missing = [s for s in ["Impact Map", "Files Changed", "Tests Run", "Acceptance Mapping", "Risks", "Rollback Plan"] if not has_section(text, s)]
    checks.append({"name": "completion_evidence_complete", "status": "pass" if not missing else "fail", "missing": missing})
    checks.append({"name": "security_checklist_declared", "status": "pass" if has_section(text, "Security Checklist") or "security" in text.lower() else "fail"})
    checks.append({"name": "architecture_boundary_declared", "status": "pass" if has_section(text, "Architecture Boundary") or "architecture" in text.lower() else "fail"})
    checks.extend(obligation_checks(ledger_path))
    if diagnostics_path and diagnostics_path.exists():
        checks.extend(diagnostics_checks(diagnostics_path))
    warnings = [f"{k} command is unknown" for k in ["lint", "typecheck", "build"] if isinstance(commands, dict) and commands.get(k) == "unknown"]
    status = "pass" if all(c["status"] == "pass" for c in checks) else "fail"
    return {"status": status, "checks": checks, "warnings": warnings}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--evidence")
    ap.add_argument("--output")
    ap.add_argument("--profile", default=".zoo-agent/project-profile.json")
    ap.add_argument("--obligation-ledger")
    ap.add_argument("--diagnostics-report")
    args = ap.parse_args()
    diag = Path(args.diagnostics_report) if args.diagnostics_report else None
    report = evaluate(Path(args.profile), Path(args.evidence) if args.evidence else None, find_ledger(args.obligation_ledger), diag)
    text = json.dumps(report, indent=2)
    if args.output and not args.dry_run:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
