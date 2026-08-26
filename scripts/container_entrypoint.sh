#!/bin/sh
set -eu

alembic upgrade head
python -m scripts.encrypt_existing_configs
python -m scripts.create_superadmin
python -m xvond_seed_providers

exec "$@"
