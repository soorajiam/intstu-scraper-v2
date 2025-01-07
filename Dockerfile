# Build stage
FROM python:3.9-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.9-slim

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core dependencies
    libasound2 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libexpat1 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    fonts-liberation \
    # Additional required dependencies
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    # Dependencies for install-deps
    sudo \
    # Install playwright CLI
    npm \
    && npm install -g playwright \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user with sudo access for install-deps
RUN useradd -m -u 1000 scraper && \
    echo "scraper ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

USER scraper

# Create app directory
WORKDIR /home/scraper/app

# Copy application code
COPY --chown=scraper:scraper src/ ./src/

# Create log directory
RUN mkdir -p /home/scraper/app/log && \
    chown -R scraper:scraper /home/scraper/app/log

# Set environment variables
ENV PYTHONPATH=/home/scraper/app \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/home/scraper/app/.playwright

# Install browser and dependencies
RUN playwright install && sudo playwright install-deps

# Set resource limits for chromium
ENV CHROMIUM_FLAGS="--disable-dev-shm-usage \
    --disable-gpu \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-software-rasterizer \
    --disable-features=IsolateOrigins,site-per-process \
    --disable-site-isolation-trials"

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')"

ENTRYPOINT ["python", "-m", "src.main"]