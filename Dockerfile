# Robot Diary Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    wget \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Hugo
# Download and install Hugo extended version (required for PaperMod theme)
RUN HUGO_VERSION=0.152.2 && \
    wget -O hugo.deb https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb && \
    dpkg -i hugo.deb && \
    rm hugo.deb && \
    hugo version

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p images memory weather hugo/content/posts hugo/static/images

# Set environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV HUGO_SITE_PATH=./hugo

# Default command
CMD ["python", "run_service.py"]

