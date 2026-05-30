#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_FIELDS = ["run_id", "goal_id", "created_by_mode", "model", "created_at", "input_artifacts", "output_artifacts", "gate_status"]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}


def resolve(path: str, cwd: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else cwd / p


def normalize_ref(value: str) -> str:
    if "=" not in value:
        return value
    typ, path = value.split("=", 1)
    return f"{typ.strip()}:{path.strip()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check runtime artifact graph integrity.")
    parser.add_argument("--graph")
    parser.add_argument("--run-dir")
    parser.add_argument("--max-age-hours", type=int, default=168)
    parser.add_argument("--output")
    args = parser.parse_args()
    graph_path = Path(args.graph) if args.graph else Path(args.run_dir or ".zoo-agent/runs/latest") / "artifact-graph.json"
    if not graph_path.exists():
        report = {"status": "fail", "error": "artifact_graph_missing", "path": str(graph_path)}
    else:
        graph = load(graph_path)
        run_id = graph.get("run_id")
        issues = []
        artifacts = graph.get("artifacts", [])
        types = {x.get("type") for x in artifacts if isinstance(x, dict)}
        run_ids = {x.get("run_id") for x in artifacts if isinstance(x, dict) and x.get("run_id")}
        if run_id and any(x != run_id for x in run_ids):
            issues.append({"type": "mixed_run_ids", "run_ids": sorted(run_ids)})
        for field in REQUIRED_FIELDS:
            if field not in graph:
                issues.append({"type": "graph_missing_field", "field": field})
        artifact_ids = {x.get("artifact_id") for x in artifacts if isinstance(x, dict)}
        cwd = Path.cwd()
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            for field in REQUIRED_FIELDS:
                if field not in item:
                    issues.append({"type": "artifact_missing_field", "artifact_id": item.get("artifact_id"), "field": field})
            path = item.get("path")
            if path and not resolve(path, cwd).exists():
                issues.append({"type": "artifact_path_missing", "artifact_id": item.get("artifact_id"), "path": path})
            if item.get("type") in {"quality_gate", "mechanical_review", "review_report", "integration_report"} and not item.get("input_artifacts"):
                issues.append({"type": "gate_missing_input_artifacts", "artifact_id": item.get("artifact_id"), "artifact_type": item.get("type")})
        for edge in graph.get("edges", []):
            for endpoint in ["from", "to"]:
                value = edge.get(endpoint)
                normalized = normalize_ref(str(value)) if value else value
                if normalized and normalized not in artifact_ids and not any(str(value) == str(x.get("path")) for x in artifacts if isinstance(x, dict)):
                    issues.append({"type": "edge_references_unknown_artifact", "endpoint": endpoint, "value": value})
        report = {"status": "pass" if not issues else "fail", "path": str(graph_path), "artifact_types": sorted(str(x) for x in types), "issues": issues}
    text = json.dumps(report, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
