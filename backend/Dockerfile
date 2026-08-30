# Runtime image for the SimplestWins API.
#
# The benchmark runner is deliberately NOT installed here: it pulls scikit-learn
# and its native stack, which the API never imports. Benchmarks are executed
# offline and their results promoted into the seed, so the served image stays
# small and its dependency surface stays narrow.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependency metadata first, so a source-only change reuses the install layer.
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./

RUN pip install --no-cache-dir . \
    && adduser --disabled-password --gecos "" --uid 10001 appuser \
    && chown -R appuser /app

USER appuser

EXPOSE 8000

# The platform's health check should hit /health, which reports how many
# problems loaded rather than merely that the process is alive.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"

# Migrations run before the app so a fresh database is usable on first boot.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
