#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare a Codex result with a Zoo review artifact.")
    parser.add_argument("--codex-result", required=True)
    parser.add_argument("--zoo-review")
    args = parser.parse_args()
    codex = json.loads(Path(args.codex_result).read_text(encoding="utf-8"))
    review_text = Path(args.zoo_review).read_text(encoding="utf-8") if args.zoo_review else ""
    report = {
        "task_id": codex.get("task_id"),
        "scope_guard": codex.get("scope_guard", {}).get("status"),
        "changed_files": codex.get("git_diff_name_only", []),
        "zoo_review_present": bool(review_text),
        "requires_review": True,
        "codex_is_final_decision": False,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
