# ─── Stage 1: Builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies (torch needs some C libs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime libs needed by OpenCV / torchvision
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m -u 1001 fluser

# Copy installed packages
COPY --from=builder /usr/local/lib/python3.11 /usr/local/lib/python3.11
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY . .

# Directories for model checkpoints and dataset cache
RUN mkdir -p /app/tmp_models /app/dataset_cache && \
    chown -R fluser:fluser /app

USER fluser

# FL microservice port — aggregator (8500) or client (8600+) set via env
EXPOSE 8500

# Set default role; override with -e NODE_ROLE=client in docker run / K8s spec
ENV NODE_ROLE=hybrid
ENV FL_BACKEND_HOST=0.0.0.0
ENV FL_BACKEND_PORT=8500

# Health check against /fl/status
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${FL_BACKEND_PORT}/fl/status')" || exit 1

CMD ["sh", "-c", "uvicorn fl_backend.main:app --host ${FL_BACKEND_HOST} --port ${FL_BACKEND_PORT} --workers 2"]
