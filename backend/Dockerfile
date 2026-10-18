# Backend image: FastAPI served by Uvicorn.
FROM python:3.13-slim

# Do not write .pyc files, and print logs immediately (no buffering).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first, so this layer is cached between code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Then copy the application code.
COPY app ./app

# Run as a non-root user for safety.
RUN useradd --create-home atlas
USER atlas

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]