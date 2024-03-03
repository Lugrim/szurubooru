#!/usr/bin/dumb-init /bin/sh

# Integrate environment variables
sed -i "s|__BACKEND__|${BACKEND_HOST}|" \
  /etc/nginx/nginx.conf
sed -i "s|__LISTEN_PORT__|${PORT:-80}|" \
  /etc/nginx/nginx.conf
sed -i "s|__BACKEND_PORT__|${BACKEND_PORT:-6666}|" \
  /etc/nginx/nginx.conf
sed -i "s|__BASEURL__|${BASE_URL:-/}|g" \
  /var/www/index.htm \
  /var/www/manifest.json

# Start server
exec nginx
