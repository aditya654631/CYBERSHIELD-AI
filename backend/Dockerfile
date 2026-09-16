# CyberShield AI — Production Backend Dockerfile
FROM python:3.13-slim AS runner

# Install runtime system dependencies (libgomp for XGBoost, curl for health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for container security
RUN useradd -u 1000 -m -s /bin/bash appuser

WORKDIR /app

# Install reproducible dependencies first for efficient layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY backend ./backend
COPY ml ./ml
COPY database ./database
COPY alembic ./alembic
COPY alembic.ini .

# Set environment paths and ownership
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    MODEL_ARTIFACTS_DIR=/app/ml/artifacts

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
