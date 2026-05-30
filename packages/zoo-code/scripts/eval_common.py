from __future__ import annotations

import json
from pathlib import Path


def parse_value(value: str):
    value = value.strip().strip('"').strip("'")
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [x.strip().strip('"').strip("'") for x in inner.split(",")]
    return value


def parse_case(path: Path) -> dict:
    data: dict = {}
    scoring: dict = {}
    current = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  ") and current == "scoring" and ":" in line:
            key, value = line.strip().split(":", 1)
            scoring[key.strip()] = parse_value(value)
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            if key == "scoring":
                current = "scoring"
                data["scoring"] = scoring
            else:
                data[key] = parse_value(value)
                current = None
    data.setdefault("scoring", scoring)
    return data


def resolve_eval_root(root: Path) -> Path:
    if root.exists():
        return root
    packaged = Path(__file__).resolve().parents[1] / root
    return packaged if packaged.exists() else root


def list_cases(root: Path, suite: str, case_id: str | None = None) -> list[Path]:
    root = resolve_eval_root(root)
    suites = [p for p in root.iterdir() if p.is_dir()] if suite == "full" and root.exists() else [root / suite]
    out: list[Path] = []
    for s in suites:
        if not s.exists():
            continue
        for path in sorted(s.glob("*.yaml")):
            if case_id and parse_case(path).get("case_id") != case_id:
                continue
            out.append(path)
    return out


def as_set(value) -> set[str]:
    if isinstance(value, list):
        return {str(x) for x in value if str(x)}
    if isinstance(value, str) and value:
        return {value}
    return set()


def score_sets(expected: set[str], predicted: set[str]) -> tuple[float, float]:
    if not expected:
        return 1.0, 1.0 if not predicted else 0.0
    true_positive = len(expected & predicted)
    recall = true_positive / len(expected)
    precision = true_positive / len(predicted) if predicted else 0.0
    return recall, precision


def predict(case: dict) -> dict:
    text = str(case.get("input_task", "")).lower()
    category = str(case.get("category", "")).lower()
    obligations = set()
    surfaces = set()
    routing = set()
    escalations = set()
    decomposition = set()
    review = set()
    parallel = set()
    forbidden = set()
    if any(k in text for k in ["field", "字段"]):
        obligations.update(["dto_schema", "mapper_storage", "validation", "tests", "docs_release_note"])
        surfaces.update(["dto", "schema", "mapper", "api_response", "tests"])
    if any(k in text for k in ["behavior", "行为"]):
        obligations.update(["affected_callers", "compatibility", "tests", "error_behavior", "observability"])
        surfaces.update(["callers", "tests", "logging"])
    if any(k in text for k in ["proc", "processor"]):
        obligations.update(["existing_pattern_search", "data_source_semantics", "old_new_behavior_tests"])
        surfaces.update(["registry", "factory", "data_source", "tests"])
        escalations.add("data_source_unknown")
    if any(k in text for k in ["route", "command", "registry", "factory", "provider"]):
        surfaces.update(["route", "command", "registry", "factory", "provider"])
    if any(k in text for k in ["security", "auth", "payment", "pii", "migration"]):
        escalations.add("security_or_auth_risk")
        routing.add("gpt_final")
    if "parallel" in category or "parallel" in text:
        parallel.add("path_locks")
        parallel.add("merge_queue")
        parallel.add("worktree")
    if "fractal" in category or "multi-module" in text or "cross-module" in text:
        decomposition.add("branch_tree")
        decomposition.add("parent_aggregation")
    if "review" in category or "bug" in text:
        review.add("blocker_detection")
    if not routing:
        routing.add("deepseek_draft_gpt_final")
    return {
        "obligations": sorted(obligations),
        "surfaces": sorted(surfaces),
        "routing": sorted(routing),
        "escalations": sorted(escalations),
        "decomposition": sorted(decomposition),
        "review": sorted(review),
        "parallel": sorted(parallel),
        "forbidden": sorted(forbidden),
    }


def score_case(case: dict, prediction: dict) -> dict:
    expected_obl = as_set(case.get("expected_obligations"))
    pred_obl = set(prediction.get("obligations", []))
    obligation_recall, obligation_precision = score_sets(expected_obl, pred_obl)
    expected_surfaces = as_set(case.get("expected_surfaces"))
    surface_recall, _ = score_sets(expected_surfaces, set(prediction.get("surfaces", [])))
    routing_expected = as_set(case.get("expected_routing"))
    routing_correctness = 1.0 if not routing_expected or routing_expected & set(prediction.get("routing", [])) else 0.0
    esc_expected = as_set(case.get("expected_escalations"))
    escalation_correctness = 1.0 if esc_expected <= set(prediction.get("escalations", [])) else 0.0
    decomp_expected = as_set(case.get("expected_decomposition"))
    decomposition_validity = 1.0 if decomp_expected <= set(prediction.get("decomposition", [])) else 0.0
    review_blocker_detection = 1.0 if "blocker_detection" in prediction.get("review", []) or "review-quality" not in str(case.get("category", "")) else 0.0
    parallel_expected = {"path_locks", "merge_queue", "worktree"} if "parallel" in str(case.get("category", "")) else set()
    parallel_safety_score = 1.0 if parallel_expected <= set(prediction.get("parallel", [])) else 0.0
    forbidden = as_set(case.get("forbidden_actions"))
    forbidden_action_violations = len(forbidden & set(prediction.get("forbidden", [])))
    return {
        "obligation_recall": obligation_recall,
        "obligation_precision": obligation_precision,
        "integration_surface_recall": surface_recall,
        "routing_correctness": routing_correctness,
        "escalation_correctness": escalation_correctness,
        "decomposition_validity": decomposition_validity,
        "review_blocker_detection": review_blocker_detection,
        "parallel_safety_score": parallel_safety_score,
        "forbidden_action_violations": forbidden_action_violations,
    }


def aggregate(results: list[dict]) -> dict:
    keys = ["obligation_recall", "obligation_precision", "integration_surface_recall", "routing_correctness", "escalation_correctness", "decomposition_validity", "review_blocker_detection", "parallel_safety_score"]
    scores = {}
    for key in keys:
        values = [r["scores"][key] for r in results]
        scores[key] = sum(values) / len(values) if values else 0.0
    scores["forbidden_action_violations"] = sum(r["scores"]["forbidden_action_violations"] for r in results)
    return scores
