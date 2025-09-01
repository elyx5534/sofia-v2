# Multi-stage build for production
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:3.11-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 sofia && \
    mkdir -p /app /data /models && \
    chown -R sofia:sofia /app /data /models

# Copy Python packages from builder
COPY --from=builder /root/.local /home/sofia/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=sofia:sofia . .

# Switch to non-root user
USER sofia

# Add local bin to PATH
ENV PATH=/home/sofia/.local/bin:$PATH

# Set Python to unbuffered mode
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8000 3000 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["python", "start_trading.py"]