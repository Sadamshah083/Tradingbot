#!/usr/bin/env bash
# Obtains the first Let's Encrypt certificate. Run once on the server after `docker compose up -d postgres app`:
#   chmod +x nginx/init-letsencrypt.sh && ./nginx/init-letsencrypt.sh
# Requires DOMAIN and CERTBOT_EMAIL in .env and the domain's A record pointing at this server.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
: "${DOMAIN:?DOMAIN missing in .env}"; : "${CERTBOT_EMAIL:?CERTBOT_EMAIL missing in .env}"

echo "1/3 temporary self-signed certificate so nginx can start"
docker compose run --rm --entrypoint sh certbot -c "mkdir -p /etc/letsencrypt/live/$DOMAIN && openssl req -x509 -nodes -newkey rsa:2048 -days 1 -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem -subj '/CN=localhost'"
docker compose up -d nginx

echo "2/3 requesting the real certificate"
docker compose run --rm --entrypoint sh certbot -c "rm -rf /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN /etc/letsencrypt/renewal/$DOMAIN.conf && certbot certonly --webroot -w /var/www/certbot -d $DOMAIN --email $CERTBOT_EMAIL --agree-tos --no-eff-email --non-interactive"

echo "3/3 reloading nginx"
docker compose exec nginx nginx -s reload
docker compose up -d certbot
echo "done: https://$DOMAIN"
