"""Comprehensive test suite for tasks module."""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from src.tasks.tasks import (
    compress_task,
    bulk_compress_task,
    convert_pdf_task,
    merge_pdfs_task,
    split_pdf_task,
    cleanup_temp_files_task,
    health_check_task,
    handle_task_error,
    RETRYABLE_ERRORS,
    NON_RETRYABLE_ERRORS
)
from src.models.job import Job, JobStatus, TaskType
from src.utils.exceptions import (
    PDFCompressionError,
    ValidationError,
    ResourceNotFoundError
)


class TestTaskErrorHandling:
    """Test the centralized error handling system."""
    
    def test_retryable_error_classification(self):
        """Test that errors are correctly classified as retryable."""
        # Transient errors
        assert ConnectionError in RETRYABLE_ERRORS['transient']
        assert TimeoutError in RETRYABLE_ERRORS['transient']
        
        # Resource errors
        assert MemoryError in RETRYABLE_ERRORS['resource']
        assert OSError in RETRYABLE_ERRORS['resource']
        
        # Processing errors
        assert RuntimeError in RETRYABLE_ERRORS['processing']
    
    def test_non_retryable_error_classification(self):
        """Test that errors are correctly classified as non-retryable."""
        assert ValidationError in NON_RETRYABLE_ERRORS
        assert ValueError in NON_RETRYABLE_ERRORS
        assert TypeError in NON_RETRYABLE_ERRORS
    
    @patch('src.tasks.tasks.db')
    def test_handle_task_error_retryable(self, mock_db):
        """Test error handling for retryable errors."""
        mock_task = Mock()
        mock_task.retry = Mock(side_effect=Exception("Retry called"))
        mock_job = Mock()
        
        error = ConnectionError("Network timeout")
        
        with pytest.raises(Exception, match="Retry called"):
            handle_task_error(mock_task, error, "job_123", mock_job)
        
        mock_task.retry.assert_called_once()
        mock_job.mark_as_failed.assert_not_called()
    
    @patch('src.tasks.tasks.db')
    def test_handle_task_error_non_retryable(self, mock_db):
        """Test error handling for non-retryable errors."""
        mock_task = Mock()
        mock_job = Mock()
        
        error = ValidationError("Invalid input")
        
        with pytest.raises(ValidationError):
            handle_task_error(mock_task, error, "job_123", mock_job)
        
        mock_task.retry.assert_not_called()
        mock_job.mark_as_failed.assert_called_once()


class TestCompressionTasks:
    """Test PDF compression tasks."""
    
    @patch('src.tasks.tasks.current_app')
    @patch('src.tasks.tasks.compression_service')
    @patch('src.tasks.tasks.db')
    def test_compress_task_success(self, mock_db, mock_compression_service, mock_app):
        """Test successful PDF compression."""
        # Setup mocks
        mock_job = Mock()
        mock_job.query.filter_by.return_value.first.return_value = mock_job
        
        mock_compression_service.compress_pdf.return_value = {
            'output_path': '/tmp/compressed.pdf',
            'original_size': 1000000,
            'compressed_size': 500000,
            'compression_ratio': 0.5
        }
        
        # Execute task
        with patch('src.tasks.tasks.Job', mock_job):
            result = compress_task.apply(
                args=['job_123', '/tmp/input.pdf', {'quality': 'medium'}]
            )
        
        # Verify results
        assert result.successful()
        mock_compression_service.compress_pdf.assert_called_once()
        mock_job.mark_as_completed.assert_called_once()
    
    @patch('src.tasks.tasks.current_app')
    @patch('src.tasks.tasks.compression_service')
    def test_compress_task_file_not_found(self, mock_compression_service, mock_app):
        """Test compression task with missing file."""
        mock_compression_service.compress_pdf.side_effect = FileNotFoundError("File not found")
        
        with pytest.raises(FileNotFoundError):
            compress_task.apply(args=['job_123', '/nonexistent/file.pdf', {}])


class TestFileManagementTasks:
    """Test file management tasks (merge, split)."""
    
    @patch('src.tasks.tasks.current_app')
    @patch('src.tasks.tasks.file_management_service')
    @patch('src.tasks.tasks.os.path.exists')
    @patch('src.tasks.tasks.os.path.getsize')
    def test_merge_pdfs_task_success(self, mock_getsize, mock_exists, mock_file_service, mock_app):
        """Test successful PDF merging."""
        # Setup mocks
        mock_exists.return_value = True
        mock_getsize.return_value = 1000000
        
        mock_file_service.merge_pdfs.return_value = {
            'success': True,
            'page_count': 10
        }
        
        mock_job = Mock()
        
        with patch('src.tasks.tasks.Job') as mock_job_class:
            mock_job_class.query.filter_by.return_value.first.return_value = None
            mock_job_class.return_value = mock_job
            
            with patch('src.tasks.tasks.task_context') as mock_context:
                mock_progress = Mock()
                mock_temp_manager = Mock()
                mock_temp_manager.create_temp_file.return_value = '/tmp/merged.pdf'
                mock_context.return_value.__enter__.return_value = (mock_progress, mock_temp_manager)
                
                result = merge_pdfs_task.apply(
                    args=['job_123', ['/tmp/file1.pdf', '/tmp/file2.pdf'], {}]
                )
        
        # Verify results
        assert result.successful()
        mock_file_service.merge_pdfs.assert_called_once()
        mock_job.mark_as_completed.assert_called_once()
    
    @patch('src.tasks.tasks.current_app')
    @patch('src.tasks.tasks.file_management_service')
    @patch('src.tasks.tasks.os.path.exists')
    def test_split_pdf_task_success(self, mock_exists, mock_file_service, mock_app):
        """Test successful PDF splitting."""
        # Setup mocks
        mock_exists.return_value = True
        
        mock_file_service.split_pdf.return_value = {
            'split_files': ['/tmp/page_1.pdf', '/tmp/page_2.pdf'],
            'total_pages': 2
        }
        
        mock_job = Mock()
        
        with patch('src.tasks.tasks.Job') as mock_job_class:
            mock_job_class.query.filter_by.return_value.first.return_value = None
            mock_job_class.return_value = mock_job
            
            with patch('src.tasks.tasks.task_context') as mock_context:
                mock_progress = Mock()
                mock_temp_manager = Mock()
                mock_temp_manager.create_temp_dir.return_value = '/tmp/split_output'
                mock_context.return_value.__enter__.return_value = (mock_progress, mock_temp_manager)
                
                result = split_pdf_task.apply(
                    args=['job_123', '/tmp/input.pdf', {}]
                )
        
        # Verify results
        assert result.successful()
        mock_file_service.split_pdf.assert_called_once()
        mock_job.mark_as_completed.assert_called_once()


class TestMaintenanceTasks:
    """Test maintenance and cleanup tasks."""
    
    @patch('src.tasks.tasks.os.walk')
    @patch('src.tasks.tasks.os.path.exists')
    @patch('src.tasks.tasks.os.stat')
    @patch('src.tasks.tasks.os.unlink')
    @patch('src.tasks.tasks.tempfile.gettempdir')
    def test_cleanup_temp_files_task(self, mock_gettempdir, mock_unlink, mock_stat, mock_exists, mock_walk):
        """Test temporary file cleanup."""
        # Setup mocks
        mock_gettempdir.return_value = '/tmp'
        mock_exists.return_value = True
        
        # Mock file system structure
        mock_walk.return_value = [
            ('/tmp', [], ['pdf_task_old.pdf', 'pdf_task_new.pdf', 'other_file.txt'])
        ]
        
        # Mock file stats (old file vs new file)
        old_time = datetime.now(timezone.utc).timestamp() - 86400 * 2  # 2 days old
        new_time = datetime.now(timezone.utc).timestamp() - 3600  # 1 hour old
        
        def mock_stat_side_effect(path):
            mock_stat_obj = Mock()
            if 'old' in path:
                mock_stat_obj.st_mtime = old_time
                mock_stat_obj.st_size = 1000
            else:
                mock_stat_obj.st_mtime = new_time
                mock_stat_obj.st_size = 500
            return mock_stat_obj
        
        mock_stat.side_effect = mock_stat_side_effect
        
        # Execute task
        result = cleanup_temp_files_task.apply(args=[24])
        
        # Verify results
        assert result.successful()
        result_data = result.result
        assert result_data['cleaned_files'] == 1  # Only old file should be cleaned
        assert result_data['cleaned_size_bytes'] == 1000
        mock_unlink.assert_called_once_with('/tmp/pdf_task_old.pdf')
    
    @patch('src.tasks.tasks.current_app')
    @patch('src.tasks.tasks.db')
    @patch('src.tasks.tasks.compression_service')
    @patch('src.tasks.tasks.shutil.disk_usage')
    def test_health_check_task(self, mock_disk_usage, mock_compression_service, mock_db, mock_app):
        """Test system health check."""
        # Setup mocks
        mock_db.session.execute.return_value = None  # Successful DB query
        mock_compression_service.health_check.return_value = {'status': 'healthy'}
        mock_disk_usage.return_value = Mock(free=5 * 1024**3)  # 5GB free
        
        # Execute task
        result = health_check_task.apply()
        
        # Verify results
        assert result.successful()
        health_data = result.result
        assert health_data['status'] == 'healthy'
        assert 'database' in health_data['checks']
        assert 'compression' in health_data['checks']
        assert 'disk_space' in health_data['checks']
        assert health_data['checks']['disk_space']['free_space_gb'] == 5.0


class TestTaskUtilities:
    """Test task utility classes and functions."""
    
    @patch('src.tasks.tasks.db')
    def test_progress_reporter(self, mock_db):
        """Test ProgressReporter functionality."""
        from src.tasks.utils import ProgressReporter
        
        mock_job = Mock()
        reporter = ProgressReporter(mock_job, total_steps=5)
        
        # Test progress update
        reporter.update(step=2, message="Processing...")
        
        assert reporter.current_step == 2
        assert reporter.progress_percentage == 40.0
        mock_job.update_progress.assert_called_with(40.0, "Processing...")
    
    def test_temporary_file_manager(self):
        """Test TemporaryFileManager functionality."""
        from src.tasks.utils import TemporaryFileManager
        
        with TemporaryFileManager() as temp_manager:
            # Create temp file
            temp_file = temp_manager.create_temp_file(suffix=".pdf")
            assert os.path.exists(temp_file)
            assert temp_file.endswith(".pdf")
            
            # Create temp directory
            temp_dir = temp_manager.create_temp_dir()
            assert os.path.exists(temp_dir)
            assert os.path.isdir(temp_dir)
        
        # Files should be cleaned up after context exit
        assert not os.path.exists(temp_file)
        assert not os.path.exists(temp_dir)


class TestTaskIntegration:
    """Integration tests for task workflows."""
    
    @patch('src.tasks.tasks.current_app')
    def test_task_context_integration(self, mock_app):
        """Test task context manager integration."""
        from src.tasks.utils import task_context
        
        mock_job = Mock()
        
        with task_context(mock_job, total_steps=3) as (progress, temp_manager):
            # Test progress reporting
            progress.update(step=1, message="Step 1")
            assert progress.current_step == 1
            
            # Test temp file creation
            temp_file = temp_manager.create_temp_file()
            assert os.path.exists(temp_file)
            
            # Complete the task
            progress.complete("Task completed")
            assert progress.current_step == 3
        
        # Temp files should be cleaned up
        assert not os.path.exists(temp_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])