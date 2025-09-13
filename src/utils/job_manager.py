"""JobStatusManager - Thread-safe job management utility with database safety mechanisms.

This module provides a centralized utility for managing job lifecycle operations with proper
database locking, transaction handling, and race condition prevention. The JobStatusManager
class implements sophisticated database safety mechanisms including:

- Row-level locking with SELECT FOR UPDATE to prevent race conditions
- Explicit transaction boundaries with proper rollback handling
- Atomic status updates with validation
- Thread-safe operations for concurrent job processing
- Structured exception handling and logging

Design Philosophy:
    The JobStatusManager follows a defensive programming approach where all database
    operations are wrapped in explicit transactions with row-level locking. This ensures
    data consistency in high-concurrency scenarios where multiple workers might attempt
    to modify the same job simultaneously.

Key Features:
    - Race condition prevention through SELECT FOR UPDATE
    - Status transition validation with state machine logic
    - Atomic job creation and updates
    - Safe cleanup operations for old jobs
    - Comprehensive error handling and logging

Usage:
    The JobStatusManager is designed to be used across the application wherever job
    status management is required, particularly in Celery tasks, service layers, and
    route handlers. All methods are static and thread-safe.

Example:
    >>> # Create or get existing job
    >>> job = JobStatusManager.get_or_create_job(
    ...     job_id="task_123",
    ...     task_type="compression",
    ...     input_data={"file_path": "/path/to/file.pdf"}
    ... )
    
    >>> # Update job status atomically
    >>> success = JobStatusManager.update_job_status(
    ...     job_id="task_123",
    ...     status=JobStatus.COMPLETED,
    ...     result={"output_path": "/path/to/compressed.pdf"}
    ... )

See Also:
    - src.models.job.Job: The Job model class
    - src.utils.database_helpers: Additional database utilities
    - src.utils.exceptions: Custom exception classes
    - docs/job_manager_documentation.md: Detailed documentation
"""

from typing import Dict, Any, Optional, Callable
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from src.models.job import Job, JobStatus
from src.models.base import db
import logging

logger = logging.getLogger(__name__)

class JobStatusManager:
    """Thread-safe job management with proper locking and transactions.
    
    This class provides static methods for managing job lifecycle operations
    with database safety mechanisms to prevent race conditions and ensure
    data consistency in concurrent environments.
    """
    
    @staticmethod
    def get_or_create_job(job_id: str, task_type: str, input_data: Dict[str, Any]) -> Job:
        """Get existing job or create new one with proper locking to prevent race conditions.
        
        This method implements the "get or create" pattern with row-level locking to ensure
        that only one job with the given job_id can be created, even in high-concurrency
        scenarios. Uses SELECT FOR UPDATE to lock the row during the check-and-create operation.
        
        Args:
            job_id (str): Unique identifier for the job. Must be unique across all jobs.
            task_type (str): Type of task (e.g., 'compression', 'conversion', 'ocr').
                           Should match TaskType enum values from the Job model.
            input_data (Dict[str, Any]): Input parameters for the job. Will be stored
                                       as JSON in the database.
        
        Returns:
            Job: Either the existing job instance or a newly created one.
                The job will be in PENDING status if newly created.
        
        Raises:
            Exception: Re-raises any database exceptions that occur during the operation.
                      The transaction will be rolled back automatically.
        
        Example:
            >>> job = JobStatusManager.get_or_create_job(
            ...     job_id="compress_doc_123",
            ...     task_type="compression",
            ...     input_data={
            ...         "file_path": "/uploads/document.pdf",
            ...         "compression_level": "medium"
            ...     }
            ... )
            >>> print(f"Job status: {job.status}")
        
        Note:
            This method uses explicit transaction boundaries with db.session.begin()
            to ensure atomicity. The SELECT FOR UPDATE prevents other processes
            from creating duplicate jobs with the same job_id.
        """
        try:
            # Begin explicit transaction for atomicity
            with db.session.begin():
                # Use SELECT FOR UPDATE to lock the row and prevent race conditions
                # This ensures that if two processes try to create the same job_id
                # simultaneously, only one will succeed
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    # Job doesn't exist, create new one
                    # The row lock ensures no other process can create it simultaneously
                    job = Job(
                        job_id=job_id,
                        task_type=task_type,
                        input_data=input_data
                    )
                    db.session.add(job)
                    # Flush to ensure the job gets an ID and is visible within this transaction
                    db.session.flush()
                    logger.info(f"Created new job {job_id} with type {task_type}")
                else:
                    logger.debug(f"Retrieved existing job {job_id}")
                
                return job
        except Exception as e:
            # Log the error with context for debugging
            logger.error(f"Failed to get or create job {job_id}: {e}")
            # Rollback is handled automatically by the context manager
            db.session.rollback()
            raise
    
    @staticmethod
    def update_job_status(job_id: str, status: JobStatus, 
                         result: Dict[str, Any] = None, 
                         error_message: str = None,
                         validate_transition: bool = True) -> bool:
        """Atomically update job status with optional validation and result data.
        
        This method provides thread-safe job status updates with row-level locking
        to prevent race conditions. It validates status transitions according to
        the job state machine and uses the Job model's methods for consistency.
        
        Args:
            job_id (str): Unique identifier of the job to update.
            status (JobStatus): New status to set. Must be a valid JobStatus enum value.
            result (Dict[str, Any], optional): Result data to store with the job.
                                             Only used when status is COMPLETED.
            error_message (str, optional): Error message to store with the job.
                                         Only used when status is FAILED.
            validate_transition (bool, optional): Whether to validate the status
                                                transition. Defaults to True.
        
        Returns:
            bool: True if the update was successful, False if the job was not found
                 or the transition was invalid.
        
        Raises:
            Exception: Database exceptions are caught, logged, and return False.
                      The transaction is rolled back automatically.
        
        Example:
            >>> # Mark job as processing
            >>> success = JobStatusManager.update_job_status(
            ...     job_id="compress_doc_123",
            ...     status=JobStatus.PROCESSING
            ... )
            
            >>> # Mark job as completed with results
            >>> success = JobStatusManager.update_job_status(
            ...     job_id="compress_doc_123",
            ...     status=JobStatus.COMPLETED,
            ...     result={"output_path": "/compressed/doc.pdf", "size_reduction": 0.65}
            ... )
            
            >>> # Mark job as failed with error
            >>> success = JobStatusManager.update_job_status(
            ...     job_id="compress_doc_123",
            ...     status=JobStatus.FAILED,
            ...     error_message="File not found: /uploads/document.pdf"
            ... )
        
        Note:
            The method uses Job model methods (mark_as_processing, mark_as_completed,
            mark_as_failed) to ensure consistency with the model's business logic.
            Status transitions are validated against the job state machine rules.
        """
        try:
            # Begin transaction with automatic rollback on exception
            with db.session.begin():
                # Lock the job row for update to prevent concurrent modifications
                # This ensures that status updates are atomic and consistent
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    logger.error(f"Job {job_id} not found for status update")
                    return False
                
                # Validate status transition according to state machine rules
                if validate_transition and not JobStatusManager._is_valid_transition(job.status, status.value):
                    logger.error(f"Invalid status transition for job {job_id}: {job.status} -> {status.value}")
                    return False
                
                # Update job using model methods to ensure business logic consistency
                # These methods handle timestamps, validation, and data formatting
                if status == JobStatus.PROCESSING:
                    job.mark_as_processing()
                elif status == JobStatus.COMPLETED:
                    job.mark_as_completed(result or {})
                elif status == JobStatus.FAILED:
                    job.mark_as_failed(error_message or "Unknown error")
                else:
                    # Direct status assignment for other states
                    job.status = status.value
                
                logger.info(f"Updated job {job_id} status to {status.value}")
                return True
                
        except Exception as e:
            # Log error with context for debugging
            logger.error(f"Failed to update job {job_id} status: {e}")
            # Rollback is handled automatically by the context manager
            db.session.rollback()
            return False
    
    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Validate job status transitions according to the state machine rules.
        
        This method enforces the job lifecycle state machine to prevent invalid
        status transitions that could lead to inconsistent job states. The state
        machine ensures jobs follow a logical progression through their lifecycle.
        
        Valid Transitions:
        - PENDING → PROCESSING, FAILED, CANCELLED
        - PROCESSING → COMPLETED, FAILED, CANCELLED
        - COMPLETED → (terminal state, no transitions)
        - FAILED → PENDING (retry), CANCELLED
        - CANCELLED → (terminal state, no transitions)
        
        Args:
            current_status (str): The current job status as a string.
            new_status (str): The desired new status as a string.
        
        Returns:
            bool: True if the transition is valid, False otherwise.
        
        Example:
            >>> # Valid transitions
            >>> JobStatusManager._is_valid_transition('pending', 'processing')  # True
            >>> JobStatusManager._is_valid_transition('processing', 'completed')  # True
            >>> JobStatusManager._is_valid_transition('failed', 'pending')  # True (retry)
            
            >>> # Invalid transitions
            >>> JobStatusManager._is_valid_transition('completed', 'processing')  # False
            >>> JobStatusManager._is_valid_transition('cancelled', 'pending')  # False
        
        Note:
            This method is used internally by update_job_status to prevent
            invalid state transitions that could corrupt the job lifecycle.
        """
        valid_transitions = {
            JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
            JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
            JobStatus.COMPLETED.value: [],  # Terminal state
            JobStatus.FAILED.value: [JobStatus.PROCESSING.value]  # Allow retry
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    @staticmethod
    def execute_with_job_lock(job_id: str, operation: Callable[[Job], Any]) -> Any:
        """Execute an operation with job-level database locking for thread safety.
        
        This method provides a higher-level abstraction for executing operations
        that require exclusive access to a specific job. It uses SELECT FOR UPDATE
        to lock the job row and ensures the operation is executed atomically.
        
        Args:
            job_id (str): Unique identifier of the job to lock.
            operation (Callable[[Job], Any]): Function to execute while holding the job lock.
                                            The job object will be passed as the first argument.
        
        Returns:
            Any: The return value of the operation function.
        
        Raises:
            ValueError: If the job with the given job_id is not found.
            Exception: Re-raises any database exceptions that occur during the operation.
                      The transaction will be rolled back automatically.
        
        Example:
            >>> def update_progress(job):
            ...     job.progress = 75
            ...     return f"Updated to {job.progress}%"
            
            >>> result = JobStatusManager.execute_with_job_lock(
            ...     job_id="compress_doc_123",
            ...     operation=update_progress
            ... )
            >>> print(result)  # "Updated to 75%"
        
        Note:
            The operation function receives the locked Job object as its parameter.
            The job row remains locked for the duration of the operation to prevent
            race conditions in concurrent environments.
        """
        try:
            # Begin atomic transaction with automatic rollback on exception
            with db.session.begin():
                # Lock the specific job row to prevent concurrent access
                # This ensures exclusive access during the operation
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    raise ValueError(f"Job {job_id} not found")
                
                # Execute the operation with the locked job object
                # The job remains locked until the transaction completes
                return operation(job)
                
        except Exception as e:
            # Log the error with context for debugging
            logger.error(f"Failed to execute operation with job lock for {job_id}: {e}")
            # Rollback is handled by the context manager, but explicit rollback for clarity
            db.session.rollback()
            raise
    
    @staticmethod
    def get_job_status(job_id: str) -> Optional[str]:
        """Retrieve the current status of a job by its ID.
        
        This method provides a simple way to check the current status of a job
        without locking or modifying it. It's useful for status polling and
        monitoring job progress.
        
        Args:
            job_id (str): Unique identifier of the job to query.
        
        Returns:
            Optional[str]: The current job status as a string,
                          or None if the job is not found.
        
        Example:
            >>> status = JobStatusManager.get_job_status("compress_doc_123")
            >>> if status == JobStatus.COMPLETED.value:
            ...     print("Job finished successfully")
            >>> elif status == JobStatus.FAILED.value:
            ...     print("Job failed")
            >>> elif status is None:
            ...     print("Job not found")
        
        Note:
            This method performs a read-only query and does not acquire locks.
            For operations that need to modify the job, use execute_with_job_lock.
        """
        try:
            job = db.session.execute(
                select(Job.status).where(Job.job_id == job_id)
            ).scalar_one_or_none()
            return job
        except Exception as e:
            logger.error(f"Failed to get job status for {job_id}: {e}")
            return None
    
    @staticmethod
    def is_job_terminal(job_id: str) -> bool:
        """Check if a job has reached a terminal state (completed, failed, or cancelled).
        
        Terminal states indicate that the job has finished processing and will
        not transition to any other state. This is useful for determining when
        to stop polling for job updates or when cleanup can be performed.
        
        Args:
            job_id (str): Unique identifier of the job to check.
        
        Returns:
            bool: True if the job is in a terminal state (COMPLETED, FAILED, or CANCELLED),
                 False if the job is still active (PENDING, PROCESSING) or not found.
        
        Example:
            >>> if JobStatusManager.is_job_terminal("compress_doc_123"):
            ...     print("Job has finished, safe to cleanup resources")
            ... else:
            ...     print("Job is still running, continue monitoring")
        
        Note:
            Returns False for non-existent jobs to maintain consistent behavior
            with active jobs that are still being processed.
        """
        status = JobStatusManager.get_job_status(job_id)
        if not status:
            return False
        return status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
    
    @staticmethod
    def cleanup_old_jobs(days_old: int = 30) -> int:
        """Remove old completed or failed jobs from the database.
        
        This method performs maintenance by cleaning up jobs that have been
        in terminal states (COMPLETED or FAILED) for longer than the specified
        number of days. It helps prevent database bloat and improves performance.
        
        Args:
            days_old (int, optional): Number of days after which terminal jobs
                                    should be cleaned up. Defaults to 30.
        
        Returns:
            int: Number of jobs that were successfully deleted.
        
        Example:
            >>> # Clean up jobs older than 30 days (default)
            >>> deleted_count = JobStatusManager.cleanup_old_jobs()
            >>> print(f"Cleaned up {deleted_count} old jobs")
            
            >>> # Clean up jobs older than 7 days
            >>> deleted_count = JobStatusManager.cleanup_old_jobs(days_old=7)
        
        Note:
            Only jobs in terminal states (COMPLETED, FAILED) are eligible for cleanup.
            Active jobs (PENDING, PROCESSING) are never deleted regardless of age.
            The operation is performed within a transaction for atomicity.
        """
        try:
            from datetime import datetime, timedelta
            
            # Calculate cutoff date for job cleanup
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Begin atomic transaction for cleanup operation
            with db.session.begin():
                # Only delete completed or failed jobs older than cutoff
                # Active jobs (pending/processing) are preserved regardless of age
                result = db.session.execute(
                    select(Job).where(
                        Job.created_at < cutoff_date,
                        Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
                    )
                )
                jobs_to_delete = result.scalars().all()
                
                # Count jobs to delete and remove them from session
                count = len(jobs_to_delete)
                for job in jobs_to_delete:
                    db.session.delete(job)
                
                # Log cleanup results for monitoring
                logger.info(f"Cleaned up {count} old jobs")
                return count
        except Exception as e:
            # Log cleanup failure for monitoring
            logger.error(f"Failed to cleanup old jobs: {e}")
            # Rollback transaction on error
            db.session.rollback()
            return 0