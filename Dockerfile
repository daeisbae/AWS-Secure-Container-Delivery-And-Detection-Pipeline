FROM python:3.12.9-alpine3.21@sha256:28b8a72c4e0704dd2048b79830e692e94ac2d43d30c914d54def6abf74448a4e AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup -S -g 10001 app \
    && adduser -S -D -H -u 10001 -G app -s /sbin/nologin app

COPY requirements.lock ./
RUN DISABLE_SQLALCHEMY_CEXT=1 python -m pip install \
    --no-cache-dir \
    --require-hashes \
    --requirement requirements.lock

COPY --chown=10001:10001 app ./app

FROM runtime AS production

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
