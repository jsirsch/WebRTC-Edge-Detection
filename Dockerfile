# Use a lightweight Python base image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# 1. Install system dependencies required for OpenCV and AioRTC
# - libgl1 / libglib2.0-0: Required by OpenCV
# - libavdevice-dev / libavfilter-dev / opus / vpx: Required by AioRTC/FFmpeg
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    libavdevice-dev \
    libavfilter-dev \
    libopus-dev \
    libvpx-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 2. Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy the rest of the application code
COPY server.py .
COPY index.html .

# 4. Expose the signaling port (TCP)
EXPOSE 8080
# Note: WebRTC also uses random UDP ports for media, see "How to Run" below.

# 5. Run the server
CMD ["python", "server.py"]