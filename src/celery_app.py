"""
src/celery_app.py
Celery application configuration for background task processing
"""
import os
from celery import Celery
from src.config import Config
# DO NOT REMOVE: This import is necessary to register tasks with Celery

def make_celery(app=None):
    """
    Create and configure Celery instance
    
    Args:
        app: Flask application instance (optional)
        
    Returns:
        Configured Celery instance
    """
    # Get configuration
    from src.tasks import tasks

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
            # Compression tasks
            'tasks.compress_task': {'queue': 'compression'},
            'tasks.bulk_compress_task': {'queue': 'compression'},
            
            # Conversion tasks
            'tasks.convert_pdf_task': {'queue': 'conversion'},
            'tasks.conversion_preview_task': {'queue': 'conversion'},
            
            # OCR tasks
            'tasks.ocr_process_task': {'queue': 'ocr'},
            'tasks.ocr_preview_task': {'queue': 'ocr'},
            
            # AI tasks
            'tasks.ai_summarize_task': {'queue': 'ai'},
            'tasks.ai_translate_task': {'queue': 'ai'},
            
            # Extraction tasks
            'tasks.extract_text_task': {'queue': 'extraction'},
            'tasks.extract_invoice_task': {'queue': 'extraction'},
            'tasks.extract_bank_statement_task': {'queue': 'extraction'},
            
            # File management tasks
            'tasks.merge_pdfs_task': {'queue': 'file_ops'},
            'tasks.split_pdf_task': {'queue': 'file_ops'},
            
            # Maintenance tasks
            'tasks.health_check_task': {'queue': 'maintenance'},
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
                'task': 'tasks.cleanup_expired_jobs',
                'schedule': 3600.0,  # Run every hour
                'options': {'queue': 'cleanup'}
            },
            'cleanup-temp-files': {
                'task': 'tasks.cleanup_temp_files_task',
                'schedule': 1800.0,  # Run every 30 minutes
                'options': {'queue': 'maintenance'},
                'kwargs': {'max_age_hours': 24}
            },
            'health-check': {
                'task': 'tasks.health_check_task',
                'schedule': 900.0,  # Run every 15 minutes
                'options': {'queue': 'maintenance'}
            }
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


# Create default Celery instance (will be replaced by Flask app integration)
celery_app = None

def get_celery_app():
    """Get the current Celery app instance"""
    global celery_app
    if celery_app is None:
        # Fallback for testing or standalone usage
        celery_app = make_celery()
    return celery_app

def set_celery_app(app):
    """Set the Celery app instance (called from Flask app factory)"""
    global celery_app
    celery_app = app