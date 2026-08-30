FROM python:3.11.16-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv "$VIRTUAL_ENV"

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install -r requirements.txt


FROM python:3.11.16-slim AS runtime

ARG APP_UID=10001
ARG APP_GID=10001

ENV HOME=/home/setu \
    HF_HOME=/cache/huggingface \
    PATH="/opt/venv/bin:$PATH" \
    PORT=8000 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp

RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid "$APP_GID" setu \
    && useradd --uid "$APP_UID" --gid "$APP_GID" --create-home \
        --shell /usr/sbin/nologin setu \
    && install -d -o "$APP_UID" -g "$APP_GID" -m 0755 \
        /app /cache/huggingface /models/openvino

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=${APP_UID}:${APP_GID} app ./app
COPY --chown=${APP_UID}:${APP_GID} ingestion ./ingestion
COPY --chown=${APP_UID}:${APP_GID} models/openvino ./models/openvino

USER ${APP_UID}:${APP_GID}

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
