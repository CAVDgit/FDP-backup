#!/bin/sh

CRON_EXPRESSION="${FDP_CRON_SCHEDULE:-0 22 * * *}"
echo "$CRON_EXPRESSION python /app/fdp_backup.py >> /app/backup/backup.log 2>&1" > /app/fdp.cron

echo "🕒 Using cron schedule: $CRON_EXPRESSION"
cat /app/fdp.cron

exec /usr/local/bin/supercronic /app/fdp.cron
