#!/bin/bash
# PlumberLink pilot launcher.
# Starts gunicorn (production mode) + a Cloudflare quick tunnel, writes the
# public URL to PUBLIC_URL.txt, and regenerates QR images with that URL.
set -e
cd "$(dirname "$0")"
mkdir -p logs media/qr

if [ ! -f .secret_key ]; then
  ./venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())" > .secret_key
  chmod 600 .secret_key
fi
export PLUMBERLINK_SECRET_KEY="$(cat .secret_key)"
export PLUMBERLINK_DEBUG=0

# Stop any previous run
pkill -f "gunicorn plumberlink.wsgi" 2>/dev/null || true
pkill -f "cloudflared tunnel --url" 2>/dev/null || true
sleep 1

./venv/bin/python manage.py collectstatic --noinput >/dev/null 2>&1
./venv/bin/python manage.py migrate --noinput >/dev/null 2>&1

rm -f tunnel.log
cloudflared tunnel --url http://127.0.0.1:8000 > tunnel.log 2>&1 &
echo "Waiting for tunnel URL..."
URL=""
for i in $(seq 1 40); do
  # Exclude api.trycloudflare.com (appears in error lines, not a tunnel URL)
  URL=$(grep -o 'https://[a-zA-Z0-9.-]*\.trycloudflare\.com' tunnel.log | grep -v 'api\.trycloudflare\.com' | head -1)
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "$URL" ]; then
  echo "ERROR: could not get tunnel URL. See tunnel.log"
  exit 1
fi
HOST="${URL#https://}"
export PLUMBERLINK_HOSTS="localhost,127.0.0.1,$HOST"
export PLUMBERLINK_CSRF_ORIGINS="$URL"
export PLUMBERLINK_PUBLIC_URL="$URL"
echo "$URL" > PUBLIC_URL.txt

./venv/bin/gunicorn plumberlink.wsgi:application \
  --bind 127.0.0.1:8000 --workers 2 \
  --daemon --pid logs/gunicorn.pid \
  --access-logfile logs/access.log --error-logfile logs/error.log

# Regenerate QR images so they point at the live public URL
./venv/bin/python manage.py regen_qr

echo "--------------------------------------------------"
echo "PlumberLink is LIVE at: $URL"
echo "--------------------------------------------------"
