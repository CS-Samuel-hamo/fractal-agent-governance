#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or print a Codex Task Pack prompt.")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    prompt = Path(args.task_dir) / "CODEX_TASK_PROMPT.md"
    if not prompt.exists():
        raise SystemExit(f"Missing prompt: {prompt}")
    text = prompt.read_text(encoding="utf-8")
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
