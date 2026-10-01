#!/bin/sh
# One entry point for "before I say a development task is done".
#   1. review battery (static + code structure + coverage)  2. UI gate (contrast/overflow/tests)
set -e
cd "$(dirname "$0")/.."
echo "--- review battery ---"
python3 tools/review_check.py
echo
echo "--- UI gate ---"
QT_QPA_PLATFORM=offscreen python3 tools/check_ui.py
