from typing import Dict, Any, Optional, Callable
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from src.models.job import Job, JobStatus
from src.models.base import db
import logging

logger = logging.getLogger(__name__)

class JobStatusManager:
    """Thread-safe job management with proper locking and transactions"""
    
    @staticmethod
    def get_or_create_job(job_id: str, task_type: str, input_data: Dict[str, Any]) -> Job:
        """Get existing job or create new one with proper locking"""
        try:
            with db.session.begin():  # Explicit transaction
                # Use SELECT FOR UPDATE to prevent race conditions
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    job = Job(
                        job_id=job_id,
                        task_type=task_type,
                        input_data=input_data
                    )
                    db.session.add(job)
                    db.session.flush()  # Ensure ID is assigned
                    logger.info(f"Created new job {job_id} with type {task_type}")
                
                return job
        except Exception as e:
            logger.error(f"Failed to get or create job {job_id}: {e}")
            db.session.rollback()
            raise
    
    @staticmethod
    def update_job_status(job_id: str, status: JobStatus, 
                         result: Dict[str, Any] = None, 
                         error_message: str = None,
                         validate_transition: bool = True) -> bool:
        """Atomically update job status with validation"""
        try:
            with db.session.begin():
                # Lock the job row for update
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    logger.error(f"Job {job_id} not found for status update")
                    return False
                
                # Validate status transition if requested
                if validate_transition and not JobStatusManager._is_valid_transition(job.status, status.value):
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
                    job.status = status.value
                
                logger.info(f"Updated job {job_id} status to {status.value}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Validate job status transitions"""
        valid_transitions = {
            JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
            JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
            JobStatus.COMPLETED.value: [],  # Terminal state
            JobStatus.FAILED.value: [JobStatus.PROCESSING.value]  # Allow retry
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    @staticmethod
    def execute_with_job_lock(job_id: str, operation: Callable[[Job], Any]) -> Any:
        """Execute operation with job locked for update"""
        try:
            with db.session.begin():
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    raise ValueError(f"Job {job_id} not found")
                
                return operation(job)
        except Exception as e:
            logger.error(f"Failed to execute operation with job lock for {job_id}: {e}")
            db.session.rollback()
            raise
    
    @staticmethod
    def get_job_status(job_id: str) -> Optional[str]:
        """Get current job status safely"""
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
        """Check if job is in terminal state (completed or failed)"""
        status = JobStatusManager.get_job_status(job_id)
        if not status:
            return False
        return status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
    
    @staticmethod
    def cleanup_old_jobs(days_old: int = 30) -> int:
        """Clean up jobs older than specified days"""
        try:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            with db.session.begin():
                # Only delete completed or failed jobs
                result = db.session.execute(
                    select(Job).where(
                        Job.created_at < cutoff_date,
                        Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
                    )
                )
                jobs_to_delete = result.scalars().all()
                
                count = len(jobs_to_delete)
                for job in jobs_to_delete:
                    db.session.delete(job)
                
                logger.info(f"Cleaned up {count} old jobs")
                return count
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {e}")
            db.session.rollback()
            return 0