#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Any

SECRET_RE = re.compile(r"(^\.env|secret|token|credential|private|\.pem$|\.key$)", re.I)
SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".java", ".kt", ".rs"}


def secret_like(path: Path) -> bool:
    return any(SECRET_RE.search(part) for part in path.parts)


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def package_manager(root: Path) -> str:
    for marker, manager in [("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("package-lock.json", "npm"), ("uv.lock", "uv"), ("poetry.lock", "poetry"), ("requirements.txt", "pip"), ("go.mod", "go"), ("pom.xml", "maven"), ("build.gradle", "gradle"), ("build.gradle.kts", "gradle"), ("Cargo.lock", "cargo")]:
        if (root / marker).exists():
            return manager
    return "npm" if (root / "package.json").exists() else "unknown"


def languages(root: Path) -> list[str]:
    out = []
    if (root / "package.json").exists(): out.append("TypeScript/JavaScript")
    if any((root / f).exists() for f in ["pyproject.toml", "requirements.txt", "setup.py"]): out.append("Python")
    if (root / "go.mod").exists(): out.append("Go")
    if any((root / f).exists() for f in ["pom.xml", "build.gradle", "build.gradle.kts"]): out.append("Java/Kotlin")
    if (root / "Cargo.toml").exists(): out.append("Rust")
    return out or ["unknown"]


def commands(root: Path) -> dict[str, str]:
    result = {"test": "unknown", "lint": "unknown", "typecheck": "unknown", "build": "unknown"}
    pkg = root / "package.json"
    if pkg.exists():
        scripts = read_json(pkg).get("scripts", {})
        if isinstance(scripts, dict):
            for key in result:
                if isinstance(scripts.get(key), str):
                    result[key] = f"npm run {key}"
    if (root / "go.mod").exists(): result["test"] = "go test ./..."
    if (root / "pom.xml").exists(): result.update({"test": "mvn test", "build": "mvn package"})
    if (root / "Cargo.toml").exists(): result.update({"test": "cargo test", "build": "cargo build"})
    if ((root / "pyproject.toml").exists() or (root / "requirements.txt").exists()) and result["test"] == "unknown":
        result["test"] = "pytest"
    return result


def dirs(root: Path, names: set[str]) -> list[str]:
    found = []
    for path in root.rglob("*"):
        if ".git" in path.parts or ".zoo-agent" in path.parts or secret_like(path):
            continue
        if path.is_dir() and path.name in names:
            found.append(path.relative_to(root).as_posix())
    return sorted(set(found)) or ["unknown"]


def entrypoints(root: Path) -> list[str]:
    found = []
    for pattern in ["src/main.*", "src/index.*", "src/server.*", "src/app.*", "app.py", "main.py", "cmd/*/main.go", "src/main.rs", "pages/api/**/*", "app/api/**/*", "routes/**/*"]:
        for path in root.glob(pattern):
            if path.is_file() and not secret_like(path):
                found.append(path.relative_to(root).as_posix())
    return sorted(set(found)) or ["unknown"]


def patterns(root: Path) -> dict[str, list[str]]:
    specs = {"registries": re.compile("registry|registrar", re.I), "factories": re.compile("factory", re.I), "providers": re.compile("provider", re.I), "processors": re.compile("proc|processor|handler|service", re.I)}
    out = {k: [] for k in specs}
    for path in root.rglob("*"):
        if ".git" in path.parts or ".zoo-agent" in path.parts or secret_like(path) or not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        for key, rx in specs.items():
            if rx.search(path.name):
                out[key].append(rel)
    return {k: (sorted(v)[:50] or ["unknown"]) for k, v in out.items()}


def profile(root: Path, codebase_indexing_status: str = "unknown") -> dict[str, Any]:
    return {"schema_version": "1.1", "generated_by": "generate-project-profile.py", "project_root": str(root), "codebase_indexing_status": codebase_indexing_status, "package_manager": package_manager(root), "languages": languages(root), "frameworks": ["unknown"], "commands": commands(root), "source_roots": dirs(root, {"src", "app", "lib", "packages", "cmd", "internal", "pkg"}), "test_roots": dirs(root, {"test", "tests", "__tests__", "spec", "e2e"}), "api_entrypoints": entrypoints(root), "patterns": patterns(root), "forbidden_paths": [".env*", "**/*secret*", "**/*token*", "**/*.pem", "**/*.key", ".git/**", "node_modules/**", "dist/**", "build/**"], "generated_files": ["unknown"], "risk_paths": {"security": ["auth/**", "security/**", "**/*auth*"], "data": ["migrations/**", "db/**", "database/**", "schema/**"], "payments": ["payment/**", "billing/**", "**/*stripe*"]}, "notes": ["unknown means no reliable evidence was found", "codebase_indexing_status records Zoo Code semantic indexing availability when known"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--output", default=".zoo-agent/project-profile.json")
    ap.add_argument("--codebase-indexing-status", choices=["available", "unavailable", "unknown"], default="unknown")
    args = ap.parse_args()
    text = json.dumps(profile(Path.cwd(), args.codebase_indexing_status), indent=2)
    if args.dry_run:
        print(text)
        return 0
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(f"[OK] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
