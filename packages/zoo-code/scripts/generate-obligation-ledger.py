#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def obligation(oid: str, category: str, description: str, why: str, signal: str, surfaces: list[str], verification: str, risk: str, status: str = "required", escalation: bool = False) -> dict:
    return {
        "obligation_id": oid,
        "category": category,
        "description": description,
        "why_required": why,
        "source_signal": signal,
        "candidate_files_or_surfaces": surfaces,
        "status": status,
        "owner_mode": "agent-executor" if not escalation else "agent-orchestrator",
        "verification": verification,
        "evidence": "",
        "risk_if_omitted": risk,
        "escalation_required": escalation,
        "discovery_method": "unknown",
    }


def infer(task: str) -> list[dict]:
    t = task.lower()
    items: list[dict] = [
        obligation("obl-pattern-search", "documentation_governance", "Search existing analogous patterns before creating new utilities, types, handlers, processors, or wiring.", "Prevents local-only implementation and duplicate abstractions.", "all coding tasks", ["source roots", "exports", "registries", "factories"], "Record search terms and existing patterns in Completion Evidence.", "Duplicate or incompatible implementation."),
        obligation("obl-tests", "verification", "Map changed behavior to tests and record test commands.", "Every behavior change needs verification.", "coding task", ["unit tests", "integration tests", "smoke tests"], "Test Plan and Tests Run sections reference commands/results.", "Regression can ship without detection."),
        obligation("obl-rollback", "operational", "Define rollback plan or state why rollback is not applicable.", "Integration requires recovery path.", "coding task", ["release note", "runbook", "rollback plan"], "Completion Evidence includes Rollback Plan.", "Failed change cannot be safely reverted."),
    ]
    if any(k in t for k in ["field", "字段", "schema", "dto"]):
        items.extend([
            obligation("obl-field-schema", "code_interface", "Update DTO/schema/type and validation surfaces for the new field.", "Field changes propagate through contracts.", "add field", ["DTO", "schema", "validator", "type"], "Request/response or schema tests cover the field.", "Runtime mismatch or invalid data."),
            obligation("obl-field-mapper-storage", "domain_data", "Update mapper and persistence/migration if the field is stored.", "Stored fields require data mapping.", "add field", ["mapper", "repository", "migration", "fixture"], "Mapper/storage tests or explicit not_applicable evidence.", "Field silently dropped or migration failure."),
            obligation("obl-field-api-doc", "documentation_governance", "Update API response docs or release note if public.", "Public fields affect consumers.", "add field", ["README", "API docs", "release note"], "Docs/release note evidence or not_applicable evidence.", "Consumers miss behavior change."),
        ])
    if any(k in t for k in ["behavior", "行为", "change", "修改"]):
        items.extend([
            obligation("obl-affected-callers", "behavior_compatibility", "Identify affected callers and compatibility impact.", "Behavior changes propagate to callers.", "change behavior", ["call graph", "routes", "commands", "jobs"], "Completion Evidence lists affected callers and tests.", "Caller regressions."),
            obligation("obl-error-observability", "operational", "Check error behavior and observability when failures are diagnosable by operators.", "Behavior changes often alter failure modes.", "change behavior", ["logging", "metrics", "error mapping"], "Test or readiness evidence covers error behavior.", "Silent production failure."),
        ])
    if any(k in t for k in ["proc", "processor", "procz"]):
        items.extend([
            obligation("obl-proc-pattern", "invocation_wiring", "Search existing Proc/Processor invocation and wiring patterns.", "Existing processors often require registration and adapters.", "use existing Proc/Processor", ["registry", "factory", "dispatcher", "provider"], "Completion Evidence records pattern search.", "Processor called outside intended lifecycle."),
            obligation("obl-proc-data-source", "domain_data", "Verify data-source semantics before reusing Proc/Processor.", "Same processor with different source may be semantically invalid.", "use existing Proc/Processor", ["data source", "adapter", "source selector"], "Old/new behavior tests or escalation.", "Incorrect results from source mismatch.", "escalated", True),
            obligation("obl-proc-tests", "verification", "Add old/new source behavior tests when data-source differs.", "Proc reuse must prove semantic equivalence or intentional difference.", "use existing Proc/Processor", ["unit tests", "integration tests", "fixtures"], "Tests compare old/new source behavior.", "Mismatch hidden until production."),
        ])
    return items


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default="run-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    parser.add_argument("--branch-id", default="root")
    parser.add_argument("--task", required=True)
    parser.add_argument("--explicit", action="append", default=[])
    parser.add_argument("--discovery-method", choices=["codebase_search", "rg", "manual", "unknown"], default="unknown")
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    out = Path(args.output) if args.output else Path(".zoo-agent") / "runs" / args.run_id / "obligation-ledger.json"
    ledger = {
        "run_id": args.run_id,
        "branch_id": args.branch_id,
        "task_summary": args.task,
        "discovery_method": args.discovery_method,
        "explicit_request": args.explicit or [args.task],
        "implicit_obligations": infer(args.task),
        "not_applicable_decisions": [],
        "deferred_items": [],
        "created_at": now(),
        "updated_at": now(),
    }
    for item in ledger["implicit_obligations"]:
        item["discovery_method"] = args.discovery_method
    text = json.dumps(ledger, indent=2)
    if not args.dry_run:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
