# NEPSE AI Trading Bot - Dockerfile
# Multi-stage build for smaller image size

# Stage 1: Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies including git (needed for pip install from GitHub)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Install NepseUnofficialApi with --no-deps to avoid tqdm version conflict
# (nepse wants tqdm==4.66.5, but pandas-ta needs tqdm>=4.67.1)
RUN pip install --no-cache-dir --user --no-deps git+https://github.com/basic-bgnr/NepseUnofficialApi

# Stage 2: Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies (for playwright)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Make sure scripts in .local are usable
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Install playwright browsers (for news scraping)
RUN playwright install chromium --with-deps || true

# Create data directory
RUN mkdir -p /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Force HTTP/1.1 for httpx (HTTP/2 has issues in Docker with NEPSE API)
ENV HTTPX_HTTP2=0

# Expose port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: Run FastAPI server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
