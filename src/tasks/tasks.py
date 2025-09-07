"""
src/tasks/tasks.py
Celery tasks for background job processing - Job-Oriented Architecture
"""

import os
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List

from celery import current_task
from celery.exceptions import Retry

from src.celery_app import celery_app
from src.models import Job, JobStatus
from src.models.base import db
from src.services.compression_service import CompressionService
from src.services.conversion_service import ConversionService
from src.services.ocr_service import OCRService
from src.services.ai_service import AIService
from src.services.bulk_compression_service import BulkCompressionService
from src.config.config import Config

logger = logging.getLogger(__name__)

# Initialize services
config = Config()
compression_service = CompressionService(config.UPLOAD_FOLDER)
conversion_service = ConversionService()
ocr_service = OCRService()
ai_service = AIService()
bulk_service = BulkCompressionService(config.UPLOAD_FOLDER)

# ============================================================================
# COMPRESSION TASKS
# ============================================================================

@celery_app.task(bind=True, name='tasks.compress_task')
def compress_task(self, job_id: str, file_data: bytes, settings: Dict, 
                 original_filename: str = None, client_job_id: str = None, 
                 client_session_id: str = None) -> Dict[str, Any]:
    """
    Process compression task asynchronously
    """
    try:
        logger.info(f"Starting compression task for job {job_id} (client_job_id: {client_job_id})")
        
        # Create/update job record
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='compress',
            input_data={
                'settings': settings,
                'file_size': len(file_data),
                'original_filename': original_filename
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        # Update task progress
        current_task.update_state(
            state='PROGRESS',
            meta={
                'progress': 10,
                'status': 'Starting compression processing'
            }
        )
        
        # Process compression
        result = compression_service.process_file_data(file_data, settings, original_filename)
        
        # Update job with result
        job.result = result
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        # Final progress update
        current_task.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'status': 'Compression completed successfully'
            }
        )
        
        logger.info(f"Compression task completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in compression task {job_id}: {str(e)}")
        
        # Update job with error
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        # Update task state
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        raise

@celery_app.task(bind=True, name='tasks.bulk_compress_task')
def bulk_compress_task(self, job_id: str, file_data_list: List[bytes], 
                      filenames: List[str], settings: Dict, 
                      client_job_id: str = None, client_session_id: str = None) -> Dict[str, Any]:
    """
    Process bulk compression task asynchronously
    """
    try:
        logger.info(f"Starting bulk compression task for job {job_id} (client_job_id: {client_job_id})")
        
        # Create/update job record
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='bulk_compress',
            input_data={
                'settings': settings,
                'file_count': len(file_data_list),
                'total_size': sum(len(data) for data in file_data_list)
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        total_files = len(file_data_list)
        processed_files = []
        errors = []
        
        for i, (file_data, filename) in enumerate(zip(file_data_list, filenames)):
            try:
                # Update progress
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
                
                # Process individual file
                result = compression_service.process_file_data(file_data, settings, filename)
                processed_files.append(result)
                
                logger.info(f"Processed file {i+1}/{total_files} for job {job_id}: {filename}")
                
            except Exception as e:
                error_info = {
                    'filename': filename,
                    'error': str(e),
                    'index': i
                }
                errors.append(error_info)
                logger.error(f"Error processing file {filename} in job {job_id}: {str(e)}")
                continue
        
        # Create result archive if any files were successful
        result_path = None
        if processed_files:
            try:
                result_path = bulk_service.create_result_archive(processed_files, job_id, )
                logger.info(f"Created result archive for job {job_id}: {result_path}")
            except Exception as e:
                logger.error(f"Error creating result archive for job {job_id}: {str(e)}")
                errors.append({
                    'operation': 'archive_creation',
                    'error': str(e)
                })
        
        # Update job with final results
        job.result = {
            'processed_files': len(processed_files),
            'total_files': total_files,
            'errors': errors,
            'result_path': result_path,
            'processed_files_info': processed_files
        }
        
        if errors and not processed_files:
            job.status = JobStatus.FAILED
            job.error = f"All files failed: {len(errors)} errors"
        elif errors:
            job.status = JobStatus.COMPLETED
            job.result['warning'] = f"Completed with {len(errors)} errors"
        else:
            job.status = JobStatus.COMPLETED
        
        db.session.commit()
        
        # Final progress update
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
        
        logger.info(f"Bulk compression task completed for job {job_id}: {len(processed_files)} files processed, {len(errors)} errors")
        return job.result
        
    except Exception as e:
        logger.error(f"Error in bulk compression task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        raise

# ============================================================================
# CONVERSION TASKS
# ============================================================================

@celery_app.task(bind=True, name='tasks.convert_pdf_task')
def convert_pdf_task(self, job_id: str, file_data: bytes, target_format: str, 
                    options: Dict, original_filename: str = None,
                    client_job_id: str = None, client_session_id: str = None) -> Dict[str, Any]:
    """
    Convert PDF to specified format asynchronously
    """
    try:
        logger.info(f"Starting conversion task for job {job_id} (format: {target_format})")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type=f'convert_to_{target_format}',
            input_data={
                'target_format': target_format,
                'options': options,
                'file_size': len(file_data),
                'original_filename': original_filename
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        current_task.update_state(
            state='PROGRESS',
            meta={
                'progress': 10,
                'status': f'Starting {target_format} conversion'
            }
        )
        
        # Process conversion
        result = conversion_service.convert_pdf_data(file_data, target_format, options, original_filename)
        
        job.result = result
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        current_task.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'status': f'Conversion to {target_format} completed'
            }
        )
        
        logger.info(f"Conversion task completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in conversion task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        raise

@celery_app.task(bind=True, name='tasks.conversion_preview_task')
def conversion_preview_task(self, job_id: str, file_data: bytes, 
                           target_format: str, options: Dict,
                           client_job_id: str = None, client_session_id: str = None) -> Dict[str, Any]:
    """
    Generate conversion preview asynchronously
    """
    try:
        logger.info(f"Starting conversion preview task for job {job_id}")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='conversion_preview',
            input_data={
                'target_format': target_format,
                'options': options,
                'file_size': len(file_data)
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        # Generate preview
        preview = conversion_service.get_conversion_preview(file_data, target_format, options)
        
        job.result = preview
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        logger.info(f"Conversion preview task completed for job {job_id}")
        return preview
        
    except Exception as e:
        logger.error(f"Error in conversion preview task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        raise

# ============================================================================
# OCR TASKS
# ============================================================================

@celery_app.task(bind=True, name='tasks.ocr_process_task')
def ocr_process_task(self, job_id: str, file_data: bytes, options: Dict,
                    original_filename: str = None, client_job_id: str = None,
                    client_session_id: str = None) -> Dict[str, Any]:
    """
    Process OCR on file data asynchronously
    """
    try:
        logger.info(f"Starting OCR task for job {job_id}")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='ocr',
            input_data={
                'options': options,
                'file_size': len(file_data),
                'original_filename': original_filename
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        current_task.update_state(
            state='PROGRESS',
            meta={
                'progress': 10,
                'status': 'Starting OCR processing'
            }
        )
        
        # Process OCR
        result = ocr_service.process_ocr_data(file_data, options, original_filename)
        
        job.result = result
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        current_task.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'status': 'OCR processing completed'
            }
        )
        
        logger.info(f"OCR task completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in OCR task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        raise

@celery_app.task(bind=True, name='tasks.ocr_preview_task')
def ocr_preview_task(self, job_id: str, file_data: bytes, options: Dict,
                    client_job_id: str = None, client_session_id: str = None) -> Dict[str, Any]:
    """
    Generate OCR preview asynchronously
    """
    try:
        logger.info(f"Starting OCR preview task for job {job_id}")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='ocr_preview',
            input_data={
                'options': options,
                'file_size': len(file_data)
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        # Generate preview
        preview = ocr_service.get_ocr_preview(file_data, options)
        
        job.result = preview
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        logger.info(f"OCR preview task completed for job {job_id}")
        return preview
        
    except Exception as e:
        logger.error(f"Error in OCR preview task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        raise

# ============================================================================
# AI TASKS
# ============================================================================

@celery_app.task(bind=True, name='tasks.ai_summarize_task')
def ai_summarize_task(self, job_id: str, text: str, options: Dict,
                     client_job_id: str = None, client_session_id: str = None) -> Dict[str, Any]:
    """
    Summarize text using AI asynchronously
    """
    try:
        logger.info(f"Starting AI summarization task for job {job_id}")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='ai_summarize',
            input_data={
                'text_length': len(text),
                'options': options
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        # Process summarization
        result = ai_service.summarize_text(text, options)
        
        job.result = result
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        logger.info(f"AI summarization task completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in AI summarization task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        raise

@celery_app.task(bind=True, name='tasks.ai_translate_task')
def ai_translate_task(self, job_id: str, text: str, target_language: str,
                     options: Dict, client_job_id: str = None,
                     client_session_id: str = None) -> Dict[str, Any]:
    """
    Translate text using AI asynchronously
    """
    try:
        logger.info(f"Starting AI translation task for job {job_id} (target: {target_language})")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='ai_translate',
            input_data={
                'target_language': target_language,
                'text_length': len(text),
                'options': options
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        # Process translation
        result = ai_service.translate_text(text, target_language, options)
        
        job.result = result
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        logger.info(f"AI translation task completed for job {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in AI translation task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        raise

@celery_app.task(bind=True, name='tasks.extract_text_task')
def extract_text_task(self, job_id: str, file_data: bytes,
                     original_filename: str = None, client_job_id: str = None,
                     client_session_id: str = None) -> Dict[str, Any]:
    """
    Extract text from PDF asynchronously
    """
    try:
        logger.info(f"Starting text extraction task for job {job_id}")
        
        job = Job.query.get(job_id) or Job(
            id=job_id,
            task_type='extract_text',
            input_data={
                'file_size': len(file_data),
                'original_filename': original_filename
            },
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        job.status = JobStatus.PROCESSING
        db.session.commit()
        
        current_task.update_state(
            state='PROGRESS',
            meta={
                'progress': 10,
                'status': 'Starting text extraction'
            }
        )
        
        # Extract text
        text_content = ai_service.extract_text_from_pdf_data(file_data)
        
        job.result = {
            'text': text_content,
            'length': len(text_content),
            'original_filename': original_filename
        }
        job.status = JobStatus.COMPLETED
        db.session.commit()
        
        current_task.update_state(
            state='SUCCESS',
            meta={
                'progress': 100,
                'status': 'Text extraction completed'
            }
        )
        
        logger.info(f"Text extraction task completed for job {job_id}")
        return job.result
        
    except Exception as e:
        logger.error(f"Error in text extraction task {job_id}: {str(e)}")
        
        if 'job' in locals() and job:
            job.status = JobStatus.FAILED
            job.error = str(e)
            db.session.commit()
        
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        raise

# ============================================================================
# MAINTENANCE TASKS
# ============================================================================

@celery_app.task(bind=True, name='tasks.cleanup_expired_jobs')
def cleanup_expired_jobs(self) -> Dict[str, Any]:
    """
    Clean up expired jobs and their associated files
    """
    try:
        logger.info("Starting cleanup of expired jobs")
        
        cutoff_time = datetime.utcnow() - timedelta(hours=24)  # 24 hours retention
        
        # Find expired jobs
        expired_jobs = Job.query.filter(
            Job.created_at < cutoff_time,
            Job.status.in_(['completed', 'failed'])
        ).all()
        
        cleaned_count = 0
        error_count = 0
        total_size_freed = 0
        
        for job in expired_jobs:
            try:
                # Clean up job files
                job_size = _cleanup_job_files(job)
                total_size_freed += job_size
                cleaned_count += 1
                
                # Delete job record
                db.session.delete(job)
                
                logger.info(f"Cleaned up expired job {job.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error cleaning up job {job.id}: {str(e)}")
        
        db.session.commit()
        
        current_task.update_state(
            state='SUCCESS',
            meta={
                'cleaned_count': cleaned_count,
                'error_count': error_count,
                'total_size_freed': total_size_freed
            }
        )
        
        logger.info(f"Cleanup completed: {cleaned_count} jobs cleaned, {error_count} errors")
        return {
            'cleaned_count': cleaned_count,
            'error_count': error_count,
            'total_size_freed': total_size_freed
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        current_task.update_state(
            state='FAILURE',
            meta={'error': str(e)}
        )
        raise

def _cleanup_job_files(job: Job) -> int:
    """
    Clean up files associated with a job
    """
    total_size = 0
    
    try:
        # Clean up result files
        if job.result and 'output_path' in job.result:
            result_path = job.result['output_path']
            if os.path.exists(result_path):
                total_size += os.path.getsize(result_path)
                os.remove(result_path)
                logger.debug(f"Removed result file: {result_path}")
        
        # Clean up temporary files
        if job.result and 'temp_files' in job.result:
            for temp_file in job.result['temp_files']:
                if os.path.exists(temp_file):
                    total_size += os.path.getsize(temp_file)
                    os.remove(temp_file)
                    logger.debug(f"Removed temp file: {temp_file}")
                    
    except Exception as e:
        logger.error(f"Error cleaning up files for job {job.id}: {str(e)}")
    
    return total_size

@celery_app.task(bind=True, name='tasks.get_task_status')
def get_task_status(self, task_id: str) -> Dict[str, Any]:
    """
    Get the status of a Celery task
    """
    try:
        result = celery_app.AsyncResult(task_id)
        
        response = {
            'state': result.state,
            'task_id': task_id
        }
        
        if result.state == 'PROGRESS':
            response.update(result.info or {})
        elif result.state == 'SUCCESS':
            response['result'] = result.result
        elif result.state == 'FAILURE':
            response['error'] = str(result.info)
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        return {
            'state': 'ERROR',
            'error': str(e),
            'task_id': task_id
        }