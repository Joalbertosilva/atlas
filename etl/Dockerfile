FROM docker.io/library/python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# poppler-utils: pdftotext para conferir o relatório oficial de totalização (reconcile)
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY etl/requirements.txt /app/etl/requirements.txt
RUN pip install -r /app/etl/requirements.txt
COPY etl /app/etl
RUN pip install --no-deps /app/etl
COPY migrations /app/migrations
ENTRYPOINT ["atlas-etl"]
CMD ["--help"]
