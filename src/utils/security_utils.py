import os
from flask import request

def validate_file(file):
    """Validate uploaded file"""
    if file.filename == '':
        return 'No file selected'
    
    # Check file extension
    allowed_extensions = {'pdf'}
    if '.' not in file.filename or \
       file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return 'Invalid file type. Only PDF files are allowed.'
    
    # Check file size (additional check beyond Flask's MAX_CONTENT_LENGTH)
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_length > 100 * 1024 * 1024:  # 100MB
        return 'File too large. Maximum size is 100MB.'
    
    return None

def validate_origin(allowed_origins):
    """Validate request origin"""
    origin = request.headers.get('Origin')
    if origin and origin not in allowed_origins:
        return 'Origin not allowed'
    return None
