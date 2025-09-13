"""
Integration tests for JobOperations migration from JobStatusManager.

This test suite verifies that:
1. JobOperations correctly replaces JobStatusManager functionality
2. All migrated components work together
3. Legacy JobStatusManager is properly deprecated
4. Database operations maintain consistency
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import uuid

from src.models import Job, JobStatus
from src.utils.job_operations import JobOperations
from src.utils.job_manager import JobStatusManager  # For legacy testing
from src.tasks.tasks import compress_task, ocr_process_task
from src.routes.compression_routes import compress_pdf


class TestJobOperationsFunctionality:
    """Test JobOperations core functionality."""

    def test_create_job_safely(self, app, db_session):
        """Test safe job creation with transaction management."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            assert job is not None
            assert job.job_id == job_id
            assert job.job_type == "test_compress"
            assert job.status == JobStatus.PENDING
            assert job.input_data == {"file_path": "/test/file.pdf"}

    def test_create_job_safely_existing_job(self, app, db_session):
        """Test that existing jobs are returned without duplication."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Create initial job
            job1 = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file1.pdf"}
            )
            
            # Try to create same job again
            job2 = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file2.pdf"}
            )
            
            assert job1.id == job2.id
            assert job1.job_id == job2.job_id
            # Original input data should be preserved
            assert job1.input_data == {"file_path": "/test/file1.pdf"}

    def test_update_job_status(self, app, db_session):
        """Test job status updates with proper state transitions."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Create job
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            # Update to processing
            success = JobOperations.update_job_status(
                job_id, JobStatus.PROCESSING
            )
            assert success is True
            
            # Update to completed with result
            result_data = {"compressed_size": 1024}
            success = JobOperations.update_job_status(
                job_id, JobStatus.COMPLETED, result=result_data
            )
            assert success is True
            
            # Verify updates
            updated_job = Job.query.filter_by(job_id=job_id).first()
            assert updated_job.status == JobStatus.COMPLETED
            assert updated_job.result == result_data

    def test_update_job_status_invalid_transition(self, app, db_session):
        """Test that invalid state transitions are rejected."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Create job and complete it
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            JobOperations.update_job_status(job_id, JobStatus.COMPLETED)
            
            # Try invalid transition from COMPLETED to PROCESSING
            success = JobOperations.update_job_status(
                job_id, JobStatus.PROCESSING
            )
            assert success is False

    def test_get_job_status(self, app, db_session):
        """Test retrieving job status."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            status = JobOperations.get_job_status(job_id)
            assert status == JobStatus.PENDING.value

    def test_is_job_terminal(self, app, db_session):
        """Test terminal state detection."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            # Pending is not terminal
            assert JobOperations.is_job_terminal(job_id) is False
            
            # Completed is terminal
            JobOperations.update_job_status(job_id, JobStatus.COMPLETED)
            assert JobOperations.is_job_terminal(job_id) is True


class TestLegacyJobStatusManager:
    """Test that JobStatusManager is properly deprecated."""

    def test_job_status_manager_deprecation_warning(self, app):
        """Test that JobStatusManager methods show deprecation warnings."""
        with app.app_context():
            job_id = str(uuid.uuid4())
            
            # Test deprecated create_ai_job method
            with patch('src.services.ai_service.logger') as mock_logger:
                from src.services.ai_service import AIService
                service = AIService()
                result = service.create_ai_job("test text", {})
                
                # Should log deprecation warning
                mock_logger.warning.assert_called()
                assert "deprecated" in str(mock_logger.warning.call_args)
                assert result["success"] is False
                assert "deprecated" in result["error"]

    def test_job_status_manager_still_functions(self, app, db_session):
        """Test that JobStatusManager still works for backward compatibility."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Should still work but be deprecated
            job = JobStatusManager.get_or_create_job(
                job_id=job_id,
                task_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            assert job is not None
            assert job.job_id == job_id


class TestTaskIntegration:
    """Test integration of JobOperations with tasks."""

    @patch('src.tasks.tasks.ServiceRegistry.get_compression_service')
    def test_compress_task_job_operations(self, mock_compression_service, app, db_session):
        """Test that compress_task uses JobOperations correctly."""
        job_id = str(uuid.uuid4())
        mock_service = MagicMock()
        mock_service.compress_pdf.return_value = {
            "success": True,
            "compressed_data": b"compressed_data",
            "original_size": 1000,
            "compressed_size": 500,
            "compression_ratio": 0.5
        }
        mock_compression_service.return_value = mock_service
        
        with app.app_context():
            # Execute compress task
            result = compress_task(job_id, b"test_data", {"quality": 80}, "test.pdf")
            
            # Verify job was created and updated
            job = Job.query.filter_by(job_id=job_id).first()
            assert job is not None
            assert job.status == JobStatus.COMPLETED
            assert job.job_type == "compress"
            assert "original_size" in job.result

    @patch('src.tasks.tasks.ServiceRegistry.get_ocr_service')
    def test_ocr_task_job_operations(self, mock_ocr_service, app, db_session):
        """Test that ocr_process_task uses JobOperations correctly."""
        job_id = str(uuid.uuid4())
        mock_service = MagicMock()
        mock_service.process_ocr_data.return_value = {
            "success": True,
            "text": "Extracted text content",
            "pages": 5
        }
        mock_ocr_service.return_value = mock_service
        
        with app.app_context():
            result = ocr_process_task(job_id, b"test_pdf_data", {}, "test.pdf")
            
            # Verify job was created and updated
            job = Job.query.filter_by(job_id=job_id).first()
            assert job is not None
            assert job.status == JobStatus.COMPLETED
            assert job.job_type == "ocr"


class TestRouteIntegration:
    """Test integration of JobOperations with routes."""

    @patch('src.routes.compression_routes.compress_task')
    def test_compression_route_job_operations(self, mock_compress_task, app):
        """Test that compression routes use JobOperations correctly."""
        mock_compress_task.delay.return_value = None
        
        with app.test_client() as client:
            # Mock file upload
            data = {
                'file': (b'test_pdf_content', 'test.pdf'),
                'compressionLevel': 'medium',
                'imageQuality': '80'
            }
            
            response = client.post('/api/compress', data=data)
            
            assert response.status_code == 202
            response_data = response.get_json()
            assert response_data['success'] is True
            assert 'job_id' in response_data

    def test_route_job_failure_handling(self, app):
        """Test that routes handle job operation failures gracefully."""
        with app.test_client() as client:
            # Test with no file
            response = client.post('/api/compress')
            
            assert response.status_code == 400
            response_data = response.get_json()
            assert response_data['success'] is False
            assert 'No file provided' in response_data['message']


class TestDatabaseConsistency:
    """Test database consistency during concurrent operations."""

    def test_concurrent_job_creation(self, app, db_session):
        """Test that concurrent job creation doesn't create duplicates."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Simulate concurrent job creation
            job1 = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file1.pdf"}
            )
            
            job2 = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file2.pdf"}
            )
            
            # Should be the same job
            assert job1.id == job2.id
            assert Job.query.filter_by(job_id=job_id).count() == 1

    def test_transaction_rollback_on_error(self, app, db_session):
        """Test that failed operations roll back properly."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Create job
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="test_compress",
                input_data={"file_path": "/test/file.pdf"}
            )
            
            # Simulate database error during update
            with patch('src.models.db.session.commit') as mock_commit:
                mock_commit.side_effect = Exception("Database error")
                
                success = JobOperations.update_job_status(
                    job_id, JobStatus.PROCESSING
                )
                
                assert success is False
                
                # Verify job status wasn't changed
                updated_job = Job.query.filter_by(job_id=job_id).first()
                assert updated_job.status == JobStatus.PENDING


class TestMigrationValidation:
    """Test to validate the complete migration."""

    def test_no_job_status_manager_usage_in_tasks(self, app):
        """Verify no JobStatusManager usage remains in tasks.py."""
        import src.tasks.tasks as tasks_module
        
        # Read the tasks.py file content
        import inspect
        source = inspect.getsource(tasks_module)
        
        # Should not contain JobStatusManager usage
        assert "JobStatusManager" not in source
        assert "create_job_safely" in source
        assert "update_job_status" in source

    def test_no_job_status_manager_usage_in_routes(self, app):
        """Verify no JobStatusManager usage remains in compression_routes.py."""
        import src.routes.compression_routes as routes_module
        
        # Read the routes file content
        import inspect
        source = inspect.getsource(routes_module)
        
        # Should not contain JobStatusManager usage
        assert "JobStatusManager" not in source
        assert "JobOperations" in source

    def test_job_operations_api_consistency(self, app, db_session):
        """Test that JobOperations API is consistent across all usages."""
        job_id = str(uuid.uuid4())
        
        with app.app_context():
            # Test the complete lifecycle
            job = JobOperations.create_job_safely(
                job_id=job_id,
                job_type="integration_test",
                input_data={"test": "data"}
            )
            
            JobOperations.update_job_status(job_id, JobStatus.PROCESSING)
            JobOperations.update_job_status(
                job_id, 
                JobStatus.COMPLETED, 
                result={"test": "result"}
            )
            
            # Verify final state
            job = Job.query.filter_by(job_id=job_id).first()
            assert job.status == JobStatus.COMPLETED
            assert job.result == {"test": "result"}


# Test fixtures
@pytest.fixture
def app():
    """Create test Flask application."""
    from src import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    from src.models import db
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])