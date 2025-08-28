#!/usr/bin/env python3
"""
Celery worker entry point for PDF compression tasks
"""
import os
import sys
from src.main.main import create_app
from src.celery_app import make_celery

# Create Flask app
app = create_app()

# Create Celery instance with Flask app context
celery = make_celery(app)

if __name__ == '__main__':
    # Start the worker
    celery.start()