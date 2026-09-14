#!/bin/sh
set -eu
PROJECT_DIR="/opt/cv_matching"
cd "$PROJECT_DIR/infra/edge"
docker compose exec -T nginx nginx -s reload
