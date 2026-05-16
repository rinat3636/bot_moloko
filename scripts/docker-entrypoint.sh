#!/bin/sh
set -e

export PYTHONPATH="${PYTHONPATH:-/app}"
cd /app

echo "Running database migrations..."
alembic upgrade head

echo "Starting milk bot..."
exec python -m milk_bot.bot.main
