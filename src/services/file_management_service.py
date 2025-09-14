"""Combined File Management Service

This service combines the functionality of FileManager and CleanupService
into a unified service that handles all file-related operations including:
- File storage and retrieval
- File cleanup and retention policies
- Job-based file management
- File downloads for job results
"""

import os
import uuid
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from typing import Tuple, List, Dict, Any, Optional
from pathlib import Path
from flask import send_file

from src.config import Config
from src.models import Job, JobStatus
from src.models.base import db
from src.utils.file_utils import cleanup_old_files, _get_file_size
from src.utils.response_helpers import error_response
from src.utils.job_manager import JobStatusManager
from src.utils.db_transaction import db_transaction, safe_db_operation, transactional

logger = logging.getLogger(__name__)


class FileManagementService:
    """Unified service for all file management operations"""
    
    # Default retention periods (in hours) - job-based retention policy
    DEFAULT_RETENTION_PERIODS = {
        'completed': 24,  # 1 day for completed jobs
        'failed': 24,  # 1 day for failed jobs
        'pending': 1,  # 1 hour for pending jobs (shouldn't stay pending long)
        'processing': 4  # 4 hours for processing jobs (should complete by then)
    }
    
    # File cleanup settings
    TEMP_FILE_MAX_AGE_HOURS = 1  # Clean up temp files after 1 hour
    
    def __init__(self, upload_folder: str = None):
        """Initialize the file management service
        
        Args:
            upload_folder: Directory to store uploaded files. Defaults to Config.UPLOAD_FOLDER.
        """
        self.upload_folder = upload_folder or Config.UPLOAD_FOLDER
        os.makedirs(self.upload_folder, exist_ok=True)
        logger.info(f"FileManagementService initialized with upload folder: {self.upload_folder}")
    
    # ========================= FILE STORAGE OPERATIONS =========================
    
    def save_file(self, file_data: bytes, original_filename: str = None) -> Tuple[str, str]:
        """Save file data to disk with a unique filename
        
        Args:
            file_data: Binary file data to save
            original_filename: Original filename (used for extension)
            
        Returns:
            Tuple of (unique_id, file_path)
        """
        try:
            # Generate unique ID and create safe filename
            unique_id = str(uuid.uuid4())
            
            # Get file extension from original filename or default to .pdf
            extension = '.pdf'
            if original_filename:
                _, ext = os.path.splitext(original_filename)
                if ext:
                    extension = ext
            
            # Create filename and path
            filename = f"{unique_id}{extension}"
            file_path = os.path.join(self.upload_folder, filename)
            
            # Save file
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            file_size = len(file_data)
            logger.info(f"File saved: {filename} ({file_size} bytes)")
            
            return unique_id, file_path
            
        except Exception as e:
            logger.error(f"Error saving file {original_filename}: {str(e)}")
            raise
    
    def get_file_path(self, file_id: str, extension: str = '.pdf') -> str:
        """Get the full path for a file based on its ID
        
        Args:
            file_id: Unique file identifier
            extension: File extension (default: .pdf)
            
        Returns:
            Full file path
        """
        filename = f"{file_id}{extension}"
        return os.path.join(self.upload_folder, filename)
    
    @staticmethod
    def file_exists(file_path: str) -> bool:
        """Check if a file exists
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file exists, False otherwise
        """
        return os.path.isfile(file_path)

    @staticmethod
    def get_file_size(file_path: str) -> int:
        """Get file size in bytes
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in bytes
        """
        try:
            return os.path.getsize(file_path)
        except OSError as e:
            raise e

    @staticmethod
    def delete_file(file_path: str) -> bool:
        """Delete a file safely
        Args:
            file_path: Path to the file to delete
        Returns:
            True if file was deleted successfully, False otherwise
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {str(e)}")
            return False
    
    # ========================= FILE DOWNLOAD OPERATIONS =========================

    @staticmethod
    def get_job_download_response(job_id: str):
        """Get Flask response for downloading job result file
        Args:
            job_id: Job identifier
        Returns:
            Flask response object or error response
        """
        try:
            # Get job from database
            job = Job.query.filter_by(job_id=job_id).first()
            if not job:
                return error_response(message="Job not found", status_code=404)
            
            # Check if job is completed
            if not job.is_completed():
                return error_response(message="Job not completed yet", status_code=400)
            
            # Check if result file exists
            if not job.result or "output_path" not in job.result:
                return error_response(message="No result file available", status_code=404)
            
            # Resolve file path
            raw_path = job.result["output_path"]
            path = (Path.cwd() / raw_path).resolve()
            
            if not path.is_file():
                logger.warning(f"Result file not found on disk: {path}")
                return error_response(message="Result file not found on disk", status_code=404)
            
            # Get file metadata
            filename = job.result.get("original_filename", "result")
            mime_type = job.result.get("mime_type", "application/octet-stream")
            
            logger.info(f"Serving download for job {job_id}: {filename}")
            
            return send_file(
                str(path),
                as_attachment=True,
                download_name=filename,
                mimetype=mime_type
            )
            
        except Exception as e:
            logger.error(f"Error preparing download for job {job_id}: {str(e)}")
            return error_response(message="Error preparing file download", status_code=500)

    @staticmethod
    def is_download_available(job_id: str) -> bool:
        """Check if download is available for a job
        Args:
            job_id: Job identifier
        Returns:
            True if download is available, False otherwise
        """
        try:
            job = Job.query.filter_by(job_id=job_id).first()
            if not job or not job.is_completed() or not job.result:
                return False
            
            output_path = job.result.get("output_path")
            if not output_path:
                return False
            
            path = (Path.cwd() / output_path).resolve()
            return path.is_file()
            
        except Exception as e:
            logger.error(f"Error checking download availability for job {job_id}: {str(e)}")
            return False
    
    # ========================= ARCHIVE OPERATIONS =========================
    
    def create_result_archive(self, processed_files: List[Dict[str, Any]], job_id: str) -> str:
        """Create a ZIP archive of processed files and return the archive path
        
        Args:
            processed_files: List of processed file dictionaries containing file info
            job_id: Job identifier for naming the archive
            
        Returns:
            Path to the created archive file
            
        Raises:
            Exception: If archive creation fails
        """
        try:
            # Create archive filename with job ID
            archive_filename = f"processed_files_{job_id}.zip"
            archive_path = os.path.join(self.upload_folder, archive_filename)
            
            # Create ZIP archive
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_info in processed_files:
                    # Get file path from the processed file info
                    file_path = file_info.get('output_path') or file_info.get('file_path')
                    if not file_path or not os.path.exists(file_path):
                        logger.warning(f"Skipping missing file: {file_path}")
                        continue
                    
                    # Get original filename or create one from file info
                    original_filename = file_info.get('original_filename') or file_info.get('filename')
                    if not original_filename:
                        # Generate filename from path
                        original_filename = os.path.basename(file_path)
                    
                    # Add file to archive with original filename
                    zipf.write(file_path, original_filename)
                    logger.debug(f"Added file to archive: {original_filename}")
            
            # Verify archive was created successfully
            if not os.path.exists(archive_path):
                raise Exception("Archive file was not created")
            
            archive_size = os.path.getsize(archive_path)
            logger.info(f"Created result archive for job {job_id}: {archive_path} ({archive_size} bytes)")
            
            return archive_path
            
        except Exception as e:
            logger.error(f"Error creating result archive for job {job_id}: {str(e)}")
            # Clean up partial archive if it exists
            # noinspection PyUnboundLocalVariable
            if 'archive_path' in locals() and os.path.exists(archive_path):
                try:
                    os.remove(archive_path)
                except OSError as e:
                    pass
            raise
    
    # ========================= CLEANUP OPERATIONS =========================
    
    def cleanup_old_files(self, max_age_hours: int = None) -> Dict[str, Any]:
        """Remove files older than specified age from upload folder
        
        Args:
            max_age_hours: Maximum age in hours (default: from config)
            
        Returns:
            Cleanup summary dictionary
        """
        max_age = max_age_hours or Config.MAX_FILE_AGE
        
        cleanup_summary = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            cleanup_old_files(self.upload_folder, max_age)
            logger.info(f"Cleanup completed for files older than {max_age} hours")
        except Exception as e:
            error_msg = f"Error during file cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary
    
    def cleanup_expired_jobs(self) -> Dict[str, Any]:
        """Clean up expired jobs and their associated files
        
        Returns:
            Summary of cleanup operations
        """
        cleanup_summary = {
            'jobs_cleaned': 0,
            'files_deleted': 0,
            'errors': [],
            'total_space_freed_mb': 0
        }
        
        try:
            # Get all jobs that need cleanup
            expired_jobs = self._get_expired_jobs()
            
            for job in expired_jobs:
                try:
                    space_freed = self._cleanup_job_files(job)
                    cleanup_summary['total_space_freed_mb'] += space_freed
                    
                    # Delete the job record
                    db.session.delete(job)
                    cleanup_summary['jobs_cleaned'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job.job_id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_summary['errors'].append(error_msg)
            
            # Use safe database operation for cleanup commit
            def commit_cleanup():
                logger.info(f"Job cleanup completed: {cleanup_summary['jobs_cleaned']} jobs cleaned, "
                           f"{cleanup_summary['total_space_freed_mb']:.2f}MB freed")
            
            safe_db_operation(
                commit_cleanup,
                "cleanup_expired_jobs_commit",
                max_retries=2,
                default_return=None
            )
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during job cleanup process: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary
    
    def cleanup_temp_files(self) -> Dict[str, Any]:
        """Clean up temporary files older than specified age
        
        Returns:
            Cleanup summary dictionary
        """
        cleanup_summary = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            if not os.path.exists(self.upload_folder):
                return cleanup_summary
            
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.TEMP_FILE_MAX_AGE_HOURS)
            
            for filename in os.listdir(self.upload_folder):
                file_path = os.path.join(self.upload_folder, filename)
                
                try:
                    # Skip directories
                    if os.path.isdir(file_path):
                        continue
                    
                    # Check if file is old enough to delete
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_time:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        os.remove(file_path)
                        cleanup_summary['files_deleted'] += 1
                        cleanup_summary['space_freed_mb'] += file_size_mb
                        logger.debug(f"Deleted temp file: {file_path}")
                
                except Exception as e:
                    error_msg = f"Error deleting temp file {file_path}: {str(e)}"
                    logger.warning(error_msg)
                    cleanup_summary['errors'].append(error_msg)
            
            if cleanup_summary['files_deleted'] > 0:
                logger.info(f"Temp cleanup: {cleanup_summary['files_deleted']} files deleted, "
                           f"{cleanup_summary['space_freed_mb']:.2f}MB freed")
        
        except Exception as e:
            error_msg = f"Error during temp file cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary
    
    def get_cleanup_statistics(self) -> Dict[str, Any]:
        """Get statistics about jobs and files that can be cleaned up
        
        Returns:
            Statistics dictionary
        """
        try:
            stats = {'total_jobs': Job.query.count(), 'expired_jobs': 0, 'estimated_space_to_free_mb': 0,
                     'jobs_by_status': {}, 'jobs_by_age': {}, 'upload_folder_size_mb': 0, 'upload_folder_file_count': 0}
            
            # Get total job count

            # Get job counts by status
            status_counts = db.session.query(
                Job.status,
                db.func.count(Job.job_id)
            ).group_by(Job.status).all()
            
            for status, count in status_counts:
                stats['jobs_by_status'][status] = count
            
            # Get expired jobs
            expired_jobs = self._get_expired_jobs()
            stats['expired_jobs'] = len(expired_jobs)
            
            # Calculate estimated space to free
            for job in expired_jobs:
                if job.input_data and isinstance(job.input_data, dict):
                    if 'file_size' in job.input_data:
                        stats['estimated_space_to_free_mb'] += job.input_data['file_size'] / (1024 * 1024)
                    elif 'total_size' in job.input_data:
                        stats['estimated_space_to_free_mb'] += job.input_data['total_size'] / (1024 * 1024)
            
            # Get upload folder statistics
            if os.path.exists(self.upload_folder):
                total_size = 0
                file_count = 0
                for filename in os.listdir(self.upload_folder):
                    file_path = os.path.join(self.upload_folder, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                
                stats['upload_folder_size_mb'] = total_size / (1024 * 1024)
                stats['upload_folder_file_count'] = file_count
            
            # Get jobs by age categories
            now = datetime.now(timezone.utc)
            age_categories = {
                'less_than_1_hour': timedelta(hours=1),
                'less_than_1_day': timedelta(days=1),
                'less_than_1_week': timedelta(days=7),
                'older_than_1_week': None
            }
            
            for category, age_limit in age_categories.items():
                if age_limit:
                    cutoff = now - age_limit
                    if category == 'less_than_1_hour':
                        count = Job.query.filter(Job.created_at >= cutoff).count()
                    else:
                        # Get the previous category's time limit
                        category_keys = list(age_categories.keys())
                        prev_index = category_keys.index(category) - 1
                        if prev_index >= 0:
                            prev_limit = age_categories[category_keys[prev_index]]
                            prev_cutoff = now - prev_limit
                            count = Job.query.filter(
                                Job.created_at >= cutoff,
                                Job.created_at < prev_cutoff
                            ).count()
                        else:
                            count = 0
                else:
                    # Older than 1 week
                    cutoff = now - timedelta(days=7)
                    count = Job.query.filter(Job.created_at < cutoff).count()
                
                stats['jobs_by_age'][category] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cleanup statistics: {str(e)}")
            return {
                'error': str(e),
                'total_jobs': 0,
                'expired_jobs': 0,
                'estimated_space_to_free_mb': 0
            }
    
    # ========================= PRIVATE HELPER METHODS =========================
    
    def _get_expired_jobs(self) -> List[Job]:
        """Get all jobs that have expired based on retention policies
        
        Returns:
            List of expired Job objects
        """
        try:
            expired_jobs = []
            
            # Get jobs older than retention period based on status
            for status, retention_hours in self.DEFAULT_RETENTION_PERIODS.items():
                cutoff_time = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
                
                # Query jobs with this status that are older than cutoff
                jobs = Job.query \
                    .filter(Job.status == status) \
                    .filter(Job.created_at < cutoff_time) \
                    .all()
                
                expired_jobs.extend(jobs)
            
            # Remove duplicates (in case a job matches multiple criteria)
            unique_jobs = list({job.job_id: job for job in expired_jobs}.values())
            
            return unique_jobs
            
        except Exception as e:
            logger.error(f"Error getting expired jobs: {str(e)}")
            return []

    @staticmethod
    def _cleanup_job_files(job: Job) -> float:
        """Clean up files associated with a job
        Args:
            job: Job object to clean up files for
        Returns:
            Space freed in MB
        """
        space_freed_mb = 0
        files_deleted = 0
        
        try:
            # List of file paths to clean up
            file_paths = []
            
            # Check result data for file paths
            if job.result and isinstance(job.result, dict):
                # Check for various possible file path fields in result
                for path_key in ['output_path', 'result_path', 'file_path', 'temp_path']:
                    if path_key in job.result and job.result[path_key]:
                        file_path = job.result[path_key]
                        if os.path.exists(file_path):
                            file_paths.append(file_path)
                
                # Check for temp_files array
                if 'temp_files' in job.result and isinstance(job.result['temp_files'], list):
                    for temp_file in job.result['temp_files']:
                        if os.path.exists(temp_file):
                            file_paths.append(temp_file)
            
            # Check input data for file paths
            if job.input_data and isinstance(job.input_data, dict):
                for path_key in ['input_path', 'upload_path', 'original_path']:
                    if path_key in job.input_data and job.input_data[path_key]:
                        file_path = job.input_data[path_key]
                        if os.path.exists(file_path):
                            file_paths.append(file_path)
            
            # Remove duplicates
            file_paths = list(set(file_paths))
            
            # Delete files and calculate space freed
            for file_path in file_paths:
                try:
                    if os.path.exists(file_path):
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        os.remove(file_path)
                        space_freed_mb += file_size_mb
                        files_deleted += 1
                        logger.debug(f"Deleted file: {file_path} ({file_size_mb:.2f}MB)")
                
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")
            
            if files_deleted > 0:
                logger.info(f"Cleaned up {files_deleted} files for job {job.job_id}, "
                           f"freed {space_freed_mb:.2f}MB")
        
        except Exception as e:
            logger.error(f"Error cleaning up files for job {job.job_id}: {str(e)}")
        
        return space_freed_mb
    
    # ========================= UTILITY METHODS =========================
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current status of the file management service
        Returns:
            Service status dictionary
        """
        try:
            status = {
                'service_name': 'FileManagementService',
                'upload_folder': self.upload_folder,
                'upload_folder_exists': os.path.exists(self.upload_folder),
                'retention_periods': self.DEFAULT_RETENTION_PERIODS,
                'temp_file_max_age_hours': self.TEMP_FILE_MAX_AGE_HOURS,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Add folder statistics if folder exists
            if os.path.exists(self.upload_folder):
                file_count = len([f for f in os.listdir(self.upload_folder) 
                                if os.path.isfile(os.path.join(self.upload_folder, f))])
                status['upload_folder_file_count'] = file_count
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting service status: {str(e)}")
            return {
                'service_name': 'FileManagementService',
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }