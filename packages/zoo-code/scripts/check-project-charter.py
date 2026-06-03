#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


MATERIAL_FIELDS = [
    "mission",
    "target_users",
    "product_goals",
    "technical_goals",
    "non_goals",
    "success_criteria",
    "quality_bar",
    "data_security_constraints",
    "risk_tolerance",
    "human_gates",
    "fallback_abort_conditions",
]
SECRET_PATTERNS = [
    ("private_key_block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}")),
    ("api_key_assignment", re.compile(r"(?i)\b(api_key|token|secret|password|credential)\b\s*[:=]\s*['\"]?(?!<|your_|example|placeholder)[A-Za-z0-9_./+\-=]{16,}")),
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def unknown(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"", "unknown", "tbd", "todo"}
    if isinstance(value, list):
        return not value or all(unknown(item) for item in value)
    return False


def add(issues: list[dict[str, Any]], typ: str, severity: str = "blocker", **extra: Any) -> None:
    issues.append({"severity": severity, "type": typ, **extra})


def scan_secret_patterns(path: Path, issues: list[dict[str, Any]]) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return
    for idx, line in enumerate(lines, start=1):
        for typ, regex in SECRET_PATTERNS:
            if regex.search(line):
                add(issues, "secret_like_content", path=str(path), line=idx, secret_type=typ)


def check(charter_json: Path, charter_md: Path, allow_draft: bool) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not charter_json.exists():
        add(issues, "missing_project_charter_json", fix="run init-project-charter.py")
    if not charter_md.exists():
        add(issues, "missing_project_charter_md", fix="run init-project-charter.py")
    data = load_json(charter_json)
    if data and data.get("schema_version") != "1.0":
        add(issues, "unsupported_project_charter_schema", schema_version=data.get("schema_version"))
    for field in MATERIAL_FIELDS:
        if unknown(data.get(field)):
            target = warnings if allow_draft else issues
            add(target, "material_charter_field_unknown", field=field, severity="warning" if allow_draft else "blocker")
    scan_secret_patterns(charter_json, issues)
    scan_secret_patterns(charter_md, issues)
    return {
        "schema_version": "1.0",
        "status": "pass" if not issues else "fail",
        "project_charter": str(charter_json),
        "project_charter_md": str(charter_md),
        "issues": issues,
        "warnings": warnings,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Project Charter Check", "", f"- status: `{report['status']}`", "", "## Issues", ""]
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report.get("issues", [])] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report.get("warnings", [])] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check project charter completeness without printing secret values.")
    parser.add_argument("--project-charter", default=".zoo-agent/project-charter.json")
    parser.add_argument("--project-charter-md", default="docs/project-charter.md")
    parser.add_argument("--allow-draft", action="store_true")
    parser.add_argument("--output-json", default=".zoo-agent/project-charter-check.json")
    parser.add_argument("--output-md", default=".zoo-agent/project-charter-check.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report = check(Path(args.project_charter), Path(args.project_charter_md), args.allow_draft)
    if not args.dry_run:
        out_json = Path(args.output_json)
        out_md = Path(args.output_md)
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        out_md.write_text(render_md(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
