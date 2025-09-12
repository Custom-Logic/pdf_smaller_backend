"""Comprehensive test suite for database transaction fixes.

Tests the JobStatusManager, database constraints, and transaction handling
to ensure data integrity and consistency.
"""

import pytest
import threading
import time
from unittest.mock import patch, Mock
from sqlalchemy.exc import IntegrityError, OperationalError
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.models.job import Job, JobStatus, TaskType
from src.utils.job_manager import JobStatusManager
from src.models.base import db


class TestJobStatusManager:
    """Test JobStatusManager functionality for consistent database operations."""
    
    def test_get_or_create_job_new(self, app, db_session):
        """Test creating a new job through JobStatusManager."""
        with app.app_context():
            job_id = "test-job-123"
            task_type = TaskType.COMPRESS.value
            input_data = {"file_size": 1024, "compression_level": 5}
            
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=task_type,
                input_data=input_data
            )
            
            assert job is not None
            assert job.job_id == job_id
            assert job.task_type == task_type
            assert job.status == JobStatus.PENDING.value
            assert job.input_data == input_data
    
    def test_get_or_create_job_existing(self, app, db_session):
        """Test retrieving an existing job through JobStatusManager."""
        with app.app_context():
            job_id = "existing-job-456"
            
            # Create initial job
            original_job = Job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={"original": True}
            )
            db_session.add(original_job)
            db_session.commit()
            
            # Try to get or create the same job
            retrieved_job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.CONVERT.value,  # Different task type
                input_data={"new": True}  # Different input data
            )
            
            # Should return existing job, not create new one
            assert retrieved_job.job_id == job_id
            assert retrieved_job.task_type == TaskType.COMPRESS.value  # Original type
            assert retrieved_job.input_data == {"original": True}  # Original data
    
    def test_update_job_status_valid_transitions(self, app, db_session):
        """Test valid job status transitions through JobStatusManager."""
        with app.app_context():
            job_id = "transition-test-789"
            
            # Create job
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={}
            )
            
            # Test valid transitions
            assert JobStatusManager.update_job_status(job_id, JobStatus.PROCESSING)
            updated_job = Job.query.filter_by(job_id=job_id).first()
            assert updated_job.status == JobStatus.PROCESSING.value
            
            assert JobStatusManager.update_job_status(
                job_id, JobStatus.COMPLETED, result={"output_file": "test.pdf"}
            )
            updated_job = Job.query.filter_by(job_id=job_id).first()
            assert updated_job.status == JobStatus.COMPLETED.value
            assert updated_job.result == {"output_file": "test.pdf"}
    
    def test_update_job_status_invalid_transitions(self, app, db_session):
        """Test invalid job status transitions are rejected."""
        with app.app_context():
            job_id = "invalid-transition-test"
            
            # Create completed job
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={}
            )
            JobStatusManager.update_job_status(job_id, JobStatus.COMPLETED)
            
            # Try invalid transition from COMPLETED to PROCESSING
            result = JobStatusManager.update_job_status(
                job_id, JobStatus.PROCESSING, validate_transition=True
            )
            
            assert result is False
            updated_job = Job.query.filter_by(job_id=job_id).first()
            assert updated_job.status == JobStatus.COMPLETED.value  # Unchanged
    
    def test_update_job_status_with_error(self, app, db_session):
        """Test updating job status with error message."""
        with app.app_context():
            job_id = "error-test-job"
            
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={}
            )
            
            error_message = "File processing failed due to corruption"
            assert JobStatusManager.update_job_status(
                job_id, JobStatus.FAILED, error_message=error_message
            )
            
            updated_job = Job.query.filter_by(job_id=job_id).first()
            assert updated_job.status == JobStatus.FAILED.value
            assert updated_job.error == error_message
    
    def test_update_nonexistent_job(self, app, db_session):
        """Test updating status of non-existent job returns False."""
        with app.app_context():
            result = JobStatusManager.update_job_status(
                "nonexistent-job", JobStatus.PROCESSING
            )
            assert result is False


class TestDatabaseConstraints:
    """Test database constraints and data integrity."""
    
    def test_job_status_constraint(self, app, db_session):
        """Test that invalid job status values are rejected."""
        with app.app_context():
            job = Job(
                job_id="constraint-test-1",
                task_type=TaskType.COMPRESS.value,
                status="invalid_status"  # Invalid status
            )
            
            db_session.add(job)
            
            with pytest.raises(IntegrityError):
                db_session.commit()
    
    def test_timestamp_constraint(self, app, db_session):
        """Test that created_at <= updated_at constraint is enforced."""
        with app.app_context():
            from datetime import datetime, timezone, timedelta
            
            # Create job with updated_at before created_at (invalid)
            now = datetime.now(timezone.utc)
            job = Job(
                job_id="timestamp-test-1",
                task_type=TaskType.COMPRESS.value
            )
            job.created_at = now
            job.updated_at = now - timedelta(hours=1)  # Invalid: updated before created
            
            db_session.add(job)
            
            with pytest.raises(IntegrityError):
                db_session.commit()
    
    def test_job_id_uniqueness(self, app, db_session):
        """Test that job_id uniqueness constraint is enforced."""
        with app.app_context():
            job_id = "duplicate-test-job"
            
            # Create first job
            job1 = Job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value
            )
            db_session.add(job1)
            db_session.commit()
            
            # Try to create second job with same ID
            job2 = Job(
                job_id=job_id,
                task_type=TaskType.CONVERT.value
            )
            db_session.add(job2)
            
            with pytest.raises(IntegrityError):
                db_session.commit()


class TestConcurrencyAndRaceConditions:
    """Test concurrent access and race condition handling."""
    
    def test_concurrent_job_creation(self, app, db_session):
        """Test that concurrent job creation doesn't create duplicates."""
        with app.app_context():
            job_id = "concurrent-test-job"
            results = []
            
            def create_job():
                try:
                    job = JobStatusManager.get_or_create_job(
                        job_id=job_id,
                        task_type=TaskType.COMPRESS.value,
                        input_data={"thread": threading.current_thread().name}
                    )
                    return job.job_id
                except Exception as e:
                    return str(e)
            
            # Run multiple threads trying to create the same job
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_job) for _ in range(5)]
                results = [future.result() for future in as_completed(futures)]
            
            # All should return the same job_id (no duplicates created)
            assert all(result == job_id for result in results)
            
            # Verify only one job exists in database
            jobs = Job.query.filter_by(job_id=job_id).all()
            assert len(jobs) == 1
    
    def test_concurrent_status_updates(self, app, db_session):
        """Test concurrent status updates don't cause inconsistencies."""
        with app.app_context():
            job_id = "concurrent-status-test"
            
            # Create initial job
            JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={}
            )
            
            results = []
            
            def update_status(status):
                try:
                    return JobStatusManager.update_job_status(job_id, status)
                except Exception as e:
                    return str(e)
            
            # Run concurrent status updates
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [
                    executor.submit(update_status, JobStatus.PROCESSING),
                    executor.submit(update_status, JobStatus.COMPLETED),
                    executor.submit(update_status, JobStatus.FAILED)
                ]
                results = [future.result() for future in as_completed(futures)]
            
            # At least one update should succeed
            assert any(result is True for result in results)
            
            # Job should be in a valid final state
            final_job = Job.query.filter_by(job_id=job_id).first()
            assert final_job.status in [s.value for s in JobStatus]


class TestTransactionHandling:
    """Test transaction handling and rollback scenarios."""
    
    @patch('src.utils.job_manager.db.session.commit')
    def test_transaction_rollback_on_commit_failure(self, mock_commit, app, db_session):
        """Test that transactions are properly rolled back on commit failure."""
        with app.app_context():
            # Mock commit to raise an exception
            mock_commit.side_effect = OperationalError("Database error", None, None)
            
            job_id = "rollback-test-job"
            
            # This should handle the commit failure gracefully
            result = JobStatusManager.update_job_status(
                job_id, JobStatus.PROCESSING
            )
            
            # Should return False due to commit failure
            assert result is False
    
    def test_job_status_validation_methods(self, app, db_session):
        """Test job status validation methods work correctly."""
        with app.app_context():
            job = Job(
                job_id="validation-test-job",
                task_type=TaskType.COMPRESS.value,
                status=JobStatus.PENDING.value
            )
            
            # Test transition validation
            assert job.can_transition_to(JobStatus.PROCESSING)
            assert job.can_transition_to(JobStatus.FAILED)
            assert not job.can_transition_to(JobStatus.COMPLETED)  # Invalid from PENDING
            
            # Test terminal state detection
            assert not job.is_terminal()
            
            job.status = JobStatus.COMPLETED.value
            assert job.is_terminal()
            assert not job.can_transition_to(JobStatus.PROCESSING)  # Can't transition from terminal
    
    def test_job_model_methods_consistency(self, app, db_session):
        """Test that job model methods maintain consistency."""
        with app.app_context():
            job = Job(
                job_id="consistency-test-job",
                task_type=TaskType.COMPRESS.value
            )
            db_session.add(job)
            db_session.commit()
            
            original_updated_at = job.updated_at
            
            # Test mark_as_processing updates timestamp
            time.sleep(0.01)  # Ensure timestamp difference
            job.mark_as_processing()
            assert job.status == JobStatus.PROCESSING.value
            assert job.updated_at > original_updated_at
            
            # Test mark_as_completed with result
            result_data = {"output_file": "compressed.pdf", "size_reduction": 0.3}
            job.mark_as_completed(result_data)
            assert job.status == JobStatus.COMPLETED.value
            assert job.result == result_data
            assert job.is_successful()
            assert job.is_completed()
            
            # Test mark_as_failed with error
            job.status = JobStatus.PROCESSING.value  # Reset for test
            error_msg = "Compression failed due to invalid PDF structure"
            job.mark_as_failed(error_msg)
            assert job.status == JobStatus.FAILED.value
            assert job.error == error_msg
            assert not job.is_successful()
            assert job.is_completed()


class TestJobManagerIntegration:
    """Integration tests for JobStatusManager with other components."""
    
    def test_job_manager_with_celery_task_simulation(self, app, db_session):
        """Test JobStatusManager integration with simulated Celery task workflow."""
        with app.app_context():
            job_id = "celery-integration-test"
            
            # Simulate task creation
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={
                    "file_size": 2048,
                    "compression_level": 7,
                    "original_filename": "test.pdf"
                }
            )
            
            assert job.status == JobStatus.PENDING.value
            
            # Simulate task starting
            assert JobStatusManager.update_job_status(job_id, JobStatus.PROCESSING)
            
            # Simulate task completion
            result = {
                "output_file": "compressed_test.pdf",
                "original_size": 2048,
                "compressed_size": 1024,
                "compression_ratio": 0.5
            }
            
            assert JobStatusManager.update_job_status(
                job_id, JobStatus.COMPLETED, result=result
            )
            
            # Verify final state
            final_job = Job.query.filter_by(job_id=job_id).first()
            assert final_job.status == JobStatus.COMPLETED.value
            assert final_job.result == result
            assert final_job.is_successful()
    
    def test_job_manager_error_recovery(self, app, db_session):
        """Test JobStatusManager handles errors and allows recovery."""
        with app.app_context():
            job_id = "error-recovery-test"
            
            # Create and fail a job
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type=TaskType.COMPRESS.value,
                input_data={}
            )
            
            JobStatusManager.update_job_status(job_id, JobStatus.PROCESSING)
            JobStatusManager.update_job_status(
                job_id, JobStatus.FAILED, 
                error_message="Temporary processing error"
            )
            
            # Verify failed state
            failed_job = Job.query.filter_by(job_id=job_id).first()
            assert failed_job.status == JobStatus.FAILED.value
            
            # Test recovery (retry)
            assert JobStatusManager.update_job_status(job_id, JobStatus.PROCESSING)
            assert JobStatusManager.update_job_status(
                job_id, JobStatus.COMPLETED,
                result={"retry_successful": True}
            )
            
            # Verify recovery
            recovered_job = Job.query.filter_by(job_id=job_id).first()
            assert recovered_job.status == JobStatus.COMPLETED.value
            assert recovered_job.is_successful()