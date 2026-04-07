#!/usr/bin/env bash
# Запуск API за reverse proxy (Nginx/Caddy). На сервере: chmod +x scripts/run_production.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -d .venv ]]; then
  echo "Создайте venv: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
