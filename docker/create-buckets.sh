#!/bin/sh
# Create the development buckets in the compose MinIO, idempotently. Run by the one-shot `buckets` compose service
# (image minio/mc); MINIO_ROOT_USER / MINIO_ROOT_PASSWORD come from its environment.
set -eu

until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
    echo "waiting for minio..."
    sleep 1
done

for bucket in lms-media-dev lms-assessment-dev lms-proctoring-dev lms-certificates-dev; do
    mc mb --ignore-existing "local/$bucket"
done
