#!/bin/sh

# Start the backend in the background
echo "Starting backend..."
cd /app/backend
uvicorn main:app --host 127.0.0.1 --port 8000 &

# Start nginx in the foreground
echo "Starting nginx..."
exec nginx -g "daemon off;"
