"""JobOperations - Centralized database session management for job operations.

Refactored for SQLite (on-disk).
SQLite has no row-level locking or `with_for_update`, so all locking logic
has been adapted/removed. Concurrency is handled via transaction retries
and SQLite’s database-level locks.
"""

import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from src.models import Job, JobStatus
from src.models.base import db
from src.utils.db_transaction import safe_db_operation

logger = logging.getLogger(__name__)


class JobOperations:
    """Centralized database session management for job operations (SQLite)."""

    @staticmethod
    @contextmanager
    def session_scope(auto_commit: bool = True):
        """Provide a transactional scope around a series of operations."""
        session: Session = db.session
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
        """
        Execute operation on a job.
        NOTE: SQLite does not support row-level locking; we rely on transaction isolation
        and retries if the database is locked.
        """
        def wrapped_operation():
            with JobOperations.session_scope() as session:
                job = session.query(Job).filter_by(job_id=job_id).first()
                if not isinstance(job, Job):
                    raise ValueError(f"Job {job_id} not found")
                return operation(job, session)

        return safe_db_operation(
            wrapped_operation,
            f"execute_with_lock_{job_id}",
            max_retries=2,
            default_return=None
        )

    @staticmethod
    def get_job(job_id: str) -> Optional[Job]:
        """Get job by ID (simplified)."""

        def get_operation():
            with JobOperations.session_scope(auto_commit=False) as session:
                return session.query(Job).filter_by(job_id=job_id).first()

        return safe_db_operation(
            get_operation,
            f"get_job_{job_id}",
            max_retries=1,
            default_return=None
        )

    @staticmethod
    def create_job(job_id: str, task_type: str, input_data: Dict[str, Any]) -> Optional[Job]:
        """Create a new job; prevent duplicates by checking first."""
        def create_operation():
            with JobOperations.session_scope() as session:
                existing_job = session.query(Job).filter_by(job_id=job_id).first()
                if isinstance(existing_job, Job):
                    return existing_job

                job = Job(
                    job_id=job_id,
                    task_type=task_type,
                    input_data=input_data
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
        """Update job fields directly (no row-level lock)."""
        def update_operation():
            with JobOperations.session_scope() as session:
                job = session.query(Job).filter_by(job_id=job_id).first()

                if not isinstance(job, Job):
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
        results: Dict[str, bool] = {}

        def bulk_operation():
            with JobOperations.session_scope() as session:
                for update_info in job_updates:
                    job_id = update_info.get('job_id')
                    if not job_id:
                        results[job_id] = False
                        continue

                    try:
                        job = session.execute(
                            select(Job).where(Job.job_id == job_id)
                        ).scalar_one_or_none()

                        if not isinstance(job, Job):
                            results[job_id] = False
                            continue

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
                job = session.query(Job).filter_by(job_id=job_id).first()
                if not isinstance(job, Job):
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
        """Delete jobs older than `days_old` with completed/failed status."""
        def cleanup_operation():
            with JobOperations.session_scope() as session:
                cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
                result = session.execute(
                    delete(Job).where(
                        Job.created_at < cutoff_date,
                        Job.status.in_([JobStatus.COMPLETED.value, JobStatus.FAILED.value])
                    )
                )
                deleted_count = result.rowcount or 0
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
