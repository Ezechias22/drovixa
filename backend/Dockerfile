FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY backend/requirements.txt ./requirements.txt
RUN pip wheel --wheel-dir=/wheels -r requirements.txt

FROM python:3.12-slim AS runtime

ARG BUILD_SHA=local
ARG RELEASE=drovixa@0.9.0
LABEL org.opencontainers.image.title="Drovixa API" \
      org.opencontainers.image.version="0.9.0" \
      org.opencontainers.image.revision="$BUILD_SHA"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    BUILD_SHA=$BUILD_SHA \
    RELEASE=$RELEASE

RUN groupadd --system drovixa && useradd --system --gid drovixa --create-home drovixa

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations
COPY backend/app ./app

USER drovixa
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
