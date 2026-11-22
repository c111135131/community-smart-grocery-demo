# Backend image. Build context is the REPOSITORY ROOT (see docker-compose.yml) so the
# knowledge base can be copied in:   docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    KNOWLEDGE_BASE_PATH=/app/knowledge_base/nutrition_seed.json

WORKDIR /app

# Install dependencies first so this layer is cached until requirements.txt changes.
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ ./
COPY knowledge_base/ ./knowledge_base/

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["sh", "scripts/docker-entrypoint.sh"]
