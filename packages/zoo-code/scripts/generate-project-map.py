#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_RE = re.compile(r"(^\.env(?:\..*)?$|secret|token|credential|private|\.pem$|\.key$)", re.I)
SKIP_DIRS = {
    ".git", ".zoo-agent", ".venv", "venv", "node_modules", "dist", "build",
    "coverage", ".pytest_cache", ".mypy_cache", "__pycache__", ".next", ".turbo",
}
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".rs"}
TEST_HINTS = {"test", "tests", "__tests__", "spec", "e2e"}
DOC_SUFFIXES = {".md", ".rst", ".adoc"}
CONFIG_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "go.mod", "Cargo.toml",
    "pom.xml", "build.gradle", "build.gradle.kts", "tsconfig.json",
}
ENTRYPOINT_NAMES = {"main", "index", "server", "app", "cli"}
RISK_RE = re.compile(r"auth|security|permission|pii|payment|billing|stripe|migration|database|schema|credential|config", re.I)
IMPORT_RE = re.compile(
    r"(?:from\s+['\"]([^'\"]+)['\"]|import\s+[^'\"]*from\s+['\"]([^'\"]+)['\"]|require\(\s*['\"]([^'\"]+)['\"]\s*\)|^\s*from\s+([A-Za-z0-9_\.]+)\s+import|^\s*import\s+([A-Za-z0-9_\.]+))",
    re.M,
)


def secret_like(path: Path) -> bool:
    return any(SECRET_RE.search(part) for part in path.parts)


def skipped(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts) or secret_like(path)


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def safe_read(path: Path) -> str:
    if path.stat().st_size > 2_000_000:
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def module_root(parts: tuple[str, ...]) -> str:
    if not parts:
        return "root"
    first = parts[0]
    if len(parts) == 1:
        return "root"
    if first in {"packages", "apps", "services", "modules"} and len(parts) >= 2:
        return f"{first}/{parts[1]}"
    if first in {"src", "app", "lib", "internal", "pkg", "cmd"} and len(parts) >= 2:
        second = parts[1]
        if second.endswith((".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".rs")):
            return first
        return f"{first}/{second}"
    if first in {"docs", "test", "tests", "__tests__", "spec", "e2e", "config", "data", "scripts"}:
        return first
    return first


def module_id_for(path: Path) -> str:
    return module_root(path.parts)


def classify_file(path: Path) -> str:
    parts = {p.lower() for p in path.parts}
    if path.name in CONFIG_NAMES or path.suffix in {".yaml", ".yml", ".toml", ".ini"}:
        return "config"
    if path.suffix in DOC_SUFFIXES or "docs" in parts:
        return "doc"
    if parts & TEST_HINTS or re.search(r"(^|[-_.])(test|spec)([-_.]|$)", path.name, re.I):
        return "test"
    if path.suffix in SOURCE_SUFFIXES:
        return "source"
    return "other"


def risk_level(path: Path) -> str:
    text = path.as_posix()
    if re.search(r"auth|security|permission|pii|payment|billing|stripe|migration", text, re.I):
        return "high"
    if RISK_RE.search(text):
        return "medium"
    return "low"


def entrypoint(path: Path) -> bool:
    stem = path.stem.lower()
    if stem in ENTRYPOINT_NAMES and path.suffix in SOURCE_SUFFIXES:
        return True
    text = path.as_posix().lower()
    return "/api/" in text or text.startswith("routes/") or text.startswith("pages/api/")


def scan_files(root: Path, max_files: int) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob("*"):
        if skipped(path.relative_to(root)):
            continue
        if not path.is_file():
            continue
        kind = classify_file(path.relative_to(root))
        if kind in {"source", "test", "doc", "config"}:
            out.append(path)
        if len(out) >= max_files:
            break
    return sorted(out)


def ensure_module(modules: dict[str, dict[str, Any]], mid: str) -> dict[str, Any]:
    if mid not in modules:
        modules[mid] = {
            "module_id": mid,
            "name": mid.replace("/", " ").replace("_", " ").title(),
            "owned_paths": set(),
            "source_files": [],
            "test_files": [],
            "docs": [],
            "configs": [],
            "entrypoints": [],
            "provides": ["unknown"],
            "consumes": ["unknown"],
            "risk_level": "low",
            "architecture_notes": "unknown",
        }
    return modules[mid]


def add_file(module: dict[str, Any], rel_path: str, kind: str, is_entrypoint: bool, risk: str) -> None:
    root = "/".join(rel_path.split("/")[:2]) if "/" in rel_path else rel_path
    module["owned_paths"].add(root)
    if kind == "source":
        module["source_files"].append(rel_path)
    elif kind == "test":
        module["test_files"].append(rel_path)
    elif kind == "doc":
        module["docs"].append(rel_path)
    elif kind == "config":
        module["configs"].append(rel_path)
    if is_entrypoint:
        module["entrypoints"].append(rel_path)
    if risk == "high":
        module["risk_level"] = "high"
    elif risk == "medium" and module["risk_level"] == "low":
        module["risk_level"] = "medium"


def imported_specs(path: Path) -> list[str]:
    if path.suffix not in SOURCE_SUFFIXES:
        return []
    text = safe_read(path)
    specs: list[str] = []
    for match in IMPORT_RE.findall(text):
        spec = next((x for x in match if x), "")
        if spec:
            specs.append(spec)
    return specs[:100]


def spec_to_module(spec: str, source: Path, root: Path) -> tuple[str, str] | None:
    if spec.startswith("."):
        base = (source.parent / spec).resolve()
        try:
            target = base.relative_to(root.resolve())
        except ValueError:
            return None
        return ("internal", module_id_for(target))
    normalized = spec.replace(".", "/")
    candidate = Path(normalized)
    if candidate.parts and candidate.parts[0] in {"src", "app", "lib", "packages", "apps", "services", "modules", "internal", "pkg", "cmd"}:
        return ("internal", module_id_for(candidate))
    return ("external", spec.split("/")[0])


def build_dependencies(files: list[Path], root: Path, modules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    known = set(modules)
    deps: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in files:
        source_rel = path.relative_to(root)
        source_module = module_id_for(source_rel)
        for spec in imported_specs(path):
            mapped = spec_to_module(spec, path, root)
            if not mapped:
                continue
            dep_type, target = mapped
            if dep_type == "internal" and target == source_module:
                continue
            if dep_type == "internal" and target not in known:
                continue
            key = (source_module, target, dep_type)
            deps.setdefault(key, {
                "from": source_module,
                "to": target,
                "type": dep_type,
                "evidence": [],
                "allowed": "unknown",
            })
            if len(deps[key]["evidence"]) < 10:
                deps[key]["evidence"].append(source_rel.as_posix())
    return sorted(deps.values(), key=lambda x: (x["from"], x["to"], x["type"]))


def normalize_modules(modules: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for module in modules.values():
        clean = dict(module)
        clean["owned_paths"] = sorted(clean["owned_paths"])
        for key in ["source_files", "test_files", "docs", "configs", "entrypoints"]:
            clean[key] = sorted(set(clean[key]))[:200]
        out.append(clean)
    return sorted(out, key=lambda x: x["module_id"])


def boundaries(project_map: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "generated_by": "generate-project-map.py",
        "project_root": project_map["project_root"],
        "status": "draft",
        "confidence": "low",
        "layers": [
            {"layer": "domain", "allowed_to_depend_on": [], "notes": "Pure domain should avoid IO/env/network/UI."},
            {"layer": "application", "allowed_to_depend_on": ["domain"], "notes": "Use ports for infrastructure."},
            {"layer": "infrastructure", "allowed_to_depend_on": ["application", "domain"], "notes": "Implements adapters/providers."},
            {"layer": "api_ui", "allowed_to_depend_on": ["application", "domain"], "notes": "Adapts external input/output."},
            {"layer": "tests", "allowed_to_depend_on": ["api_ui", "application", "domain", "infrastructure"], "notes": "Tests may depend on fixture contracts."},
        ],
        "module_layer_assignments": [
            {"module_id": m["module_id"], "layer": infer_layer(m["module_id"]), "confidence": "heuristic"}
            for m in project_map.get("modules", [])
        ],
        "unknowns": ["Confirm module layer assignments before high-risk architecture changes."],
    }


def infer_layer(module_id: str) -> str:
    text = module_id.lower()
    if any(x in text for x in ["ui", "component", "page", "route", "api"]):
        return "api_ui"
    if any(x in text for x in ["infra", "adapter", "provider", "repository", "data", "db"]):
        return "infrastructure"
    if any(x in text for x in ["domain", "model", "entity"]):
        return "domain"
    if any(x in text for x in ["test", "spec", "e2e"]):
        return "tests"
    return "application"


def project_map(root: Path, max_files: int) -> dict[str, Any]:
    files = scan_files(root, max_files)
    modules: dict[str, dict[str, Any]] = {}
    for path in files:
        rel_path = Path(rel(path, root))
        mid = module_id_for(rel_path)
        module = ensure_module(modules, mid)
        add_file(module, rel_path.as_posix(), classify_file(rel_path), entrypoint(rel_path), risk_level(rel_path))
    normalized = normalize_modules(modules)
    data = {
        "schema_version": "1.0",
        "generated_by": "generate-project-map.py",
        "project_root": str(root.resolve()),
        "module_count": len(normalized),
        "scanned_file_count": len(files),
        "modules": normalized,
        "dependencies": build_dependencies(files, root, modules),
        "unknowns": [],
        "notes": [
            "This is a lightweight project architecture map, not a code style policy.",
            "Secrets and secret-like files are skipped by name.",
            "Use AGENTS.md or local project rules for coding conventions.",
        ],
    }
    if len(files) >= max_files:
        data["unknowns"].append("scan_file_limit_reached")
    if not normalized:
        data["unknowns"].append("no_modules_detected")
    return data


def render_md(data: dict[str, Any]) -> str:
    lines = [
        "# Project Architecture Map",
        "",
        f"- project_root: `{data['project_root']}`",
        f"- module_count: `{data['module_count']}`",
        f"- scanned_file_count: `{data['scanned_file_count']}`",
        "",
        "## Modules",
        "",
    ]
    for module in data.get("modules", []):
        lines.append(f"### {module['module_id']}")
        lines.append(f"- risk_level: `{module['risk_level']}`")
        lines.append(f"- owned_paths: {', '.join(f'`{x}`' for x in module.get('owned_paths', [])) or '`unknown`'}")
        if module.get("entrypoints"):
            lines.append(f"- entrypoints: {', '.join(f'`{x}`' for x in module['entrypoints'])}")
        if module.get("source_files"):
            lines.append(f"- source_files: {len(module['source_files'])}")
        if module.get("test_files"):
            lines.append(f"- test_files: {len(module['test_files'])}")
        if module.get("docs"):
            lines.append(f"- docs: {len(module['docs'])}")
        lines.append("")
    lines.extend(["## Dependencies", ""])
    for dep in data.get("dependencies", [])[:200]:
        lines.append(f"- `{dep['from']}` -> `{dep['to']}` ({dep['type']})")
    if not data.get("dependencies"):
        lines.append("- none detected")
    lines.extend(["", "## Unknowns", ""])
    lines.extend([f"- `{x}`" for x in data.get("unknowns", [])] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate .zoo-agent/project-map.json and project-map.md without reading secret-like files.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output-json", default=".zoo-agent/project-map.json")
    parser.add_argument("--output-md", default=".zoo-agent/project-map.md")
    parser.add_argument("--architecture-boundaries", default=".zoo-agent/architecture-boundaries.json")
    parser.add_argument("--max-files", type=int, default=5000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-boundaries", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    data = project_map(root, args.max_files)
    md = render_md(data)
    boundary_data = boundaries(data)
    if args.dry_run:
        print(json.dumps({"project_map": data, "architecture_boundaries": boundary_data}, indent=2))
        return 0
    out_json = root / args.output_json
    out_md = root / args.output_md
    out_boundaries = root / args.architecture_boundaries
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    if args.force_boundaries or not out_boundaries.exists():
        out_boundaries.write_text(json.dumps(boundary_data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "pass",
        "project_map": str(out_json),
        "project_map_md": str(out_md),
        "architecture_boundaries": str(out_boundaries),
        "module_count": data["module_count"],
        "scanned_file_count": data["scanned_file_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
