#!/usr/bin/env bash
# Runs on the VPS (called by GitHub Actions). Pulls main, updates deps, restarts services.
set -euo pipefail

APP=/home/botops/axealgo
cd "$APP"

git fetch origin main
git reset --hard origin/main   # .env, db.sqlite3 and .venv are untracked, so they are kept

for app in portal webhook_bot; do
  venv="$APP/$app/.venv"
  [ -d "$venv" ] || python3 -m venv "$venv"
  "$venv/bin/pip" install -q -r "$APP/$app/requirements.txt"
done

cd "$APP/portal"
"$APP/portal/.venv/bin/python" manage.py migrate --noinput
"$APP/portal/.venv/bin/python" manage.py collectstatic --noinput

sudo systemctl restart axealgo-portal axealgo-bot
sudo systemctl is-active axealgo-portal axealgo-bot
