#!/usr/bin/env bash
# Wrapper para LaunchAgent — refresca el long-lived IG token de Manzanos Mobility.
set -euo pipefail
cd "$(dirname "$0")"
/usr/bin/env python3 refresh_token.py >> token-refresh.log 2>&1
