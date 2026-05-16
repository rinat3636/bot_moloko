#!/bin/sh
set -e

export PYTHONPATH="${PYTHONPATH:-/app}"
cd /app

echo "Running database migrations..."
alembic upgrade head

if [ "${IMPORT_CATALOG_ON_START:-1}" != "0" ]; then
  echo "Importing catalog from n-i.ru (if empty)..."
  python scripts/import_catalog.py --if-empty || echo "WARN: catalog import failed, bot will start anyway"
fi

echo "Starting milk bot..."
exec python -m milk_bot.bot.main
