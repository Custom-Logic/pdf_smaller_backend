"""
Integration tests for Enhanced Cleanup Service

Tests automated cleanup functionality, storage quota management,
and cleanup policies based on user tiers and retention rules.
Requirements: 6.2, 6.3, 6.4
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage
from io import BytesIO

from src.services.enhanced_cleanup_service import EnhancedCleanupService
from src.services.file_manager import FileManager
from src.models import User, CompressionJob, Subscription, Plan
from src.models.base import db


class TestEnhancedCleanupService:
    """Test cases for Enhanced Cleanup Service"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def file_manager(self, temp_dir):
        """Create FileManager instance with temporary directory"""
        return FileManager(base_upload_folder=temp_dir)
    
    @pytest.fixture
    def cleanup_service(self, file_manager):
        """Create Enhanced Cleanup Service instance"""
        return EnhancedCleanupService(file_manager=file_manager)
    
    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing"""
        user = Mock()
        user.id = 123
        user.email = "test@example.com"
        return user
    
    @pytest.fixture
    def mock_job(self, mock_user, temp_dir):
        """Create mock compression job"""
        job = Mock()
        job.id = 456
        job.user_id = mock_user.id
        job.status = 'completed'
        job.created_at = datetime.utcnow() - timedelta(days=2)
        job.input_path = os.path.join(temp_dir, 'input_test.pdf')
        job.result_path = os.path.join(temp_dir, 'result_test.pdf')
        
        # Create actual files for testing
        with open(job.input_path, 'wb') as f:
            f.write(b"Input file content")
        with open(job.result_path, 'wb') as f:
            f.write(b"Result file content")
        
        return job
    
    def test_cleanup_service_initialization(self, cleanup_service, file_manager):
        """Test cleanup service initialization"""
        assert cleanup_service.file_manager == file_manager
        assert hasattr(cleanup_service, 'STORAGE_QUOTAS')
        assert hasattr(cleanup_service, 'RETENTION_PERIODS')
        assert 'free' in cleanup_service.STORAGE_QUOTAS
        assert 'premium' in cleanup_service.STORAGE_QUOTAS
        assert 'pro' in cleanup_service.STORAGE_QUOTAS
    
    def test_storage_quota_configuration(self, cleanup_service):
        """Test storage quota configuration"""
        quotas = cleanup_service.STORAGE_QUOTAS
        
        assert quotas['free'] < quotas['premium']
        assert quotas['premium'] < quotas['pro']
        assert all(isinstance(quota, (int, float)) for quota in quotas.values())
    
    def test_retention_period_configuration(self, cleanup_service):
        """Test retention period configuration"""
        periods = cleanup_service.RETENTION_PERIODS
        
        assert periods['free'] < periods['premium']
        assert periods['premium'] < periods['pro']
        assert all(isinstance(period, (int, float)) for period in periods.values())
    
    def test_cleanup_temp_files(self, cleanup_service, temp_dir):
        """Test temporary files cleanup"""
        # Create temp files with different ages
        temp_folder = cleanup_service.file_manager.temp_folder
        
        # Old temp file (should be deleted)
        old_file = os.path.join(temp_folder, 'old_temp.pdf')
        with open(old_file, 'wb') as f:
            f.write(b"Old temp file content")
        
        # Make file old by modifying its timestamp
        old_time = datetime.utcnow() - timedelta(hours=2)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
        
        # Recent temp file (should not be deleted)
        recent_file = os.path.join(temp_folder, 'recent_temp.pdf')
        with open(recent_file, 'wb') as f:
            f.write(b"Recent temp file content")
        
        # Run cleanup
        result = cleanup_service.cleanup_temp_files()
        
        # Check results
        assert result['files_deleted'] >= 1
        assert result['space_freed_mb'] > 0
        assert not os.path.exists(old_file)  # Old file should be deleted
        assert os.path.exists(recent_file)   # Recent file should remain
    
    @patch('src.services.enhanced_cleanup_service.CompressionJob')
    @patch('src.services.enhanced_cleanup_service.db')
    def test_cleanup_failed_jobs(self, mock_db, mock_job_model, cleanup_service, mock_job):
        """Test failed jobs cleanup"""
        # Setup mock failed job
        mock_job.status = 'failed'
        mock_job.created_at = datetime.utcnow() - timedelta(hours=25)  # Older than retention
        
        mock_job_model.query.filter.return_value.all.return_value = [mock_job]
        
        # Run cleanup
        result = cleanup_service.cleanup_failed_jobs()
        
        # Verify cleanup was attempted
        assert 'jobs_cleaned' in result
        assert 'space_freed_mb' in result
        assert 'errors' in result
    
    @patch('src.services.enhanced_cleanup_service.User')
    def test_enforce_storage_quotas(self, mock_user_model, cleanup_service, mock_user):
        """Test storage quota enforcement"""
        # Mock user query
        mock_user_model.query.all.return_value = [mock_user]
        
        # Mock file manager methods
        with patch.object(cleanup_service.file_manager, 'get_user_storage_usage') as mock_usage:
            with patch.object(cleanup_service, '_get_user_tier') as mock_tier:
                with patch.object(cleanup_service, '_cleanup_user_files_to_quota') as mock_cleanup:
                    
                    # Setup mocks
                    mock_usage.return_value = {'total_size_mb': 150}  # Over free quota
                    mock_tier.return_value = 'free'  # Free tier (100MB quota)
                    mock_cleanup.return_value = 50  # 50MB freed
                    
                    # Run quota enforcement
                    result = cleanup_service.enforce_storage_quotas()
                    
                    # Verify enforcement was attempted
                    assert result['users_processed'] >= 1
                    assert result['quota_violations'] >= 1
                    mock_cleanup.assert_called_once()
    
    def test_get_cleanup_statistics(self, cleanup_service):
        """Test cleanup statistics generation"""
        with patch('src.services.enhanced_cleanup_service.CompressionJob') as mock_job:
            with patch('src.services.enhanced_cleanup_service.User') as mock_user:
                with patch('src.services.enhanced_cleanup_service.db') as mock_db:
                    
                    # Mock database queries
                    mock_job.query.count.return_value = 100
                    mock_db.session.query.return_value.group_by.return_value.all.return_value = [
                        ('completed', 80),
                        ('failed', 15),
                        ('processing', 5)
                    ]
                    mock_user.query.all.return_value = []
                    
                    # Get statistics
                    stats = cleanup_service.get_cleanup_statistics()
                    
                    # Verify statistics structure
                    assert 'timestamp' in stats
                    assert 'total_jobs' in stats
                    assert 'jobs_by_status' in stats
                    assert 'storage_usage' in stats
                    assert 'cleanup_recommendations' in stats
                    
                    assert stats['total_jobs'] == 100
                    assert stats['jobs_by_status']['completed'] == 80
    
    def test_comprehensive_cleanup(self, cleanup_service):
        """Test comprehensive cleanup operation"""
        with patch.object(cleanup_service, 'cleanup_expired_jobs') as mock_expired:
            with patch.object(cleanup_service, 'cleanup_temp_files') as mock_temp:
                with patch.object(cleanup_service, 'cleanup_orphaned_files') as mock_orphaned:
                    with patch.object(cleanup_service, 'enforce_storage_quotas') as mock_quota:
                        with patch.object(cleanup_service, 'cleanup_failed_jobs') as mock_failed:
                            
                            # Setup mock returns
                            mock_expired.return_value = {'files_deleted': 5, 'space_freed_mb': 10}
                            mock_temp.return_value = {'files_deleted': 3, 'space_freed_mb': 2}
                            mock_orphaned.return_value = {'files_deleted': 2, 'space_freed_mb': 1}
                            mock_quota.return_value = {'files_deleted': 1, 'space_freed_mb': 5}
                            mock_failed.return_value = {'files_deleted': 2, 'space_freed_mb': 3}
                            
                            # Run comprehensive cleanup
                            result = cleanup_service.run_comprehensive_cleanup()
                            
                            # Verify all cleanup methods were called
                            mock_expired.assert_called_once()
                            mock_temp.assert_called_once()
                            mock_orphaned.assert_called_once()
                            mock_quota.assert_called_once()
                            mock_failed.assert_called_once()
                            
                            # Verify totals
                            assert result['total_files_deleted'] == 13  # 5+3+2+1+2
                            assert result['total_space_freed_mb'] == 21  # 10+2+1+5+3
                            assert 'operations' in result
    
    def test_get_user_tier_free(self, cleanup_service):
        """Test user tier detection for free users"""
        with patch('src.services.enhanced_cleanup_service.Subscription') as mock_sub:
            mock_sub.query.filter_by.return_value.first.return_value = None
            
            tier = cleanup_service._get_user_tier(123)
            assert tier == 'free'
    
    def test_get_user_tier_premium(self, cleanup_service):
        """Test user tier detection for premium users"""
        with patch('src.services.enhanced_cleanup_service.Subscription') as mock_sub:
            mock_subscription = Mock()
            mock_plan = Mock()
            mock_plan.name = 'Premium'
            mock_subscription.plan = mock_plan
            
            mock_sub.query.filter_by.return_value.first.return_value = mock_subscription
            
            tier = cleanup_service._get_user_tier(123)
            assert tier == 'premium'
    
    def test_file_has_job_record_exists(self, cleanup_service):
        """Test file job record check when record exists"""
        with patch('src.services.enhanced_cleanup_service.CompressionJob') as mock_job:
            mock_job.query.filter.return_value.first.return_value = Mock()  # Job exists
            
            has_record = cleanup_service._file_has_job_record('/path/to/file.pdf', 123)
            assert has_record is True
    
    def test_file_has_job_record_not_exists(self, cleanup_service):
        """Test file job record check when record doesn't exist"""
        with patch('src.services.enhanced_cleanup_service.CompressionJob') as mock_job:
            mock_job.query.filter.return_value.first.return_value = None  # No job
            
            has_record = cleanup_service._file_has_job_record('/path/to/file.pdf', 123)
            assert has_record is False
    
    def test_cleanup_user_files_to_quota(self, cleanup_service, temp_dir):
        """Test cleaning up user files to meet quota"""
        user_id = 123
        quota_mb = 50
        
        # Mock file manager methods
        with patch.object(cleanup_service.file_manager, 'list_user_files') as mock_list:
            with patch.object(cleanup_service.file_manager, 'get_user_storage_usage') as mock_usage:
                with patch.object(cleanup_service.file_manager, 'delete_file') as mock_delete:
                    
                    # Setup mock file list (oldest first after sorting)
                    mock_files = [
                        {
                            'file_path': '/path/old_file1.pdf',
                            'file_size': 30 * 1024 * 1024,  # 30MB
                            'created_at': datetime.utcnow() - timedelta(days=5)
                        },
                        {
                            'file_path': '/path/old_file2.pdf',
                            'file_size': 25 * 1024 * 1024,  # 25MB
                            'created_at': datetime.utcnow() - timedelta(days=3)
                        }
                    ]
                    mock_list.return_value = mock_files
                    
                    # Mock current usage (over quota)
                    mock_usage.return_value = {'total_size_mb': 80}
                    
                    # Mock successful deletion
                    mock_delete.return_value = True
                    
                    # Run cleanup to quota
                    space_freed = cleanup_service._cleanup_user_files_to_quota(user_id, quota_mb)
                    
                    # Verify files were processed for deletion
                    assert mock_delete.call_count >= 1
                    assert space_freed > 0
    
    def test_generate_cleanup_recommendations(self, cleanup_service):
        """Test cleanup recommendations generation"""
        # Mock statistics with various conditions
        mock_stats = {
            'storage_usage': {
                'free': [
                    {'user_id': 1, 'usage_percentage': 85},  # High usage
                    {'user_id': 2, 'usage_percentage': 50}   # Normal usage
                ],
                'premium': [
                    {'user_id': 3, 'usage_percentage': 90}   # High usage
                ]
            },
            'quota_violations': [
                {'user_id': 4, 'usage_mb': 150, 'quota_mb': 100}
            ],
            'jobs_by_status': {
                'failed': 15,      # Many failed jobs
                'completed': 150   # Many completed jobs
            }
        }
        
        recommendations = cleanup_service._generate_cleanup_recommendations(mock_stats)
        
        # Should generate recommendations for various issues
        assert len(recommendations) > 0
        
        # Check for specific recommendation types
        rec_text = ' '.join(recommendations)
        assert 'storage quota' in rec_text or 'failed jobs' in rec_text or 'completed jobs' in rec_text


class TestCleanupServiceIntegration:
    """Integration tests with real file operations"""
    
    def test_real_file_cleanup(self, temp_dir):
        """Test cleanup with real file operations"""
        # Create FileManager and cleanup service
        file_manager = FileManager(base_upload_folder=temp_dir)
        cleanup_service = EnhancedCleanupService(file_manager=file_manager)
        
        # Create some test files in temp folder
        temp_folder = file_manager.temp_folder
        
        # Old file
        old_file = os.path.join(temp_folder, 'old_test.pdf')
        with open(old_file, 'wb') as f:
            f.write(b"Old file content for cleanup test")
        
        # Make it old
        old_time = datetime.utcnow() - timedelta(hours=2)
        os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))
        
        # Recent file
        recent_file = os.path.join(temp_folder, 'recent_test.pdf')
        with open(recent_file, 'wb') as f:
            f.write(b"Recent file content")
        
        # Run temp file cleanup
        result = cleanup_service.cleanup_temp_files()
        
        # Verify cleanup worked
        assert result['files_deleted'] >= 1
        assert result['space_freed_mb'] > 0
        assert not os.path.exists(old_file)
        assert os.path.exists(recent_file)
    
    def test_storage_usage_calculation(self, temp_dir):
        """Test storage usage calculation with real files"""
        file_manager = FileManager(base_upload_folder=temp_dir)
        cleanup_service = EnhancedCleanupService(file_manager=file_manager)
        
        user_id = 123
        
        # Create some files for the user
        from werkzeug.datastructures import FileStorage
        from io import BytesIO
        
        # Create mock files
        file1 = FileStorage(
            stream=BytesIO(b"File 1 content for testing"),
            filename="test1.pdf",
            content_type="application/pdf"
        )
        
        file2 = FileStorage(
            stream=BytesIO(b"File 2 content for testing with more data"),
            filename="test2.pdf",
            content_type="application/pdf"
        )
        
        # Store files
        file_manager.store_uploaded_file(file1, user_id)
        file_manager.store_uploaded_file(file2, user_id)
        
        # Get storage usage
        usage = file_manager.get_user_storage_usage(user_id)
        
        # Verify usage calculation
        assert usage['user_id'] == user_id
        assert usage['total_size_bytes'] > 0
        assert usage['file_count'] >= 2
        assert usage['total_size_mb'] > 0