"""File validation utilities for PDF Smaller Backend"""
import os
import logging
import magic
from typing import Dict, Any, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Define allowed file types and their MIME types
ALLOWED_MIME_TYPES = {
    'application/pdf': '.pdf',
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/tiff': '.tiff',
    'application/msword': '.doc',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx'
}

# Maximum file size (100MB)
MAX_FILE_SIZE_MB = 100

def validate_file_type(file) -> Tuple[bool, Optional[str]]:
    """Validate file type using magic numbers
    
    Args:
        file: The file object to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file or file.filename == '':
        return False, "No file selected"
    
    # Check file extension
    if '.' not in file.filename:
        return False, "Invalid file format"
    
    # Read the beginning of the file to determine its type
    file.seek(0)
    file_data = file.read(2048)  # Read first 2KB for type detection
    file.seek(0)  # Reset file pointer
    
    if not file_data:
        return False, "Empty file"
    
    try:
        # Use python-magic to detect file type
        mime_type = magic.from_buffer(file_data, mime=True)
        
        if mime_type not in ALLOWED_MIME_TYPES:
            return False, f"Unsupported file type: {mime_type}"
        
        # Additional validation: check if extension matches the detected MIME type
        expected_ext = ALLOWED_MIME_TYPES[mime_type]
        actual_ext = os.path.splitext(file.filename)[1].lower()
        
        if expected_ext != actual_ext and mime_type != 'application/pdf':
            logger.warning(f"File extension mismatch: {file.filename} has MIME type {mime_type}")
            return False, "File extension doesn't match its content"
            
        return True, None
        
    except Exception as e:
        logger.error(f"Error validating file type: {str(e)}")
        return False, "Error validating file type"

def validate_file_size(file, max_size_mb: int = MAX_FILE_SIZE_MB) -> Tuple[bool, Optional[str]]:
    """Validate file size against maximum allowed size
    
    Args:
        file: The file object to validate
        max_size_mb: Maximum allowed file size in MB
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file:
        return False, "No file provided"
    
    try:
        # Get file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        
        # Convert MB to bytes
        max_size_bytes = max_size_mb * 1024 * 1024
        
        if file_size > max_size_bytes:
            return False, f"File too large. Maximum size is {max_size_mb}MB."
            
        if file_size == 0:
            return False, "File is empty"
            
        return True, None
        
    except Exception as e:
        logger.error(f"Error validating file size: {str(e)}")
        return False, "Error validating file size"