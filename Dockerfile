# Use Python 3.10 slim as base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by OpenCV, MediaPipe, and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgl1 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install protobuf FIRST and lock it
RUN pip install --no-cache-dir protobuf==4.25.3

# Install mediapipe next (so it binds to correct protobuf)
RUN pip install --no-cache-dir mediapipe==0.10.18

RUN pip install --no-cache-dir torch==2.1.0 torchvision==0.16.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir boto3

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p logs static models/weights
# Disable reload in production
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
