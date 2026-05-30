#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {"raw": path.read_text(encoding="utf-8", errors="replace")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    base = Path(".zoo-agent") / "runs" / args.run_id
    quality = load(base / "quality-gate.json")
    obligation = load(base / "obligation-ledger.json")
    risks = load(base / "risk-register.json")
    checks = {
        "quality_gate_pass": quality.get("status") == "pass",
        "obligation_ledger_present": bool(obligation),
        "review_verdict_present": (base / "review-verdict.json").exists() or (base / "mechanical-review.json").exists(),
        "risk_register_present": bool(risks),
        "rollback_plan_present": (base / "rollback-plan.md").exists() or "rollback" in json.dumps(obligation).lower(),
        "smoke_test_present": (base / "smoke-test.txt").exists() or "smoke" in json.dumps(quality).lower(),
        "observability_checked": (base / "operational-readiness.json").exists() or "observability" in json.dumps(obligation).lower(),
    }
    status = "pass" if all(checks.values()) else "fail"
    report = {"status": status, "run_id": args.run_id, "checks": checks, "note": "Readiness report only; no deploy or publish performed."}
    out = json.dumps(report, indent=2)
    target = Path(args.output) if args.output else base / "release-readiness.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(out + "\n", encoding="utf-8")
    print(out)
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
