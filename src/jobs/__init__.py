"""Enhanced job operations using the new session-managed architecture.

This now becomes a thin wrapper around JobOperations and JobStatusManager.
"""
import logging
from typing import Dict, Any, Optional, List
from src.jobs.job_operations import JobOperations
from src.jobs.job_manager import JobStatusManager
from src.models.job import Job, JobStatus
logger = logging.getLogger(__name__)
# For backward compatibility, you can keep the old interface
class JobOperationsWrapper:
    """Wrapper for backward compatibility with enhanced job operations."""

    @staticmethod
    def create_job_safely(job_id: str, task_type: str,
                         input_data: Dict[str, Any] = None) -> Optional[Job]:
        """Create a new job safely using the new architecture.

        Args:
            job_id: Unique identifier for the job
            task_type: Type of task (e.g., 'extract_text', 'compress', 'convert')
            input_data: Input parameters for the job

        Returns:
            Created Job instance or None if creation failed

        Example:
            >>> job = JobOperationsWrapper.create_job_safely(
            ...     job_id="extract_123",
            ...     task_type='extract_text',
            ...     input_data={'file_size': 1024, 'original_filename': 'document.pdf'}
            ... )
        """
        try:
            # Use JobOperations for session-managed job creation
            job = JobOperations.create_job(job_id=job_id, task_type=task_type, input_data=input_data)

            if job:
                logger.info(f"Successfully created job {job_id} with type {task_type}")
            else:
                logger.error(f"Failed to create job {job_id} - possible duplicate")

            return job

        except Exception as e:
            logger.error(f"Error creating job {job_id}: {e}")
            return None

    @staticmethod
    def update_job_status_safely(job_id: str, status: JobStatus,
                               result: Dict[str, Any] = None,
                               error_message: str = None,
                               progress: Optional[float] = None) -> bool:
        """Update job status using the new architecture.

        Args:
            job_id: Unique identifier of the job
            status: New status to set
            result: Optional result data
            error_message: Optional error message
            progress: Optional progress percentage (0-100)

        Returns:
            True if update was successful, False otherwise
        """
        success = JobStatusManager.update_job_status(
            job_id=job_id,
            status=status,
            result=result,
            error_message=error_message
        )

        # Update progress if needed (separate operation since it's not part of core status logic)
        if success and progress is not None:
            JobOperations.update_job(job_id, {'progress': progress})

        return success

    @staticmethod
    def get_job_with_progress(job_id: str) -> Optional[Dict[str, Any]]:
        """Get job with progress information.

        Args:
            job_id: Unique identifier of the job

        Returns:
            Dictionary with job information including progress, or None if not found
        """
        job: Job = JobOperations.get_job(job_id=job_id,lock=True)
        if not job:
            return None

        return {
            'job_id': job.job_id,
            'status': job.status,
            'progress': getattr(job, 'progress', None),
            'task_type': job.task_type,
            'created_at': job.created_at,
            'updated_at': job.updated_at
        }

    @staticmethod
    def batch_create_jobs(jobs_data: List[Dict[str, Any]]) -> Dict[str, Optional[Job]]:
        """Batch create multiple jobs.

        Args:
            jobs_data: List of dictionaries with job creation data.
                     Each dict should contain 'job_id', 'task_type', and 'input_data'

        Returns:
            Dictionary mapping job_id to created Job instance or None if failed

        Example:
            >>> jobs_to_create = [
            ...     {
            ...         'job_id': 'extract_1',
            ...         'task_type': 'extract_text',
            ...         'input_data': {'file_size': 1024, 'filename': 'doc1.pdf'}
            ...     },
            ...     {
            ...         'job_id': 'extract_2',
            ...         'task_type': 'extract_text',
            ...         'input_data': {'file_size': 2048, 'filename': 'doc2.pdf'}
            ...     }
            ... ]
            >>> results = JobOperationsWrapper.batch_create_jobs(jobs_to_create)
        """
        results = {}

        for job_data in jobs_data:
            job_id = job_data.get('job_id')
            task_type = job_data.get('task_type')
            input_data = job_data.get('input_data', {})

            if not job_id or not task_type:
                results[job_id] = None
                continue

            job = JobOperationsWrapper.create_job_safely(job_id, task_type, input_data)
            results[job_id] = job

        return results

    @staticmethod
    def ensure_job_exists(job_id: str, task_type: str,
                         input_data: Dict[str, Any] = None) -> Optional[Job]:
        """Ensure a job exists, creating it if necessary.

        This is a convenience method that combines get and create operations.

        Args:
            job_id: Unique identifier for the job
            task_type: Type of task
            input_data: Input parameters for the job

        Returns:
            Existing or newly created Job instance, or None if failed
        """
        # Try to get existing job first
        job = JobOperations.get_job(job_id)

        if job:
            return job

        # Job doesn't exist, create it
        return JobOperationsWrapper.create_job_safely(job_id, task_type, input_data)

# For even simpler backward compatibility, you can add module-level functions
def create_job_safely(job_id: str, task_type: str,
                     input_data: Dict[str, Any] = None) -> Optional[Job]:
    """Module-level function for backward compatibility."""
    return JobOperationsWrapper.create_job_safely(job_id, task_type, input_data)

def update_job_status_safely(job_id: str, status: JobStatus,
                           result: Dict[str, Any] = None,
                           error_message: str = None,
                           progress: Optional[float] = None) -> bool:
    """Module-level function for backward compatibility."""
    return JobOperationsWrapper.update_job_status_safely(
        job_id, status, result, error_message, progress
    )