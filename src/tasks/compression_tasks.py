"""
Celery tasks for background compression processing
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from celery import current_task
from celery.exceptions import Retry

from src.celery_app import celery_app
from src.models import CompressionJob, User
from src.models.base import db
from src.services.bulk_compression_service import BulkCompressionService
from src.services.subscription_service import SubscriptionService
from src.config.config import Config


logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name='src.tasks.compression_tasks.process_bulk_compression')
def process_bulk_compression(self, job_id: int) -> Dict[str, Any]:
    """
    Process a bulk compression job asynchronously
    
    Args:
        job_id: ID of the compression job to process
        
    Returns:
        Dictionary with processing results
    """
    try:
        logger.info(f"Starting bulk compression task for job {job_id}")
        
        # Get the job from database
        job = CompressionJob.query.get(job_id)
        if not job:
            error_msg = f"Job {job_id} not found"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'job_id': job_id
            }
        
        if job.job_type != 'bulk':
            error_msg = f"Job {job_id} is not a bulk job"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'job_id': job_id
            }
        
        # Check if job is already being processed or completed
        if job.status in ['processing', 'completed']:
            logger.warning(f"Job {job_id} is already {job.status}")
            return {
                'success': True,
                'message': f"Job already {job.status}",
                'job_id': job_id
            }
        
        # Mark job as processing and update task ID
        job.mark_as_processing()
        job.task_id = self.request.id
        db.session.commit()
        
        # Initialize bulk compression service
        config = Config()
        bulk_service = BulkCompressionService(config.UPLOAD_FOLDER)
        
        # Get job settings and files
        settings = job.get_settings()
        input_files = settings.get('input_files', [])
        job_dir = settings.get('job_directory')
        
        if not job_dir or not os.path.exists(job_dir):
            error_msg = f"Job directory not found for job {job_id}"
            logger.error(error_msg)
            job.mark_as_failed(error_msg)
            db.session.commit()
            return {
                'success': False,
                'error': error_msg,
                'job_id': job_id
            }
        
        # Process files with progress updates
        processed_files = []
        total_compressed_size = 0
        errors = []
        
        total_files = len(input_files)
        
        for i, file_info in enumerate(input_files):
            try:
                # Update task progress
                progress = int((i / total_files) * 100)
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': i,
                        'total': total_files,
                        'progress': progress,
                        'status': f'Processing file {i+1} of {total_files}: {file_info["original_name"]}'
                    }
                )
                
                # Process the file
                result = bulk_service._process_single_file_in_batch(
                    file_info, job_dir, settings, i
                )
                processed_files.append(result)
                total_compressed_size += result['compressed_size']
                
                # Update job progress in database
                job.completed_count = i + 1
                db.session.commit()
                
                logger.info(f"Processed file {i+1}/{total_files} for job {job_id}: {file_info['original_name']}")
                
            except Exception as e:
                error_info = {
                    'file': file_info['original_name'],
                    'error': str(e),
                    'index': i
                }
                errors.append(error_info)
                logger.error(f"Error processing file {file_info['original_name']} in job {job_id}: {str(e)}")
                
                # Continue processing other files
                continue
        
        # Create result archive if any files were processed successfully
        result_path = None
        if processed_files:
            try:
                result_path = bulk_service._create_result_archive(job_dir, processed_files, job.id)
                logger.info(f"Created result archive for job {job_id}: {result_path}")
            except Exception as e:
                logger.error(f"Error creating result archive for job {job_id}: {str(e)}")
                errors.append({
                    'file': 'result_archive',
                    'error': f"Failed to create result archive: {str(e)}",
                    'index': -1
                })
        
        # Update job with final results
        job.compressed_size_bytes = total_compressed_size
        job.result_path = result_path
        job.calculate_compression_ratio()
        
        # Determine final job status
        if errors and not processed_files:
            # All files failed
            error_msg = f"All files failed to process. Errors: {len(errors)}"
            job.mark_as_failed(error_msg)
            logger.error(f"Job {job_id} failed completely: {error_msg}")
        elif errors:
            # Some files failed
            job.mark_as_completed()
            job.error_message = f"Completed with {len(errors)} errors"
            logger.warning(f"Job {job_id} completed with errors: {len(errors)} files failed")
        else:
            # All files succeeded
            job.mark_as_completed()
            logger.info(f"Job {job_id} completed successfully: {len(processed_files)} files processed")
        
        db.session.commit()
        
        # Increment usage counter for successful compressions
        if processed_files:
            try:
                SubscriptionService.increment_usage(job.user_id, len(processed_files))
                logger.info(f"Updated usage count for user {job.user_id}: +{len(processed_files)} compressions")
            except Exception as e:
                logger.error(f"Error updating usage count for user {job.user_id}: {str(e)}")
        
        # Update final task state
        current_task.update_state(
            state='SUCCESS',
            meta={
                'current': total_files,
                'total': total_files,
                'progress': 100,
                'status': 'Completed',
                'processed_count': len(processed_files),
                'error_count': len(errors)
            }
        )
        
        return {
            'success': True,
            'job_id': job_id,
            'processed_count': len(processed_files),
            'error_count': len(errors),
            'errors': errors,
            'result_path': result_path,
            'total_compressed_size': total_compressed_size
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in bulk compression task for job {job_id}: {str(e)}")
        
        # Mark job as failed if we have access to it
        try:
            if 'job' in locals() and job:
                job.mark_as_failed(f"Task error: {str(e)}")
                db.session.commit()
        except Exception as db_error:
            logger.error(f"Error updating job status after task failure: {str(db_error)}")
        
        # Update task state to failure
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e),
                'job_id': job_id
            }
        )
        
        # Re-raise the exception for Celery to handle
        raise


@celery_app.task(bind=True, name='src.tasks.compression_tasks.cleanup_expired_jobs')
def cleanup_expired_jobs(self) -> Dict[str, Any]:
    """
    Clean up expired compression jobs and their associated files
    
    Returns:
        Dictionary with cleanup results
    """
    try:
        logger.info("Starting cleanup of expired compression jobs")
        
        config = Config()
        cutoff_time = datetime.utcnow() - config.MAX_FILE_AGE
        
        # Find expired jobs
        expired_jobs = CompressionJob.query.filter(
            CompressionJob.created_at < cutoff_time,
            CompressionJob.status.in_(['completed', 'failed'])
        ).all()
        
        cleaned_count = 0
        error_count = 0
        total_size_freed = 0
        
        bulk_service = BulkCompressionService(config.UPLOAD_FOLDER)
        
        for job in expired_jobs:
            try:
                # Calculate size before cleanup
                job_size = 0
                if job.input_path and os.path.exists(job.input_path):
                    job_size = _get_directory_size(job.input_path)
                
                # Clean up job files
                if bulk_service.cleanup_job_files(job.id):
                    total_size_freed += job_size
                    cleaned_count += 1
                    logger.info(f"Cleaned up expired job {job.id} (freed {job_size} bytes)")
                else:
                    error_count += 1
                    logger.warning(f"Failed to clean up job {job.id}")
                
            except Exception as e:
                error_count += 1
                logger.error(f"Error cleaning up job {job.id}: {str(e)}")
        
        # Update task progress
        current_task.update_state(
            state='SUCCESS',
            meta={
                'cleaned_count': cleaned_count,
                'error_count': error_count,
                'total_size_freed': total_size_freed,
                'status': f'Cleaned {cleaned_count} jobs, freed {total_size_freed} bytes'
            }
        )
        
        logger.info(f"Cleanup completed: {cleaned_count} jobs cleaned, {error_count} errors, {total_size_freed} bytes freed")
        
        return {
            'success': True,
            'cleaned_count': cleaned_count,
            'error_count': error_count,
            'total_size_freed': total_size_freed
        }
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")
        
        current_task.update_state(
            state='FAILURE',
            meta={
                'error': str(e)
            }
        )
        
        raise


def _get_directory_size(directory_path: str) -> int:
    """
    Calculate the total size of a directory and its contents
    
    Args:
        directory_path: Path to the directory
        
    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                if os.path.exists(file_path):
                    total_size += os.path.getsize(file_path)
    except Exception as e:
        logger.error(f"Error calculating directory size for {directory_path}: {str(e)}")
    
    return total_size


@celery_app.task(bind=True, name='src.tasks.compression_tasks.get_task_status')
def get_task_status(self, task_id: str) -> Dict[str, Any]:
    """
    Get the status of a Celery task
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Task status information
    """
    try:
        result = celery_app.AsyncResult(task_id)
        
        if result.state == 'PENDING':
            response = {
                'state': result.state,
                'status': 'Task is waiting to be processed'
            }
        elif result.state == 'PROGRESS':
            response = {
                'state': result.state,
                'current': result.info.get('current', 0),
                'total': result.info.get('total', 1),
                'progress': result.info.get('progress', 0),
                'status': result.info.get('status', 'Processing...')
            }
        elif result.state == 'SUCCESS':
            response = {
                'state': result.state,
                'result': result.result,
                'status': 'Task completed successfully'
            }
        elif result.state == 'FAILURE':
            response = {
                'state': result.state,
                'error': str(result.info),
                'status': 'Task failed'
            }
        else:
            response = {
                'state': result.state,
                'status': f'Task state: {result.state}'
            }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        return {
            'state': 'ERROR',
            'error': str(e),
            'status': 'Error retrieving task status'
        }