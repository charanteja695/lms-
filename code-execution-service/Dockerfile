# syntax=docker/dockerfile:1
#
# Build context is lms-backend/ (every service depends on ./shared, the lms-common package):
#   docker build -f code-execution-service/Dockerfile -t lms-code-execution-service lms-backend/
# docker compose does this for you (see docker-compose.yml).

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY shared /shared
COPY code-execution-service/requirements.txt .
# requirements.txt lists the shared package as an editable path for local development (`-e ../shared`);
# in the image it is installed normally, so the runtime stage needs only the virtualenv.
RUN sed 's#^-e \.\./shared#/shared#' requirements.txt > requirements.docker.txt \
    && python -m venv /opt/venv && /opt/venv/bin/pip install -r requirements.docker.txt

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system --gid 10001 app && useradd --system --uid 10001 --gid app --no-create-home app
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app code-execution-service/alembic.ini ./
COPY --chown=app:app code-execution-service/alembic ./alembic
COPY --chown=app:app code-execution-service/app ./app
COPY --chown=app:app code-execution-service/runtimes ./runtimes

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"

# Migrations run as a separate step (see docker-compose `code-execution-service-migrate`), never on app start.
# The background worker uses this same image with `python -m app.worker`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--no-server-header"]
