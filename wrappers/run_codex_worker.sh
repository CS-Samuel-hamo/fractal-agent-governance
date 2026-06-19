#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Optional:
#   CODEX_HOME=/path/to/codex_home ./run_codex_worker.sh ...
# or pass:
#   ./run_codex_worker.sh --codex-home /path/to/codex_home ...
python "$SCRIPT_DIR/../scripts/run_codex_worker.py" "$@"

