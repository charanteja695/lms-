#!/bin/sh
# Create one PostgreSQL database per service, idempotently (safe on an existing data volume).
# Run by the one-shot `databases` compose service; PGHOST/PGUSER/PGPASSWORD come from its environment.
set -eu

for db in \
    lms_user_management lms_catalog lms_media lms_subscription lms_learning lms_notification \
    lms_code_execution lms_assessment lms_proctoring lms_certificate lms_ai_gateway lms_ai_tutor lms_support lms_career lms_job_portal lms_interview lms_analytics lms_billing; do
    if [ "$(psql -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$db'")" = "1" ]; then
        echo "database $db exists"
    else
        psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $db"
        echo "database $db created"
    fi
done
