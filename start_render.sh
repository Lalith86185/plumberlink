#!/bin/bash
# Render.com start script: migrates, bakes the public URL into QR codes, serves with gunicorn.
set -e
HOST="${RENDER_EXTERNAL_HOSTNAME:-localhost}"
export PLUMBERLINK_DEBUG=0
export PLUMBERLINK_HOSTS="$HOST,localhost"
export PLUMBERLINK_CSRF_ORIGINS="https://$HOST"
export PLUMBERLINK_PUBLIC_URL="https://$HOST"
python manage.py migrate --noinput
python manage.py regen_qr
exec gunicorn plumberlink.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2
