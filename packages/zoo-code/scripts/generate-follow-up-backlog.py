#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate follow-up backlog for local optimization items.")
    parser.add_argument("--workspace", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--queue", default="")
    parser.add_argument("--title", action="append", default=[])
    parser.add_argument("--reason", action="append", default=[])
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    run_root = workspace / ".zoo-agent" / "runs" / args.run_id
    items = []
    queue_path = Path(args.queue) if args.queue else run_root / "implementation-queue.json"
    if queue_path.exists():
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        for item in queue.get("items", []):
            if item.get("status") == "follow_up" or item.get("follow_up_reason"):
                items.append(item)
    for index, title in enumerate(args.title):
        items.append({
            "item_id": f"follow-up-{len(items)+1}",
            "title": title,
            "follow_up_reason": args.reason[index] if index < len(args.reason) else "local optimization deferred",
        })
    payload = {"run_id": args.run_id, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "items": items}
    out_json = run_root / "follow-up-backlog.json"
    out_md = run_root / "follow-up-backlog.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# Follow-up Backlog", ""]
    for item in items:
        lines.append(f"- `{item.get('item_id')}` {item.get('title')} - {item.get('follow_up_reason', '')}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
