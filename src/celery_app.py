"""
Celery application configuration for background task processing
"""
import os
from celery import Celery
from src.config import Config


def make_celery(app=None):
    """
    Create and configure Celery instance
    
    Args:
        app: Flask application instance (optional)
        
    Returns:
        Configured Celery instance
    """
    # Get configuration
    config = Config()
    
    # Create Celery instance
    celery = Celery(
        'pdf_tools_tasks',
        broker=config.CELERY_BROKER_URL,
        backend=config.CELERY_RESULT_BACKEND,
        include=['src.tasks.tasks']
    )
    
    # Configure Celery
    celery.conf.update(
        # Task settings
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
        
        # Task routing
        task_routes={
            'src.tasks.process_bulk_compression': {'queue': 'compression'},
            'src.tasks.cleanup_expired_jobs': {'queue': 'cleanup'},
            'src.tasks.process_compression': {'queue': 'compression'},
            'tasks.compress_task': {'queue': 'compression'},
            'tasks.bulk_compress_task': {'queue': 'compression'},
            'tasks.cleanup_expired_jobs': {'queue': 'cleanup'},
            'tasks.get_task_status': {'queue': 'default'}
        },
        
        # Worker settings
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        worker_max_tasks_per_child=50,
        
        # Result backend settings
        result_expires=3600,  # 1 hour
        
        # Task execution settings
        task_soft_time_limit=300,  # 5 minutes soft limit
        task_time_limit=600,       # 10 minutes hard limit
        
        # Retry settings
        task_default_retry_delay=60,  # 1 minute
        task_max_retries=3,
        
        # Beat schedule for periodic tasks
        beat_schedule={
            'cleanup-expired-jobs': {
                'task': 'src.tasks.cleanup_expired_jobs',
                'schedule': 3600.0,  # Run every hour
                'options': {'queue': 'cleanup'}
            },
        },
    )
    
    # Update task base classes if Flask app is provided
    if app:
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context"""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
    
    return celery


# Create default Celery instance
celery_app = make_celery()