#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED = ["name", "description", "version", "scope", "applies_to", "last_updated", "deprecated_by"]
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def parse(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    data: dict[str, str] = {}
    for line in text[4:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip("'\"")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Check SKILL.md versioning metadata.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    root = Path(args.root)
    issues = []
    deprecated = []
    default_text = ""
    for rel in [".roo/commands/agent-run.md", ".roomodes"]:
        path = root / rel
        if path.exists():
            default_text += "\n" + path.read_text(encoding="utf-8", errors="replace")
    skills = sorted((root / ".roo").glob("skills-*/**/SKILL.md"))
    for sf in skills:
        data = parse(sf)
        rel = sf.relative_to(root).as_posix()
        for field in REQUIRED:
            if field not in data:
                issues.append({"skill": rel, "severity": "blocker", "issue": f"missing {field}"})
        name = data.get("name", "")
        if name != sf.parent.name:
            issues.append({"skill": rel, "severity": "blocker", "issue": "name does not match directory"})
        if name and not NAME_RE.fullmatch(name):
            issues.append({"skill": rel, "severity": "blocker", "issue": "invalid skill name"})
        if data.get("deprecated_by"):
            deprecated.append(name)
            if name and name in default_text:
                issues.append({"skill": rel, "severity": "blocker", "issue": "deprecated skill appears in default invocation flow"})
    report = {"status": "pass" if not any(i["severity"] == "blocker" for i in issues) else "fail", "skill_count": len(skills), "deprecated": deprecated, "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
