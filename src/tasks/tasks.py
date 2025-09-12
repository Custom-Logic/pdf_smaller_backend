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
from src.exceptions.extraction_exceptions import ExtractionError, ExtractionValidationError
from src.exceptions.export_exceptions import ExportError, FormatError

# Exception imports for specific error handling
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError, StatementError
from celery.exceptions import Retry, WorkerLostError, Ignore, Reject

# ------------------------------------------------------
#  IMPORT THE HELPER – keeps context for every task
# ------------------------------------------------------
from .app_context import *   # noqa: F401,F403  (registers signals)

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
                job_size = _cleanup_job_files(job)
                total_size_freed += job_size
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

def _cleanup_job_files(job: Job) -> int:
    """Clean up files associated with a job – identical behaviour."""
    total_size = 0
    try:
        if job.result and 'output_path' in job.result:
            result_path = job.result['output_path']
            if os.path.exists(result_path):
                total_size += os.path.getsize(result_path)
                os.remove(result_path)
                logger.debug(f"Removed result file: {result_path}")

        if job.result and 'temp_files' in job.result:
            for temp_file in job.result['temp_files']:
                if os.path.exists(temp_file):
                    total_size += os.path.getsize(temp_file)
                    os.remove(temp_file)
                    logger.debug(f"Removed temp file: {temp_file}")
    except Exception as e:
        logger.error(f"Error cleaning up files for job {job.job_id}: {str(e)}")
    return total_size

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