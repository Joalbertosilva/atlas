FROM docker.io/library/python:3.14-slim-bookworm@sha256:48b13b003dda20b16f9442b8475aa05fe21bf6579a8c881db92ffb4d8fd20f83

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 HOME=/tmp
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install -r requirements.txt && useradd --system --uid 10001 --home-dir /tmp atlas
COPY backend/atlas_api /app/atlas_api
COPY backend/wsgi.py /app/wsgi.py
USER atlas
EXPOSE 8000
# 1 processo com threads: o rate limit e o cache de geometria ficam em memória do processo.
# Sem --access-logfile: consultas de busca não são registradas.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", "--timeout", "60", \
     "--error-logfile", "-", "--log-level", "warning", "wsgi:app"]
