"""Unit tests for FileManagementService

Tests the combined file management service that integrates file storage,
cleanup operations, and download functionality.
"""

import os
import tempfile
import shutil
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import pytest
from flask import Flask

from src.services.file_management_service import FileManagementService
from src.models.job import Job, JobStatus, TaskType
from src.utils.response_helpers import error_response


class TestFileManagementService:
    """Test cases for FileManagementService"""
    
    @pytest.fixture
    def temp_upload_folder(self):
        """Create a temporary upload folder for testing"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.fixture
    def file_service(self, temp_upload_folder):
        """Create FileManagementService instance with temp folder"""
        return FileManagementService(upload_folder=temp_upload_folder)
    
    @pytest.fixture
    def sample_file_data(self):
        """Sample file data for testing"""
        return b"Sample PDF content for testing"
    
    @pytest.fixture
    def mock_job(self):
        """Create a mock job for testing"""
        job = Mock(spec=Job)
        job.job_id = "test-job-123"
        job.status = JobStatus.COMPLETED
        job.task_type = TaskType.COMPRESS
        job.created_at = datetime.utcnow()
        job.updated_at = datetime.utcnow()
        job.is_completed.return_value = True
        job.result = {
            "output_path": "./uploads/test/result.pdf",
            "original_filename": "test_document.pdf",
            "mime_type": "application/pdf"
        }
        job.input_data = {
            "input_path": "./uploads/test/input.pdf",
            "file_size": 1024000
        }
        return job
    
    # ========================= INITIALIZATION TESTS =========================
    
    def test_initialization_default_folder(self):
        """Test service initialization with default upload folder"""
        with patch('src.services.file_management_service.Config') as mock_config:
            mock_config.UPLOAD_FOLDER = "/default/upload"
            with patch('os.makedirs') as mock_makedirs:
                service = FileManagementService()
                assert service.upload_folder == "/default/upload"
                mock_makedirs.assert_called_once_with("/default/upload", exist_ok=True)
    
    def test_initialization_custom_folder(self, temp_upload_folder):
        """Test service initialization with custom upload folder"""
        service = FileManagementService(upload_folder=temp_upload_folder)
        assert service.upload_folder == temp_upload_folder
        assert os.path.exists(temp_upload_folder)
    
    # ========================= FILE STORAGE TESTS =========================
    
    def test_save_file_success(self, file_service, sample_file_data):
        """Test successful file saving"""
        file_id, file_path = file_service.save_file(sample_file_data, "test.pdf")
        
        # Check that file ID is generated
        assert file_id is not None
        assert len(file_id) == 36  # UUID length
        
        # Check that file path is correct
        assert file_path.endswith(".pdf")
        assert file_service.upload_folder in file_path
        
        # Check that file exists and has correct content
        assert os.path.exists(file_path)
        with open(file_path, 'rb') as f:
            assert f.read() == sample_file_data
    
    def test_save_file_no_extension(self, file_service, sample_file_data):
        """Test saving file without extension defaults to .pdf"""
        file_id, file_path = file_service.save_file(sample_file_data)
        
        assert file_path.endswith(".pdf")
        assert os.path.exists(file_path)
    
    def test_save_file_custom_extension(self, file_service, sample_file_data):
        """Test saving file with custom extension"""
        file_id, file_path = file_service.save_file(sample_file_data, "document.docx")
        
        assert file_path.endswith(".docx")
        assert os.path.exists(file_path)
    
    def test_save_file_error_handling(self, file_service):
        """Test error handling during file save"""
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with pytest.raises(IOError):
                file_service.save_file(b"test data", "test.pdf")
    
    # ========================= FILE RETRIEVAL TESTS =========================
    
    def test_get_file_path(self, file_service):
        """Test getting file path from ID"""
        file_id = "test-uuid-123"
        file_path = file_service.get_file_path(file_id)
        
        expected_path = os.path.join(file_service.upload_folder, f"{file_id}.pdf")
        assert file_path == expected_path
    
    def test_get_file_path_custom_extension(self, file_service):
        """Test getting file path with custom extension"""
        file_id = "test-uuid-123"
        file_path = file_service.get_file_path(file_id, ".docx")
        
        expected_path = os.path.join(file_service.upload_folder, f"{file_id}.docx")
        assert file_path == expected_path
    
    def test_file_exists_true(self, file_service, sample_file_data):
        """Test file_exists returns True for existing file"""
        file_id, file_path = file_service.save_file(sample_file_data, "test.pdf")
        assert file_service.file_exists(file_path) is True
    
    def test_file_exists_false(self, file_service):
        """Test file_exists returns False for non-existing file"""
        non_existent_path = os.path.join(file_service.upload_folder, "nonexistent.pdf")
        assert file_service.file_exists(non_existent_path) is False
    
    def test_get_file_size(self, file_service, sample_file_data):
        """Test getting file size"""
        file_id, file_path = file_service.save_file(sample_file_data, "test.pdf")
        file_size = file_service.get_file_size(file_path)
        
        assert file_size == len(sample_file_data)
    
    def test_delete_file_success(self, file_service, sample_file_data):
        """Test successful file deletion"""
        file_id, file_path = file_service.save_file(sample_file_data, "test.pdf")
        
        # Verify file exists
        assert os.path.exists(file_path)
        
        # Delete file
        result = file_service.delete_file(file_path)
        
        # Verify deletion
        assert result is True
        assert not os.path.exists(file_path)
    
    def test_delete_file_nonexistent(self, file_service):
        """Test deleting non-existent file"""
        non_existent_path = os.path.join(file_service.upload_folder, "nonexistent.pdf")
        result = file_service.delete_file(non_existent_path)
        
        assert result is False
    
    # ========================= DOWNLOAD TESTS =========================
    
    @patch('src.services.file_management_service.Job')
    @patch('src.services.file_management_service.send_file')
    @patch('src.services.file_management_service.Path')
    def test_get_job_download_response_success(self, mock_path, mock_send_file, mock_job_query, file_service, mock_job):
        """Test successful job download response"""
        # Setup mocks
        mock_job_query.query.filter_by.return_value.first.return_value = mock_job
        mock_path_instance = Mock()
        mock_path_instance.is_file.return_value = True
        mock_path.return_value.resolve.return_value = mock_path_instance
        mock_send_file.return_value = "file_response"
        
        # Test download
        response = file_service.get_job_download_response("test-job-123")
        
        # Verify response
        assert response == "file_response"
        mock_send_file.assert_called_once()
    
    @patch('src.services.file_management_service.Job')
    def test_get_job_download_response_job_not_found(self, mock_job_query, file_service):
        """Test download response when job not found"""
        mock_job_query.query.filter_by.return_value.first.return_value = None
        
        response = file_service.get_job_download_response("nonexistent-job")
        
        # Should return error response (we can't easily test the exact response here)
        assert response is not None
    
    @patch('src.services.file_management_service.Job')
    def test_get_job_download_response_job_not_completed(self, mock_job_query, file_service, mock_job):
        """Test download response when job not completed"""
        mock_job.is_completed.return_value = False
        mock_job_query.query.filter_by.return_value.first.return_value = mock_job
        
        response = file_service.get_job_download_response("test-job-123")
        
        # Should return error response
        assert response is not None
    
    @patch('src.services.file_management_service.Job')
    def test_is_download_available_true(self, mock_job_query, file_service, mock_job):
        """Test download availability check returns True"""
        mock_job_query.query.filter_by.return_value.first.return_value = mock_job
        
        with patch('src.services.file_management_service.Path') as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.is_file.return_value = True
            mock_path.return_value.resolve.return_value = mock_path_instance
            
            result = file_service.is_download_available("test-job-123")
            assert result is True
    
    @patch('src.services.file_management_service.Job')
    def test_is_download_available_false(self, mock_job_query, file_service):
        """Test download availability check returns False"""
        mock_job_query.query.filter_by.return_value.first.return_value = None
        
        result = file_service.is_download_available("nonexistent-job")
        assert result is False
    
    # ========================= CLEANUP TESTS =========================
    
    def test_cleanup_old_files(self, file_service):
        """Test cleanup of old files"""
        with patch('src.services.file_management_service.cleanup_old_files') as mock_cleanup:
            with patch('src.services.file_management_service.Config') as mock_config:
                mock_config.FILE_RETENTION_HOURS = 24
                
                result = file_service.cleanup_old_files()
                
                mock_cleanup.assert_called_once_with(file_service.upload_folder, 24)
                assert 'files_deleted' in result
                assert 'space_freed_mb' in result
                assert 'errors' in result
    
    @patch('src.services.file_management_service.Job')
    @patch('src.services.file_management_service.db')
    def test_cleanup_expired_jobs_success(self, mock_db, mock_job_query, file_service):
        """Test successful cleanup of expired jobs"""
        # Create mock expired jobs
        expired_job = Mock(spec=Job)
        expired_job.job_id = "expired-job-123"
        
        # Mock the _get_expired_jobs method
        with patch.object(file_service, '_get_expired_jobs', return_value=[expired_job]):
            with patch.object(file_service, '_cleanup_job_files', return_value=5.0):
                result = file_service.cleanup_expired_jobs()
                
                assert result['jobs_cleaned'] == 1
                assert result['total_space_freed_mb'] == 5.0
                mock_db.session.delete.assert_called_once_with(expired_job)
                mock_db.session.commit.assert_called_once()
    
    def test_cleanup_temp_files(self, file_service, temp_upload_folder):
        """Test cleanup of temporary files"""
        # Create old temp file
        old_file_path = os.path.join(temp_upload_folder, "old_temp_file.pdf")
        with open(old_file_path, 'w') as f:
            f.write("old temp content")
        
        # Set file modification time to 2 hours ago
        old_time = datetime.utcnow() - timedelta(hours=2)
        os.utime(old_file_path, (old_time.timestamp(), old_time.timestamp()))
        
        # Create recent temp file
        recent_file_path = os.path.join(temp_upload_folder, "recent_temp_file.pdf")
        with open(recent_file_path, 'w') as f:
            f.write("recent temp content")
        
        # Run cleanup
        result = file_service.cleanup_temp_files()
        
        # Verify old file was deleted, recent file remains
        assert not os.path.exists(old_file_path)
        assert os.path.exists(recent_file_path)
        assert result['files_deleted'] == 1
        assert result['space_freed_mb'] > 0
    
    @patch('src.services.file_management_service.Job')
    @patch('src.services.file_management_service.db')
    def test_get_cleanup_statistics(self, mock_db, mock_job_query, file_service):
        """Test getting cleanup statistics"""
        # Mock job count
        mock_job_query.query.count.return_value = 100
        
        # Mock status counts
        mock_db.session.query.return_value.group_by.return_value.all.return_value = [
            (JobStatus.COMPLETED, 50),
            (JobStatus.FAILED, 20),
            (JobStatus.PENDING, 30)
        ]
        
        # Mock expired jobs
        with patch.object(file_service, '_get_expired_jobs', return_value=[]):
            result = file_service.get_cleanup_statistics()
            
            assert result['total_jobs'] == 100
            assert result['expired_jobs'] == 0
            assert 'jobs_by_status' in result
            assert 'upload_folder_size_mb' in result
    
    # ========================= HELPER METHOD TESTS =========================
    
    @patch('src.services.file_management_service.Job')
    def test_get_expired_jobs(self, mock_job_query, file_service):
        """Test getting expired jobs"""
        # Mock query results
        mock_job_query.query.filter.return_value.filter.return_value.all.return_value = [Mock(), Mock()]
        
        expired_jobs = file_service._get_expired_jobs()
        
        # Should return jobs (exact count depends on mock setup)
        assert isinstance(expired_jobs, list)
    
    def test_cleanup_job_files(self, file_service, temp_upload_folder):
        """Test cleanup of job files"""
        # Create test files
        test_file1 = os.path.join(temp_upload_folder, "job_file1.pdf")
        test_file2 = os.path.join(temp_upload_folder, "job_file2.pdf")
        
        with open(test_file1, 'w') as f:
            f.write("test content 1")
        with open(test_file2, 'w') as f:
            f.write("test content 2")
        
        # Create mock job with file paths
        mock_job = Mock()
        mock_job.job_id = "test-job"
        mock_job.result = {
            "output_path": test_file1,
            "temp_files": [test_file2]
        }
        mock_job.input_data = {}
        
        # Run cleanup
        space_freed = file_service._cleanup_job_files(mock_job)
        
        # Verify files were deleted
        assert not os.path.exists(test_file1)
        assert not os.path.exists(test_file2)
        assert space_freed > 0
    
    # ========================= UTILITY METHOD TESTS =========================
    
    def test_get_service_status(self, file_service):
        """Test getting service status"""
        status = file_service.get_service_status()
        
        assert status['service_name'] == 'FileManagementService'
        assert status['upload_folder'] == file_service.upload_folder
        assert 'upload_folder_exists' in status
        assert 'retention_periods' in status
        assert 'timestamp' in status
    
    def test_get_service_status_with_files(self, file_service, sample_file_data):
        """Test getting service status with files in upload folder"""
        # Add a file to upload folder
        file_service.save_file(sample_file_data, "test.pdf")
        
        status = file_service.get_service_status()
        
        assert status['upload_folder_file_count'] == 1
    
    # ========================= ERROR HANDLING TESTS =========================
    
    def test_error_handling_in_cleanup_expired_jobs(self, file_service):
        """Test error handling during job cleanup"""
        with patch.object(file_service, '_get_expired_jobs', side_effect=Exception("Database error")):
            result = file_service.cleanup_expired_jobs()
            
            assert result['jobs_cleaned'] == 0
            assert len(result['errors']) > 0
    
    def test_error_handling_in_get_cleanup_statistics(self, file_service):
        """Test error handling when getting cleanup statistics"""
        with patch('src.services.file_management_service.Job.query', side_effect=Exception("Database error")):
            result = file_service.get_cleanup_statistics()
            
            assert 'error' in result
            assert result['total_jobs'] == 0
    
    def test_error_handling_in_get_service_status(self, file_service):
        """Test error handling when getting service status"""
        with patch('os.path.exists', side_effect=Exception("Filesystem error")):
            status = file_service.get_service_status()
            
            assert 'error' in status
            assert status['service_name'] == 'FileManagementService'