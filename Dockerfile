# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for dlib and face-recognition
# build-essential: gcc, g++, make for compiling C/C++ code
# cmake: build tool required by dlib
# libopenblas-dev: optimized BLAS library for numerical computations
# liblapack-dev: linear algebra library
# libx11-dev: X11 development files for display support
# libgtk-3-dev: GTK+ development files for GUI support
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip to latest version
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (specific directories and files only)
COPY app.py .
COPY azure_openai_chat.py .
COPY realtime_chat.py .
COPY src/ ./src/
COPY static/ ./static/
COPY templates/ ./templates/
COPY data/ ./data/
COPY tcg-cache/ ./tcg-cache/

# Create necessary directories for runtime
RUN mkdir -p profiles_pic cache

# Expose port 8000 (gunicorn default)
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Run gunicorn with 4 workers
# --bind 0.0.0.0:8000 - listen on all interfaces
# --workers 4 - use 4 worker processes
# --timeout 120 - 120 second timeout for requests
# --access-logfile - - log to stdout
# --error-logfile - - log errors to stdout
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
