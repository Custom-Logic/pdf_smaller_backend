import os
import uuid
from typing import Tuple
from src.config import Config
from src.utils.file_utils import cleanup_old_files, get_file_size


class FileManager:
    """Manages file operations for the application"""
    
    def __init__(self, upload_folder: str = None):
        """Initialize the file manager
        
        Args:
            upload_folder: Directory to store uploaded files. Defaults to Config.UPLOAD_FOLDER.
        """
        self.upload_folder = upload_folder or Config.UPLOAD_FOLDER
        os.makedirs(self.upload_folder, exist_ok=True)
    
    def save_file(self, file_data: bytes, original_filename: str = None) -> Tuple[str, str]:
        """Save file data to disk with a unique filename
        
        Args:
            file_data: Binary file data to save
            original_filename: Original filename (used for extension)
            
        Returns:
            Tuple of (unique_id, file_path)
        """
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
        
        return unique_id, file_path
    
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
    
    def cleanup_old_files(self, max_age_hours: int = None):
        """Remove files older than specified age
        
        Args:
            max_age_hours: Maximum age in hours (default: from config)
        """
        max_age = max_age_hours or Config.FILE_RETENTION_HOURS
        cleanup_old_files(self.upload_folder, max_age)
    
    def file_exists(self, file_path: str) -> bool:
        """Check if a file exists
        
        Args:
            file_path: Path to the file
            
        Returns:
            True if file exists, False otherwise
        """
        return os.path.isfile(file_path)
    
    def get_file_size(self, file_path: str) -> int:
        """Get file size in bytes
        
        Args:
            file_path: Path to the file
            
        Returns:
            File size in bytes
        """
        return get_file_size(file_path)