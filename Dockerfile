FROM python:3.12-slim

# Install arm-none-eabi-gcc toolchain + git + make
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    git \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY . .

# Create output directory
RUN mkdir -p /app/generated

# Default entrypoint
ENTRYPOINT ["python", "run.py"]
