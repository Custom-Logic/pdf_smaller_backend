"""
Enhanced File Manager Service

This module provides secure file management capabilities including:
- Secure file handling with ownership validation
- Unique file naming and storage organization
- File permission checking and access control
- Storage quota management
- Comprehensive error handling and logging

Requirements: 6.1, 6.5
"""

import os
import uuid
import hashlib
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from werkzeug.utils import secure_filename as werkzeug_secure_filename

from src.config import Config
from src.models import User, CompressionJob
from src.models.base import db
from src.utils.file_utils import (
    ensure_directory_exists, 
    is_safe_path, 
    get_file_size,
    delete_file_safely
)

logger = logging.getLogger(__name__)


class FileManagerError(Exception):
    """Custom exception for file manager operations"""
    pass


class FileManager:
    """
    Enhanced file manager with secure file handling and ownership validation
    """
    
    def __init__(self, base_upload_folder: str = None):
        """
        Initialize FileManager with base upload folder
        
        Args:
            base_upload_folder: Base directory for file uploads
        """
        self.base_upload_folder = base_upload_folder or Config.UPLOAD_FOLDER
        self.max_file_age = Config.MAX_FILE_AGE
        
        # Ensure base directory exists
        if not ensure_directory_exists(self.base_upload_folder):
            raise FileManagerError(f"Cannot create base upload folder: {self.base_upload_folder}")
        
        # Storage organization
        self.temp_folder = os.path.join(self.base_upload_folder, 'temp')
        self.user_folder = os.path.join(self.base_upload_folder, 'users')
        self.results_folder = os.path.join(self.base_upload_folder, 'results')
        
        # Create subdirectories
        for folder in [self.temp_folder, self.user_folder, self.results_folder]:
            ensure_directory_exists(folder)
    
    def generate_unique_filename(self, original_filename: str, user_id: int = None) -> str:
        """
        Generate a unique filename with timestamp and UUID
        
        Args:
            original_filename: Original filename from upload
            user_id: Optional user ID for additional uniqueness
            
        Returns:
            Unique filename string
        """
        # Secure the original filename
        secure_name = werkzeug_secure_filename(original_filename)
        if not secure_name:
            secure_name = "unnamed_file.pdf"
        
        # Split name and extension
        name, ext = os.path.splitext(secure_name)
        if not ext:
            ext = '.pdf'  # Default extension
        
        # Generate unique identifier
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = uuid.uuid4().hex[:8]
        
        # Include user ID if provided
        if user_id:
            unique_filename = f"{name}_{timestamp}_{user_id}_{unique_id}{ext}"
        else:
            unique_filename = f"{name}_{timestamp}_{unique_id}{ext}"
        
        # Ensure filename length is reasonable
        if len(unique_filename) > 255:
            # Truncate name part but keep timestamp and unique parts
            max_name_length = 255 - len(f"_{timestamp}_{user_id or ''}_{unique_id}{ext}")
            name = name[:max_name_length]
            unique_filename = f"{name}_{timestamp}_{user_id or ''}_{unique_id}{ext}"
        
        return unique_filename
    
    def get_user_storage_path(self, user_id: int) -> str:
        """
        Get storage path for a specific user
        
        Args:
            user_id: User ID
            
        Returns:
            User-specific storage path
        """
        user_path = os.path.join(self.user_folder, str(user_id))
        ensure_directory_exists(user_path)
        return user_path
    
    def store_uploaded_file(self, file_obj, user_id: int, job_id: int = None) -> Dict[str, Any]:
        """
        Store an uploaded file securely with ownership tracking
        
        Args:
            file_obj: File object from request
            user_id: ID of the user uploading the file
            job_id: Optional compression job ID for tracking
            
        Returns:
            Dictionary with file information
        """
        try:
            # Validate file object
            if not file_obj or not file_obj.filename:
                raise FileManagerError("Invalid file object or filename")
            
            # Generate unique filename
            unique_filename = self.generate_unique_filename(file_obj.filename, user_id)
            
            # Get user storage path
            user_storage_path = self.get_user_storage_path(user_id)
            
            # Create full file path
            file_path = os.path.join(user_storage_path, unique_filename)
            
            # Ensure path is safe (prevent directory traversal)
            if not is_safe_path(self.base_upload_folder, file_path):
                raise FileManagerError("Unsafe file path detected")
            
            # Save file
            file_obj.save(file_path)
            
            # Get file information
            file_size = get_file_size(file_path)
            file_hash = self._calculate_file_hash(file_path)
            
            # Create file metadata
            file_metadata = {
                'original_filename': file_obj.filename,
                'stored_filename': unique_filename,
                'file_path': file_path,
                'file_size': file_size,
                'file_hash': file_hash,
                'user_id': user_id,
                'job_id': job_id,
                'created_at': datetime.utcnow(),
                'mime_type': file_obj.content_type
            }
            
            logger.info(f"Stored file {unique_filename} for user {user_id}, size: {file_size} bytes")
            return file_metadata
            
        except Exception as e:
            logger.error(f"Error storing uploaded file: {str(e)}")
            raise FileManagerError(f"Failed to store file: {str(e)}")
    
    def store_result_file(self, source_path: str, user_id: int, job_id: int, 
                         result_type: str = 'compressed') -> Dict[str, Any]:
        """
        Store a result file (compressed PDF, ZIP archive, etc.)
        
        Args:
            source_path: Path to the source file to store
            user_id: ID of the user who owns the result
            job_id: Compression job ID
            result_type: Type of result ('compressed', 'archive', etc.)
            
        Returns:
            Dictionary with result file information
        """
        try:
            if not os.path.exists(source_path):
                raise FileManagerError(f"Source file does not exist: {source_path}")
            
            # Generate result filename
            original_name = os.path.basename(source_path)
            result_filename = f"{result_type}_{job_id}_{original_name}"
            
            # Get results storage path
            results_path = os.path.join(self.results_folder, str(user_id))
            ensure_directory_exists(results_path)
            
            # Create destination path
            dest_path = os.path.join(results_path, result_filename)
            
            # Ensure path is safe
            if not is_safe_path(self.base_upload_folder, dest_path):
                raise FileManagerError("Unsafe result path detected")
            
            # Copy file to results folder
            shutil.copy2(source_path, dest_path)
            
            # Get file information
            file_size = get_file_size(dest_path)
            file_hash = self._calculate_file_hash(dest_path)
            
            # Create result metadata
            result_metadata = {
                'result_filename': result_filename,
                'result_path': dest_path,
                'file_size': file_size,
                'file_hash': file_hash,
                'user_id': user_id,
                'job_id': job_id,
                'result_type': result_type,
                'created_at': datetime.utcnow()
            }
            
            logger.info(f"Stored result file {result_filename} for user {user_id}, job {job_id}")
            return result_metadata
            
        except Exception as e:
            logger.error(f"Error storing result file: {str(e)}")
            raise FileManagerError(f"Failed to store result file: {str(e)}")
    
    def validate_file_ownership(self, file_path: str, user_id: int) -> bool:
        """
        Validate that a user owns a specific file
        
        Args:
            file_path: Path to the file to validate
            user_id: ID of the user claiming ownership
            
        Returns:
            True if user owns the file, False otherwise
        """
        try:
            # Ensure path is safe
            if not is_safe_path(self.base_upload_folder, file_path):
                logger.warning(f"Unsafe file path in ownership validation: {file_path}")
                return False
            
            # Check if file exists
            if not os.path.exists(file_path):
                logger.warning(f"File does not exist for ownership validation: {file_path}")
                return False
            
            # Check if file is in user's directory
            user_storage_path = self.get_user_storage_path(user_id)
            results_path = os.path.join(self.results_folder, str(user_id))
            
            # File should be in either user storage or results folder
            is_in_user_storage = file_path.startswith(user_storage_path)
            is_in_user_results = file_path.startswith(results_path)
            
            if not (is_in_user_storage or is_in_user_results):
                logger.warning(f"File not in user's authorized directories: {file_path}")
                return False
            
            # Additional validation: check if file is associated with user's jobs
            filename = os.path.basename(file_path)
            
            # For result files, check job ownership
            if is_in_user_results:
                return self._validate_result_file_ownership(filename, user_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating file ownership: {str(e)}")
            return False
    
    def get_file_info(self, file_path: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get information about a file if user has access
        
        Args:
            file_path: Path to the file
            user_id: ID of the requesting user
            
        Returns:
            File information dictionary or None if no access
        """
        try:
            # Validate ownership first
            if not self.validate_file_ownership(file_path, user_id):
                logger.warning(f"User {user_id} denied access to file {file_path}")
                return None
            
            if not os.path.exists(file_path):
                return None
            
            # Get file stats
            stat = os.stat(file_path)
            
            return {
                'file_path': file_path,
                'filename': os.path.basename(file_path),
                'file_size': stat.st_size,
                'created_at': datetime.fromtimestamp(stat.st_ctime),
                'modified_at': datetime.fromtimestamp(stat.st_mtime),
                'is_readable': os.access(file_path, os.R_OK),
                'is_writable': os.access(file_path, os.W_OK)
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {str(e)}")
            return None
    
    def delete_file(self, file_path: str, user_id: int) -> bool:
        """
        Delete a file if user has permission
        
        Args:
            file_path: Path to the file to delete
            user_id: ID of the user requesting deletion
            
        Returns:
            True if file was deleted successfully
        """
        try:
            # Validate ownership
            if not self.validate_file_ownership(file_path, user_id):
                logger.warning(f"User {user_id} denied permission to delete file {file_path}")
                return False
            
            # Delete the file
            success = delete_file_safely(file_path)
            
            if success:
                logger.info(f"User {user_id} deleted file {file_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return False
    
    def get_user_storage_usage(self, user_id: int) -> Dict[str, Any]:
        """
        Get storage usage statistics for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with storage usage information
        """
        try:
            user_storage_path = self.get_user_storage_path(user_id)
            results_path = os.path.join(self.results_folder, str(user_id))
            
            total_size = 0
            file_count = 0
            
            # Calculate storage usage
            for folder_path in [user_storage_path, results_path]:
                if os.path.exists(folder_path):
                    for root, dirs, files in os.walk(folder_path):
                        for file in files:
                            file_path = os.path.join(root, file)
                            try:
                                total_size += os.path.getsize(file_path)
                                file_count += 1
                            except OSError:
                                continue
            
            return {
                'user_id': user_id,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'file_count': file_count,
                'storage_paths': {
                    'user_storage': user_storage_path,
                    'results_storage': results_path
                }
            }
            
        except Exception as e:
            logger.error(f"Error calculating storage usage for user {user_id}: {str(e)}")
            return {
                'user_id': user_id,
                'total_size_bytes': 0,
                'total_size_mb': 0,
                'file_count': 0,
                'error': str(e)
            }
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file
        
        Args:
            file_path: Path to the file
            
        Returns:
            Hexadecimal hash string
        """
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating file hash: {str(e)}")
            return ""
    
    def _validate_result_file_ownership(self, filename: str, user_id: int) -> bool:
        """
        Validate ownership of a result file by checking job ownership
        
        Args:
            filename: Name of the result file
            user_id: User ID to validate
            
        Returns:
            True if user owns the associated job
        """
        try:
            # Extract job ID from filename (format: result_type_job_id_original_name)
            parts = filename.split('_')
            if len(parts) < 3:
                return False
            
            try:
                job_id = int(parts[1])  # Second part should be job ID
            except ValueError:
                return False
            
            # Check if job belongs to user
            job = CompressionJob.query.filter_by(id=job_id, user_id=user_id).first()
            return job is not None
            
        except Exception as e:
            logger.error(f"Error validating result file ownership: {str(e)}")
            return False
    
    def list_user_files(self, user_id: int, file_type: str = 'all') -> List[Dict[str, Any]]:
        """
        List files belonging to a user
        
        Args:
            user_id: User ID
            file_type: Type of files to list ('uploads', 'results', 'all')
            
        Returns:
            List of file information dictionaries
        """
        try:
            files = []
            
            # Define paths to search
            paths_to_search = []
            if file_type in ['uploads', 'all']:
                paths_to_search.append(('uploads', self.get_user_storage_path(user_id)))
            if file_type in ['results', 'all']:
                paths_to_search.append(('results', os.path.join(self.results_folder, str(user_id))))
            
            # Search each path
            for path_type, search_path in paths_to_search:
                if os.path.exists(search_path):
                    for filename in os.listdir(search_path):
                        file_path = os.path.join(search_path, filename)
                        if os.path.isfile(file_path):
                            file_info = self.get_file_info(file_path, user_id)
                            if file_info:
                                file_info['file_type'] = path_type
                                files.append(file_info)
            
            # Sort by creation time (newest first)
            files.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
            
            return files
            
        except Exception as e:
            logger.error(f"Error listing user files: {str(e)}")
            return []