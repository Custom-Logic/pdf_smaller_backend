"""Task queue wrapper for Celery integration"""

import logging
from src.celery_app import celery_app
from src.tasks.tasks import compress_task as celery_compress_task
from src.tasks.tasks import bulk_compress_task as celery_bulk_compress_task

logger = logging.getLogger(__name__)

class TaskQueue:
    """Task queue wrapper for Celery integration"""
    
    def __init__(self):
        """Initialize task queue"""
        self.celery_app = celery_app
    
    def enqueue(self, task_func, *args, **kwargs):
        """Enqueue a task for asynchronous processing
        
        This method provides a compatibility layer between the old queue system
        and Celery. It maps task functions to their Celery counterparts.
        
        Args:
            task_func: The task function to execute
            *args: Positional arguments for the task
            **kwargs: Keyword arguments for the task
            
        Returns:
            The task ID
        """
        # Map task functions to their Celery counterparts
        task_mapping = {
            compress_task: celery_compress_task,
            bulk_compress_task: celery_bulk_compress_task
        }
        
        # Get the Celery task function
        celery_task = task_mapping.get(task_func)
        if not celery_task:
            logger.error(f"Unknown task function: {task_func.__name__}")
            raise ValueError(f"Unknown task function: {task_func.__name__}")
        
        # Apply the task asynchronously
        result = celery_task.delay(*args, **kwargs)
        return result.id

# Task function placeholders for compatibility
def compress_task(job_id, file_data, settings, original_filename=None, client_job_id=None, client_session_id=None):
    """Placeholder for compression task - will be replaced by Celery task"""
    pass

def bulk_compress_task(job_id, file_paths, settings, client_job_id=None, client_session_id=None):
    """Placeholder for bulk compression task - will be replaced by Celery task"""
    pass

# Create a singleton instance
task_queue = TaskQueue()