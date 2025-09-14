import os
import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass


class BaseConfig:
    """Base configuration class with common settings and validation"""
    
    # Basic settings
    SECRET_KEY = os.environ.get('SECRET_KEY', '7NwLQnT2GgY5jY8hxv-Qz8FUPQw8okUkHh1R0pFzFTOZrfyHWhpHm4kgAH5p3Er')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 100 * 1024 * 1024))  # 100MB default
    
    # Database settings
    SQLALCHEMY_DATABASE_URI = "sqlite:////root/app/pdf_smaller_backend/pdf_smaller_dev.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 20)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 0)),
    }
    

    
    # File handling
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads/dev')
    MAX_FILE_AGE = timedelta(hours=int(os.environ.get('MAX_FILE_AGE_HOURS', 1)))
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB default
    
    # Compression settings
    COMPRESSION_LEVELS = {
        'low': '/prepress',
        'medium': '/default', 
        'high': '/ebook',
        'maximum': '/screen'
    }
    DEFAULT_COMPRESSION_LEVEL = os.environ.get('DEFAULT_COMPRESSION_LEVEL', 'medium')
    
    # Security settings
    ALLOWED_EXTENSIONS = {'pdf'}
    ALLOWED_ORIGINS = ['https://pdfsmaller.site,https://www.pdfsmaller.site']
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'"
    }
    
    # Rate limiting and Redis
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    RATE_LIMIT_STORAGE_URL = REDIS_URL
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
    REDIS_DB = os.environ.get('REDIS_DB', 0)

    RATE_LIMIT_STRATEGY = os.environ.get('RATE_LIMIT_STRATEGY', 'fixed-window')
    RATE_LIMIT_DEFAULT = os.environ.get('RATE_LIMIT_DEFAULT', '100 per hour')
    
    # Rate limit for all requests
    RATE_LIMIT = os.environ.get('RATE_LIMIT', '100 per hour')
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 
                               '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))

    # Celery task queue settings
    CELERY_BROKER_URL =  REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'UTC')
    CELERY_ENABLE_UTC = True
    

    # Monitoring and health checks
    HEALTH_CHECK_ENABLED = os.environ.get('HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'false').lower() == 'true'
    
    # AI Extraction Features
    INVOICE_EXTRACTION_ENABLED = os.environ.get('INVOICE_EXTRACTION_ENABLED', 'true').lower() == 'true'
    BANK_STATEMENT_EXTRACTION_ENABLED = os.environ.get('BANK_STATEMENT_EXTRACTION_ENABLED', 'true').lower() == 'true'
    EXTRACTION_MAX_FILE_SIZE = int(os.environ.get('EXTRACTION_MAX_FILE_SIZE', 52428800))  # 50MB
    EXTRACTION_TIMEOUT = int(os.environ.get('EXTRACTION_TIMEOUT', 300))  # 5 minutes
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate required settings
        if not cls.SECRET_KEY or cls.SECRET_KEY == 'your-secret-key-here':
            errors.append("SECRET_KEY must be set to a secure random value")
        
        if len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY should be at least 32 characters long")
        
        # JWT validation removed as user authentication is not needed
        
        # Validate database URL
        if not cls.SQLALCHEMY_DATABASE_URI:
            errors.append("DATABASE_URL must be set")
        
        # Validate file settings
        if not os.path.exists(os.path.dirname(cls.UPLOAD_FOLDER)):
            try:
                os.makedirs(os.path.dirname(cls.UPLOAD_FOLDER), exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create upload folder: {e}")
        
        # Validate compression level
        if cls.DEFAULT_COMPRESSION_LEVEL not in cls.COMPRESSION_LEVELS:
            errors.append(f"DEFAULT_COMPRESSION_LEVEL must be one of: {list(cls.COMPRESSION_LEVELS.keys())}")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if cls.LOG_LEVEL.upper() not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of: {valid_log_levels}")
        
        return errors
    
    @classmethod
    def get_config_summary(cls) -> Dict[str, Any]:
        """Get a summary of current configuration (excluding sensitive data)"""
        return {
            'database_type': 'sqlite',
            'upload_folder': cls.UPLOAD_FOLDER,
            'max_file_size': cls.MAX_FILE_SIZE,
            'compression_levels': list(cls.COMPRESSION_LEVELS.keys()),
            'default_compression': cls.DEFAULT_COMPRESSION_LEVEL,
            
            
            'log_level': cls.LOG_LEVEL,
            'rate_limit_default': cls.RATE_LIMIT_DEFAULT,
            'allowed_origins': cls.ALLOWED_ORIGINS,

            'health_check_enabled': cls.HEALTH_CHECK_ENABLED,
            'metrics_enabled': cls.METRICS_ENABLED
        }


class DevelopmentConfig(BaseConfig):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # More verbose logging in development
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG')
    
    # Relaxed security for development
    SECURITY_HEADERS = {}
    
    # Development database (SQLite by default)
    SQLALCHEMY_DATABASE_URI = "sqlite:////root/app/pdf_smaller_backend/pdf_smaller_dev.db"
    
    # Development origins
    ALLOWED_ORIGINS = ['https://pdfsmaller.site,https://www.pdfsmaller.site']
       
    # Development file settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads/dev')
    MAX_FILE_AGE = timedelta(minutes=int(os.environ.get('MAX_FILE_AGE_MINUTES', 30)))


class TestingConfig(BaseConfig):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    
    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = "sqlite:////root/app/pdf_smaller_backend/pdf_smaller_dev.db"
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
      
    # Test file settings
    UPLOAD_FOLDER = './uploads/dev'
    MAX_FILE_AGE = timedelta(minutes=1)
    
    # Disable external services in testing
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Test rate limits (more permissive)
    RATE_LIMIT_DEFAULT = '1000 per hour'


class ProductionConfig(BaseConfig):
    """Production configuration"""
    DEBUG = True
    TESTING = False
    
    # Production logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'WARNING')
    
    # Strict security in production
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
    
    # Production database (SQLite)
    SQLALCHEMY_DATABASE_URI = "sqlite:////root/app/pdf_smaller_backend/pdf_smaller_prod.db"
    
    # Production file settings
    UPLOAD_FOLDER = "./uploads/dev"
    
    # Stricter rate limiting in production
    RATE_LIMIT_DEFAULT = "50 per hour"
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Additional production-specific validation"""
        errors = super().validate_config()
        
        # Production-specific validations - SQLite is acceptable for this application
        
        if cls.DEBUG:
            errors.append("DEBUG should be False in production")
        
        return errors


# Configuration mapping
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Default configuration (for backward compatibility)
Config = config_by_name[os.environ.get('FLASK_ENV', 'production')]


def get_config(config_name: Optional[str] = None) -> BaseConfig:
    """Get configuration class by name"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
    
    config_class = config_by_name.get(config_name)
    if not config_class:
        raise ConfigValidationError(f"Unknown configuration: {config_name}")
    
    return config_class


def validate_current_config() -> None:
    """Validate current configuration and raise exception if invalid"""
    config_class = get_config()
    errors = config_class.validate_config()
    
    if errors:
        error_msg = "Configuration validation failed:\n" + "\n".join(f"- {error}" for error in errors)
        raise ConfigValidationError(error_msg)
