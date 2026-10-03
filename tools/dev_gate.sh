#!/bin/sh
# One entry point for "before I say a development task is done".
#   1. review battery (static: i18n / shortcuts / theme / strings / hygiene / structure)
#   2. UI gate (contrast + overflow + min-width) AND the single pytest run for the whole gate
#
# Efficiency note (2026-10-02): the two halves used to re-run each other's work -
# review_check.py ran pytest with coverage, then its dynamic step ran tools/check_ui.py
# (pytest again), and this script then ran check_ui.py a second time (pytest a third
# time). One gate run therefore executed the test suite three times and check_ui.py
# twice (~8 min). Now pytest runs exactly once and check_ui.py exactly once:
# review_check.py is asked to skip its coverage and dynamic halves (--no-coverage
# --no-dynamic) and check_ui.py owns both the UI checks and the single test run.
set -e
cd "$(dirname "$0")/.."
echo "--- review battery (static) ---"
python3 tools/review_check.py --no-coverage --no-dynamic
echo
echo "--- UI gate (contrast / overflow / min-width + the single pytest run) ---"
QT_QPA_PLATFORM=offscreen python3 tools/check_ui.py

echo
echo "--- process policy (change-plan sections carry the process fields) ---"
python3 tools/check_plan_doc.py

echo
echo "--- data-path bench (zero loss + batch p95 budget) ---"
QT_QPA_PLATFORM=offscreen python3 tools/rx_bench.py --baud 115200 --seconds 2

# Stamp this exact tree as passing so the pre-commit hook does not re-run the gate
# for a tree we just checked (one gate run per change, not two). The key is based on
# HEAD + the full diff vs HEAD, so it does not change when the same content is staged.
key="$(git rev-parse HEAD)-$(git diff HEAD | git hash-object --stdin)"
printf '%s' "$key" > .git/serialdesk_gate_stamp
