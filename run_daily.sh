#!/usr/bin/env bash
# Wrapper para LaunchAgent — corre daily_engine.py de Manzanos Mobility.
set -euo pipefail
cd "$(dirname "$0")"
LOG="$(pwd)/daily.log"
{
  echo "── $(date '+%Y-%m-%d %H:%M:%S %Z') ──"
  /usr/bin/env python3 daily_engine.py 2>&1
  echo ""
} >> "$LOG"
