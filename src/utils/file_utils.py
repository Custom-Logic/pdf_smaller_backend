"""File handling utilities"""
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


def secure_filename(filename: str) -> str:
    """
    Secure a filename by removing dangerous characters and path components.
    This is a simplified version of werkzeug.utils.secure_filename
    """
    import re
    
    if not filename:
        return 'unnamed_file'
    
    # Get just the filename, no path
    filename = os.path.basename(filename)
    
    # Remove or replace dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Remove leading dots and underscores
    filename = filename.lstrip('._')
    
    # Ensure it's not empty after sanitization
    if not filename or filename == '.':
        return 'unnamed_file'
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


def cleanup_old_files(directory: str, max_age_hours: int = 1) -> int:
    """
    Clean up old files in a directory based on age.
    
    Args:
        directory: Directory path to clean
        max_age_hours: Maximum age of files in hours before deletion
        
    Returns:
        Number of files deleted
    """
    if not os.path.exists(directory):
        logger.warning(f"Directory does not exist: {directory}")
        return 0
    
    deleted_count = 0
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    try:
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            
            # Skip directories
            if os.path.isdir(file_path):
                continue
            
            # Check file age
            try:
                file_mtime = os.path.getmtime(file_path)
                if file_mtime < cutoff_time:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_path}")
            except OSError as e:
                logger.warning(f"Could not delete file {file_path}: {str(e)}")
                continue
    
    except OSError as e:
        logger.error(f"Error cleaning directory {directory}: {str(e)}")
        return deleted_count
    
    if deleted_count > 0:
        logger.info(f"Cleaned up {deleted_count} old files from {directory}")
    
    return deleted_count


def ensure_directory_exists(directory: str) -> bool:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory: Directory path to ensure exists
        
    Returns:
        True if directory exists or was created successfully
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except OSError as e:
        logger.error(f"Could not create directory {directory}: {str(e)}")
        return False


def get_file_size(file_path: str) -> int:
    """
    Get file size in bytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def is_safe_path(base_path: str, file_path: str) -> bool:
    """
    Check if a file path is safe (within the base directory).
    Prevents path traversal attacks.
    
    Args:
        base_path: Base directory path
        file_path: File path to check
        
    Returns:
        True if path is safe
    """
    try:
        base_path = os.path.abspath(base_path)
        file_path = os.path.abspath(file_path)
        return file_path.startswith(base_path)
    except (OSError, ValueError):
        return False


def get_unique_filename(directory: str, filename: str) -> str:
    """
    Get a unique filename in a directory by appending a number if needed.
    
    Args:
        directory: Directory path
        filename: Desired filename
        
    Returns:
        Unique filename
    """
    base_path = os.path.join(directory, filename)
    
    if not os.path.exists(base_path):
        return filename
    
    name, ext = os.path.splitext(filename)
    counter = 1
    
    while True:
        new_filename = f"{name}_{counter}{ext}"
        new_path = os.path.join(directory, new_filename)
        
        if not os.path.exists(new_path):
            return new_filename
        
        counter += 1
        
        # Prevent infinite loop
        if counter > 1000:
            import uuid
            return f"{name}_{uuid.uuid4().hex[:8]}{ext}"


def copy_file_safely(source: str, destination: str) -> bool:
    """
    Safely copy a file with error handling.
    
    Args:
        source: Source file path
        destination: Destination file path
        
    Returns:
        True if copy was successful
    """
    try:
        import shutil
        
        # Ensure destination directory exists
        dest_dir = os.path.dirname(destination)
        if not ensure_directory_exists(dest_dir):
            return False
        
        shutil.copy2(source, destination)
        return True
        
    except (OSError, IOError) as e:
        logger.error(f"Error copying file from {source} to {destination}: {str(e)}")
        return False


def delete_file_safely(file_path: str) -> bool:
    """
    Safely delete a file with error handling.
    
    Args:
        file_path: Path to file to delete
        
    Returns:
        True if deletion was successful or file didn't exist
    """
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Deleted file: {file_path}")
        return True
        
    except OSError as e:
        logger.error(f"Error deleting file {file_path}: {str(e)}")
        return False


def get_file_extension(filename: str) -> str:
    """
    Get file extension in lowercase.
    
    Args:
        filename: Filename to extract extension from
        
    Returns:
        File extension without the dot, or empty string if no extension
    """
    if not filename or '.' not in filename:
        return ''
    
    return filename.rsplit('.', 1)[1].lower()


def validate_file_type(filename: str, allowed_extensions: set) -> bool:
    """
    Validate file type against allowed extensions.
    
    Args:
        filename: Filename to validate
        allowed_extensions: Set of allowed extensions (without dots)
        
    Returns:
        True if file type is allowed
    """
    if not filename or not allowed_extensions:
        return False
    
    extension = get_file_extension(filename)
    return extension in allowed_extensions