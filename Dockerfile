# Robot Diary Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p images memory weather hugo/content/posts hugo/static/images

# Set environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV HUGO_SITE_PATH=./hugo

# Default command
CMD ["python", "run_service.py"]

