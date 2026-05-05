# Base image
FROM python:3.11-slim

WORKDIR /app

# Cài system dependencies cho Playwright/Chromium 
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libxkbcommon0 libxcomposite1 \
    libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libx11-6 libx11-xcb1 \
    libdrm2 libxext6 libxshmfence1 \
    fonts-liberation libappindicator3-1 \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Cài Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cài Playwright Chromium
RUN playwright install chromium \
    && playwright install-deps chromium

# Copy source code
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Tạo thư mục data nếu chưa có
RUN mkdir -p ./backend/data

WORKDIR /app/backend

EXPOSE 8000

# Khởi động API server
CMD ["python", "main.py"]