import os
from datetime import timedelta

class Config:
    # Basic settings
    SECRET_KEY = os.environ.get('SECRET_KEY', '7NwLQnT2GgY5jY8hxv-Qz8FUPQw8okUkHh1R0pFzFTOZrfyHWhpHm4kgAH5p3Er')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    
    # File handling
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads')
    MAX_FILE_AGE = timedelta(hours=1)  # How long to keep files
    
    # Compression settings
    COMPRESSION_LEVELS = {
        'low': '/prepress',
        'medium': '/default', 
        'high': '/ebook',
        'maximum': '/screen'
    }
    
    # Security
    ALLOWED_EXTENSIONS = {'pdf'}
    ALLOWED_ORIGINS = os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,https://pdfsmaller.site').split(',')
    
    # Rate limiting
    RATE_LIMIT_STORAGE_URL = os.environ.get('REDIS_URL', 'memory://')
    RATE_LIMIT_STRATEGY = 'fixed-window'
    RATE_LIMIT_DEFAULT = '100 per hour'
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
