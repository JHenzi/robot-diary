# syntax=docker/dockerfile:1.7

# Robot Diary Dockerfile
FROM python:3.11-slim

# Keep apt/dpkg fully noninteractive during image builds.
ARG DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    git \
    rsync \
    openssh-client

# Create .ssh directory for mounted key
RUN mkdir -p /app/.ssh && chmod 700 /app/.ssh

# Install Hugo
# Download and install Hugo extended version (required for PaperMod theme)
# Detect architecture and install appropriate Hugo binary
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    HUGO_VERSION=0.152.2 && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        wget -O hugo.deb https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-amd64.deb; \
    elif [ "$ARCH" = "arm64" ]; then \
        wget -O hugo.deb https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_linux-arm64.deb; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    dpkg -i hugo.deb || DEBIAN_FRONTEND=noninteractive apt-get install -f -y && \
    rm hugo.deb && \
    hugo version

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install CPU-only PyTorch first to prevent pip from pulling NVIDIA CUDA packages
# (sentence-transformers would otherwise resolve CUDA variants, adding ~1.5 GB)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p images memory weather hugo/content/posts hugo/static/images

# Set environment variables (can be overridden)
ENV PYTHONUNBUFFERED=1
ENV HUGO_SITE_PATH=./hugo

# Default command
CMD ["python", "run_service.py"]
