FROM python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a AS runtime

ARG BUILD_SHA=local
ARG RELEASE=drovixa@0.12.0
LABEL org.opencontainers.image.title="Drovixa API" \
      org.opencontainers.image.version="0.12.0" \
      org.opencontainers.image.revision="$BUILD_SHA"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BUILD_SHA=$BUILD_SHA \
    RELEASE=$RELEASE

RUN groupadd --system drovixa && \
    useradd --system --gid drovixa --create-home drovixa

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN set -eux; \
    test -s requirements.txt; \
    test "$(wc -l < requirements.txt)" -ge 16; \
    python -c 'import sys; print(sys.version); assert sys.version_info[:2] == (3, 12)'; \
    python -m ensurepip --upgrade; \
    python -m pip --isolated install --upgrade pip setuptools wheel; \
    python -m pip --isolated install --no-cache-dir -r requirements.txt; \
    python -m pip check; \
    command -v alembic; \
    command -v celery; \
    python -c 'import alembic, celery, fastapi, sqlalchemy; print("Drovixa backend dependencies verified")'

COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/app ./app

USER drovixa
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
