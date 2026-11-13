# FinTrack API image. Built by docker-compose.yml (`build: ./backend`).
# backend/.dockerignore keeps .env, data/ and tests out of the image.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --extra postgres --no-install-project

COPY . .
RUN uv sync --frozen --no-dev --extra postgres

# ENVIRONMENT=production refuses to start without a real SECRET_KEY and hides /api/docs.
# FORWARDED_ALLOW_IPS: uvicorn only trusts X-Forwarded-For from these addresses (the frontend's
# nginx, on a private Docker network). Trusting "*" would let any client pick its own IP and
# dodge the login rate limits.
ENV PATH="/app/.venv/bin:$PATH" \
    DATABASE_URL=sqlite:////data/fintrack.db \
    ENVIRONMENT=production \
    FORWARDED_ALLOW_IPS="127.0.0.1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16"

# Run as an unprivileged user; /data is the volume holding the SQLite database.
RUN useradd --system --uid 10001 fintrack \
    && mkdir -p /data \
    && chown fintrack /data
USER fintrack
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4)"

# Apply migrations, then serve. One worker: the in-process scheduler must run only once.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
