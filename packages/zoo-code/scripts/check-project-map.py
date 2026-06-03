#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(r"(^\.env(?:\..*)?$|secret|token|credential|private|\.pem$|\.key$)", re.I)
SKIP_DIRS = {".git", ".zoo-agent", ".venv", "venv", "node_modules", "dist", "build", "coverage", "__pycache__"}
INTERESTING_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".rs", ".md", ".yaml", ".yml", ".toml", ".json"}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts) or any(SECRET_RE.search(part) for part in path.parts)


def add(issues: list[dict[str, Any]], typ: str, severity: str = "blocker", **extra: Any) -> None:
    issues.append({"severity": severity, "type": typ, **extra})


def newest_interesting_file(root: Path) -> tuple[Path | None, float]:
    newest: tuple[Path | None, float] = (None, 0.0)
    for path in root.rglob("*"):
        try:
            rel = path.relative_to(root)
        except ValueError:
            continue
        if skipped(rel) or not path.is_file() or path.suffix not in INTERESTING_SUFFIXES:
            continue
        mtime = path.stat().st_mtime
        if mtime > newest[1]:
            newest = (path, mtime)
    return newest


def module_paths(data: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for module in data.get("modules", []):
        for key in ["owned_paths", "source_files", "test_files", "docs", "configs", "entrypoints"]:
            for item in module.get(key, []) or []:
                paths.add(str(item).replace("\\", "/"))
    return paths


def mapped(path: str, known_paths: set[str]) -> bool:
    normalized = path.replace("\\", "/")
    return any(normalized == item or normalized.startswith(item.rstrip("/") + "/") for item in known_paths)


def check(root: Path, project_map_path: Path, boundaries_path: Path, changed_files: list[str], allow_stale: bool) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not project_map_path.exists():
        add(issues, "missing_project_map", fix="run generate-project-map.py")
        return {"status": "fail", "issues": issues, "warnings": warnings}
    data = load_json(project_map_path, {})
    if data.get("schema_version") != "1.0":
        add(issues, "unsupported_project_map_schema", schema_version=data.get("schema_version"))
    if not data.get("modules"):
        add(issues, "project_map_has_no_modules")
    if not boundaries_path.exists():
        warnings.append({"severity": "warning", "type": "missing_architecture_boundaries", "fix": "run generate-project-map.py or create architecture-boundaries.json"})
    newest, newest_time = newest_interesting_file(root)
    if newest and newest_time > project_map_path.stat().st_mtime and not allow_stale:
        add(issues, "stale_project_map", newest_file=str(newest.relative_to(root)), fix="run generate-project-map.py")
    known_paths = module_paths(data)
    for changed in changed_files:
        if changed and not mapped(changed, known_paths):
            add(issues, "unmapped_changed_file", changed_file=changed, fix="update project-map.json or classify the file before review")
    for module in data.get("modules", []):
        if module.get("risk_level") in {"high", "critical"} and module.get("architecture_notes") == "unknown":
            warnings.append({"severity": "warning", "type": "high_risk_module_architecture_unknown", "module_id": module.get("module_id")})
    return {
        "schema_version": "1.0",
        "status": "pass" if not issues else "fail",
        "project_map": str(project_map_path),
        "architecture_boundaries": str(boundaries_path),
        "issues": issues,
        "warnings": warnings,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Project Map Check", "", f"- status: `{report.get('status')}`", "", "## Issues", ""]
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report.get("issues", [])] or ["- none"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- `{json.dumps(x, ensure_ascii=False)}`" for x in report.get("warnings", [])] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check project-map freshness and changed-file coverage.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--project-map", default=".zoo-agent/project-map.json")
    parser.add_argument("--architecture-boundaries", default=".zoo-agent/architecture-boundaries.json")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--allow-stale", action="store_true")
    parser.add_argument("--output-json", default=".zoo-agent/project-map-check.json")
    parser.add_argument("--output-md", default=".zoo-agent/project-map-check.md")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    report = check(root, root / args.project_map, root / args.architecture_boundaries, args.changed_file, args.allow_stale)
    if not args.dry_run:
        out_json = root / args.output_json
        out_md = root / args.output_md
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        out_md.write_text(render_md(report), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
