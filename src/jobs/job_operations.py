"""JobOperations - Centralized database session management for job operations.

Refactored for SQLite (on-disk).
SQLite has no row-level locking or `with_for_update`, so all locking logic
has been adapted/removed. Concurrency is handled via transaction retries
and SQLite’s database-level locks.
"""

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

from flask import Flask
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from src.models import Job, JobStatus
from src.models.base import db

logger = logging.getLogger(__name__)


class JobOperations:
    """Centralized database session management for job operations (SQLite)."""

    def __init__(self):
        pass

    def init_app(self, app: Flask):
        pass

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


    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID (simplified)."""
        with self.session_scope(auto_commit=False) as session:
            return session.query(Job).filter_by(job_id=job_id).first()
        return None

    def create_job(self, job_id: str, task_type: str, input_data: Dict[str, Any]) -> Optional[Job]:
        """Create a new job; prevent duplicates by checking first."""
        with self.session_scope() as session:
            existing_job = session.query(Job).filter_by(job_id=job_id).first()
            if isinstance(existing_job, Job):
                return existing_job

            job = Job(
                job_id=job_id,
                task_type=task_type,
                input_data=input_data
            )
            session.add(job)
            return job
        return None

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> bool:
        """Update job fields directly (no row-level lock)."""

        with self.session_scope() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not isinstance(job, Job):
                return False

            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)

            job.updated_at = datetime.now(timezone.utc)
            return job
        return None


    def bulk_update_jobs(self, job_updates: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Update multiple jobs in a single transaction."""
        results: Dict[str, bool] = {}
        with self.session_scope() as session:
            for update_info in job_updates:
                job_id = update_info.get('job_id')
                if not job_id:
                    results[job_id] = False
                    continue

                try:
                    job = session.query(Job).filter_by(job_id=job_id).first()
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
        return None


    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID."""
        with self.session_scope() as session:
            job = session.query(Job).filter_by(job_id=job_id).first()
            if not isinstance(job, Job):
                return False

            session.delete(job)
            return True
        return None

    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """Delete jobs older than `days_old` with completed/failed status."""

        with self.session_scope() as session:
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
        return None

    def get_jobs_by_status(self, status: JobStatus, limit: int = 100) -> List[Job]:
        """Get jobs by status."""

        with self.session_scope(auto_commit=False) as session:
            results = session.query(Job).filter_by(status=status.value).limit(limit).order_by(Job.created_at.desc()).all()
            return results
        return []


