#!/usr/bin/env bash
set -euo pipefail

websockify ${WS_PORT:-8080} localhost:${MINECRAFT_PORT:-25565} &
exec python3 /opt/microvm/hook.py
