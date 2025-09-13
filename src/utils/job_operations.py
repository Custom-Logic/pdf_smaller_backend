"""Enhanced job operations utility with transaction safety.

This module provides an enhanced layer on top of JobStatusManager that uses
the new database transaction utilities for improved safety and consistency.
It serves as a bridge between the existing JobStatusManager and the new
transaction management system.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from src.models.job import Job, JobStatus
from src.models.base import db
from src.utils.db_transaction import (
    db_transaction, 
    DatabaseTransactionError, 
    transactional, 
    safe_db_operation,
    get_or_create_with_lock
)
from src.utils.job_manager import JobStatusManager

logger = logging.getLogger(__name__)


class JobOperations:
    """Enhanced job operations with transaction safety.
    
    This class provides a higher-level interface for job operations that
    leverages the new transaction management utilities while maintaining
    compatibility with existing JobStatusManager functionality.
    """
    
    @staticmethod
    @transactional("create_job_safely")
    def create_job_safely(job_id: str, task_type: str, 
                         input_data: Dict[str, Any] = None,
                         initial_status: JobStatus = JobStatus.PENDING) -> Optional[Job]:
        """Create a new job with transaction safety.
        
        Args:
            job_id: Unique identifier for the job
            task_type: Type of task (e.g., 'compress', 'extract')
            input_data: Optional input data for the job
            initial_status: Initial status for the job
            
        Returns:
            Created Job instance or None if creation failed
            
        Example:
            ```python
            job = JobOperations.create_job_safely(
                job_id="compress_123",
                task_type="compress",
                input_data={"file_path": "/uploads/doc.pdf"},
                initial_status=JobStatus.PENDING
            )
            ```
        """
        try:
            # Use the enhanced get_or_create with proper locking
            job, created = get_or_create_with_lock(
                Job,
                {'job_id': job_id},
                {
                    'task_type': task_type,
                    'input_data': input_data or {},
                    'status': initial_status.value,
                    'created_at': datetime.now(timezone.utc),
                    'updated_at': datetime.now(timezone.utc)
                },
                f"create_job_{job_id}"
            )
            
            if created:
                logger.info(f"Created new job {job_id} with type {task_type}")
            else:
                logger.info(f"Retrieved existing job {job_id}")
                
            return job
            
        except DatabaseTransactionError as e:
            logger.error(f"Failed to create job {job_id}: {e}")
            return None
    
    @staticmethod
    def update_job_status_safely(job_id: str, status: JobStatus,
                               result: Dict[str, Any] = None,
                               error_message: str = None,
                               progress: Optional[float] = None) -> bool:
        """Update job status with enhanced transaction safety.
        
        Args:
            job_id: Unique identifier of the job
            status: New status to set
            result: Optional result data
            error_message: Optional error message
            progress: Optional progress percentage (0-100)
            
        Returns:
            True if update was successful, False otherwise
        """
        def update_operation():
            with db_transaction(f"update_job_status_{job_id}") as session:
                # Get job with row lock
                job = session.query(Job).filter_by(job_id=job_id).with_for_update().first()
                
                if not job:
                    logger.warning(f"Job {job_id} not found for status update")
                    return False
                
                # Validate status transition
                if not JobStatusManager._is_valid_transition(job.status, status.value):
                    logger.error(f"Invalid status transition for job {job_id}: {job.status} -> {status.value}")
                    return False
                
                # Update job using model methods for consistency
                if status == JobStatus.PROCESSING:
                    job.mark_as_processing()
                elif status == JobStatus.COMPLETED:
                    job.mark_as_completed(result or {})
                elif status == JobStatus.FAILED:
                    job.mark_as_failed(error_message or "Unknown error")
                else:
                    # Direct status update for other statuses
                    job.status = status.value
                    job.updated_at = datetime.now(timezone.utc)
                
                # Update progress if provided
                if progress is not None:
                    job.progress = max(0, min(100, progress))  # Clamp to 0-100
                
                logger.info(f"Updated job {job_id} status to {status.value}")
                return True
        
        return safe_db_operation(
            update_operation,
            f"update_job_status_{job_id}",
            max_retries=2,
            default_return=False
        )
    
    @staticmethod
    def get_job_with_lock(job_id: str) -> Optional[Job]:
        """Get a job with row-level lock for safe modification.
        
        Args:
            job_id: Unique identifier of the job
            
        Returns:
            Job instance with lock acquired, or None if not found
            
        Note:
            This method should be used within a transaction context.
        """
        try:
            with db_transaction(f"get_job_with_lock_{job_id}", auto_commit=False) as session:
                job = session.query(Job).filter_by(job_id=job_id).with_for_update().first()
                return job
        except DatabaseTransactionError as e:
            logger.error(f"Failed to get job {job_id} with lock: {e}")
            return None
    
    @staticmethod
    def execute_job_operation(job_id: str, operation_func, *args, **kwargs) -> Any:
        """Execute a custom operation on a job with proper locking.
        
        Args:
            job_id: Unique identifier of the job
            operation_func: Function to execute with the job as first parameter
            *args: Additional arguments for the operation function
            **kwargs: Additional keyword arguments for the operation function
            
        Returns:
            Result of the operation function
            
        Example:
            ```python
            def update_progress(job, progress, message):
                job.progress = progress
                job.status_message = message
                return f"Updated to {progress}%"
            
            result = JobOperations.execute_job_operation(
                "compress_123",
                update_progress,
                75,
                "Applying compression algorithms"
            )
            ```
        """
        def wrapped_operation():
            with db_transaction(f"job_operation_{job_id}") as session:
                job = session.query(Job).filter_by(job_id=job_id).with_for_update().first()
                
                if not job:
                    logger.warning(f"Job {job_id} not found for operation")
                    return None
                
                return operation_func(job, *args, **kwargs)
        
        return safe_db_operation(
            wrapped_operation,
            f"execute_job_operation_{job_id}",
            max_retries=1,
            default_return=None
        )
    
    @staticmethod
    @transactional("batch_update_jobs")
    def batch_update_jobs(job_updates: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Update multiple jobs in a single transaction.
        
        Args:
            job_updates: List of dictionaries with job update information.
                        Each dict should contain 'job_id' and update fields.
                        
        Returns:
            Dictionary mapping job_id to success status
            
        Example:
            ```python
            updates = [
                {'job_id': 'job1', 'status': JobStatus.COMPLETED, 'result': {'size': 1024}},
                {'job_id': 'job2', 'status': JobStatus.FAILED, 'error_message': 'Timeout'}
            ]
            results = JobOperations.batch_update_jobs(updates)
            ```
        """
        results = {}
        
        for update_info in job_updates:
            job_id = update_info.get('job_id')
            if not job_id:
                logger.error("Missing job_id in batch update")
                continue
                
            try:
                job = db.session.query(Job).filter_by(job_id=job_id).with_for_update().first()
                
                if not job:
                    logger.warning(f"Job {job_id} not found in batch update")
                    results[job_id] = False
                    continue
                
                # Apply updates
                if 'status' in update_info:
                    status = update_info['status']
                    if isinstance(status, JobStatus):
                        status = status.value
                    
                    # Validate transition if current status exists
                    if job.status and not JobStatusManager._is_valid_transition(job.status, status):
                        logger.error(f"Invalid transition for job {job_id}: {job.status} -> {status}")
                        results[job_id] = False
                        continue
                    
                    job.status = status
                
                if 'result' in update_info:
                    job.result = update_info['result']
                
                if 'error_message' in update_info:
                    job.error = update_info['error_message']
                
                if 'progress' in update_info:
                    job.progress = max(0, min(100, update_info['progress']))
                
                job.updated_at = datetime.now(timezone.utc)
                results[job_id] = True
                
                logger.debug(f"Updated job {job_id} in batch operation")
                
            except Exception as e:
                logger.error(f"Failed to update job {job_id} in batch: {e}")
                results[job_id] = False
        
        return results
    
    @staticmethod
    @transactional("cleanup_old_jobs")
    def cleanup_old_jobs(days_old: int = 30, batch_size: int = 100) -> int:
        """Clean up old jobs with transaction safety.
        
        Args:
            days_old: Number of days after which jobs are considered old
            batch_size: Number of jobs to delete in each batch
            
        Returns:
            Number of jobs deleted
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
        total_deleted = 0
        
        while True:
            # Get a batch of old jobs
            old_jobs = db.session.query(Job).filter(
                Job.created_at < cutoff_date,
                Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
            ).limit(batch_size).all()
            
            if not old_jobs:
                break
            
            # Delete the batch
            for job in old_jobs:
                db.session.delete(job)
            
            batch_count = len(old_jobs)
            total_deleted += batch_count
            
            logger.info(f"Deleted batch of {batch_count} old jobs (total: {total_deleted})")
            
            # If we got fewer than batch_size, we're done
            if batch_count < batch_size:
                break
        
        logger.info(f"Cleanup completed: deleted {total_deleted} jobs older than {days_old} days")
        return total_deleted
    
    @staticmethod
    def get_job_statistics() -> Dict[str, Any]:
        """Get job statistics with transaction safety.
        
        Returns:
            Dictionary containing job statistics
        """
        def stats_operation():
            with db_transaction("get_job_statistics", auto_commit=False) as session:
                stats = {
                    'total_jobs': session.query(Job).count(),
                    'pending_jobs': session.query(Job).filter_by(status=JobStatus.PENDING.value).count(),
                    'processing_jobs': session.query(Job).filter_by(status=JobStatus.PROCESSING.value).count(),
                    'completed_jobs': session.query(Job).filter_by(status=JobStatus.COMPLETED.value).count(),
                    'failed_jobs': session.query(Job).filter_by(status=JobStatus.FAILED.value).count(),
                }
                
                # Calculate success rate
                total_finished = stats['completed_jobs'] + stats['failed_jobs']
                if total_finished > 0:
                    stats['success_rate'] = stats['completed_jobs'] / total_finished
                else:
                    stats['success_rate'] = 0.0
                
                return stats
        
        return safe_db_operation(
            stats_operation,
            "get_job_statistics",
            max_retries=1,
            default_return={
                'total_jobs': 0,
                'pending_jobs': 0,
                'processing_jobs': 0,
                'completed_jobs': 0,
                'failed_jobs': 0,
                'success_rate': 0.0
            }
        )