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
# TODO all services could just be imported from src.services
from src.services.ai_service import AIService

from src.services.compression_service import CompressionService
from src.services.conversion_service import ConversionService
from src.services.ocr_service import OCRService
from src.services.invoice_extraction_service import InvoiceExtractionService
from src.services.bank_statement_extraction_service import BankStatementExtractionService
from src.services.export_service import ExportService
from src.services.file_management_service import FileManagementService
from src.exceptions.extraction_exceptions import ExtractionError, ExtractionValidationError
from src.exceptions.export_exceptions import ExportError, FormatError

# Exception imports for specific error handling
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError, StatementError
from celery.exceptions import Retry, WorkerLostError, Ignore, Reject

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

compression_service = CompressionService()
conversion_service = ConversionService()
ocr_service = OCRService()
ai_service = AIService()

invoice_extraction_service = InvoiceExtractionService()
bank_statement_extraction_service = BankStatementExtractionService()
export_service = ExportService()

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

def handle_task_error(task_instance, exc, job_id, job=None):
    """Centralized error handling for all tasks."""
    from flask import current_app
    
    # Determine error tier and retry strategy
    error_tier = None
    for tier_name, tier_config in RETRYABLE_ERRORS.items():
        if isinstance(exc, tier_config['exceptions']):
            error_tier = tier_name
            break
    
    # Update job status in database
    try:
        with current_app.app_context():
            if not job:
                job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.mark_as_failed(str(exc))
                db.session.commit()
    except Exception:
        logger.exception(f"Failed to update job {job_id} status")
    
    # Handle non-retryable errors
    if type(exc) in NON_RETRYABLE_ERRORS:
        logger.error(f"Non-retryable error in job {job_id}: {exc}")
        raise Ignore()
    
    # Handle retryable errors
    if error_tier and task_instance.request.retries < RETRYABLE_ERRORS[error_tier]['max_retries']:
        countdown = RETRYABLE_ERRORS[error_tier]['countdown'](task_instance.request.retries)
        logger.warning(f"Retrying job {job_id} ({error_tier} error, attempt {task_instance.request.retries + 1}): {exc}")
        raise task_instance.retry(countdown=countdown, exc=exc)
    
    # Max retries exceeded or unknown error
    logger.error(f"Task failed permanently for job {job_id}: {exc}")
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
    """Async compression task – identical behaviour."""
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        logger.debug(f"Starting compression task for job {job_id}")
        if not job:
            job = Job(
                job_id=job_id,
                task_type='compress',
                input_data={
                    'compression_settings': compression_settings,
                    'file_size': len(file_data),
                    'original_filename': original_filename
                },

            )
            db.session.add(job)

        job.mark_as_processing()
        db.session.commit()
        logger.debug(f"Job {job_id} marked as processing")

        result = compression_service.process_file_data(
            file_data=file_data,
            settings=compression_settings,
            original_filename=original_filename)
        logger.debug(f"File processed for job {job_id}, result: {result}")

        job.mark_as_completed(result=result)
        db.session.commit()
        logger.info(f"Compression job {job_id} completed successfully")
        return result

    except (DBAPIError, OperationalError, IntegrityError) as db_e:
        logger.error(f"Database error in compression task for job {job_id}: {str(db_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(db_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying compression job {job_id} due to database error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except (EnvironmentError, TimeoutError) as env_e:
        logger.error(f"Environment/timeout error in compression task for job {job_id}: {str(env_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(env_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        # Don't retry environment errors (like missing Ghostscript)
        if isinstance(env_e, EnvironmentError):
            logger.error(f"Environment error - not retrying: {env_e}")
            raise Ignore()
        
        # Retry timeout errors
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying compression job {job_id} due to timeout (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except Exception as e:
        logger.error(f"Compression task failed for job {job_id}: {str(e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying compression job {job_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise

# ------------------------------------------------------
#  BULK COMPRESSION  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.bulk_compress_task', max_retries=3)
def bulk_compress_task(self, job_id: str, file_data_list: List[bytes],
                       filenames: List[str], settings: Dict[str, Any]) -> dict[str, int | list[Any] | Any] | None:
    """Process bulk compression task asynchronously – identical behaviour."""
    try:
        logger.info(f"Starting bulk compression task for job {job_id}")
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            job = Job(
                job_id=job_id,
                task_type='bulk_compress',
                input_data={
                    'settings': settings,
                    'file_count': len(file_data_list),
                    'total_size': sum(len(d) for d in file_data_list)
                },

            )
            db.session.add(job)

        job.mark_as_processing()
        db.session.commit()

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
                    job.mark_as_failed(f"All files failed: {len(errors)} errors")
                elif errors:
                    job.mark_as_completed(result=result_data)
                    job.result['warning'] = f"Completed with {len(errors)} errors"
                else:
                    job.mark_as_completed(result=result_data)

                db.session.commit()

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




    except Exception as e:
        logger.error(f"Error in bulk compression task {job_id}: {str(e)}")
        # noinspection PyUnboundLocalVariable
        if 'job' in locals() and job:
            job.mark_as_failed(str(e))
            db.session.commit()
        current_task.update_state(state='FAILURE', meta={'error': str(e), 'job_id': job_id})
        raise

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
    """Convert PDF → target format – safe for retries & context."""
    from flask import current_app

    try:
        with current_app.app_context():  # push context
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type="convert",
                    input_data={
                        "target_format": target_format,
                        "options": options,
                        "file_size": len(file_data),
                        "original_filename": original_filename,
                    },
                )
                db.session.add(job)

            job.mark_as_processing()
            db.session.commit()

            current_task.update_state(
                state="PROGRESS",
                meta={"progress": 10, "status": f"Starting {target_format} conversion"},
            )

            result = conversion_service.convert_pdf_data(
                file_data=file_data,
                target_format=target_format,
                options=options,
                original_filename=original_filename,
            )

            # result always contains success/error
            if result["success"]:
                job.mark_as_completed(result)
            else:
                job.mark_as_failed(result["error"])
            db.session.commit()

            current_task.update_state(
                state="SUCCESS",
                meta={"progress": 100, "status": f"Conversion to {target_format} completed"},
            )
            return result

    except (DBAPIError, OperationalError, IntegrityError) as db_exc:
        logger.exception("Database error in conversion task %s", job_id)
        # context-safe error update
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(db_exc))
                    db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:  # noqa: F841
            logger.error(f"Failed to update job status due to database error: {db_err}")
    except (ValueError, RuntimeError) as conv_exc:
        logger.exception("Conversion error in task %s: %s", job_id, str(conv_exc))
        # context-safe error update
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(conv_exc))
                    db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:  # noqa: F841
            logger.error(f"Failed to update job status due to database error: {db_err}")
        
        # Don't retry ValueError (unsupported format) but retry RuntimeError (missing libraries)
        if isinstance(conv_exc, ValueError):
            logger.error(f"Unsupported format error - not retrying: {conv_exc}")
            raise Ignore()
        
        # Retry RuntimeError (missing libraries) - might be temporary
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying conversion job {job_id} due to runtime error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except Exception as exc:
        logger.exception("Conversion task %s failed", job_id)
        # context-safe error update
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(exc))
                    db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:  # noqa: F841
            pass  # already logging

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise


@celery_app.task(bind=True, name="tasks.conversion_preview_task", max_retries=3)
def conversion_preview_task(
    self,
    job_id: str,
    file_data: bytes,
    target_format: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate preview – context & retry safe."""
    from flask import current_app

    try:
        with current_app.app_context():
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type="conversion_preview",
                    input_data={
                        "target_format": target_format,
                        "options": options,
                        "file_size": len(file_data),
                    },
                )
                db.session.add(job)

            job.mark_as_processing()
            db.session.commit()

            preview = conversion_service.get_conversion_preview(file_data, target_format, options)
            job.mark_as_completed(preview)
            db.session.commit()
            return preview

    except Exception as exc:
        logger.exception("Preview task %s failed", job_id)
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(exc))
                    db.session.commit()
        except Exception:  # noqa
            pass
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)
        # final fallback
        return {
            "success": False,
            "error": str(exc),
            "original_size": len(file_data),
            "page_count": 0,
            "estimated_size": 0,
            "estimated_time": 0,
            "complexity": "unknown",
            "recommendations": [],
            "supported_formats": conversion_service.supported_formats,
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
    """OCR PDF/image → disk file – context & retry safe."""
    from flask import current_app

    try:
        with current_app.app_context():
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type="ocr",
                    input_data={
                        "options": options,
                        "file_size": len(file_data),
                        "original_filename": original_filename,
                    },
                )
                db.session.add(job)

            job.status = JobStatus.PROCESSING.value
            db.session.commit()

            current_task.update_state(
                state="PROGRESS", meta={"progress": 10, "status": "Starting OCR"}
            )

            result = ocr_service.process_ocr_data(
                file_data=file_data,
                options=options,
                original_filename=original_filename,
            )

            if result["success"]:
                job.mark_as_completed(result)
            else:
                job.mark_as_failed(result["error"])
            db.session.commit()

            current_task.update_state(
                state="SUCCESS", meta={"progress": 100, "status": "OCR completed"}
            )
            return result

    except Exception as exc:
        logger.exception("OCR task %s failed", job_id)
        # context-safe error update
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(exc))
                    db.session.commit()
        except Exception:
            pass  # already logging

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise


@celery_app.task(bind=True, name="tasks.ocr_preview_task", max_retries=2)
def ocr_preview_task(self,job_id: str,file_data: bytes,options: Dict[str, Any]) -> Dict[str, Any]:
    """OCR preview – context-safe, uniform payload."""


    try:
        with current_app.app_context():
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type="ocr_preview",
                    input_data={
                        "options": options,
                        "file_size": len(file_data),
                    },
                )
                db.session.add(job)

            job.status = JobStatus.PROCESSING.value
            db.session.commit()

            preview = ocr_service.get_ocr_preview(file_data, options)
            job.mark_as_completed(preview)
            db.session.commit()
            return preview

    except Exception as exc:
        logger.exception("OCR preview task %s failed", job_id)
        # context-safe error update
        try:
            with current_app.app_context():
                job = Job.query.filter_by(job_id=job_id).first()
                if job:
                    job.mark_as_failed(str(exc))
                    db.session.commit()
        except Exception:
            pass

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=30)

        # final fallback – uniform shape
        return {
            "success": False,
            "error": str(exc),
            "original_size": len(file_data),
            "estimated_time": 0,
            "complexity": "unknown",
            "estimated_accuracy": 0.0,
            "recommendations": [],
            "supported_formats": ocr_service.output_formats,
            "supported_languages": ocr_service.supported_languages,
        }

# ------------------------------------------------------
#  AI TASKS  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.ai_summarize_task', max_retries=3)
def ai_summarize_task(self, job_id: str, text: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize text using AI asynchronously – identical behaviour."""
    try:
        logger.info(f"Starting AI summarisation task for job {job_id}")
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            job = Job(
                job_id=job_id,
                task_type='ai_summarize',
                input_data={'text_length': len(text), 'options': options}
                
            )
            db.session.add(job)

        job.mark_as_processing()
        db.session.commit()

        result = ai_service.summarize_text(text, options)
        job.mark_as_completed(result)
        db.session.commit()
        logger.info(f"AI summarisation task completed for job {job_id}")
        return result

    except Exception as e:
        logger.error(f"Error in AI summarisation task {job_id}: {str(e)}")

        # noinspection PyUnboundLocalVariable
        if 'job' in locals() and job:
            job.mark_as_failed(str(e))
            db.session.commit()
        raise

@celery_app.task(bind=True, name='tasks.ai_translate_task', max_retries=3)
def ai_translate_task(self, job_id: str, text: str, target_language: str,
                      options: Dict[str, Any]) -> Dict[str, Any]:
    """Translate text using AI asynchronously – identical behaviour."""
    try:
        logger.info(f"Starting AI translation task for job {job_id} (target: {target_language})")
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            job = Job(
                job_id=job_id,
                task_type='ai_translate',
                input_data={
                    'target_language': target_language,
                    'text_length': len(text),
                    'options': options
                }
                
            )
            db.session.add(job)

        job.mark_as_processing()
        db.session.commit()

        result = ai_service.translate_text(text, target_language, options)
        job.mark_as_completed(result)
        db.session.commit()
        logger.info(f"AI translation task completed for job {job_id}")
        return result

    except Exception as e:
        logger.error(f"Error in AI translation task {job_id}: {str(e)}")
        # noinspection PyUnboundLocalVariable
        if 'job' in locals() and job:
            job.mark_as_failed(str(e))
            db.session.commit()
        raise

@celery_app.task(bind=True, name='tasks.extract_text_task', max_retries=3)
def extract_text_task(self, job_id: str, file_data: bytes,
                      original_filename: str | None = None) -> Dict[str, Any]:
    """Extract text from PDF asynchronously – identical behaviour."""
    try:
        logger.info(f"Starting text-extraction task for job {job_id}")
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            job = Job(
                job_id=job_id,
                task_type='extract_text',
                input_data={'file_size': len(file_data), 'original_filename': original_filename}
                
            )
            db.session.add(job)

        job.mark_as_processing()
        db.session.commit()

        current_task.update_state(state='PROGRESS', meta={'progress': 10, 'status': 'Starting text extraction'})
        text_content = ai_service.extract_text_from_pdf_data(file_data)
        result = {'text': text_content, 'length': len(text_content), 'original_filename': original_filename}
        job.status = JobStatus.COMPLETED.value
        db.session.commit()
        current_task.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'Text extraction completed'})
        logger.info(f"Text-extraction task completed for job {job_id}")
        return result

    except Exception as e:
        logger.error(f"Error in text-extraction task {job_id}: {str(e)}")
        # noinspection PyUnboundLocalVariable
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED.value
            job.error = str(e)
            db.session.commit()
        current_task.update_state(state='FAILURE', meta={'error': str(e), 'job_id': job_id})
        raise

# ------------------------------------------------------
#  MAINTENANCE TASKS  (logic 100 % preserved)
# ------------------------------------------------------
@celery_app.task(bind=True, name='tasks.cleanup_expired_jobs')
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

        db.session.commit()
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
def extract_invoice_task(self, job_id: str, file_path: str, extraction_options: Dict[str, Any]) -> Dict[str, Any]:
    """Async invoice extraction task."""
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
        db.session.commit()
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
        extraction_result = invoice_extraction_service.extract_invoice_data(file_path, extraction_options)
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
                export_result = export_service.export_invoice_data(
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
        db.session.commit()
        logger.info(f"Invoice extraction job {job_id} completed successfully")
        return extraction_result

    except (DBAPIError, OperationalError, IntegrityError) as db_e:
        logger.error(f"Database error in invoice extraction task for job {job_id}: {str(db_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(db_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(db_e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying invoice extraction job {job_id} due to database error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except ExtractionValidationError as val_e:
        logger.error(f"Validation error in invoice extraction task for job {job_id}: {str(val_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(val_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(val_e), 'job_id': job_id}
        )
        
        # Don't retry validation errors - they won't succeed on retry
        logger.error(f"Validation error - not retrying: {val_e}")
        raise Ignore()
    except ExtractionError as ext_e:
        logger.error(f"Extraction error in invoice extraction task for job {job_id}: {str(ext_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(ext_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(ext_e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying invoice extraction job {job_id} due to extraction error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except Exception as e:
        logger.error(f"Invoice extraction task failed for job {job_id}: {str(e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying invoice extraction job {job_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise


# ------------------------------------------------------
#  NEW TASK IMPLEMENTATIONS
# ------------------------------------------------------

@celery_app.task(bind=True, name='tasks.merge_pdfs_task', max_retries=3)
def merge_pdfs_task(self, job_id: str, file_paths: List[str], options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Merge multiple PDF files into a single PDF."""
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
            db.session.commit()
            
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
                db.session.commit()
                
                return result
    
    except Exception as exc:
        logger.exception(f"PDF merge task failed for job {job_id}")
        handle_task_error(self, exc, job_id, job)


@celery_app.task(bind=True, name='tasks.split_pdf_task', max_retries=3)
def split_pdf_task(self, job_id: str, file_path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Split a PDF file into multiple files."""
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
            db.session.commit()
            
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
                db.session.commit()
                
                return result
    
    except Exception as exc:
        logger.exception(f"PDF split task failed for job {job_id}")
        handle_task_error(self, exc, job_id, job)


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
def extract_bank_statement_task(self, job_id: str, file_path: str, extraction_options: Dict[str, Any]) -> Dict[str, Any]:
    """Async bank statement extraction task."""
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
        db.session.commit()
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
        extraction_result = bank_statement_extraction_service.extract_statement_data(file_path, extraction_options)
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
                export_result = export_service.export_bank_statement_data(
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
        db.session.commit()
        logger.info(f"Bank statement extraction job {job_id} completed successfully")
        return extraction_result

    except (DBAPIError, OperationalError, IntegrityError) as db_e:
        logger.error(f"Database error in bank statement extraction task for job {job_id}: {str(db_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(db_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(db_e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying bank statement extraction job {job_id} due to database error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except ExtractionValidationError as val_e:
        logger.error(f"Validation error in bank statement extraction task for job {job_id}: {str(val_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(val_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(val_e), 'job_id': job_id}
        )
        
        # Don't retry validation errors - they won't succeed on retry
        logger.error(f"Validation error - not retrying: {val_e}")
        raise Ignore()
    except ExtractionError as ext_e:
        logger.error(f"Extraction error in bank statement extraction task for job {job_id}: {str(ext_e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(ext_e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(ext_e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying bank statement extraction job {job_id} due to extraction error (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
    except Exception as e:
        logger.error(f"Bank statement extraction task failed for job {job_id}: {str(e)}")
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.error = str(e)
                db.session.commit()
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            logger.error(f"Failed to update job status due to database error: {db_err}")

        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e), 'job_id': job_id}
        )

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying bank statement extraction job {job_id} (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise