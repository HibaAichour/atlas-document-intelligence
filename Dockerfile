# Production image of ATLAS: one container for the online demo.
# FastAPI serves the API and the compiled frontend; the LLM (Groq) and the
# embeddings (Gemini) are external APIs, so no model runs in the container.
# Build from the root of the repository:  docker build -t atlas .
# The local stack (Nginx + Ollama on the Mac) is docker-compose.yml, unchanged.

# Base images pinned to exact versions (measured on 2026-10-29), so that a
# new release of an image never rebuilds or changes the demo by surprise.
# To take security fixes, raise these versions on purpose and rebuild.

# Stage 1: compile the React frontend into static files (/app/frontend/dist).
FROM node:24.22.2-alpine3.24 AS frontend
WORKDIR /app/frontend
# Dependencies first, so this layer stays cached between code changes.
# npm ci also installs the development tools: "npm run build" runs tsc -b.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python backend, which also serves the compiled frontend.
FROM python:3.13.18-slim-trixie

# Do not write .pyc files, and print logs immediately (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Tesseract reads the scanned demo invoice while the image is built
# (uploads are disabled in the online demo, see DEMO_MODE below).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies before the code, so this layer stays cached.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/scripts ./scripts
COPY demo_documents ./demo_documents
COPY --from=frontend /app/frontend/dist ./static

# Run as a non-root user, who owns the data folder (SQLite and Chroma).
RUN useradd --create-home atlas \
    && mkdir -p /app/data \
    && chown atlas:atlas /app/data
USER atlas

# Record the demo documents with their pages (OCR included), without
# embeddings: the build needs neither the network nor an API key.
ENV DATA_DIR=/app/data
RUN python -m scripts.seed_demo demo_documents

# Online configuration. The two keys are NOT here: they are secrets given to
# the container at run time (LLM_API_KEY for Groq, EMBEDDING_API_KEY for Gemini).
ENV DEMO_MODE=true \
    STATIC_DIR=/app/static \
    LLM_PROVIDER=openai_compatible \
    LLM_BASE_URL=https://api.groq.com/openai/v1 \
    LLM_MODEL=openai/gpt-oss-20b \
    EMBEDDING_PROVIDER=openai_compatible \
    EMBEDDING_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai \
    EMBEDDING_MODEL=gemini-embedding-001

# The hosting platform gives the port in $PORT (8000 when run locally).
EXPOSE 8000

# At each start (the free host erases the disk when the service sleeps):
# compute the vectors of the demo documents, then start the server. If the
# embedding API fails, the server still starts and questions are refused.
CMD ["sh", "-c", "python -m scripts.reindex; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]