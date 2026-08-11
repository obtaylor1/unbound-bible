FROM ghcr.io/astral-sh/uv:0.8.13 AS uv
FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY backend ./backend
RUN groupadd --system app && useradd --system --gid app --home /app app \
    && chown -R app:app /app

USER app
WORKDIR /app/backend
EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.application:app --host 0.0.0.0 --port 8000"]
