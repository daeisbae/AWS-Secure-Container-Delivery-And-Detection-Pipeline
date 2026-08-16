FROM python:3.12.14-alpine3.23@sha256:aa81c9c4cc2f42592a6c8a9fba3a13838d9372e81e86030bf73132d5b8c5e4e8 AS runtime

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
