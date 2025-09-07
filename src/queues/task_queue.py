"""Task queue wrapper for Celery integration"""

import logging
from src.celery_app import celery_app
from src.tasks.tasks import (
    compress_task as celery_compress_task,
    bulk_compress_task as celery_bulk_compress_task,
    convert_pdf_task as celery_convert_pdf_task,
    conversion_preview_task as celery_conversion_preview_task,
    ocr_process_task as celery_ocr_process_task,
    ocr_preview_task as celery_ocr_preview_task,
    ai_summarize_task as celery_ai_summarize_task,
    ai_translate_task as celery_ai_translate_task,
    extract_text_task as celery_extract_text_task
)

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
            bulk_compress_task: celery_bulk_compress_task,
            convert_pdf_task: celery_convert_pdf_task,
            conversion_preview_task: celery_conversion_preview_task,
            ocr_process_task: celery_ocr_process_task,
            ocr_preview_task: celery_ocr_preview_task,
            ai_summarize_task: celery_ai_summarize_task,
            ai_translate_task: celery_ai_translate_task,
            extract_text_task: celery_extract_text_task
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

def convert_pdf_task(job_id, file_data, target_format, options, original_filename=None, client_job_id=None, client_session_id=None):
    """Placeholder for PDF conversion task - will be replaced by Celery task"""
    pass

def conversion_preview_task(job_id, file_data, target_format, options, client_job_id=None, client_session_id=None):
    """Placeholder for conversion preview task - will be replaced by Celery task"""
    pass

def ocr_process_task(job_id, file_data, options, original_filename=None, client_job_id=None, client_session_id=None):
    """Placeholder for OCR processing task - will be replaced by Celery task"""
    pass

def ocr_preview_task(job_id, file_data, options, client_job_id=None, client_session_id=None):
    """Placeholder for OCR preview task - will be replaced by Celery task"""
    pass

def ai_summarize_task(job_id, text, options, client_job_id=None, client_session_id=None):
    """Placeholder for AI summarization task - will be replaced by Celery task"""
    pass

def ai_translate_task(job_id, text, target_language, options, client_job_id=None, client_session_id=None):
    """Placeholder for AI translation task - will be replaced by Celery task"""
    pass

def extract_text_task(job_id, file_data, original_filename=None, client_job_id=None, client_session_id=None):
    """Placeholder for text extraction task - will be replaced by Celery task"""
    pass

# Create a singleton instance
task_queue = TaskQueue()

# Add Redis connection for compatibility
try:
    import redis
    from src.config.config import Config
    config = Config()
    redis_conn = redis.Redis.from_url(config.CELERY_BROKER_URL)
except ImportError:
    redis_conn = None
    logger.warning("Redis not available - using mock connection")