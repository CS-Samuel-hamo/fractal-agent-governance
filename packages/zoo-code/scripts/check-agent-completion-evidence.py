#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path

REQUIRED = ["Impact Map", "Existing Patterns", "Integration Surfaces", "Files Changed", "Tests Run", "Acceptance Mapping", "Risks", "Rollback Plan"]


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def has_section(text: str, title: str) -> bool:
    wanted = norm(title)
    return any(norm(line.strip().strip("#:*` ")) == wanted for line in text.splitlines())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists():
        print(json.dumps({"status": "fail", "error": f"file not found: {path}"}, indent=2))
        return 1
    text = path.read_text(encoding="utf-8", errors="replace")
    missing = [s for s in REQUIRED if not has_section(text, s)]
    result = {"status": "pass" if not missing else "fail", "file": str(path), "required_sections": REQUIRED, "missing_sections": missing}
    print(json.dumps(result, indent=2))
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.exit(main())
