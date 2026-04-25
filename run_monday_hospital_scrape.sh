#!/bin/zsh
set -euo pipefail

PROJECT_DIR="/Users/allyanna/Desktop/Coding/5211/work/5211_final"
PYTHON_BIN="/Users/allyanna/miniforge3/bin/python"

cd "$PROJECT_DIR"

"$PYTHON_BIN" tableau_extract_hospital_beds.py \
  --mode monitor_24h \
  --output hospital_bed_capacity_monday.csv

# Disable this launch agent after it finishes so it runs only once.
launchctl unload "/Users/allyanna/Library/LaunchAgents/com.allyanna.hospital_bed_capacity_monday.plist" >/dev/null 2>&1 || true
