FROM python:3.12-slim-bookworm

WORKDIR /app

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl build-essential python3-dev \
        libffi-dev libssl-dev; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary --timeout 180 -r requirements.txt

COPY . .

RUN mkdir -p logs

EXPOSE 5000
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "4", "--threads", "4", \
     "--worker-class", "gthread", \
     "--timeout", "180", "--graceful-timeout", "30", \
     "--max-requests", "1000", "--max-requests-jitter", "100", \
     "--keep-alive", "5", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "run:app"]
