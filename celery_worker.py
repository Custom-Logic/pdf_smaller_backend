#!/usr/bin/env python3
"""
celery_worker.py
Celery worker entry point for PDF compression tasks
"""
import os
import sys

# Add the project root to Python path
sys.path.insert(0, '/root/app/pdf_smaller_backend')

from src.main.main import create_app
from src.celery_app import make_celery

# Create Flask app
app = create_app()

# Create Celery instance with Flask app context
celery = make_celery(app)

if __name__ == '__main__':
    # Start the worker with proper arguments
    argv = [
        'worker',
        '--loglevel=info',
        '--queues=compression,cleanup,default',
        '--concurrency=2',
        '--hostname=pdf_worker@%h'
    ]
    celery.worker_main(argv)