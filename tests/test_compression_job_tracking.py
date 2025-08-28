"""Unit tests for compression job tracking functionality"""
import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.models import CompressionJob, User, Plan, Subscription
from src.services.compression_service import CompressionService
from src.services.cleanup_service import CleanupService
from src.models.base import db


class TestCompressionJobTracking:
    """Test compression job tracking and management"""
    
    def test_compression_job_creation(self, app, test_user):
        """Test creating a compression job"""
        with app.app_context():
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename='test.pdf',
                settings={'compression_level': 'medium', 'image_quality': 80}
            )
            
            db.session.add(job)
            db.session.commit()
            
            assert job.id is not None
            assert job.user_id == test_user.id
            assert job.job_type == 'single'
            assert job.status == 'pending'
            assert job.original_filename == 'test.pdf'
            assert job.get_settings()['compression_level'] == 'medium'
    
    def test_job_status_transitions(self, app, test_user):
        """Test job status transitions"""
        with app.app_context():
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename='test.pdf'
            )
            
            db.session.add(job)
            db.session.commit()
            
            # Test marking as processing
            job.mark_as_processing()
            assert job.status == 'processing'
            assert job.started_at is not None
            
            # Test marking as completed
            job.mark_as_completed()
            assert job.status == 'completed'
            assert job.completed_at is not None
            assert job.is_completed()
            assert job.is_successful()
            
            # Test marking as failed
            job.mark_as_failed('Test error')
            assert job.status == 'failed'
            assert job.error_message == 'Test error'
            assert job.is_completed()
            assert not job.is_successful()
    
    def test_compression_ratio_calculation(self, app, test_user):
        """Test compression ratio calculation"""
        with app.app_context():
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename='test.pdf'
            )
            
            job.original_size_bytes = 1000000  # 1MB
            job.compressed_size_bytes = 500000  # 500KB
            
            ratio = job.calculate_compression_ratio()
            assert ratio == 50.0  # 50% compression
            assert job.compression_ratio == 50.0
    
    def test_progress_percentage(self, app, test_user):
        """Test progress percentage calculation"""
        with app.app_context():
            job = CompressionJob(
                user_id=test_user.id,
                job_type='bulk',
                original_filename='bulk.zip'
            )
            
            job.file_count = 10
            job.completed_count = 3
            
            progress = job.get_progress_percentage()
            assert progress == 30.0
    
    def test_job_to_dict_serialization(self, app, test_user):
        """Test job serialization to dictionary"""
        with app.app_context():
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename='test.pdf',
                settings={'compression_level': 'high'}
            )
            
            job.original_size_bytes = 1000000
            job.compressed_size_bytes = 600000
            job.calculate_compression_ratio()
            
            db.session.add(job)
            db.session.commit()
            
            job_dict = job.to_dict()
            
            assert job_dict['id'] == job.id
            assert job_dict['user_id'] == test_user.id
            assert job_dict['job_type'] == 'single'
            assert job_dict['status'] == 'pending'
            assert job_dict['original_filename'] == 'test.pdf'
            assert job_dict['settings']['compression_level'] == 'high'
            assert job_dict['compression_ratio'] == 40.0
            assert 'created_at' in job_dict


class TestCompressionServiceWithTracking:
    """Test compression service with job tracking"""
    
    @patch('src.services.compression_service.CompressionService.compress_pdf')
    def test_process_upload_with_user_context(self, mock_compress, app, test_user, temp_upload_folder):
        """Test file processing with user context and job tracking"""
        with app.app_context():
            # Mock file
            mock_file = MagicMock()
            mock_file.filename = 'test.pdf'
            mock_file.save = MagicMock()
            
            # Mock successful compression
            mock_compress.return_value = True
            
            # Create temp files to simulate compression
            input_path = os.path.join(temp_upload_folder, 'input_test.pdf')
            output_path = os.path.join(temp_upload_folder, 'compressed_test.pdf')
            
            with open(input_path, 'wb') as f:
                f.write(b'fake pdf content' * 1000)  # 17KB file
            
            with open(output_path, 'wb') as f:
                f.write(b'compressed content' * 500)  # 9KB file
            
            # Mock os.path.getsize to return our file sizes
            with patch('os.path.getsize') as mock_getsize:
                mock_getsize.side_effect = lambda path: {
                    input_path: 17000,
                    output_path: 9000
                }.get(path, 0)
                
                service = CompressionService(temp_upload_folder)
                result_path = service.process_upload(
                    mock_file, 
                    compression_level='medium',
                    image_quality=80,
                    user_id=test_user.id
                )
                
                assert result_path == output_path
                
                # Check that job was created and completed
                job = CompressionJob.query.filter_by(user_id=test_user.id).first()
                assert job is not None
                assert job.status == 'completed'
                assert job.original_filename == 'test.pdf'
                assert job.original_size_bytes == 17000
                assert job.compressed_size_bytes == 9000
                assert job.compression_ratio == (17000 - 9000) / 17000 * 100
    
    def test_check_user_permissions(self, app, test_user_with_subscription, temp_upload_folder):
        """Test user permission checking"""
        with app.app_context():
            service = CompressionService(temp_upload_folder)
            
            # Test with valid permissions
            permissions = service.check_user_permissions(test_user_with_subscription.id, 5.0)
            assert permissions['allowed'] is True
            
            # Test with file too large
            permissions = service.check_user_permissions(test_user_with_subscription.id, 50.0)
            assert permissions['allowed'] is False
            assert 'exceeds limit' in permissions['reason']
    
    def test_get_user_compression_jobs(self, app, test_user, temp_upload_folder):
        """Test retrieving user's compression jobs"""
        with app.app_context():
            # Create some test jobs
            for i in range(5):
                job = CompressionJob(
                    user_id=test_user.id,
                    job_type='single',
                    original_filename=f'test_{i}.pdf'
                )
                db.session.add(job)
            
            db.session.commit()
            
            service = CompressionService(temp_upload_folder)
            jobs = service.get_user_compression_jobs(test_user.id, limit=3)
            
            assert len(jobs) == 3
            assert all(job['user_id'] == test_user.id for job in jobs)


class TestCleanupService:
    """Test cleanup service functionality"""
    
    def test_cleanup_statistics(self, app, test_user):
        """Test getting cleanup statistics"""
        with app.app_context():
            # Create some test jobs
            for i in range(3):
                job = CompressionJob(
                    user_id=test_user.id,
                    job_type='single',
                    original_filename=f'test_{i}.pdf'
                )
                if i == 0:
                    job.status = 'failed'
                db.session.add(job)
            
            db.session.commit()
            
            stats = CleanupService.get_cleanup_statistics()
            
            assert stats['total_jobs'] >= 3
            assert 'jobs_by_status' in stats
            assert 'pending' in stats['jobs_by_status']
            assert 'failed' in stats['jobs_by_status']
    
    def test_temp_file_cleanup(self, temp_upload_folder):
        """Test temporary file cleanup"""
        # Create some test files
        old_file = os.path.join(temp_upload_folder, 'old_file.pdf')
        new_file = os.path.join(temp_upload_folder, 'new_file.pdf')
        
        with open(old_file, 'w') as f:
            f.write('old content')
        
        with open(new_file, 'w') as f:
            f.write('new content')
        
        # Make old file appear old by modifying its timestamp
        old_time = datetime.now() - timedelta(hours=2)
        old_timestamp = old_time.timestamp()
        os.utime(old_file, (old_timestamp, old_timestamp))
        
        # Run cleanup
        result = CleanupService.cleanup_temp_files(temp_upload_folder)
        
        assert result['files_deleted'] >= 1
        assert not os.path.exists(old_file)  # Old file should be deleted
        assert os.path.exists(new_file)      # New file should remain
    
    def test_force_cleanup_user_jobs(self, app, test_user, temp_upload_folder):
        """Test force cleanup of user jobs"""
        with app.app_context():
            # Create test job with files
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename='test.pdf'
            )
            
            # Create fake files
            input_file = os.path.join(temp_upload_folder, 'input_test.pdf')
            output_file = os.path.join(temp_upload_folder, 'output_test.pdf')
            
            with open(input_file, 'w') as f:
                f.write('input content')
            with open(output_file, 'w') as f:
                f.write('output content')
            
            job.input_path = input_file
            job.result_path = output_file
            
            db.session.add(job)
            db.session.commit()
            
            # Run force cleanup
            result = CleanupService.force_cleanup_user_jobs(test_user.id)
            
            assert result['jobs_cleaned'] == 1
            assert not os.path.exists(input_file)
            assert not os.path.exists(output_file)
            
            # Verify job was deleted from database
            remaining_jobs = CompressionJob.query.filter_by(user_id=test_user.id).count()
            assert remaining_jobs == 0


# Fixtures for testing
@pytest.fixture
def temp_upload_folder():
    """Create a temporary upload folder for testing"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def test_user(app):
    """Create a test user"""
    with app.app_context():
        user = User(
            email='test@example.com',
            password='TestPassword123',
            name='Test User'
        )
        db.session.add(user)
        db.session.commit()
        yield user
        
        # Cleanup
        db.session.delete(user)
        db.session.commit()


@pytest.fixture
def test_user_with_subscription(app, test_user):
    """Create a test user with subscription"""
    with app.app_context():
        # Create a test plan
        plan = Plan(
            name='premium',
            display_name='Premium Plan',
            price_monthly=9.99,
            daily_compression_limit=500,
            max_file_size_mb=25,
            bulk_processing=True,
            priority_processing=False,
            api_access=True
        )
        db.session.add(plan)
        db.session.commit()
        
        # Create subscription
        subscription = Subscription(
            user_id=test_user.id,
            plan_id=plan.id,
            billing_cycle='monthly'
        )
        db.session.add(subscription)
        db.session.commit()
        
        yield test_user
        
        # Cleanup
        db.session.delete(subscription)
        db.session.delete(plan)
        db.session.commit()