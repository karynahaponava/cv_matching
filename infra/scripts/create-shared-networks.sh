#!/bin/sh
set -eu
# Общие docker-сети для dev/prod, к которым подключается edge-nginx.
# Идемпотентно: можно запускать сколько угодно раз.
docker network inspect internal_net_dev >/dev/null 2>&1 || docker network create internal_net_dev
docker network inspect internal_net_prod >/dev/null 2>&1 || docker network create internal_net_prod
