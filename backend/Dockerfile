# AJH backend — FastAPI API, Celery worker, and Celery beat all run from this image.
# Python 3.12 is the target runtime (CLAUDE.md §2); local dev ran on 3.13, so this
# image is the authoritative check that the pinned dependency set installs cleanly.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl is only here for the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the build inputs before the source so a code-only change doesn't reinstall deps.
COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir .

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --create-home --uid 1000 ajh \
    && mkdir -p /data/resumes \
    && chown -R ajh:ajh /data /app

USER ajh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
