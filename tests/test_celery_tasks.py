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
from src.models import CompressionJob
from src.tasks.tasks import cleanup_expired_jobs
# Bulk compression service removed as dead weight
from src.celery_app import make_celery


class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'

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


# User fixtures removed - no authentication needed


# Test job fixture removed - bulk compression not needed


class TestCeleryTasks:
    """Test Celery background tasks"""
    
    # Bulk compression tests removed - feature not needed
    
    def test_cleanup_expired_jobs(self, app):
        """Test cleanup of expired jobs"""
        with app.app_context():
            # Create expired job without user dependency
            expired_job = CompressionJob(
                job_type='single',
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
            with patch('src.services.cleanup_service.CleanupService.cleanup_job_files') as mock_cleanup:
                mock_cleanup.return_value = True
                
                # Execute cleanup task
                result = cleanup_expired_jobs()
                
                # Verify results
                assert result['success'] is True
                assert result['cleaned_count'] >= 1
                assert mock_cleanup.called
    
    # Bulk compression service integration tests removed - feature not needed


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
            
            # Check task routing for cleanup tasks
            assert 'src.tasks.tasks.cleanup_expired_jobs' in celery.conf.task_routes
            
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