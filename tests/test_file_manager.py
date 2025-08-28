"""
Unit tests for FileManager service

Tests secure file handling, ownership validation, and storage organization.
Requirements: 6.1, 6.5
"""

import os
import tempfile
import shutil
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from werkzeug.datastructures import FileStorage
from io import BytesIO

from src.services.file_manager import FileManager, FileManagerError
from src.models import User, CompressionJob
from src.models.base import db


class TestFileManager:
    """Test cases for FileManager class"""
    
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
    def mock_file(self):
        """Create mock file object for testing"""
        file_content = b"Mock PDF content for testing"
        file_obj = FileStorage(
            stream=BytesIO(file_content),
            filename="test_document.pdf",
            content_type="application/pdf"
        )
        return file_obj
    
    @pytest.fixture
    def sample_user_id(self):
        """Sample user ID for testing"""
        return 123
    
    def test_file_manager_initialization(self, temp_dir):
        """Test FileManager initialization and directory creation"""
        fm = FileManager(base_upload_folder=temp_dir)
        
        # Check that all required directories are created
        assert os.path.exists(fm.base_upload_folder)
        assert os.path.exists(fm.temp_folder)
        assert os.path.exists(fm.user_folder)
        assert os.path.exists(fm.results_folder)
        
        # Check directory paths are correct
        assert fm.temp_folder == os.path.join(temp_dir, 'temp')
        assert fm.user_folder == os.path.join(temp_dir, 'users')
        assert fm.results_folder == os.path.join(temp_dir, 'results')
    
    def test_file_manager_initialization_failure(self):
        """Test FileManager initialization with invalid directory"""
        with pytest.raises(FileManagerError):
            # Try to create FileManager with invalid path
            FileManager(base_upload_folder="/invalid/path/that/cannot/be/created")
    
    def test_generate_unique_filename(self, file_manager):
        """Test unique filename generation"""
        original_filename = "test_document.pdf"
        user_id = 123
        
        # Generate multiple filenames
        filename1 = file_manager.generate_unique_filename(original_filename, user_id)
        filename2 = file_manager.generate_unique_filename(original_filename, user_id)
        
        # Filenames should be different
        assert filename1 != filename2
        
        # Both should contain original name parts
        assert "test_document" in filename1
        assert "test_document" in filename2
        
        # Both should have PDF extension
        assert filename1.endswith('.pdf')
        assert filename2.endswith('.pdf')
        
        # Both should contain user ID
        assert str(user_id) in filename1
        assert str(user_id) in filename2
    
    def test_generate_unique_filename_without_user_id(self, file_manager):
        """Test unique filename generation without user ID"""
        original_filename = "test_document.pdf"
        
        filename = file_manager.generate_unique_filename(original_filename)
        
        assert "test_document" in filename
        assert filename.endswith('.pdf')
        # Should not contain user ID placeholder
        assert "_None_" not in filename
    
    def test_generate_unique_filename_invalid_input(self, file_manager):
        """Test unique filename generation with invalid input"""
        # Empty filename
        filename1 = file_manager.generate_unique_filename("")
        assert filename1 == "unnamed_file.pdf"
        
        # Filename without extension
        filename2 = file_manager.generate_unique_filename("document")
        assert filename2.endswith('.pdf')
        assert "document" in filename2
        
        # Very long filename
        long_name = "a" * 300 + ".pdf"
        filename3 = file_manager.generate_unique_filename(long_name, 123)
        assert len(filename3) <= 255
        assert filename3.endswith('.pdf')
    
    def test_get_user_storage_path(self, file_manager, sample_user_id):
        """Test user storage path creation"""
        user_path = file_manager.get_user_storage_path(sample_user_id)
        
        # Path should be created
        assert os.path.exists(user_path)
        
        # Path should be under user folder
        expected_path = os.path.join(file_manager.user_folder, str(sample_user_id))
        assert user_path == expected_path
    
    def test_store_uploaded_file_success(self, file_manager, mock_file, sample_user_id):
        """Test successful file upload storage"""
        job_id = 456
        
        result = file_manager.store_uploaded_file(mock_file, sample_user_id, job_id)
        
        # Check result structure
        assert 'original_filename' in result
        assert 'stored_filename' in result
        assert 'file_path' in result
        assert 'file_size' in result
        assert 'file_hash' in result
        assert 'user_id' in result
        assert 'job_id' in result
        assert 'created_at' in result
        
        # Check values
        assert result['original_filename'] == 'test_document.pdf'
        assert result['user_id'] == sample_user_id
        assert result['job_id'] == job_id
        assert result['file_size'] > 0
        
        # Check file was actually stored
        assert os.path.exists(result['file_path'])
        
        # Check file is in correct user directory
        user_path = file_manager.get_user_storage_path(sample_user_id)
        assert result['file_path'].startswith(user_path)
    
    def test_store_uploaded_file_invalid_input(self, file_manager, sample_user_id):
        """Test file upload storage with invalid input"""
        # None file object
        with pytest.raises(FileManagerError):
            file_manager.store_uploaded_file(None, sample_user_id)
        
        # File object without filename
        mock_file = Mock()
        mock_file.filename = None
        with pytest.raises(FileManagerError):
            file_manager.store_uploaded_file(mock_file, sample_user_id)
    
    def test_store_result_file_success(self, file_manager, temp_dir, sample_user_id):
        """Test successful result file storage"""
        # Create a source file
        source_path = os.path.join(temp_dir, "source_result.pdf")
        with open(source_path, 'wb') as f:
            f.write(b"Compressed PDF content")
        
        job_id = 789
        result_type = "compressed"
        
        result = file_manager.store_result_file(source_path, sample_user_id, job_id, result_type)
        
        # Check result structure
        assert 'result_filename' in result
        assert 'result_path' in result
        assert 'file_size' in result
        assert 'file_hash' in result
        assert 'user_id' in result
        assert 'job_id' in result
        assert 'result_type' in result
        
        # Check values
        assert result['user_id'] == sample_user_id
        assert result['job_id'] == job_id
        assert result['result_type'] == result_type
        assert result['file_size'] > 0
        
        # Check file was stored
        assert os.path.exists(result['result_path'])
        
        # Check file is in results directory
        results_path = os.path.join(file_manager.results_folder, str(sample_user_id))
        assert result['result_path'].startswith(results_path)
    
    def test_store_result_file_nonexistent_source(self, file_manager, sample_user_id):
        """Test result file storage with nonexistent source"""
        with pytest.raises(FileManagerError):
            file_manager.store_result_file("/nonexistent/file.pdf", sample_user_id, 123)
    
    @patch('src.services.file_manager.is_safe_path')
    def test_validate_file_ownership_safe_path_check(self, mock_is_safe_path, file_manager, sample_user_id):
        """Test file ownership validation with path safety check"""
        mock_is_safe_path.return_value = False
        
        result = file_manager.validate_file_ownership("/unsafe/path", sample_user_id)
        assert result is False
        mock_is_safe_path.assert_called_once()
    
    def test_validate_file_ownership_nonexistent_file(self, file_manager, sample_user_id):
        """Test file ownership validation with nonexistent file"""
        result = file_manager.validate_file_ownership("/nonexistent/file.pdf", sample_user_id)
        assert result is False
    
    def test_validate_file_ownership_user_storage(self, file_manager, mock_file, sample_user_id):
        """Test file ownership validation for user storage files"""
        # Store a file first
        result = file_manager.store_uploaded_file(mock_file, sample_user_id)
        file_path = result['file_path']
        
        # Validate ownership
        is_owner = file_manager.validate_file_ownership(file_path, sample_user_id)
        assert is_owner is True
        
        # Test with different user
        is_not_owner = file_manager.validate_file_ownership(file_path, sample_user_id + 1)
        assert is_not_owner is False
    
    @patch('src.services.file_manager.CompressionJob')
    def test_validate_result_file_ownership(self, mock_job_model, file_manager, temp_dir, sample_user_id):
        """Test result file ownership validation"""
        # Create a result file
        source_path = os.path.join(temp_dir, "test_result.pdf")
        with open(source_path, 'wb') as f:
            f.write(b"Result content")
        
        job_id = 999
        result = file_manager.store_result_file(source_path, sample_user_id, job_id)
        
        # Mock job query
        mock_job = Mock()
        mock_job_model.query.filter_by.return_value.first.return_value = mock_job
        
        # Validate ownership
        is_owner = file_manager.validate_file_ownership(result['result_path'], sample_user_id)
        assert is_owner is True
        
        # Test with no job found
        mock_job_model.query.filter_by.return_value.first.return_value = None
        is_not_owner = file_manager.validate_file_ownership(result['result_path'], sample_user_id + 1)
        assert is_not_owner is False
    
    def test_get_file_info_success(self, file_manager, mock_file, sample_user_id):
        """Test getting file information"""
        # Store a file first
        result = file_manager.store_uploaded_file(mock_file, sample_user_id)
        file_path = result['file_path']
        
        # Get file info
        file_info = file_manager.get_file_info(file_path, sample_user_id)
        
        assert file_info is not None
        assert 'file_path' in file_info
        assert 'filename' in file_info
        assert 'file_size' in file_info
        assert 'created_at' in file_info
        assert 'modified_at' in file_info
        assert 'is_readable' in file_info
        assert 'is_writable' in file_info
        
        assert file_info['file_path'] == file_path
        assert file_info['file_size'] > 0
    
    def test_get_file_info_no_access(self, file_manager, mock_file, sample_user_id):
        """Test getting file information without access"""
        # Store a file for one user
        result = file_manager.store_uploaded_file(mock_file, sample_user_id)
        file_path = result['file_path']
        
        # Try to get info as different user
        file_info = file_manager.get_file_info(file_path, sample_user_id + 1)
        assert file_info is None
    
    def test_delete_file_success(self, file_manager, mock_file, sample_user_id):
        """Test successful file deletion"""
        # Store a file first
        result = file_manager.store_uploaded_file(mock_file, sample_user_id)
        file_path = result['file_path']
        
        # Verify file exists
        assert os.path.exists(file_path)
        
        # Delete file
        success = file_manager.delete_file(file_path, sample_user_id)
        assert success is True
        
        # Verify file is deleted
        assert not os.path.exists(file_path)
    
    def test_delete_file_no_permission(self, file_manager, mock_file, sample_user_id):
        """Test file deletion without permission"""
        # Store a file for one user
        result = file_manager.store_uploaded_file(mock_file, sample_user_id)
        file_path = result['file_path']
        
        # Try to delete as different user
        success = file_manager.delete_file(file_path, sample_user_id + 1)
        assert success is False
        
        # Verify file still exists
        assert os.path.exists(file_path)
    
    def test_get_user_storage_usage(self, file_manager, mock_file, sample_user_id):
        """Test user storage usage calculation"""
        # Store some files
        file_manager.store_uploaded_file(mock_file, sample_user_id)
        
        # Create another mock file
        mock_file2 = FileStorage(
            stream=BytesIO(b"Another test file content"),
            filename="another_test.pdf",
            content_type="application/pdf"
        )
        file_manager.store_uploaded_file(mock_file2, sample_user_id)
        
        # Get storage usage
        usage = file_manager.get_user_storage_usage(sample_user_id)
        
        assert 'user_id' in usage
        assert 'total_size_bytes' in usage
        assert 'total_size_mb' in usage
        assert 'file_count' in usage
        assert 'storage_paths' in usage
        
        assert usage['user_id'] == sample_user_id
        assert usage['total_size_bytes'] > 0
        assert usage['file_count'] >= 2
    
    def test_list_user_files(self, file_manager, mock_file, sample_user_id, temp_dir):
        """Test listing user files"""
        # Store upload file
        file_manager.store_uploaded_file(mock_file, sample_user_id)
        
        # Store result file
        source_path = os.path.join(temp_dir, "result.pdf")
        with open(source_path, 'wb') as f:
            f.write(b"Result content")
        file_manager.store_result_file(source_path, sample_user_id, 123)
        
        # List all files
        all_files = file_manager.list_user_files(sample_user_id, 'all')
        assert len(all_files) >= 2
        
        # List only uploads
        upload_files = file_manager.list_user_files(sample_user_id, 'uploads')
        assert len(upload_files) >= 1
        assert all(f['file_type'] == 'uploads' for f in upload_files)
        
        # List only results
        result_files = file_manager.list_user_files(sample_user_id, 'results')
        assert len(result_files) >= 1
        assert all(f['file_type'] == 'results' for f in result_files)
    
    def test_calculate_file_hash(self, file_manager, temp_dir):
        """Test file hash calculation"""
        # Create test file
        test_file = os.path.join(temp_dir, "hash_test.txt")
        test_content = b"Test content for hash calculation"
        with open(test_file, 'wb') as f:
            f.write(test_content)
        
        # Calculate hash
        file_hash = file_manager._calculate_file_hash(test_file)
        
        # Hash should be non-empty string
        assert isinstance(file_hash, str)
        assert len(file_hash) > 0
        
        # Same content should produce same hash
        file_hash2 = file_manager._calculate_file_hash(test_file)
        assert file_hash == file_hash2
    
    def test_calculate_file_hash_nonexistent_file(self, file_manager):
        """Test file hash calculation with nonexistent file"""
        file_hash = file_manager._calculate_file_hash("/nonexistent/file.txt")
        assert file_hash == ""


# Integration test fixtures and helpers
@pytest.fixture
def app():
    """Create Flask app for testing"""
    from src.main import create_app
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app


@pytest.fixture
def app_context(app):
    """Create application context"""
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


class TestFileManagerIntegration:
    """Integration tests for FileManager with database"""
    
    def test_file_manager_with_real_job(self, app_context, temp_dir):
        """Test FileManager with real compression job"""
        # Create user and job
        user = User(email="test@example.com", name="Test User")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        
        job = CompressionJob(
            user_id=user.id,
            job_type='single',
            original_filename='test.pdf'
        )
        db.session.add(job)
        db.session.commit()
        
        # Create FileManager
        fm = FileManager(base_upload_folder=temp_dir)
        
        # Create result file
        source_path = os.path.join(temp_dir, "compressed_result.pdf")
        with open(source_path, 'wb') as f:
            f.write(b"Compressed PDF content")
        
        # Store result file
        result = fm.store_result_file(source_path, user.id, job.id)
        
        # Validate ownership
        is_owner = fm.validate_file_ownership(result['result_path'], user.id)
        assert is_owner is True
        
        # Test with different user
        other_user = User(email="other@example.com", name="Other User")
        other_user.set_password("password123")
        db.session.add(other_user)
        db.session.commit()
        
        is_not_owner = fm.validate_file_ownership(result['result_path'], other_user.id)
        assert is_not_owner is False