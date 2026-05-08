# --- Stage 1: Build Frontend ---
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend dependency files and install
COPY frontend/package*.json ./
RUN npm install

# Copy the rest of the frontend source and build
COPY frontend .
RUN npm run build

# --- Stage 2: Build Final Image ---
FROM python:3.11-slim

WORKDIR /app

# Install nginx and dos2unix (to fix line endings on windows hosts)
RUN apt-get update && \
    apt-get install -y nginx dos2unix && \
    rm -rf /var/lib/apt/lists/*

# Install Backend dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy Backend source code
COPY backend ./backend

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist /var/www/html

# Copy configurations and scripts
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/start.sh /app/start.sh

# Fix line endings and make script executable
RUN dos2unix /app/start.sh && chmod +x /app/start.sh

# Create data directories to be used as volumes
RUN mkdir -p /app/data /app/data/covers /app/data/works

# Expose HTTP port
EXPOSE 80

# Expose data directory for persistence
VOLUME ["/app/data"]

# Start services
CMD ["/app/start.sh"]
