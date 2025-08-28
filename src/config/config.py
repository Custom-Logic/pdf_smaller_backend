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
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///pdf_smaller.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': int(os.environ.get('DB_POOL_RECYCLE', 300)),
        'pool_timeout': int(os.environ.get('DB_POOL_TIMEOUT', 20)),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', 0)),
    }
    
    # JWT settings
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_MINUTES', 15)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.environ.get('JWT_REFRESH_TOKEN_DAYS', 7)))
    JWT_ALGORITHM = os.environ.get('JWT_ALGORITHM', 'HS256')
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']
    
    # File handling
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads')
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
    ALLOWED_ORIGINS = [origin.strip() for origin in 
                      os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,https://pdfsmaller.site').split(',')]
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
    RATE_LIMIT_STRATEGY = os.environ.get('RATE_LIMIT_STRATEGY', 'fixed-window')
    RATE_LIMIT_DEFAULT = os.environ.get('RATE_LIMIT_DEFAULT', '100 per hour')
    
    # User tier rate limits
    RATE_LIMITS = {
        'free': {
            'compression': '10 per day',
            'api': '50 per hour',
            'auth': '5 per minute'
        },
        'premium': {
            'compression': '500 per day',
            'api': '1000 per hour',
            'auth': '10 per minute'
        },
        'pro': {
            'compression': '10000 per day',
            'api': '5000 per hour',
            'auth': '20 per minute'
        }
    }
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'app.log')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 
                               '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    LOG_MAX_BYTES = int(os.environ.get('LOG_MAX_BYTES', 10 * 1024 * 1024))  # 10MB
    LOG_BACKUP_COUNT = int(os.environ.get('LOG_BACKUP_COUNT', 5))
    
    # Stripe payment settings
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_API_VERSION = os.environ.get('STRIPE_API_VERSION', '2023-10-16')
    
    # Subscription plans configuration
    SUBSCRIPTION_PLANS = {
        'free': {
            'name': 'Free',
            'price': 0,
            'compressions_per_day': 10,
            'max_file_size': 10 * 1024 * 1024,  # 10MB
            'bulk_processing': False,
            'priority_processing': False
        },
        'premium': {
            'name': 'Premium',
            'price': 999,  # $9.99 in cents
            'compressions_per_day': 500,
            'max_file_size': 50 * 1024 * 1024,  # 50MB
            'bulk_processing': True,
            'priority_processing': False
        },
        'pro': {
            'name': 'Pro',
            'price': 1999,  # $19.99 in cents
            'compressions_per_day': -1,  # Unlimited
            'max_file_size': 100 * 1024 * 1024,  # 100MB
            'bulk_processing': True,
            'priority_processing': True
        }
    }
    
    # Celery task queue settings
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = os.environ.get('CELERY_TIMEZONE', 'UTC')
    CELERY_ENABLE_UTC = True
    CELERY_TASK_ROUTES = {
        'src.tasks.compression_tasks.process_bulk_compression': {'queue': 'compression'},
        'src.tasks.cleanup_tasks.cleanup_expired_files': {'queue': 'cleanup'},
    }
    
    # Email settings (for notifications)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    # Monitoring and health checks
    HEALTH_CHECK_ENABLED = os.environ.get('HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    METRICS_ENABLED = os.environ.get('METRICS_ENABLED', 'false').lower() == 'true'
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate required settings
        if not cls.SECRET_KEY or cls.SECRET_KEY == 'your-secret-key-here':
            errors.append("SECRET_KEY must be set to a secure random value")
        
        if len(cls.SECRET_KEY) < 32:
            errors.append("SECRET_KEY should be at least 32 characters long")
        
        # Validate JWT settings
        if not cls.JWT_SECRET_KEY:
            errors.append("JWT_SECRET_KEY must be set")
        
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
            'database_type': 'sqlite' if 'sqlite' in cls.SQLALCHEMY_DATABASE_URI else 'postgresql',
            'upload_folder': cls.UPLOAD_FOLDER,
            'max_file_size': cls.MAX_FILE_SIZE,
            'compression_levels': list(cls.COMPRESSION_LEVELS.keys()),
            'default_compression': cls.DEFAULT_COMPRESSION_LEVEL,
            'jwt_access_expires': str(cls.JWT_ACCESS_TOKEN_EXPIRES),
            'jwt_refresh_expires': str(cls.JWT_REFRESH_TOKEN_EXPIRES),
            'log_level': cls.LOG_LEVEL,
            'rate_limit_default': cls.RATE_LIMIT_DEFAULT,
            'allowed_origins': cls.ALLOWED_ORIGINS,
            'subscription_plans': list(cls.SUBSCRIPTION_PLANS.keys()),
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
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///pdf_smaller_dev.db')
    
    # Development origins
    ALLOWED_ORIGINS = [origin.strip() for origin in 
                      os.environ.get('ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')]
    
    # Shorter token expiry for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.environ.get('JWT_ACCESS_TOKEN_MINUTES', 60)))
    
    # Development file settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', './uploads/dev')
    MAX_FILE_AGE = timedelta(minutes=int(os.environ.get('MAX_FILE_AGE_MINUTES', 30)))


class TestingConfig(BaseConfig):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    
    # In-memory database for testing
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Fast token expiry for testing
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=5)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(minutes=10)
    
    # Test file settings
    UPLOAD_FOLDER = '/tmp/pdf_test_uploads'
    MAX_FILE_AGE = timedelta(minutes=1)
    
    # Disable external services in testing
    STRIPE_SECRET_KEY = 'sk_test_fake_key_for_testing'
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Test rate limits (more permissive)
    RATE_LIMIT_DEFAULT = '1000 per hour'


class ProductionConfig(BaseConfig):
    """Production configuration"""
    DEBUG = False
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
    
    # Production database (PostgreSQL recommended)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 
        'postgresql://user:password@localhost/pdf_smaller_prod')
    
    # Production file settings
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', '/var/app/uploads')
    
    # Stricter rate limiting in production
    RATE_LIMIT_DEFAULT = os.environ.get('RATE_LIMIT_DEFAULT', '50 per hour')
    
    @classmethod
    def validate_config(cls) -> List[str]:
        """Additional production-specific validation"""
        errors = super().validate_config()
        
        # Production-specific validations
        if 'sqlite' in cls.SQLALCHEMY_DATABASE_URI:
            errors.append("Production should use PostgreSQL, not SQLite")
        
        if not cls.STRIPE_SECRET_KEY or 'test' in cls.STRIPE_SECRET_KEY:
            errors.append("Production STRIPE_SECRET_KEY must be set and not a test key")
        
        if not cls.STRIPE_WEBHOOK_SECRET:
            errors.append("STRIPE_WEBHOOK_SECRET must be set in production")
        
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
Config = config_by_name[os.environ.get('FLASK_ENV', 'default')]


def get_config(config_name: Optional[str] = None) -> BaseConfig:
    """Get configuration class by name"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    
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
