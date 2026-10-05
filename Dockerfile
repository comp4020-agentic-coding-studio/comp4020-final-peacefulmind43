# syntax = docker/dockerfile:1

# The app: FastAPI on uvicorn, one process (doc/adr/0001). It serves HTTP on
# 0.0.0.0:$PORT (fly.toml sets PORT) and renders README.md at /readme/.
# SQLite lives on the volume at /data; migrations run as the app starts.

FROM docker.io/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/ data/
COPY README.md .

# exec, so uvicorn gets signals directly and shuts down cleanly on a redeploy
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
