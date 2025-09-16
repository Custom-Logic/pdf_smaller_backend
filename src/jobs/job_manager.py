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
from datetime import datetime, timezone

from flask import Flask

"""JobStatusManager - Pure business logic for job status management.

This class contains only status-related business logic and uses JobOperations
for all database interactions. No session management here!
"""

from typing import Dict, Any, Optional
from src.models.job import Job, JobStatus
from src.jobs import JobOperations  # Our new class
import logging

logger = logging.getLogger(__name__)


class JobStatusManager:
    """Pure business logic for job status management."""
    def __init__(self, job_operations: JobOperations | None = None):
        self.job_operations = job_operations if job_operations else JobOperations()

    def init_app(self, app: Flask, job_operations: JobOperations):
        self.job_operations = job_operations if job_operations else JobOperations()


    def get_or_create_job(self, job_id: str, task_type: str, input_data: Dict[str, Any]) -> Optional[Job]:
        """Get existing job or create new one - pure business logic."""
        # Let JobOperations handle the database work
        job = self.job_operations.get_job(job_id)

        if not job:
            # Job doesn't exist, create it
            job = self.job_operations.create_job(job_id, task_type, input_data)
            if job:
                logger.info(f"Created new job {job_id} with type {task_type}")
            else:
                logger.error(f"Failed to create job {job_id}")
        else:
            logger.debug(f"Retrieved existing job {job_id}")

        return job


    def update_job_status(self, job_id: str, status: JobStatus,
                          result: Dict[str, Any] = None,
                          error_message: str = None,
                          validate_transition: bool = True) -> bool:
        """Atomically update job status - pure business logic."""
        present_status = self.get_job_status(job_id=job_id)
        if validate_transition and not self._is_valid_transition(present_status, status.value):
            logger.error(f"Invalid status transition for job {job_id}: {present_status} -> {status.value}")
            return False

        # Apply status-specific business logic
        updates = {
            'status': status.value,
            'updated_at': datetime.now(timezone.utc)
        }

        if status == JobStatus.COMPLETED and result:
            updates['result'] = result
            updates['error'] = None  # Clear any previous error

        elif status == JobStatus.FAILED and error_message:
            updates['error'] = error_message
            updates['result'] = None  # Clear any previous result

        elif status == JobStatus.PROCESSING:
            updates['error'] = None  # Clear error when retrying
            updates['result'] = None  # Clear previous result

        # Let JobOperations handle the database transaction
        return self.job_operations.update_job(job_id, updates=updates)

    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Validate job status transitions - pure business logic."""
        valid_transitions = {
            JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
            JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
            JobStatus.COMPLETED.value: [],  # Terminal state
            JobStatus.FAILED.value: [JobStatus.PROCESSING.value]  # Allow retry
        }

        return new_status in valid_transitions.get(current_status, [])

    def get_job_status(self, job_id: str) -> Optional[str]:
        """Get job status - pure business logic."""
        job = self.job_operations.get_job(job_id)
        return job.status if job else None


    def is_job_terminal(self, job_id: str) -> bool:
        """Check if job is in terminal state - pure business logic."""
        status = self.get_job_status(job_id)
        if not status:
            return False
        return status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]

    @staticmethod
    def retry_failed_job(job_id: str) -> bool:
        """Retry a failed job - pure business logic."""

        def retry_operation(job: Job, session) -> bool:
            if job.status != JobStatus.FAILED.value:
                logger.error(f"Cannot retry job {job_id} with status {job.status}")
                return False

            # Business logic for retry
            job.status = JobStatus.PENDING.value
            job.updated_at = datetime.now(timezone.utc)
            # Keep error for reference but mark for retry
            job.retry_count = (job.retry_count or 0) + 1

            logger.info(f"Retrying job {job_id} (attempt {job.retry_count})")
            return True

    @staticmethod
    def cancel_job(job_id: str) -> bool:
        """Cancel a job - pure business logic."""

        def cancel_operation(job: Job, session) -> bool:
            if job.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
                logger.warning(f"Cannot cancel job {job_id} in terminal state {job.status}")
                return False

            # Business logic for cancellation
            job.status = JobStatus.FAILED.value
            job.error = "Job cancelled by user"
            job.updated_at = datetime.now(timezone.utc)

            logger.info(f"Cancelled job {job_id}")
            return True
