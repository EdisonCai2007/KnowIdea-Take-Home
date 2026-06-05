#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: bash scripts/openrouter_smoke_test.sh [supported|refuted|undecidable|all]

Runs the OpenRouter-backed `verify explain` flow against representative
decision-battery cases:
  supported   -> D2
  refuted     -> D3
  undecidable -> D1
  all         -> run every case above
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

mode="${1:-all}"

case "$mode" in
  supported|refuted|undecidable|all)
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac

if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  echo "OPENROUTER_API_KEY is required." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"
battery_path="$repo_root/codex-resources/original-project-specs/decision_battery.json"

export PYTHONPATH="$repo_root/src${PYTHONPATH:+:$PYTHONPATH}"

run_case() {
  local label="$1"
  local decision_id="$2"
  local expected_classification="$3"

  echo
  echo "== $label =="
  echo "decision_id=$decision_id expected_classification=$expected_classification model=${OPENROUTER_MODEL:-google/gemini-2.5-flash-lite}"
  python3 -m decision_prover verify explain --input "$battery_path" --decision-id "$decision_id"
}

cd "$repo_root"

if [[ "$mode" == "supported" || "$mode" == "all" ]]; then
  run_case "SUPPORTED smoke test" "D2" "SUPPORTED"
fi

if [[ "$mode" == "refuted" || "$mode" == "all" ]]; then
  run_case "REFUTED smoke test" "D3" "REFUTED"
fi

if [[ "$mode" == "undecidable" || "$mode" == "all" ]]; then
  run_case "UNDECIDABLE smoke test" "D1" "UNDECIDABLE"
fi
