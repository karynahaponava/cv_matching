#!/bin/sh
set -eu
PROJECT_DIR="/opt/cv_matching"
ENV_FILE="$PROJECT_DIR/infra/prod/.env"
BACKUP_ENV_FILE="$PROJECT_DIR/infra/backup.env"
CONTAINER="cv_matching_db_prod"
STAMP="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
DUMP_FILE="/tmp/cv_matching_prod_${STAMP}.dump"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
[ -f "$BACKUP_ENV_FILE" ] && . "$BACKUP_ENV_FILE"
: "${POSTGRES_USER:?POSTGRES_USER is not set}"
: "${POSTGRES_DB:?POSTGRES_DB is not set}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET is not set (see infra/backup.env)}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is not set (see infra/backup.env)}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is not set (see infra/backup.env)}"
cleanup() {
  rm -f "$DUMP_FILE"
}
trap cleanup EXIT

echo "[$(date -u +%FT%TZ)] Dumping ${POSTGRES_DB} from ${CONTAINER}"
docker exec "$CONTAINER" pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > "$DUMP_FILE"
echo "[$(date -u +%FT%TZ)] Uploading to s3://${BACKUP_BUCKET}/postgres/${STAMP}.dump"
AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
aws --endpoint-url=https://storage.yandexcloud.net s3 cp "$DUMP_FILE" \
  "s3://${BACKUP_BUCKET}/postgres/${STAMP}.dump"
echo "[$(date -u +%FT%TZ)] Backup complete"