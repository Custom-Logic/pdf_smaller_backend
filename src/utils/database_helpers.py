"""Database operation helpers with consistent error handling.

This module provides utilities for safe database operations with standardized
error handling, retry logic, and transaction management.
"""

from typing import Callable, Any, Optional
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError
from src.models.base import db
from src.models.job import Job, JobStatus
from src.utils.db_transaction import safe_db_operation as new_safe_db_operation
import logging
import time

logger = logging.getLogger(__name__)


def safe_db_operation(operation: Callable, rollback_on_error: bool = True, 
                     max_retries: int = 3) -> Optional[Any]:
    """Safely execute database operation with consistent error handling.
    
    This is a compatibility wrapper around the new transaction utilities.
    
    Args:
        operation: Callable that performs the database operation
        rollback_on_error: Whether to rollback on database errors (ignored, always True in new system)
        max_retries: Maximum number of retry attempts
        
    Returns:
        Result of the operation if successful, None if failed
        
    Raises:
        Exception: Re-raises the final exception if all retries fail
    """
    # Use the new transaction system with a unique operation name
    operation_name = f"legacy_db_operation_{id(operation)}"
    return new_safe_db_operation(
        operation,
        operation_name,
        max_retries=max_retries,
        default_return=None
    )


def update_job_status_safely(job_id: str, status: JobStatus, error_msg: str = None, 
                           job: Job = None, result_data: dict = None) -> Optional[Job]:
    """Safely update job status with consistent error handling.
    
    Args:
        job_id: ID of the job to update
        status: New status for the job
        error_msg: Error message if status is FAILED
        job: Existing job instance (optional, will query if not provided)
        result_data: Result data if status is COMPLETED
        
    Returns:
        Updated job instance if successful, None if failed
    """
    def update_operation():
        target_job = job or Job.query.filter_by(job_id=job_id).first()
        if not target_job:
            logger.warning(f"Job {job_id} not found for status update")
            return None
            
        if status == JobStatus.FAILED:
            target_job.mark_as_failed(error_msg or "Unknown error")
        elif status == JobStatus.COMPLETED:
            target_job.mark_as_completed(result_data or {})
        elif status == JobStatus.PROCESSING:
            target_job.status = JobStatus.PROCESSING.value
        elif status == JobStatus.PENDING:
            target_job.status = JobStatus.PENDING.value
        else:
            logger.warning(f"Unknown job status: {status}")
            return None
            
        return target_job
    
    return safe_db_operation(update_operation)


def create_job_safely(job_data: dict) -> Optional[Job]:
    """Safely create a new job with consistent error handling.
    
    Args:
        job_data: Dictionary containing job creation data
        
    Returns:
        Created job instance if successful, None if failed
    """
    def create_operation():
        job = Job(
            job_id=job_data.get('job_id'), 
            task_id=job_data.get('task_id'), 
            task_type= job_data.get('task_type'), 
            status=job_data.get('status'), 
            input_data=job_data.get('input_data'), 
            result=input_data.get('result'), error=input_data.get('error'))
        db.session.add(job)
        return job
    
    return safe_db_operation(create_operation)


def delete_job_safely(job_id: str) -> bool:
    """Safely delete a job with consistent error handling.
    
    Args:
        job_id: ID of the job to delete
        
    Returns:
        True if deletion was successful, False otherwise
    """
    def delete_operation():
        job = Job.query.filter_by(job_id=job_id).first()
        if job:
            db.session.delete(job)
            return True
        return False
    
    try:
        return safe_db_operation(delete_operation) or False
    except Exception:
        return False


def bulk_update_jobs_safely(job_ids: list, update_data: dict) -> int:
    """Safely update multiple jobs with consistent error handling.
    
    Args:
        job_ids: List of job IDs to update
        update_data: Dictionary of fields to update
        
    Returns:
        Number of jobs successfully updated
    """
    def bulk_update_operation():
        updated_count = Job.query.filter(Job.job_id.in_(job_ids)).update(
            update_data, synchronize_session=False
        )
        return updated_count
    
    try:
        return safe_db_operation(bulk_update_operation) or 0
    except Exception:
        return 0