@echo off
REM Start Celery worker and beat scheduler for PDF compression tasks (Windows)

REM Set environment variables
set FLASK_APP=app.py
set FLASK_ENV=development

echo Starting Redis server...
REM Note: Redis needs to be installed separately on Windows
REM You can use Redis for Windows or run it via Docker
REM docker run -d -p 6379:6379 redis:alpine

echo Starting Celery worker...
start "Celery Worker" celery -A celery_worker.celery worker --loglevel=info --concurrency=2 --queues=compression,cleanup

echo Starting Celery beat scheduler...
start "Celery Beat" celery -A celery_worker.celery beat --loglevel=info

echo Celery processes started in separate windows
echo Close the worker and beat windows to stop the processes
pause