FROM python:3.11-slim-bullseye

# Installeer RTL-SDR dependencies
RUN apt-get update && apt-get install -y \
    rtl-sdr \
    librtlsdr-dev \
    libusb-1.0-0-dev \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# Maak werkdirectory
WORKDIR /app

# Kopieer requirements en installeer dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Kopieer applicatie files
COPY src/ /app/src/
COPY configs/ /app/configs/

# Maak logs directory
RUN mkdir -p /app/logs

# Set Python path
ENV PYTHONPATH=/app/src

# Start script
WORKDIR /app/src
CMD ["python", "-u", "tetra_detector.py"]