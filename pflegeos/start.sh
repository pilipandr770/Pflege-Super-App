#!/bin/bash
# ============================================================
# PflegeOS — Production Startup Script
# Runs on Render.com (and any Docker production environment)
# 1. Apply DB migrations
# 2. Start Gunicorn
# ============================================================
set -e

echo "▶ Running database migrations..."
flask db upgrade

echo "▶ Starting Gunicorn..."
exec gunicorn run:app \
    --workers 2 \
    --bind "0.0.0.0:${PORT:-5000}" \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
