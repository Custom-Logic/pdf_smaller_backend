"""JobOperations - Centralized database session management for job operations.

This class handles all database session management, transactions, and locking.
JobStatusManager and other components should use this class for all database operations.
"""

import logging
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session, joinedload

from src.models.job import Job, JobStatus
from src.models.base import db
from src.utils.db_transaction import db_transaction, safe_db_operation

logger = logging.getLogger(__name__)


class JobOperations:
    """Centralized database session management for job operations."""

    @staticmethod
    @contextmanager
    def session_scope(auto_commit: bool = True):
        """Provide a transactional scope around a series of operations."""
        session = db.session
        try:
            yield session
            if auto_commit:
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session operation failed: {e}")
            raise
        finally:
            session.close()

    @staticmethod
    def execute_with_lock(job_id: str, operation: Callable[[Job, Session], Any]) -> Any:
        """Execute operation with job-level locking and automatic session management."""
        def locked_operation():
            with JobOperations.session_scope() as session:
                # Get job with row lock
                job = session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()

                if not job:
                    raise ValueError(f"Job {job_id} not found")

                return operation(job, session)

        return safe_db_operation(
            locked_operation,
            f"execute_with_lock_{job_id}",
            max_retries=2,
            default_return=None
        )

    @staticmethod
    def get_job(job_id: str, lock: bool = False) -> Optional[Job]:
        """Get job by ID with optional locking."""
        def get_operation():
            with JobOperations.session_scope(auto_commit=False) as session:
                query = select(Job).where(Job.job_id == job_id)
                if lock:
                    query = query.with_for_update()
                return session.execute(query).scalar_one_or_none()

        return safe_db_operation(
            get_operation,
            f"get_job_{job_id}",
            max_retries=1,
            default_return=None
        )

    @staticmethod
    def create_job(job_id: str, task_type: str, input_data: Dict[str, Any]) -> Optional[Job]:
        """Create a new job with proper locking to prevent duplicates."""
        def create_operation():
            with JobOperations.session_scope() as session:
                # Check if job already exists with lock
                existing_job = session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()

                if existing_job:
                    return existing_job

                # Create new job
                job = Job(
                    job_id=job_id,
                    task_type=task_type,
                    input_data=input_data or {},
                    status=JobStatus.PENDING.value,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(job)
                session.flush()
                return job

        return safe_db_operation(
            create_operation,
            f"create_job_{job_id}",
            max_retries=2,
            default_return=None
        )

    @staticmethod
    def update_job(job_id: str, updates: Dict[str, Any]) -> bool:
        """Update job fields directly."""
        def update_operation():
            with JobOperations.session_scope() as session:
                job = session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()

                if not job:
                    return False

                for key, value in updates.items():
                    if hasattr(job, key):
                        setattr(job, key, value)

                job.updated_at = datetime.now(timezone.utc)
                return True

        return safe_db_operation(
            update_operation,
            f"update_job_{job_id}",
            max_retries=2,
            default_return=False
        )

    @staticmethod
    def bulk_update_jobs(job_updates: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Update multiple jobs in a single transaction."""
        results = {}

        def bulk_operation():
            with JobOperations.session_scope() as session:
                for update_info in job_updates:
                    job_id = update_info.get('job_id')
                    if not job_id:
                        results[job_id] = False
                        continue

                    try:
                        job = session.execute(
                            select(Job).where(Job.job_id == job_id).with_for_update()
                        ).scalar_one_or_none()

                        if not job:
                            results[job_id] = False
                            continue

                        # Apply updates
                        for key, value in update_info.items():
                            if key != 'job_id' and hasattr(job, key):
                                setattr(job, key, value)

                        job.updated_at = datetime.now(timezone.utc)
                        results[job_id] = True

                    except Exception as e:
                        logger.error(f"Failed to update job {job_id}: {e}")
                        results[job_id] = False

                return results

        return safe_db_operation(
            bulk_operation,
            "bulk_update_jobs",
            max_retries=1,
            default_return=results
        )

    @staticmethod
    def delete_job(job_id: str) -> bool:
        """Delete a job by ID."""
        def delete_operation():
            with JobOperations.session_scope() as session:
                job = session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()

                if not job:
                    return False

                session.delete(job)
                return True

        return safe_db_operation(
            delete_operation,
            f"delete_job_{job_id}",
            max_retries=1,
            default_return=False
        )

    @staticmethod
    def cleanup_old_jobs(days_old: int = 30) -> int:
        """Clean up old completed/failed jobs."""
        def cleanup_operation():
            with JobOperations.session_scope() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)

                # Delete old completed/failed jobs
                result = session.execute(
                    delete(Job).where(
                        Job.created_at < cutoff_date,
                        Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
                    )
                )

                deleted_count = result.rowcount
                logger.info(f"Cleaned up {deleted_count} jobs older than {days_old} days")
                return deleted_count

        return safe_db_operation(
            cleanup_operation,
            "cleanup_old_jobs",
            max_retries=1,
            default_return=0
        )

    @staticmethod
    def get_jobs_by_status(status: JobStatus, limit: int = 100) -> List[Job]:
        """Get jobs by status."""
        def query_operation():
            with JobOperations.session_scope(auto_commit=False) as session:
                result = session.execute(
                    select(Job)
                    .where(Job.status == status.value)
                    .limit(limit)
                    .order_by(Job.created_at.desc())
                )
                return result.scalars().all()

        return safe_db_operation(
            query_operation,
            f"get_jobs_by_status_{status.value}",
            max_retries=1,
            default_return=[]
        )