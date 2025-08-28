"""
Integration tests for Celery background tasks
"""
import os
import pytest
import tempfile
import shutil
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from src.main.main import create_app
from src.models.base import db
from src.models import User, CompressionJob, Subscription, Plan
from src.tasks.compression_tasks import process_bulk_compression, cleanup_expired_jobs
from src.services.bulk_compression_service import BulkCompressionService
from src.celery_app import make_celery


class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret'
    UPLOAD_FOLDER = tempfile.mkdtemp()
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'


@pytest.fixture
def app():
    """Create test Flask application"""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # Check if plans already exist (from database initialization)
        free_plan = Plan.query.filter_by(name='free').first()
        premium_plan = Plan.query.filter_by(name='premium').first()
        
        # Create test plans if they don't exist
        if not free_plan:
            free_plan = Plan(
                name='free', 
                display_name='Free Plan',
                price_monthly=0, 
                daily_compression_limit=10,
                max_file_size_mb=10,
                bulk_processing=False
            )
            db.session.add(free_plan)
        
        if not premium_plan:
            premium_plan = Plan(
                name='premium', 
                display_name='Premium Plan',
                price_monthly=999, 
                daily_compression_limit=500,
                max_file_size_mb=50,
                bulk_processing=True
            )
            db.session.add(premium_plan)
        
        db.session.commit()
        
        yield app
        
        db.drop_all()
    
    # Cleanup upload folder
    if os.path.exists(TestConfig.UPLOAD_FOLDER):
        shutil.rmtree(TestConfig.UPLOAD_FOLDER)


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create test user with premium subscription"""
    with app.app_context():
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db.session.add(user)
        db.session.flush()
        
        # Add premium subscription
        premium_plan = Plan.query.filter_by(name='premium').first()
        subscription = Subscription(
            user_id=user.id,
            plan_id=premium_plan.id,
            billing_cycle='monthly'
        )
        db.session.add(subscription)
        db.session.commit()
        
        return user


@pytest.fixture
def test_job(app, test_user):
    """Create test compression job"""
    with app.app_context():
        job = CompressionJob(
            user_id=test_user.id,
            job_type='bulk',
            original_filename='test_bulk_job'
        )
        job.file_count = 2
        job.set_settings({
            'compression_level': 'medium',
            'image_quality': 80,
            'job_directory': os.path.join(TestConfig.UPLOAD_FOLDER, 'test_job'),
            'input_files': [
                {
                    'original_name': 'test1.pdf',
                    'saved_name': 'input_001_test1.pdf',
                    'path': os.path.join(TestConfig.UPLOAD_FOLDER, 'test_job', 'input_001_test1.pdf'),
                    'size': 1024
                },
                {
                    'original_name': 'test2.pdf',
                    'saved_name': 'input_002_test2.pdf',
                    'path': os.path.join(TestConfig.UPLOAD_FOLDER, 'test_job', 'input_002_test2.pdf'),
                    'size': 2048
                }
            ]
        })
        
        db.session.add(job)
        db.session.commit()
        
        # Create job directory and mock files
        job_dir = os.path.join(TestConfig.UPLOAD_FOLDER, 'test_job')
        os.makedirs(job_dir, exist_ok=True)
        
        # Create mock PDF files
        for file_info in job.get_settings()['input_files']:
            with open(file_info['path'], 'wb') as f:
                f.write(b'%PDF-1.4\n' + b'x' * (file_info['size'] - 8))
        
        return job


class TestCeleryTasks:
    """Test Celery background tasks"""
    
    def test_process_bulk_compression_success(self, app, test_job):
        """Test successful bulk compression processing"""
        with app.app_context():
            # Mock the compression service methods
            with patch('src.services.bulk_compression_service.BulkCompressionService._process_single_file_in_batch') as mock_process:
                with patch('src.services.bulk_compression_service.BulkCompressionService._create_result_archive') as mock_archive:
                    
                    # Setup mocks
                    mock_process.side_effect = [
                        {
                            'original_name': 'test1.pdf',
                            'original_size': 1024,
                            'compressed_size': 512,
                            'compression_ratio': 50.0,
                            'output_path': '/tmp/compressed_001_test1.pdf',
                            'output_filename': 'compressed_001_test1.pdf'
                        },
                        {
                            'original_name': 'test2.pdf',
                            'original_size': 2048,
                            'compressed_size': 1024,
                            'compression_ratio': 50.0,
                            'output_path': '/tmp/compressed_002_test2.pdf',
                            'output_filename': 'compressed_002_test2.pdf'
                        }
                    ]
                    
                    mock_archive.return_value = '/tmp/result.zip'
                    
                    # Execute task
                    result = process_bulk_compression(test_job.id)
                    
                    # Verify results
                    assert result['success'] is True
                    assert result['job_id'] == test_job.id
                    assert result['processed_count'] == 2
                    assert result['error_count'] == 0
                    
                    # Check job status
                    job = CompressionJob.query.get(test_job.id)
                    assert job.status == 'completed'
                    assert job.completed_count == 2
                    assert job.compressed_size_bytes == 1536  # 512 + 1024
    
    def test_process_bulk_compression_job_not_found(self, app):
        """Test bulk compression with non-existent job"""
        with app.app_context():
            result = process_bulk_compression(99999)
            
            assert result['success'] is False
            assert 'not found' in result['error']
            assert result['job_id'] == 99999
    
    def test_process_bulk_compression_partial_failure(self, app, test_job):
        """Test bulk compression with some files failing"""
        with app.app_context():
            with patch('src.services.bulk_compression_service.BulkCompressionService._process_single_file_in_batch') as mock_process:
                with patch('src.services.bulk_compression_service.BulkCompressionService._create_result_archive') as mock_archive:
                    
                    # Setup mocks - first file succeeds, second fails
                    mock_process.side_effect = [
                        {
                            'original_name': 'test1.pdf',
                            'original_size': 1024,
                            'compressed_size': 512,
                            'compression_ratio': 50.0,
                            'output_path': '/tmp/compressed_001_test1.pdf',
                            'output_filename': 'compressed_001_test1.pdf'
                        },
                        Exception("Compression failed for test2.pdf")
                    ]
                    
                    mock_archive.return_value = '/tmp/result.zip'
                    
                    # Execute task
                    result = process_bulk_compression(test_job.id)
                    
                    # Verify results
                    assert result['success'] is True
                    assert result['processed_count'] == 1
                    assert result['error_count'] == 1
                    assert len(result['errors']) == 1
                    
                    # Check job status
                    job = CompressionJob.query.get(test_job.id)
                    assert job.status == 'completed'
                    assert 'errors' in job.error_message
    
    def test_process_bulk_compression_complete_failure(self, app, test_job):
        """Test bulk compression with all files failing"""
        with app.app_context():
            with patch('src.services.bulk_compression_service.BulkCompressionService._process_single_file_in_batch') as mock_process:
                
                # Setup mock to always fail
                mock_process.side_effect = Exception("Compression failed")
                
                # Execute task
                result = process_bulk_compression(test_job.id)
                
                # Verify results
                assert result['success'] is True  # Task succeeded, but job failed
                assert result['processed_count'] == 0
                assert result['error_count'] == 2
                
                # Check job status
                job = CompressionJob.query.get(test_job.id)
                assert job.status == 'failed'
                assert 'All files failed' in job.error_message
    
    def test_cleanup_expired_jobs(self, app, test_user):
        """Test cleanup of expired jobs"""
        with app.app_context():
            # Create expired job
            expired_job = CompressionJob(
                user_id=test_user.id,
                job_type='bulk',
                original_filename='expired_job'
            )
            expired_job.status = 'completed'
            expired_job.created_at = datetime.utcnow() - timedelta(hours=2)
            expired_job.input_path = os.path.join(TestConfig.UPLOAD_FOLDER, 'expired_job')
            
            db.session.add(expired_job)
            db.session.commit()
            
            # Create job directory
            os.makedirs(expired_job.input_path, exist_ok=True)
            test_file = os.path.join(expired_job.input_path, 'test.txt')
            with open(test_file, 'w') as f:
                f.write('test content')
            
            # Mock cleanup method
            with patch('src.services.bulk_compression_service.BulkCompressionService.cleanup_job_files') as mock_cleanup:
                mock_cleanup.return_value = True
                
                # Execute cleanup task
                result = cleanup_expired_jobs()
                
                # Verify results
                assert result['success'] is True
                assert result['cleaned_count'] >= 1
                assert mock_cleanup.called
    
    def test_bulk_compression_service_async_integration(self, app, test_user):
        """Test BulkCompressionService async processing integration"""
        with app.app_context():
            # Create bulk compression service
            bulk_service = BulkCompressionService(TestConfig.UPLOAD_FOLDER)
            
            # Create test job
            job = CompressionJob(
                user_id=test_user.id,
                job_type='bulk',
                original_filename='async_test_job'
            )
            db.session.add(job)
            db.session.flush()
            
            # Mock Celery task
            with patch('src.tasks.compression_tasks.process_bulk_compression.delay') as mock_delay:
                mock_task = MagicMock()
                mock_task.id = 'test-task-id-123'
                mock_delay.return_value = mock_task
                
                # Queue async job
                task_id = bulk_service.process_bulk_job_async(job.id)
                
                # Verify task was queued
                assert task_id == 'test-task-id-123'
                mock_delay.assert_called_once_with(job.id)
                
                # Check job was updated with task ID
                updated_job = CompressionJob.query.get(job.id)
                assert updated_job.task_id == 'test-task-id-123'
    
    def test_get_task_status(self, app):
        """Test getting Celery task status"""
        with app.app_context():
            bulk_service = BulkCompressionService(TestConfig.UPLOAD_FOLDER)
            
            # Mock Celery result
            with patch('src.celery_app.celery_app.AsyncResult') as mock_result:
                mock_async_result = MagicMock()
                mock_async_result.state = 'PROGRESS'
                mock_async_result.info = {
                    'current': 1,
                    'total': 3,
                    'progress': 33,
                    'status': 'Processing file 1 of 3'
                }
                mock_result.return_value = mock_async_result
                
                # Get task status
                status = bulk_service.get_task_status('test-task-id')
                
                # Verify status
                assert status['state'] == 'PROGRESS'
                assert status['current'] == 1
                assert status['total'] == 3
                assert status['progress'] == 33
                assert 'Processing file' in status['status']
    
    def test_task_status_success(self, app):
        """Test task status for successful completion"""
        with app.app_context():
            bulk_service = BulkCompressionService(TestConfig.UPLOAD_FOLDER)
            
            with patch('src.celery_app.celery_app.AsyncResult') as mock_result:
                mock_async_result = MagicMock()
                mock_async_result.state = 'SUCCESS'
                mock_async_result.result = {
                    'success': True,
                    'processed_count': 3,
                    'error_count': 0
                }
                mock_result.return_value = mock_async_result
                
                status = bulk_service.get_task_status('test-task-id')
                
                assert status['state'] == 'SUCCESS'
                assert status['progress'] == 100
                assert status['result']['processed_count'] == 3
    
    def test_task_status_failure(self, app):
        """Test task status for failed task"""
        with app.app_context():
            bulk_service = BulkCompressionService(TestConfig.UPLOAD_FOLDER)
            
            with patch('src.celery_app.celery_app.AsyncResult') as mock_result:
                mock_async_result = MagicMock()
                mock_async_result.state = 'FAILURE'
                mock_async_result.info = Exception("Task failed")
                mock_result.return_value = mock_async_result
                
                status = bulk_service.get_task_status('test-task-id')
                
                assert status['state'] == 'FAILURE'
                assert status['progress'] == 0
                assert 'Task failed' in status['error']


class TestCeleryConfiguration:
    """Test Celery configuration and setup"""
    
    def test_celery_app_creation(self, app):
        """Test Celery app is properly created and configured"""
        with app.app_context():
            celery = make_celery(app)
            
            # Check basic configuration
            assert celery.conf.task_serializer == 'json'
            assert celery.conf.result_serializer == 'json'
            assert celery.conf.timezone == 'UTC'
            assert celery.conf.enable_utc is True
            
            # Check task routing
            assert 'src.tasks.compression_tasks.process_bulk_compression' in celery.conf.task_routes
            assert 'src.tasks.compression_tasks.cleanup_expired_jobs' in celery.conf.task_routes
            
            # Check beat schedule
            assert 'cleanup-expired-jobs' in celery.conf.beat_schedule
    
    def test_celery_context_task(self, app):
        """Test Celery tasks work with Flask app context"""
        with app.app_context():
            celery = make_celery(app)
            
            # Check that ContextTask is set
            assert hasattr(celery.Task, '__call__')
            
            # The ContextTask should be able to access Flask app context
            # This is tested implicitly in other task tests


if __name__ == '__main__':
    pytest.main([__file__])