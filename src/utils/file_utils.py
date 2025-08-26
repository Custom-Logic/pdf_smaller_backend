import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from werkzeug.utils import secure_filename

def secure_filename_with_uuid(original_filename):
    """Generate a secure filename with UUID prefix"""
    ext = os.path.splitext(original_filename)[1]
    return f"{uuid.uuid4().hex}{ext}"

def cleanup_old_files(directory, max_age_hours=1):
    """Remove files older than specified hours"""
    now = datetime.now()
    max_age = timedelta(hours=max_age_hours)
    
    for file_path in Path(directory).glob('*'):
        if file_path.is_file():
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if now - file_time > max_age:
                file_path.unlink()
