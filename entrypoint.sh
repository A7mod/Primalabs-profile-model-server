#!/bin/bash
set -euo pipefail

python3 /opt/app/app/validate_profile.py

exec python3 -m uvicorn app.server:app \
    --host 0.0.0.0 \
    --port 8000 \
    --app-dir /opt/app