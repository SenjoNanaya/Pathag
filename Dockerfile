# Pathag API — suitable for Render (Docker) or local `docker build`.
FROM python:3.11-slim-bookworm

WORKDIR /app

# libpq for psycopg2-binary
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
# Render sets PORT; default 8000 for local runs
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
