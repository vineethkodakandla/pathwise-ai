#!/bin/bash
# PathWise AI — TimescaleDB Backup Script (Req-Qual-Rel-3)
# Run daily via cron: 0 2 * * * /path/to/infra/db/backup.sh
#
# Retains last 7 daily backups.

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
DB_HOST="${DB_HOST:-timescaledb}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-pathwise}"
DB_USER="${DB_USER:-pathwise}"
RETAIN_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/pathwise_${TIMESTAMP}.sql.gz"
LOG_FILE="${BACKUP_DIR}/backup.log"

mkdir -p "${BACKUP_DIR}"

echo "[$(date)] Starting backup..." | tee -a "${LOG_FILE}"

# Dump and compress
pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    --format=custom --compress=9 \
    -f "${BACKUP_FILE}" 2>&1 | tee -a "${LOG_FILE}"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    echo "[$(date)] Backup successful: ${BACKUP_FILE} (${SIZE})" | tee -a "${LOG_FILE}"
else
    echo "[$(date)] ERROR: Backup failed!" | tee -a "${LOG_FILE}"
    exit 1
fi

# Prune old backups
echo "[$(date)] Removing backups older than ${RETAIN_DAYS} days..." | tee -a "${LOG_FILE}"
find "${BACKUP_DIR}" -name "pathwise_*.sql.gz" -mtime +${RETAIN_DAYS} -delete 2>&1 | tee -a "${LOG_FILE}"

REMAINING=$(ls -1 "${BACKUP_DIR}"/pathwise_*.sql.gz 2>/dev/null | wc -l)
echo "[$(date)] Done. ${REMAINING} backup(s) retained." | tee -a "${LOG_FILE}"
