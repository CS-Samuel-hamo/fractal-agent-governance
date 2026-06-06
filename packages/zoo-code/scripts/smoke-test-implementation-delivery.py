#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(cmd: list[str], cwd: Path, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != expect:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)} expected {expect} got {proc.returncode}")
    return proc


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="zoo-impl-delivery-smoke-") as temp:
        ws = Path(temp)
        run(["git", "init"], ws)
        (ws / "product-doc.md").write_text("# Product Plan\n", encoding="utf-8")
        run(["git", "add", "."], ws)
        run(["git", "-c", "user.email=smoke@example.invalid", "-c", "user.name=Smoke Test", "commit", "-m", "init"], ws)
        (ws / "product-doc.md").write_text("# Product Plan\n\nMore docs.\n", encoding="utf-8")

        run([
            sys.executable, str(SCRIPTS / "check-doc-only-completion.py"),
            "--workspace", str(ws), "--task-type", "code"
        ], ws, expect=1)

        run([
            sys.executable, str(SCRIPTS / "generate-implementation-queue.py"),
            "--workspace", str(ws),
            "--run-id", "run-smoke",
            "--goal-id", "goal-smoke",
            "--objective", "Implement example function",
            "--type", "code",
            "--root-goal-link", "goal-smoke",
            "--allowed-file", "src/**",
            "--allowed-file", "tests/**",
            "--test-command", "python -m pytest tests",
        ], ws)
        queue_path = ws / ".zoo-agent" / "runs" / "run-smoke" / "implementation-queue.json"
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        assert queue["summary"]["ready_for_worker"] == 1

        run([
            sys.executable, str(SCRIPTS / "promote-leaf-tasks-to-codex.py"),
            "--workspace", str(ws),
            "--run-id", "run-smoke",
        ], ws)
        meta = json.loads((ws / ".zoo-agent" / "runs" / "run-smoke" / "codex-tasks" / "impl-001" / "task-metadata.json").read_text(encoding="utf-8"))
        assert meta["implementation_item_id"] == "impl-001"
        prompt = (ws / ".zoo-agent" / "runs" / "run-smoke" / "codex-tasks" / "impl-001" / "CODEX_TASK_PROMPT.md").read_text(encoding="utf-8")
        assert "Do not write product documentation" in prompt

        (ws / "src").mkdir(exist_ok=True)
        (ws / "tests").mkdir(exist_ok=True)
        (ws / "src" / "example.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
        (ws / "tests" / "test_example.py").write_text("from src.example import add\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
        run([
            sys.executable, str(SCRIPTS / "check-code-delivery-gate.py"),
            "--workspace", str(ws),
            "--run-id", "run-smoke",
            "--task-id", "impl-001",
            "--implementation-item-id", "impl-001",
            "--tests-status", "pass",
            "--scope-status", "pass",
        ], ws)

        bad_queue = {
            "run_id": "run-bad",
            "items": [{
                "item_id": "bad",
                "task_id": "bad",
                "title": "drift",
                "type": "code",
                "status": "ready_for_worker",
                "expected_artifacts": ["code diff"],
                "allowed_files": ["src/**"],
            }],
        }
        bad_path = ws / "bad-queue.json"
        bad_path.write_text(json.dumps(bad_queue), encoding="utf-8")
        run([sys.executable, str(SCRIPTS / "check-root-goal-alignment.py"), "--queue", str(bad_path)], ws, expect=1)
        print("[OK] implementation delivery smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
