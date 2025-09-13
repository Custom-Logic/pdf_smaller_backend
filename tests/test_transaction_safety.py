"""Comprehensive test suite for transaction safety utilities.

Tests the safe_db_operation function, @transactional decorator, and other
transaction management utilities to ensure proper error handling, rollback,
and retry mechanisms.
"""

import pytest
import time
from unittest.mock import patch, Mock, MagicMock
from sqlalchemy.exc import (
    IntegrityError, 
    OperationalError, 
    DatabaseError,
    DisconnectionError,
    TimeoutError as SQLTimeoutError
)
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from src.utils.db_transaction import (
    safe_db_operation,
    transactional,
    db_transaction,
    TransactionError
)
from src.models.job import Job, JobStatus, TaskType
from src.models.base import db


class TestSafeDbOperation:
    """Test safe_db_operation function for robust database operations."""
    
    def test_safe_db_operation_success(self, app, db_session):
        """Test successful database operation with safe_db_operation."""
        with app.app_context():
            def create_job():
                job = Job(
                    job_id="safe-op-success-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            result = safe_db_operation(create_job, "test operation")
            
            assert result is not None
            assert result.job_id == "safe-op-success-test"
            
            # Verify job was committed to database
            saved_job = Job.query.filter_by(job_id="safe-op-success-test").first()
            assert saved_job is not None
    
    def test_safe_db_operation_with_integrity_error(self, app, db_session):
        """Test safe_db_operation handles IntegrityError with rollback."""
        with app.app_context():
            # Create initial job
            initial_job = Job(
                job_id="duplicate-test",
                task_type=TaskType.COMPRESS.value
            )
            db.session.add(initial_job)
            db.session.commit()
            
            def create_duplicate_job():
                # This should cause IntegrityError due to duplicate job_id
                duplicate_job = Job(
                    job_id="duplicate-test",
                    task_type=TaskType.CONVERT.value
                )
                db.session.add(duplicate_job)
                return duplicate_job
            
            result = safe_db_operation(create_duplicate_job, "duplicate creation")
            
            # Should return None due to error
            assert result is None
            
            # Verify only original job exists
            jobs = Job.query.filter_by(job_id="duplicate-test").all()
            assert len(jobs) == 1
            assert jobs[0].task_type == TaskType.COMPRESS.value
    
    @patch('src.utils.db_transaction.db.session.commit')
    def test_safe_db_operation_with_retry(self, mock_commit, app, db_session):
        """Test safe_db_operation retry mechanism on transient errors."""
        with app.app_context():
            # Mock commit to fail twice, then succeed
            mock_commit.side_effect = [
                OperationalError("Connection lost", None, None),
                OperationalError("Temporary lock", None, None),
                None  # Success on third try
            ]
            
            def create_job():
                job = Job(
                    job_id="retry-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            result = safe_db_operation(create_job, "retry test", max_retries=3)
            
            # Should succeed after retries
            assert result is not None
            assert mock_commit.call_count == 3
    
    @patch('src.utils.db_transaction.db.session.commit')
    def test_safe_db_operation_max_retries_exceeded(self, mock_commit, app, db_session):
        """Test safe_db_operation fails after max retries exceeded."""
        with app.app_context():
            # Mock commit to always fail
            mock_commit.side_effect = OperationalError("Persistent error", None, None)
            
            def create_job():
                job = Job(
                    job_id="max-retry-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            result = safe_db_operation(create_job, "max retry test", max_retries=2)
            
            # Should return None after max retries
            assert result is None
            assert mock_commit.call_count == 2
    
    def test_safe_db_operation_with_custom_exception_handler(self, app, db_session):
        """Test safe_db_operation with custom exception handling."""
        with app.app_context():
            custom_handler_called = False
            
            def custom_handler(e, attempt, operation_name):
                nonlocal custom_handler_called
                custom_handler_called = True
                return False  # Don't retry
            
            def failing_operation():
                raise ValueError("Custom error")
            
            result = safe_db_operation(
                failing_operation, 
                "custom handler test",
                exception_handler=custom_handler
            )
            
            assert result is None
            assert custom_handler_called


class TestTransactionalDecorator:
    """Test @transactional decorator for automatic transaction management."""
    
    def test_transactional_decorator_success(self, app, db_session):
        """Test @transactional decorator commits successful operations."""
        with app.app_context():
            @transactional("test_function")
            def create_job_with_decorator():
                job = Job(
                    job_id="decorator-success-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            result = create_job_with_decorator()
            
            assert result is not None
            
            # Verify job was committed
            saved_job = Job.query.filter_by(job_id="decorator-success-test").first()
            assert saved_job is not None
    
    def test_transactional_decorator_rollback_on_exception(self, app, db_session):
        """Test @transactional decorator rolls back on exceptions."""
        with app.app_context():
            @transactional("test_function_with_error")
            def create_job_then_fail():
                job = Job(
                    job_id="decorator-rollback-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                # Force an error after adding to session
                raise ValueError("Intentional error")
            
            with pytest.raises(ValueError):
                create_job_then_fail()
            
            # Verify job was not committed due to rollback
            saved_job = Job.query.filter_by(job_id="decorator-rollback-test").first()
            assert saved_job is None
    
    @patch('src.utils.db_transaction.db.session.commit')
    def test_transactional_decorator_with_retry(self, mock_commit, app, db_session):
        """Test @transactional decorator retry mechanism."""
        with app.app_context():
            # Mock commit to fail once, then succeed
            mock_commit.side_effect = [
                OperationalError("Temporary error", None, None),
                None  # Success on second try
            ]
            
            @transactional("test_retry_function", max_retries=2)
            def create_job_with_retry():
                job = Job(
                    job_id="decorator-retry-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            result = create_job_with_retry()
            
            assert result is not None
            assert mock_commit.call_count == 2
    
    def test_transactional_decorator_preserves_return_value(self, app, db_session):
        """Test @transactional decorator preserves function return values."""
        with app.app_context():
            @transactional("return_value_test")
            def function_with_return_value(multiplier):
                job = Job(
                    job_id=f"return-test-{multiplier}",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return multiplier * 2
            
            result = function_with_return_value(5)
            
            assert result == 10
            
            # Verify job was still created
            saved_job = Job.query.filter_by(job_id="return-test-5").first()
            assert saved_job is not None


class TestDbTransactionContextManager:
    """Test db_transaction context manager for explicit transaction control."""
    
    def test_db_transaction_context_manager_success(self, app, db_session):
        """Test db_transaction context manager commits on success."""
        with app.app_context():
            with db_transaction("context_manager_test"):
                job = Job(
                    job_id="context-success-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
            
            # Verify job was committed
            saved_job = Job.query.filter_by(job_id="context-success-test").first()
            assert saved_job is not None
    
    def test_db_transaction_context_manager_rollback(self, app, db_session):
        """Test db_transaction context manager rolls back on exception."""
        with app.app_context():
            with pytest.raises(ValueError):
                with db_transaction("context_manager_error_test"):
                    job = Job(
                        job_id="context-rollback-test",
                        task_type=TaskType.COMPRESS.value
                    )
                    db.session.add(job)
                    raise ValueError("Intentional error")
            
            # Verify job was not committed due to rollback
            saved_job = Job.query.filter_by(job_id="context-rollback-test").first()
            assert saved_job is None
    
    @patch('src.utils.db_transaction.db.session.commit')
    def test_db_transaction_context_manager_retry(self, mock_commit, app, db_session):
        """Test db_transaction context manager retry mechanism using safe_db_operation."""
        with app.app_context():
            # Mock commit to fail once, then succeed
            mock_commit.side_effect = [
                OperationalError("Temporary error", None, None),
                None  # Success on second try
            ]
            
            def create_job_operation():
                with db_transaction("context_retry_test"):
                    job = Job(
                        job_id="context-retry-test",
                        task_type=TaskType.COMPRESS.value
                    )
                    db.session.add(job)
                    return job
            
            result = safe_db_operation(create_job_operation, "context_retry_test", max_retries=2)
            assert result is not None
            assert mock_commit.call_count == 2


class TestConcurrentTransactionSafety:
    """Test transaction safety under concurrent access."""
    
    def test_concurrent_safe_db_operations(self, app, db_session):
        """Test multiple concurrent safe_db_operation calls."""
        with app.app_context():
            results = []
            
            def create_job(job_id):
                def operation():
                    job = Job(
                        job_id=f"concurrent-{job_id}",
                        task_type=TaskType.COMPRESS.value
                    )
                    db.session.add(job)
                    return job
                
                return safe_db_operation(operation, f"concurrent operation {job_id}")
            
            # Run multiple concurrent operations
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_job, i) for i in range(10)]
                results = [future.result() for future in as_completed(futures)]
            
            # All operations should succeed
            assert all(result is not None for result in results)
            
            # Verify all jobs were created
            jobs = Job.query.filter(Job.job_id.like("concurrent-%")).all()
            assert len(jobs) == 10
    
    def test_concurrent_transactional_decorators(self, app, db_session):
        """Test multiple concurrent @transactional decorated functions."""
        with app.app_context():
            @transactional("concurrent_decorated_function")
            def create_job_decorated(job_id):
                job = Job(
                    job_id=f"decorated-{job_id}",
                    task_type=TaskType.CONVERT.value
                )
                db.session.add(job)
                return job
            
            results = []
            
            # Run multiple concurrent decorated operations
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(create_job_decorated, i) for i in range(6)]
                results = [future.result() for future in as_completed(futures)]
            
            # All operations should succeed
            assert all(result is not None for result in results)
            
            # Verify all jobs were created
            jobs = Job.query.filter(Job.job_id.like("decorated-%")).all()
            assert len(jobs) == 6


class TestTransactionErrorHandling:
    """Test comprehensive error handling in transaction utilities."""
    
    def test_transaction_error_custom_exception(self, app, db_session):
        """Test TransactionError is raised appropriately."""
        with app.app_context():
            def failing_operation():
                raise DatabaseError("Critical database error", None, None)
            
            # TransactionError should be raised for critical errors
            with pytest.raises(TransactionError):
                safe_db_operation(failing_operation, "critical error test", max_retries=1)
    
    def test_different_exception_types_handling(self, app, db_session):
        """Test handling of different database exception types."""
        with app.app_context():
            exception_types = [
                IntegrityError("Integrity violation", None, None),
                OperationalError("Operation failed", None, None),
                DisconnectionError("Connection lost", None, None),
                SQLTimeoutError("Query timeout", None, None)
            ]
            
            for exc in exception_types:
                def failing_operation():
                    raise exc
                
                # Should handle all these exception types gracefully
                result = safe_db_operation(
                    failing_operation, 
                    f"test {type(exc).__name__}",
                    max_retries=1
                )
                assert result is None
    
    @patch('src.utils.db_transaction.logger')
    def test_transaction_logging(self, mock_logger, app, db_session):
        """Test that transaction operations are properly logged."""
        with app.app_context():
            def successful_operation():
                job = Job(
                    job_id="logging-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            safe_db_operation(successful_operation, "logging test")
            
            # Verify logging calls were made
            assert mock_logger.info.called
            assert any("logging test" in str(call) for call in mock_logger.info.call_args_list)
    
    def test_transaction_performance_monitoring(self, app, db_session):
        """Test that transaction performance is monitored."""
        with app.app_context():
            def slow_operation():
                time.sleep(0.1)  # Simulate slow operation
                job = Job(
                    job_id="performance-test",
                    task_type=TaskType.COMPRESS.value
                )
                db.session.add(job)
                return job
            
            start_time = time.time()
            result = safe_db_operation(slow_operation, "performance test")
            end_time = time.time()
            
            assert result is not None
            assert end_time - start_time >= 0.1  # Should take at least 0.1 seconds


class TestTransactionIntegration:
    """Integration tests for transaction utilities with existing codebase."""
    
    def test_integration_with_job_status_updates(self, app, db_session):
        """Test transaction utilities work with job status update workflows."""
        with app.app_context():
            # Create initial job
            job = Job(
                job_id="integration-test",
                task_type=TaskType.COMPRESS.value
            )
            db.session.add(job)
            db.session.commit()
            
            @transactional("job_status_update")
            def update_job_status():
                job.mark_as_processing()
                job.mark_as_completed({"result": "success"})
                return job
            
            result = update_job_status()
            
            assert result.status == JobStatus.COMPLETED.value
            assert result.result == {"result": "success"}
            
            # Verify changes were committed
            updated_job = Job.query.filter_by(job_id="integration-test").first()
            assert updated_job.status == JobStatus.COMPLETED.value
    
    def test_integration_with_bulk_operations(self, app, db_session):
        """Test transaction utilities with bulk database operations."""
        with app.app_context():
            @transactional("bulk_job_creation")
            def create_multiple_jobs(count):
                jobs = []
                for i in range(count):
                    job = Job(
                        job_id=f"bulk-{i}",
                        task_type=TaskType.COMPRESS.value
                    )
                    db.session.add(job)
                    jobs.append(job)
                return jobs
            
            results = create_multiple_jobs(5)
            
            assert len(results) == 5
            
            # Verify all jobs were committed
            bulk_jobs = Job.query.filter(Job.job_id.like("bulk-%")).all()
            assert len(bulk_jobs) == 5