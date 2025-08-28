#!/bin/bash
# Start Celery worker and beat scheduler for PDF compression tasks

# Set environment variables
export FLASK_APP=app.py
export FLASK_ENV=development

# Start Redis server (if not already running)
echo "Starting Redis server..."
redis-server --daemonize yes --port 6379

# Wait for Redis to start
sleep 2

# Start Celery worker in background
echo "Starting Celery worker..."
celery -A celery_worker.celery worker --loglevel=info --concurrency=2 --queues=compression,cleanup &
WORKER_PID=$!

# Start Celery beat scheduler in background
echo "Starting Celery beat scheduler..."
celery -A celery_worker.celery beat --loglevel=info &
BEAT_PID=$!

# Function to cleanup on exit
cleanup() {
    echo "Stopping Celery processes..."
    kill $WORKER_PID 2>/dev/null
    kill $BEAT_PID 2>/dev/null
    echo "Celery processes stopped."
}

# Set trap to cleanup on script exit
trap cleanup EXIT

echo "Celery worker PID: $WORKER_PID"
echo "Celery beat PID: $BEAT_PID"
echo "Press Ctrl+C to stop all processes"

# Wait for processes
wait