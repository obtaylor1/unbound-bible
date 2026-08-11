FROM python:3.12.11-slim-bookworm@sha256:519591d6871b7bc437060736b9f7456b8731f1499a57e22e6c285135ae657bf7

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
RUN apt-get update \
    && apt-get install --no-install-recommends --yes postgresql-client \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.8.13
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY backend ./backend
COPY scripts/backup-staging.sh scripts/restore-check-staging.sh ./backend/scripts/
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && mkdir -p /var/backups/unbound-bible \
    && chmod 0755 /app/backend/scripts/backup-staging.sh /app/backend/scripts/restore-check-staging.sh \
    && chown -R app:app /app \
    && chown app:app /var/backups/unbound-bible

USER app
WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.application:app --host 0.0.0.0 --port 8000"]
