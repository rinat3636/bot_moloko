FROM python:3.11-slim-bookworm

WORKDIR /app

# selectolax may compile C extensions on Linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN mkdir -p /app/logs /app/data /app/data/photo_cache \
    && chmod +x /app/scripts/docker-entrypoint.sh

# Telegram polling bot — no HTTP port required
CMD ["/app/scripts/docker-entrypoint.sh"]
