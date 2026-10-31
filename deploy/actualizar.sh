#!/usr/bin/env bash
# Actualiza la app en el droplet con lo último de main. Se corre como root en el servidor:
#   bash /srv/editor/app/deploy/actualizar.sh
set -euo pipefail

cd /srv/editor/app
sudo -u editor git pull --ff-only
sudo -u editor uv sync --no-dev --frozen
sudo -u editor .venv/bin/alembic upgrade head
systemctl restart editor
systemctl --no-pager --lines=0 status editor
