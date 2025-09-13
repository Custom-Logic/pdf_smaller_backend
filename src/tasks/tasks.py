"""
src/tasks/tasks.py
Celery tasks for background job processing – context-safe refactor
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from celery import current_task
from src.celery_app import get_celery_app

# Get the Celery app instance
from flask import current_app
celery_app = get_celery_app()
from src.config.config import Config
from src.models import Job, JobStatus
from src.models.base import db

from src.services.service_registry import ServiceRegistry
from src.exceptions.extraction_exceptions import ExtractionError, ExtractionValidationError
from src.exceptions.export_exceptions import ExportError, FormatError
from src.utils.job_operations import JobOperations
from src.utils.db_transaction import db_transaction, transactional, safe_db_operation
from src.utils.job_operations import JobOperations

# Exception imports for specific error handling
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError, StatementError
from celery.exceptions import Retry, WorkerLostError, Ignore, Reject
import requests
from src.utils.exceptions import ValidationError, ConfigurationError

# ------------------------------------------------------
#  IMPORT THE HELPER – keeps context for every task
# ------------------------------------------------------
# Context handling is now done via ContextTask class in celery_app.py
# No imports needed from app_context as it only contains pass

# ------------------------------------------------------
#  identical initialisation
# ------------------------------------------------------
logger = logging.getLogger(__name__)
config = Config()

# Services are now managed through ServiceRegistry
# No need for global service instances

# Three-tier error handling configuration
RETRYABLE_ERRORS = {
    # Tier 1: Transient errors - retry with exponential backoff
    'transient': {
        'exceptions': (DBAPIError, OperationalError, ConnectionError, TimeoutError),
        'max_retries': 3,
        'countdown': lambda retry_count: 60 * (2 ** retry_count),  # Exponential backoff
        'description': 'Database connection issues, network timeouts'
    },
    # Tier 2: Resource errors - retry with linear backoff
    'resource': {
        'exceptions': (MemoryError, OSError, IOError),
        'max_retries': 2,
        'countdown': lambda retry_count: 30 * (retry_count + 1),  # Linear backoff
        'description': 'Memory issues, file system errors'
    },
    # Tier 3: Processing errors - limited retry
    'processing': {
        'exceptions': (ExtractionError, RuntimeError),
        'max_retries': 1,
        'countdown': lambda retry_count: 120,  # Fixed delay
        'description': 'Processing failures that might be temporary'
    }
}

NON_RETRYABLE_ERRORS = {
    ExtractionValidationError, ValueError, 
    TypeError, AttributeError, KeyError
}

def categorize_error(exc: Exception) -> str:
    """Categorize error for appropriate handling strategy."""
    # Database errors - usually retryable
    if isinstance(exc, (DBAPIError, OperationalError, IntegrityError)):
        return 'database'
    
    # Network/external service errors - retryable with backoff
    if isinstance(exc, (ConnectionError, TimeoutError, requests.exceptions.RequestException)):
        return 'network'
    
    # File system errors - sometimes retryable
    if isinstance(exc, (IOError, OSError, PermissionError)):
        return 'filesystem'
    
    # Memory errors - not retryable
    if isinstance(exc, MemoryError):
        return 'memory'
    
    # Validation errors - not retryable
    if isinstance(exc, (ValueError, TypeError, ValidationError)):
        return 'validation'
    
    # Configuration errors - not retryable
    if isinstance(exc, (ImportError, AttributeError, ConfigurationError)):
        return 'configuration'
    
    # Unknown errors - limited retries
    return 'unknown'


def should_retry(error_tier: str, exc: Exception, current_retries: int) -> bool:
    """Determine if error should be retried based on tier and retry count."""
    retry_config = {
        'database': {'max_retries': 3, 'retryable': True},
        'network': {'max_retries': 5, 'retryable': True},
        'filesystem': {'max_retries': 2, 'retryable': True},
        'memory': {'max_retries': 0, 'retryable': False},
        'validation': {'max_retries': 0, 'retryable': False},
        'configuration': {'max_retries': 0, 'retryable': False},
        'unknown': {'max_retries': 1, 'retryable': True}
    }
    
    config = retry_config.get(error_tier, retry_config['unknown'])
    return config['retryable'] and current_retries < config['max_retries']


def calculate_retry_delay(error_tier: str, retry_count: int) -> int:
    """Calculate retry delay based on error tier and retry count."""
    base_delays = {
        'database': 30,  # Database issues need time to resolve
        'network': 60,   # Network issues may need longer
        'filesystem': 15, # File system issues usually resolve quickly
        'unknown': 45    # Conservative approach for unknown errors
    }
    
    base_delay = base_delays.get(error_tier, 45)
    # Exponential backoff with jitter
    return base_delay * (2 ** retry_count)


def handle_task_error(task_instance, exc, job_id, job=None):
    """Enhanced centralized error handling for all tasks."""
    from flask import current_app
    from src.utils.database_helpers import update_job_status_safely
    
    # Enhanced error categorization
    error_tier = categorize_error(exc)
    
    # Standardized job status update with safe database operation
    try:
        with current_app.app_context():
            update_job_status_safely(job_id, JobStatus.FAILED, str(exc), job)
    except Exception as db_err:
        logger.exception(f"Failed to update job {job_id} status: {db_err}")
    
    # Handle non-retryable errors
    if type(exc) in NON_RETRYABLE_ERRORS or not should_retry(error_tier, exc, task_instance.request.retries):
        logger.error(f"Non-retryable or max retries exceeded for job {job_id} ({error_tier} error): {exc}")
        if error_tier in ['memory', 'validation', 'configuration']:
            raise Ignore()  # Don't retry these error types
        raise exc
    
    # Handle retryable errors with consistent retry logic
    if should_retry(error_tier, exc, task_instance.request.retries):
        countdown = calculate_retry_delay(error_tier, task_instance.request.retries)
        logger.warning(
            f"Retrying job {job_id} ({error_tier} error, attempt {task_instance.request.retries + 1}): {exc}"
        )
        raise task_instance.retry(countdown=countdown, exc=exc)
    
    # Final error logging and handling
    logger.error(f"Task failed permanently for job {job_id} ({error_tier} error): {exc}")
    raise exc

# ------------------------------------------------------
#  helper – unchanged
# ------------------------------------------------------


# ------------------------------------------------------
#  COMPRESSION TASKS  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, name='tasks.compress_task')
def compress_task(self, job_id: str, file_data: bytes, compression_settings: Dict[str, Any],
                  original_filename: str | None = None) -> Dict[str, Any]:
    """Async compression task with centralized error handling."""
    job = None
    try:
        job = JobOperations.create_job_safely(
            job_id=job_id,
            job_type='compress',
            input_data={
                'compression_settings': compression_settings,
                'file_size': len(file_data),
                'original_filename': original_filename
            }
        )
        logger.debug(f"Starting compression task for job {job_id}")

        JobOperations.update_job_status(job_id, JobStatus.PROCESSING)
        logger.debug(f"Job {job_id} marked as processing")

        result = ServiceRegistry.get_compression_service().process_file_data(
            file_data=file_data,
            settings=compression_settings,
            original_filename=original_filename)
        logger.debug(f"File processed for job {job_id}, result: {result}")

        JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        logger.info(f"Compression job {job_id} completed successfully")
        return result

    except Exception as exc:
        handle_task_error(self, exc, job_id, job)

# ------------------------------------------------------
#  BULK COMPRESSION  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.bulk_compress_task', max_retries=3)
def bulk_compress_task(self, job_id: str, file_data_list: List[bytes],
                       filenames: List[str], settings: Dict[str, Any]) -> dict[str, int | list[Any] | Any] | None:
    """Process bulk compression task asynchronously with centralized error handling."""
    job = None
    try:
        logger.info(f"Starting bulk compression task for job {job_id}")
        job = JobOperations.create_job_safely(
            job_id=job_id,
            job_type='bulk_compress',
            input_data={
                'settings': settings,
                'file_count': len(file_data_list),
                'total_size': sum(len(d) for d in file_data_list)
            }
        )

        JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

        total_files = len(file_data_list)
        processed_files, errors = [], []

        for i, (file_data, filename) in enumerate(zip(file_data_list, filenames)):
            try:
                progress = int((i / total_files) * 100)
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i + 1,
                        'total': total_files,
                        'progress': progress,
                        'status': f'Processing file {i+1} of {total_files}: {filename}'
                    }
                )
                result = compression_service.process_file_data(file_data, settings, filename)
                processed_files.append(result)
                logger.info(f"Processed file {i+1}/{total_files} for job {job_id}: {filename}")

            except Exception as e:
                errors.append({'filename': filename, 'error': str(e), 'index': i})
                logger.error(f"Error processing file {filename} in job {job_id}: {str(e)}")
                continue

        result_path = None
        if processed_files:
            try:
                # Create archive of processed files and store on disk
                output_path = compression_service.file_service.create_result_archive(processed_files, job_id)
                result_data = {
                    'processed_files': len(processed_files),
                    'output_path': output_path,
                    'total_files': total_files,
                    'errors': errors,
                    'processed_files_info': processed_files
                }

                logger.info(f"Created result archive for job {job_id}: {output_path}")

                if errors and not processed_files:
                    JobOperations.update_job_status(job_id, JobStatus.FAILED, error_message=f"All files failed: {len(errors)} errors")
                elif errors:
                    result_data['warning'] = f"Completed with {len(errors)} errors"
                    JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result_data)
                else:
                    JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result_data)

                current_task.update_state(
                    state='SUCCESS',
                    meta={
                        'current': total_files,
                        'total': total_files,
                        'progress': 100,
                        'status': 'Bulk compression completed',
                        'processed_count': len(processed_files),
                        'error_count': len(errors)
                    }
                )
                logger.info(f"Bulk compression task completed for job {job_id}")
                return result_data

            except Exception as e:
                logger.error(f"Error creating result archive for job {job_id}: {str(e)}")
                errors.append({'operation': 'archive_creation', 'error': str(e)})
                raise  # Re-raise to be handled by centralized error handler

    except Exception as exc:
        handle_task_error(self, exc, job_id, job)

# --------------------------------------------------------------------------
#  CONVERSION TASKS – crash-hardened
# --------------------------------------------------------------------------
@celery_app.task(bind=True, name="tasks.convert_pdf_task", max_retries=3)
def convert_pdf_task(
    self,
    job_id: str,
    file_data: bytes,
    target_format: str,
    options: Dict[str, Any],
    original_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert PDF → target format with centralized error handling."""
    from flask import current_app
    job = None

    try:
        with current_app.app_context():  # push context
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="convert",
                input_data={
                    "target_format": target_format,
                    "options": options,
                    "file_size": len(file_data),
                    "original_filename": original_filename,
                }
            )

            JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

            current_task.update_state(
                state="PROGRESS",
                meta={"progress": 10, "status": f"Starting {target_format} conversion"},
            )

            result = ServiceRegistry.get_conversion_service().convert_pdf_data(
                file_data=file_data,
                target_format=target_format,
                options=options,
                original_filename=original_filename,
            )

            # result always contains success/error
            if result["success"]:
                JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
            else:
                JobOperations.update_job_status(job_id, JobStatus.FAILED, error_message=result["error"])

            current_task.update_state(
                state="SUCCESS",
                meta={"progress": 100, "status": f"Conversion to {target_format} completed"},
            )
            return result

    except Exception as exc:
        handle_task_error(self, exc, job_id, job)


@celery_app.task(bind=True, name="tasks.conversion_preview_task", max_retries=3)
def conversion_preview_task(
    self,
    job_id: str,
    file_data: bytes,
    target_format: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate preview with centralized error handling."""
    from flask import current_app
    job = None

    try:
        with current_app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="conversion_preview",
                input_data={
                    "target_format": target_format,
                    "options": options,
                    "file_size": len(file_data),
                }
            )

            JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

            preview = ServiceRegistry.get_conversion_service().get_conversion_preview(file_data, target_format, options)
            JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=preview)
            return preview

    except Exception as exc:
        # Use centralized error handling but provide fallback for preview tasks
        try:
            handle_task_error(self, exc, job_id, job)
        except:
            # Final fallback for preview tasks to ensure they always return a response
            return {
                "success": False,
                "error": str(exc),
                "original_size": len(file_data),
                "page_count": 0,
                "estimated_size": 0,
                "estimated_time": 0,
                "complexity": "unknown",
                "recommendations": [],
                "supported_formats": ServiceRegistry.get_conversion_service().supported_formats,
            }

# --------------------------------------------------------------------------
#  OCR TASKS – crash-hardened & context-safe
# --------------------------------------------------------------------------
@celery_app.task(bind=True, name="tasks.ocr_process_task", max_retries=3)
def ocr_process_task(
    self,
    job_id: str,
    file_data: bytes,
    options: Dict[str, Any],
    original_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """OCR PDF/image → disk file – uses centralized error handling."""
    from flask import current_app
    job = None

    try:
        with current_app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="ocr",
                input_data={
                    "options": options,
                    "file_size": len(file_data),
                    "original_filename": original_filename,
                }
            )

            JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

            current_task.update_state(
                state="PROGRESS", meta={"progress": 10, "status": "Starting OCR"}
            )

            result = ServiceRegistry.get_ocr_service().process_ocr_data(
                file_data=file_data,
                options=options,
                original_filename=original_filename,
            )

            if result["success"]:
                JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
            else:
                JobOperations.update_job_status(job_id, JobStatus.FAILED, error_message=result["error"])

            current_task.update_state(
                state="SUCCESS", meta={"progress": 100, "status": "OCR completed"}
            )
            return result

    except Exception as exc:
        return handle_task_error(self, exc, job_id, job, "OCR task")


@celery_app.task(bind=True, name="tasks.ocr_preview_task", max_retries=2)
def ocr_preview_task(self,job_id: str,file_data: bytes,options: Dict[str, Any]) -> Dict[str, Any]:
    """OCR preview – uses centralized error handling."""
    from flask import current_app
    job = None

    try:
        with current_app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="ocr_preview",
                input_data={
                    "options": options,
                    "file_size": len(file_data),
                }
            )

            JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

            preview = ServiceRegistry.get_ocr_service().get_ocr_preview(file_data, options)
            JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=preview)
            return preview

    except Exception as exc:
        # Use centralized error handling with fallback return
        handle_task_error(self, exc, job_id, job, "OCR preview task")
        
        # final fallback – uniform shape
        return {
            "success": False,
            "error": str(exc),
            "original_size": len(file_data),
            "estimated_time": 0,
            "complexity": "unknown",
            "estimated_accuracy": 0.0,
            "recommendations": [],
            "supported_formats": ServiceRegistry.get_ocr_service().output_formats,
            "supported_languages": ServiceRegistry.get_ocr_service().supported_languages,
        }

# ------------------------------------------------------
#  AI TASKS  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.ai_summarize_task', max_retries=3)
def ai_summarize_task(self, job_id: str, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize text using AI asynchronously – uses centralized error handling."""
    job = None
    
    try:
        logger.info(f"Starting AI summarisation task for job {job_id}")
        job = JobOperations.create_job_safely(
            job_id=job_id,
            job_type='ai_summarize',
            input_data={'text_length': len(text), 'options': options}
        )

        JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

        result = ServiceRegistry.get_ai_service().summarize_text(text, options)
        JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        logger.info(f"AI summarisation task completed for job {job_id}")
        return result

    except Exception as e:
        return handle_task_error(self, e, job_id, job, "AI summarization task")

@celery_app.task(bind=True, name='tasks.ai_translate_task', max_retries=3)
def ai_translate_task(self, job_id: str, text: str, target_language: str,
                      options: Dict[str, Any]) -> Dict[str, Any]:
    """Translate text using AI asynchronously – uses centralized error handling."""
    job = None
    
    try:
        logger.info(f"Starting AI translation task for job {job_id} (target: {target_language})")
        job = JobOperations.create_job_safely(
            job_id=job_id,
            job_type='ai_translate',
            input_data={
                'target_language': target_language,
                'text_length': len(text),
                'options': options
            }
        )

        JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

        result = ServiceRegistry.get_ai_service().translate_text(text, target_language, options)
        JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        logger.info(f"AI translation task completed for job {job_id}")
        return result

    except Exception as e:
        return handle_task_error(self, e, job_id, job, "AI translation task")

@celery_app.task(bind=True, name='tasks.extract_text_task', max_retries=3)
def extract_text_task(self, job_id: str, file_data: bytes,
                      original_filename: str | None = None) -> Dict[str, Any]:
    """Extract text from PDF asynchronously – uses centralized error handling."""
    job = None
    
    try:
        logger.info(f"Starting text-extraction task for job {job_id}")
        job = JobOperations.create_job_safely(
            job_id=job_id,
            job_type='extract_text',
            input_data={'file_size': len(file_data), 'original_filename': original_filename}
        )

        JobOperations.update_job_status(job_id, JobStatus.PROCESSING)

        current_task.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Starting text extraction'})
        text_content = ServiceRegistry.get_ai_service().extract_text_from_pdf_data(file_data)
        result = {'text': text_content, 'length': len(text_content), 'original_filename': original_filename}
        JobOperations.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        current_task.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'Text extraction completed'})
        logger.info(f"Text-extraction task completed for job {job_id}")
        return result

    except Exception as e:
        return handle_task_error(self, e, job_id, job, "Text extraction task")

# ------------------------------------------------------
#  MAINTENANCE TASKS  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.cleanup_expired_jobs')
@transactional("cleanup_expired_jobs")
def cleanup_expired_jobs(self) -> Dict[str, Any]:
    """Clean up expired jobs and their associated files – identical behaviour."""
    try:
        logger.info("Starting cleanup of expired jobs")
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        expired_jobs = Job.query.filter(
            Job.created_at < cutoff_time,
            Job.status.in_(['completed', 'failed'])
        ).all()

        cleaned_count = error_count = total_size_freed = 0
        for job in expired_jobs:
            try:
                job_size_mb = FileManagementService._cleanup_job_files(job)
                total_size_freed += job_size_mb
                cleaned_count += 1
                db.session.delete(job)
                logger.info(f"Cleaned up expired job {job.job_id}")
            except Exception as e:
                error_count += 1
                logger.error(f"Error cleaning up job {job.job_id}: {str(e)}")

        # Transaction is automatically committed by the transactional decorator
        current_task.update_state(
            state='SUCCESS',
            meta={'cleaned_count': cleaned_count, 'error_count': error_count, 'total_size_freed': total_size_freed}
        )
        logger.info(f"Cleanup completed: {cleaned_count} jobs cleaned, {error_count} errors")
        return {'cleaned_count': cleaned_count, 'error_count': error_count, 'total_size_freed': total_size_freed}

    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        current_task.update_state(state='FAILURE', meta={'error': str(e)})
        raise

# _cleanup_job_files function removed - use FileManagementService._cleanup_job_files instead

@celery_app.task(bind=True, name='tasks.get_task_status')
def get_task_status(self, task_id: str) -> Dict[str, Any]:
    """Get the status of a Celery task – identical behaviour."""
    try:
        result = celery_app.AsyncResult(task_id)
        response = {'state': result.state, 'task_id': task_id}
        if result.state == 'PROGRESS':
            response.update(result.info or {})
        elif result.state == 'SUCCESS':
            response['result'] = result.result
        elif result.state == 'FAILURE':
            response['error'] = str(result.info)
        return response
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        return {'state': 'ERROR', 'error': str(e), 'task_id': task_id}


# ------------------------------------------------------
#  AI EXTRACTION TASKS
# ------------------------------------------------------
@celery_app.task(bind=True, max_retries=3, name='tasks.extract_invoice_task')
@transactional("extract_invoice_task")
def extract_invoice_task(self, job_id: str, file_path: str, extraction_options: Dict[str, Any]) -> Dict[str, Any]:
    """Async invoice extraction task – uses centralized error handling."""
    job = None
    
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        logger.debug(f"Starting invoice extraction task for job {job_id}")
        
        if not job:
            job = Job(
                job_id=job_id,
                task_type='extract_invoice',
                input_data={
                    'file_path': file_path,
                    'extraction_options': extraction_options
                },
            )
            db.session.add(job)

        job.mark_as_processing()
        # Transaction will be committed automatically by decorator
        logger.debug(f"Job {job_id} marked as processing")

        # Update task progress
        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': 4,
                'progress': 25,
                'status': 'Starting invoice extraction...'
            }
        )

        # Extract invoice data
        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'progress': 50,
                'status': 'Extracting invoice data...'
            }
        )
        
        start_time = datetime.now(timezone.utc)
        extraction_result = ServiceRegistry.get_invoice_extraction_service().extract_invoice_data(file_path, extraction_options)
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Add processing time to metadata
        if 'metadata' in extraction_result:
            extraction_result['metadata']['processing_time'] = processing_time

        # Export data if requested
        export_result = None
        export_format = extraction_options.get('export_format')
        if export_format and export_format != 'none':
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': 3,
                    'total': 4,
                    'progress': 75,
                    'status': f'Exporting to {export_format}...'
                }
            )
            
            try:
                export_result = ServiceRegistry.get_export_service().export_invoice_data(
                    extraction_result,
                    export_format,
                    extraction_options.get('export_filename')
                )
                extraction_result['export'] = export_result
            except Exception as e:
                logger.warning(f"Export failed for job {job_id}: {str(e)}")
                extraction_result['export_error'] = str(e)

        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 4,
                'total': 4,
                'progress': 100,
                'status': 'Invoice extraction completed'
            }
        )

        job.mark_as_completed(result=extraction_result)
        # Transaction will be committed automatically by decorator
        logger.info(f"Invoice extraction job {job_id} completed successfully")
        return extraction_result

    except Exception as e:
        return handle_task_error(self, e, job_id, job, "Invoice extraction task")


# ------------------------------------------------------
#  NEW TASK IMPLEMENTATIONS
# ------------------------------------------------------

@celery_app.task(bind=True, name='tasks.merge_pdfs_task', max_retries=3)
@transactional("merge_pdfs_task")
def merge_pdfs_task(self, job_id: str, file_paths: List[str], options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Merge multiple PDF files into a single PDF.
    
    Uses centralized error handling for consistent error management.
    """
    from flask import current_app
    
    options = options or {}
    job = None
    
    try:
        with current_app.app_context():
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type='merge_pdfs',
                    input_data={
                        'file_count': len(file_paths),
                        'options': options
                    }
                )
                db.session.add(job)
            
            job.mark_as_processing()
            # Transaction will be committed automatically by decorator
            
            # Use task context for progress reporting and temp file management
            with task_context(job, total_steps=len(file_paths) + 2) as (progress, temp_manager):
                metrics = TaskMetrics(job)
                
                progress.update(step=1, message="Initializing PDF merge")
                
                # Validate input files
                valid_files = []
                for i, file_path in enumerate(file_paths):
                    if os.path.exists(file_path):
                        valid_files.append(file_path)
                        file_size = os.path.getsize(file_path)
                        metrics.record_file_processed(file_size)
                    else:
                        logger.warning(f"File not found: {file_path}")
                    
                    progress.update(step=i + 2, message=f"Validating file {i + 1}/{len(file_paths)}")
                
                if not valid_files:
                    raise ValidationError("No valid PDF files found for merging")
                
                # Perform merge operation
                progress.update(step=len(file_paths) + 1, message="Merging PDF files")
                
                # Create output file in temp directory
                output_path = temp_manager.create_temp_file(suffix=".pdf")
                
                # Use file management service for merge operation
                merge_result = file_management_service.merge_pdfs(
                    input_files=valid_files,
                    output_path=output_path,
                    options=options
                )
                
                progress.complete("PDF merge completed successfully")
                metrics.finalize()
                
                result = {
                    'success': True,
                    'output_path': output_path,
                    'merged_files': len(valid_files),
                    'output_size': os.path.getsize(output_path),
                    **merge_result
                }
                
                job.mark_as_completed(result)
                # Transaction will be committed automatically by decorator
                
                return result
    
    except Exception as exc:
        return handle_task_error(self, exc, job_id, job, "PDF merge task")


@celery_app.task(bind=True, name='tasks.split_pdf_task', max_retries=3)
@transactional("split_pdf_task")
def split_pdf_task(self, job_id: str, file_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Split a PDF file into multiple files.
    
    Uses centralized error handling for consistent error management.
    """
    from flask import current_app
    
    options = options or {}
    job = None
    
    try:
        with current_app.app_context():
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type='split_pdf',
                    input_data={
                        'file_path': file_path,
                        'options': options
                    }
                )
                db.session.add(job)
            
            job.mark_as_processing()
            # Transaction will be committed automatically by decorator
            
            with task_context(job, total_steps=4) as (progress, temp_manager):
                metrics = TaskMetrics(job)
                
                progress.update(step=1, message="Analyzing PDF structure")
                
                if not os.path.exists(file_path):
                    raise ResourceNotFoundError("PDF file", file_path)
                
                file_size = os.path.getsize(file_path)
                metrics.record_file_processed(file_size)
                
                progress.update(step=2, message="Preparing split operation")
                
                # Create output directory in temp space
                output_dir = temp_manager.create_temp_dir()
                
                progress.update(step=3, message="Splitting PDF file")
                
                # Use file management service for split operation
                split_result = file_management_service.split_pdf(
                    input_file=file_path,
                    output_dir=output_dir,
                    options=options
                )
                
                progress.complete("PDF split completed successfully")
                metrics.finalize()
                
                result = {
                    'success': True,
                    'output_directory': output_dir,
                    'split_files': split_result.get('split_files', []),
                    'total_pages': split_result.get('total_pages', 0),
                    **split_result
                }
                
                job.mark_as_completed(result)
                # Transaction will be committed automatically by decorator
                
                return result
    
    except Exception as exc:
        return handle_task_error(self, exc, job_id, job, "PDF split task")


# ------------------------------------------------------
#  MAINTENANCE TASKS
# ------------------------------------------------------

@celery_app.task(bind=True, name='tasks.cleanup_temp_files_task')
def cleanup_temp_files_task(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """Clean up temporary files older than specified age."""
    try:
        logger.info(f"Starting cleanup of temporary files older than {max_age_hours} hours")
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        temp_dirs = [tempfile.gettempdir(), '/tmp', './uploads/temp']
        
        cleaned_files = 0
        cleaned_size = 0
        errors = 0
        
        for temp_dir in temp_dirs:
            if not os.path.exists(temp_dir):
                continue
                
            try:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        if file.startswith('pdf_task_') or file.startswith('temp_'):
                            file_path = os.path.join(root, file)
                            try:
                                file_stat = os.stat(file_path)
                                file_time = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)
                                
                                if file_time < cutoff_time:
                                    file_size = file_stat.st_size
                                    os.unlink(file_path)
                                    cleaned_files += 1
                                    cleaned_size += file_size
                                    logger.debug(f"Cleaned temp file: {file_path}")
                            except Exception as e:
                                errors += 1
                                logger.warning(f"Error cleaning file {file_path}: {e}")
            except Exception as e:
                logger.error(f"Error accessing temp directory {temp_dir}: {e}")
                errors += 1
        
        result = {
            'cleaned_files': cleaned_files,
            'cleaned_size_bytes': cleaned_size,
            'errors': errors,
            'max_age_hours': max_age_hours
        }
        
        logger.info(f"Temp file cleanup completed: {cleaned_files} files, {cleaned_size} bytes freed")
        return result
        
    except Exception as exc:
        logger.exception("Temp file cleanup task failed")
        raise


@celery_app.task(bind=True, name='tasks.health_check_task')
def health_check_task(self) -> Dict[str, Any]:
    """Perform system health checks."""
    from flask import current_app
    
    try:
        health_status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'healthy',
            'checks': {}
        }
        
        # Database connectivity check
        try:
            with current_app.app_context():
                db.session.execute('SELECT 1')
                health_status['checks']['database'] = {'status': 'healthy', 'response_time_ms': 0}
        except Exception as e:
            health_status['checks']['database'] = {'status': 'unhealthy', 'error': str(e)}
            health_status['status'] = 'degraded'
        
        # Service availability checks
        services_to_check = [
            ('compression', compression_service),
            ('conversion', conversion_service),
            ('ocr', ocr_service),
            ('ai', ai_service)
        ]
        
        for service_name, service_instance in services_to_check:
            try:
                # Basic service health check (if method exists)
                if hasattr(service_instance, 'health_check'):
                    service_health = service_instance.health_check()
                    health_status['checks'][service_name] = service_health
                else:
                    health_status['checks'][service_name] = {'status': 'healthy', 'note': 'No health check method'}
            except Exception as e:
                health_status['checks'][service_name] = {'status': 'unhealthy', 'error': str(e)}
                health_status['status'] = 'degraded'
        
        # Disk space check
        try:
            disk_usage = shutil.disk_usage('.')
            free_space_gb = disk_usage.free / (1024**3)
            health_status['checks']['disk_space'] = {
                'status': 'healthy' if free_space_gb > 1.0 else 'warning',
                'free_space_gb': round(free_space_gb, 2)
            }
            if free_space_gb <= 1.0:
                health_status['status'] = 'degraded'
        except Exception as e:
            health_status['checks']['disk_space'] = {'status': 'unhealthy', 'error': str(e)}
        
        return health_status
        
    except Exception as exc:
        logger.exception("Health check task failed")
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': 'unhealthy',
            'error': str(exc)
        }


@celery_app.task(bind=True, max_retries=3, name='tasks.extract_bank_statement_task')
@transactional("extract_bank_statement_task")
def extract_bank_statement_task(self, job_id: str, file_path: str, extraction_options: Dict[str, Any]) -> Dict[str, Any]:
    """Async bank statement extraction task.
    
    Uses centralized error handling for consistent error management.
    """
    job = None
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        logger.debug(f"Starting bank statement extraction task for job {job_id}")
        
        if not job:
            job = Job(
                job_id=job_id,
                task_type='extract_bank_statement',
                input_data={
                    'file_path': file_path,
                    'extraction_options': extraction_options
                },
            )
            db.session.add(job)

        job.mark_as_processing()
        # Transaction automatically committed by @transactional decorator
        logger.debug(f"Job {job_id} marked as processing")

        # Update task progress
        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 1,
                'total': 4,
                'progress': 25,
                'status': 'Starting bank statement extraction...'
            }
        )

        # Extract bank statement data
        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 2,
                'total': 4,
                'progress': 50,
                'status': 'Extracting bank statement data...'
            }
        )
        
        start_time = datetime.now(timezone.utc)
        extraction_result = ServiceRegistry.get_bank_statement_extraction_service().extract_statement_data(file_path, extraction_options)
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        # Add processing time to metadata
        if 'metadata' in extraction_result:
            extraction_result['metadata']['processing_time'] = processing_time

        # Export data if requested
        export_result = None
        export_format = extraction_options.get('export_format')
        if export_format and export_format != 'none':
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': 3,
                    'total': 4,
                    'progress': 75,
                    'status': f'Exporting to {export_format}...'
                }
            )
            
            try:
                export_result = ServiceRegistry.get_export_service().export_bank_statement_data(
                    extraction_result,
                    export_format,
                    extraction_options.get('export_filename')
                )
                extraction_result['export'] = export_result
            except Exception as e:
                logger.warning(f"Export failed for job {job_id}: {str(e)}")
                extraction_result['export_error'] = str(e)

        current_task.update_state(
            state='PROGRESS',
            meta={
                'current': 4,
                'total': 4,
                'progress': 100,
                'status': 'Bank statement extraction completed'
            }
        )

        job.mark_as_completed(result=extraction_result)
        # Transaction automatically committed by @transactional decorator
        logger.info(f"Bank statement extraction job {job_id} completed successfully")
        return extraction_result

    except Exception as e:
        return handle_task_error(self, e, job_id, job, "Bank statement extraction task")